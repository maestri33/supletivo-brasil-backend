"""Fila leve de payout: empurra os Payouts QUEUED pro asaas e sincroniza o status.

Reusa o padrao da fila do infinitepay (claim atomico antes de agir, retry com backoff).
A diferenca: a fila PESADA (transferencia, espera de saldo) e do asaas. Aqui:

  - Payout QUEUED            -> POST /payment no asaas (idempotente por external_reference)
  - Payout SUBMITTED/AWAIT.. -> GET /payment p/ reconciliar status (rede de seguranca do webhook)

`attempts`/`max_attempts` contam APENAS falhas transitorias do PUSH (asaas fora do ar).
A reconciliacao de quem ja foi aceito NAO consome tentativas — repete ate status terminal.

ATENCAO: chamar isto com o asaas real (dev usa Asaas REAL) DISPARA Pix de verdade.
Roda dentro do worker (services/worker.py); nada aqui executa so por importar.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session_maker
from app.integrations import IntegrationError
from app.integrations.asaas_client import AsaasPayoutClient
from app.models import Commission, CommissionStatus, Payout, PayoutStatus
from app.utils.logging import get_logger

logger = get_logger("commissions.payout")

# Backoff do PUSH (mesmos passos do infinitepay): 1min,5min,30min,2h,12h,24h.
BACKOFF_SECONDS = [60, 300, 1800, 7200, 43200, 86400]
# Intervalo de reconciliacao de quem ja foi aceito pelo asaas (rede de seguranca).
RECONCILE_SECONDS = 300
# Trava enquanto um job esta sendo processado (evita corrida entre workers).
_LOCK_SECONDS = 120

_ACTIVE_STATUSES = (
    PayoutStatus.QUEUED,
    PayoutStatus.SUBMITTED,
    PayoutStatus.AWAITING_BALANCE,
)
_TERMINAL_STATUSES = (PayoutStatus.PAID, PayoutStatus.FAILED, PayoutStatus.CANCELLED)

# asaas status (verbatim) -> (PayoutStatus, terminal?)
_ASAAS_TO_PAYOUT: dict[str, tuple[PayoutStatus, bool]] = {
    "PAID": (PayoutStatus.PAID, True),
    "FAILED": (PayoutStatus.FAILED, True),
    "CANCELLED": (PayoutStatus.CANCELLED, True),
    "AWAITING_BALANCE": (PayoutStatus.AWAITING_BALANCE, False),
    "SCHEDULED": (PayoutStatus.SUBMITTED, False),
    "QUEUED": (PayoutStatus.SUBMITTED, False),
    "SUBMITTING": (PayoutStatus.SUBMITTED, False),
    "SUBMITTED": (PayoutStatus.SUBMITTED, False),
}


def _now() -> datetime:
    return datetime.now(UTC)


def _map_status(asaas_status: str | None) -> tuple[PayoutStatus, bool]:
    if not asaas_status:
        return PayoutStatus.SUBMITTED, False
    return _ASAAS_TO_PAYOUT.get(asaas_status, (PayoutStatus.SUBMITTED, False))


async def apply_payout_status(
    db: AsyncSession,
    *,
    external_reference: str,
    asaas_status: str | None,
    asaas_id: str | None = None,
) -> Payout | None:
    """Aplica um status vindo do asaas (webhook OU consulta) ao Payout e suas comissoes.

    Fonte de verdade pos-aceite. Em status terminal, propaga PAID/FAILED para todas as
    comissoes carimbadas com este external_reference. NAO commita (o caller commita).
    """
    payout = (
        await db.execute(
            select(Payout).where(Payout.external_reference == external_reference)
        )
    ).scalar_one_or_none()
    if payout is None:
        logger.warning(
            "payout.apply_status_unknown_ref",
            ref=external_reference,
            asaas_status=asaas_status,
        )
        return None

    mapped, terminal = _map_status(asaas_status)
    if asaas_status:
        payout.asaas_status = asaas_status
    if asaas_id:
        payout.asaas_id = asaas_id
    payout.status = mapped

    if terminal:
        payout.next_attempt_at = None
        comm_status = (
            CommissionStatus.PAID if mapped == PayoutStatus.PAID else CommissionStatus.FAILED
        )
        await db.execute(
            update(Commission)
            .where(Commission.external_reference == external_reference)
            .values(status=comm_status)
        )
        logger.info(
            "payout.terminal",
            ref=external_reference,
            status=mapped.value,
            asaas_id=payout.asaas_id,
        )
    else:
        payout.next_attempt_at = _now() + timedelta(seconds=RECONCILE_SECONDS)

    await db.flush()
    return payout


async def process_due_payouts(limit: int = 20) -> int:
    """Processa Payouts vencidos: empurra os QUEUED, reconcilia os em voo.

    Claim atomico (commit) antes de agir evita entrega dupla. Retorna quantos processou.
    """
    now = _now()
    async with async_session_maker() as s:
        due_ids = (
            await s.execute(
                select(Payout.id)
                .where(Payout.status.in_(_ACTIVE_STATUSES))
                .where(or_(Payout.next_attempt_at.is_(None), Payout.next_attempt_at <= now))
                .order_by(Payout.created_at.asc())
                .limit(limit)
            )
        ).scalars().all()

    if not due_ids:
        return 0

    client = AsaasPayoutClient()
    processed = 0
    try:
        for payout_id in due_ids:
            # ── claim atomico: trava por _LOCK_SECONDS antes de processar ──
            async with async_session_maker() as s:
                locked = (
                    await s.execute(
                        update(Payout)
                        .where(Payout.id == payout_id)
                        .where(Payout.status.in_(_ACTIVE_STATUSES))
                        .where(
                            or_(
                                Payout.next_attempt_at.is_(None),
                                Payout.next_attempt_at <= _now(),
                            )
                        )
                        .values(next_attempt_at=_now() + timedelta(seconds=_LOCK_SECONDS))
                    )
                ).rowcount == 1
                await s.commit()
            if not locked:
                continue

            async with async_session_maker() as s:
                payout = await s.get(Payout, payout_id)
                if payout is None or payout.status in _TERMINAL_STATUSES:
                    continue

                if payout.status == PayoutStatus.QUEUED:
                    await _push(s, client, payout)
                else:
                    await _reconcile(s, client, payout)
                await s.commit()
            processed += 1
    finally:
        await client.aclose()
    return processed


async def _push(db: AsyncSession, client: AsaasPayoutClient, payout: Payout) -> None:
    """Empurra um Payout QUEUED pro asaas (idempotente)."""
    try:
        result = await client.create_payout(
            external_id=payout.recipient_external_id,
            amount_cents=payout.amount_cents,
            payment_id=payout.external_reference,
            description=f"Comissoes {payout.week_of}",
        )
    except IntegrationError as exc:
        # Falha transitoria (asaas fora do ar): backoff e conta tentativa.
        payout.attempts += 1
        payout.last_error = str(exc)[:500]
        if payout.attempts >= payout.max_attempts:
            payout.status = PayoutStatus.FAILED
            payout.next_attempt_at = None
            await _fail_commissions(db, payout.external_reference)
            logger.error("payout.push_giveup", ref=payout.external_reference, attempts=payout.attempts)
        else:
            delay = BACKOFF_SECONDS[min(payout.attempts - 1, len(BACKOFF_SECONDS) - 1)]
            payout.next_attempt_at = _now() + timedelta(seconds=delay)
            logger.warning("payout.push_retry", ref=payout.external_reference, attempt=payout.attempts)
        return

    if result.is_permanent_error:
        # Falha de negocio (pixkey_not_found, invalid_amount...): nao adianta retentar.
        payout.status = PayoutStatus.FAILED
        payout.last_error = result.error
        payout.next_attempt_at = None
        await _fail_commissions(db, payout.external_reference)
        logger.error("payout.push_rejected", ref=payout.external_reference, error=result.error)
        return

    # Aceito pelo asaas: reseta tentativas e aplica o status retornado.
    payout.attempts = 0
    payout.last_error = None
    await apply_payout_status(
        db,
        external_reference=payout.external_reference,
        asaas_status=result.asaas_status,
        asaas_id=result.asaas_id,
    )


async def _reconcile(db: AsyncSession, client: AsaasPayoutClient, payout: Payout) -> None:
    """Consulta o asaas e atualiza o status (rede de seguranca do webhook)."""
    try:
        result = await client.get_payout(payout.external_reference)
    except IntegrationError as exc:
        payout.last_error = str(exc)[:500]
        payout.next_attempt_at = _now() + timedelta(seconds=RECONCILE_SECONDS)
        return

    if result.is_permanent_error:
        # not_found ou outro erro de leitura: repete mais tarde, sem queimar tentativa.
        payout.last_error = f"asaas:{result.error}"
        payout.next_attempt_at = _now() + timedelta(seconds=RECONCILE_SECONDS)
        logger.warning("payout.reconcile_error", ref=payout.external_reference, error=result.error)
        return

    await apply_payout_status(
        db,
        external_reference=payout.external_reference,
        asaas_status=result.asaas_status,
        asaas_id=result.asaas_id,
    )


async def _fail_commissions(db: AsyncSession, external_reference: str) -> None:
    await db.execute(
        update(Commission)
        .where(Commission.external_reference == external_reference)
        .values(status=CommissionStatus.FAILED)
    )
