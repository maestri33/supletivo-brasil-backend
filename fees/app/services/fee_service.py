"""Regras de negócio das taxas de matrícula.

Fluxo (decisões confirmadas com o produto):
- O coordenador do polo cria uma taxa por aluno; ela tem **dois payouts PIX**
  por QR Code (BR Code), feitos via serviço `asaas`: um à vista e um agendado.
- O status da taxa é **derivado** dos status dos dois pagamentos. Quando a parte
  à vista é paga (`FIRST_PAID`), o acesso à plataforma fica liberável — o fees
  só guarda o status; quem libera acesso consulta depois.
- Idempotência do caminho do dinheiro: a intenção (linhas no DB) é **commitada
  antes** de chamar o asaas, e o `payment_id` é determinístico — um re-submit
  recebe `payment_id_already_exists` do asaas e nunca duplica o pagamento.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import uuid4

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.exceptions import Conflict
from app.integrations import IntegrationError
from app.integrations.asaas import AsaasClient
from app.models import (
    FAILED_STATUSES,
    PAID_STATUS,
    Fee,
    FeePayment,
    FeePaymentKind,
    FeeStatus,
)
from app.schemas import ScheduledLeg, UpfrontLeg

logger = structlog.get_logger()

# Taxa "ativa" = ainda em jogo; bloqueia criar outra para o mesmo aluno.
# FAILED/CANCELLED não bloqueiam (permitem nova tentativa).
ACTIVE_FEE_STATUSES = frozenset(
    {FeeStatus.PENDING.value, FeeStatus.FIRST_PAID.value, FeeStatus.FULLY_PAID.value}
)


def derive_fee_status(upfront_status: str, scheduled_status: str) -> FeeStatus:
    """Deriva o status da taxa a partir dos status das duas parcelas.

    O acesso depende só da parte à vista (`FIRST_PAID`); a falha da agendada não
    rebaixa uma taxa já paga na 1ª parte.
    """
    up_paid = upfront_status == PAID_STATUS
    sch_paid = scheduled_status == PAID_STATUS
    if up_paid and sch_paid:
        return FeeStatus.FULLY_PAID
    if up_paid:
        return FeeStatus.FIRST_PAID
    if upfront_status in FAILED_STATUSES:
        return FeeStatus.FAILED
    return FeeStatus.PENDING


async def get_fee(session: AsyncSession, fee_id: str) -> Fee | None:
    return await session.get(Fee, fee_id)


async def load_payments(session: AsyncSession, fee_id: str) -> list[FeePayment]:
    result = await session.scalars(
        select(FeePayment).where(FeePayment.fee_id == fee_id).order_by(FeePayment.kind)
    )
    return list(result.all())


async def get_active_fee_by_student(session: AsyncSession, student_external_id: str) -> Fee | None:
    return await session.scalar(
        select(Fee)
        .where(
            Fee.student_external_id == student_external_id,
            Fee.status.in_(ACTIVE_FEE_STATUSES),
        )
        .order_by(Fee.created_at.desc(), Fee.id.desc())
        .limit(1)
    )


async def get_latest_fee_by_student(session: AsyncSession, student_external_id: str) -> Fee | None:
    return await session.scalar(
        select(Fee)
        .where(Fee.student_external_id == student_external_id)
        .order_by(Fee.created_at.desc(), Fee.id.desc())
        .limit(1)
    )


async def list_fees(
    session: AsyncSession,
    *,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Fee]:
    stmt = select(Fee).order_by(Fee.created_at.desc(), Fee.id.desc())
    if status:
        stmt = stmt.where(Fee.status == status)
    result = await session.scalars(stmt.offset(offset).limit(limit))
    return list(result.all())


async def create_fee(
    session: AsyncSession,
    asaas: AsaasClient,
    *,
    student_external_id: str,
    coordinator_external_id: str,
    description: str | None,
    upfront: UpfrontLeg,
    scheduled: ScheduledLeg,
) -> tuple[Fee, list[FeePayment]]:
    """Cria a taxa e dispara os dois payouts no asaas.

    Levanta `Conflict` se já existir taxa ativa para o aluno.
    """
    existing = await get_active_fee_by_student(session, student_external_id)
    if existing is not None:
        raise Conflict("Já existe uma taxa ativa para este aluno", code="FEE_ALREADY_EXISTS")

    fee_id = str(uuid4())
    fee = Fee(
        id=fee_id,
        student_external_id=student_external_id,
        coordinator_external_id=coordinator_external_id,
        status=FeeStatus.PENDING.value,
        description=description,
    )
    up = FeePayment(
        id=str(uuid4()),
        fee_id=fee_id,
        kind=FeePaymentKind.UPFRONT.value,
        payment_id=f"fee-{fee_id}-upfront",
        qrcode_payload=upfront.qrcode_payload,
        amount=upfront.amount,
        status="PENDING",
    )
    sch = FeePayment(
        id=str(uuid4()),
        fee_id=fee_id,
        kind=FeePaymentKind.SCHEDULED.value,
        payment_id=f"fee-{fee_id}-scheduled",
        qrcode_payload=scheduled.qrcode_payload,
        amount=scheduled.amount,
        scheduled_date=date.fromisoformat(scheduled.date),
        status="PENDING",
    )
    session.add_all([fee, up, sch])
    # Persiste a intenção ANTES de mover dinheiro (idempotência do money path).
    await session.commit()

    desc = description or get_settings().fee_description_default

    try:
        res = await asaas.pay_qrcode(
            qrcode_payload=up.qrcode_payload,
            amount=up.amount,
            payment_id=up.payment_id,
            description=desc,
        )
        up.status = res.get("status") or "QUEUED"
        up.asaas_id = res.get("asaas_id")
        up.last_error = None
    except IntegrationError as exc:
        up.status = "SUBMIT_ERROR"
        up.last_error = str(exc)[:500]
        logger.warning("asaas_upfront_submit_failed", fee_id=fee_id, error=str(exc))

    try:
        res = await asaas.pay_qrcode_scheduled(
            qrcode_payload=sch.qrcode_payload,
            amount=sch.amount,
            payment_id=sch.payment_id,
            date=scheduled.date,
            hour=scheduled.hour,
            minute=scheduled.minute,
            description=desc,
        )
        sch.status = res.get("status") or "SCHEDULED"
        sch.asaas_id = res.get("asaas_id")
        sch.last_error = None
    except IntegrationError as exc:
        sch.status = "SUBMIT_ERROR"
        sch.last_error = str(exc)[:500]
        logger.warning("asaas_scheduled_submit_failed", fee_id=fee_id, error=str(exc))

    fee.status = derive_fee_status(up.status, sch.status).value
    await session.commit()
    logger.info(
        "fee_created",
        fee_id=fee_id,
        student=student_external_id,
        fee_status=fee.status,
        upfront_status=up.status,
        scheduled_status=sch.status,
    )
    return fee, [up, sch]


@dataclass
class WebhookOutcome:
    """Resultado de aplicar um webhook de status do asaas."""

    fee: Fee
    payment: FeePayment
    transitioned: bool  # o status da TAXA mudou
    new_fee_status: str
    payment_failed: bool  # esta parcela acabou de ir para FAILED/CANCELLED


async def apply_payout_webhook(
    session: AsyncSession,
    *,
    payment_id: str,
    status: str,
    asaas_id: str | None = None,
) -> WebhookOutcome | None:
    """Aplica o status recebido do asaas a uma parcela e re-deriva a taxa.

    Idempotente: re-entregar o mesmo status não gera nova transição. Retorna
    `None` quando o `payment_id` é desconhecido (webhook de outra origem).
    """
    pay = await session.scalar(select(FeePayment).where(FeePayment.payment_id == payment_id))
    if pay is None:
        return None
    fee = await get_fee(session, pay.fee_id)
    if fee is None:
        return None

    payment_changed = status != pay.status
    if payment_changed:
        pay.status = status
        if asaas_id:
            pay.asaas_id = asaas_id

    payments = await load_payments(session, fee.id)
    up = next((p for p in payments if p.kind == FeePaymentKind.UPFRONT.value), None)
    sch = next((p for p in payments if p.kind == FeePaymentKind.SCHEDULED.value), None)
    new_status = derive_fee_status(up.status if up else "", sch.status if sch else "").value
    transitioned = new_status != fee.status
    fee.status = new_status

    return WebhookOutcome(
        fee=fee,
        payment=pay,
        transitioned=transitioned,
        new_fee_status=new_status,
        payment_failed=payment_changed and status in FAILED_STATUSES,
    )
