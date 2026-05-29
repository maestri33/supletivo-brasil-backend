"""Commissions — CRUD + processamento do lote semanal (desenho do dono).

Lote (sexta 18h America/Sao_Paulo):
  1. junta as comissoes PENDING (lead + coordenador), ainda nao loteadas;
  2. calcula BONUS FLAT por promotor (>= threshold indicacoes que pagaram na semana
     -> bonus_flat_cents UMA vez; NAO escala);
  3. agrega TUDO por beneficiario -> 1 Payout por pessoa;
  4. external_reference = {ordinal-sexta}_{MM}_{AAAA}_{external_id} (idempotencia),
     carimbado em TODAS as comissoes/bonus do payout; comissoes viram PROCESSED.

Os Payouts nascem QUEUED. Quem os empurra pro asaas (que detem a fila pesada) e o
worker — ver services/payout.py. AQUI nao se chama o asaas nem se move dinheiro.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import (
    Commission,
    CommissionStatus,
    PaymentBatch,
    PaymentBatchStatus,
    Payout,
    PayoutStatus,
)
from app.utils.logging import get_logger

BR_TZ = ZoneInfo("America/Sao_Paulo")
logger = get_logger("commissions.service")

# Namespace fixo p/ gerar source_external_id deterministico dos bonus (idempotencia).
_BONUS_NS = uuid.UUID("b0000005-0000-0000-0000-000000000005")


# ---------------------------------------------------------------------------
# Commission CRUD
# ---------------------------------------------------------------------------


async def create_commission(
    db: AsyncSession,
    *,
    recipient_external_id: UUID,
    recipient_role: str,
    source_type: str,
    source_external_id: UUID,
    amount_cents: int,
) -> Commission:
    """Cria (ou retorna a existente) uma comissao pendente.

    Idempotente por (source_type, source_external_id): o mesmo evento de origem
    (ex: o mesmo lead que pagou) nunca gera duas comissoes.
    """
    existing = await _get_commission_by_source(db, source_type, source_external_id)
    if existing is not None:
        return existing

    commission = Commission(
        recipient_external_id=recipient_external_id,
        recipient_role=recipient_role,
        source_type=source_type,
        source_external_id=source_external_id,
        amount_cents=amount_cents,
        status=CommissionStatus.PENDING,
    )
    db.add(commission)
    await db.flush()
    logger.info(
        "commission.created",
        id=commission.id,
        recipient_role=recipient_role,
        source_type=source_type,
        amount_cents=amount_cents,
    )
    return commission


async def _get_commission_by_source(
    db: AsyncSession, source_type: str, source_external_id: UUID
) -> Commission | None:
    return (
        await db.execute(
            select(Commission).where(
                Commission.source_type == source_type,
                Commission.source_external_id == source_external_id,
            )
        )
    ).scalar_one_or_none()


async def get_commission(db: AsyncSession, commission_id: int) -> Commission | None:
    return (
        await db.execute(select(Commission).where(Commission.id == commission_id))
    ).scalar_one_or_none()


async def list_commissions(
    db: AsyncSession,
    *,
    status: str | None = None,
    recipient_external_id: UUID | None = None,
    recipient_role: str | None = None,
    payment_batch_id: int | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[Commission], int]:
    """Lista comissoes com filtros opcionais. Retorna (items, total)."""
    q = select(Commission)
    if status:
        q = q.where(Commission.status == status)
    if recipient_external_id:
        q = q.where(Commission.recipient_external_id == recipient_external_id)
    if recipient_role:
        q = q.where(Commission.recipient_role == recipient_role)
    if payment_batch_id is not None:
        q = q.where(Commission.payment_batch_id == payment_batch_id)

    total = (
        await db.execute(select(func.count()).select_from(q.subquery()))
    ).scalar() or 0
    items = (
        await db.execute(
            q.order_by(Commission.created_at.desc()).offset(offset).limit(limit)
        )
    ).scalars().all()
    return list(items), total


# ---------------------------------------------------------------------------
# PaymentBatch CRUD
# ---------------------------------------------------------------------------


async def get_payment_batch(db: AsyncSession, batch_id: int) -> PaymentBatch | None:
    return (
        await db.execute(select(PaymentBatch).where(PaymentBatch.id == batch_id))
    ).scalar_one_or_none()


async def list_payment_batches(
    db: AsyncSession,
    *,
    status: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[PaymentBatch], int]:
    q = select(PaymentBatch)
    if status:
        q = q.where(PaymentBatch.status == status)
    total = (
        await db.execute(select(func.count()).select_from(q.subquery()))
    ).scalar() or 0
    items = (
        await db.execute(
            q.order_by(PaymentBatch.created_at.desc()).offset(offset).limit(limit)
        )
    ).scalars().all()
    return list(items), total


# ---------------------------------------------------------------------------
# Payout (leitura)
# ---------------------------------------------------------------------------


async def list_payouts(
    db: AsyncSession,
    *,
    status: str | None = None,
    week_of: str | None = None,
    recipient_external_id: UUID | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[Payout], int]:
    """Lista payouts com filtros opcionais. Retorna (items, total)."""
    q = select(Payout)
    if status:
        q = q.where(Payout.status == status)
    if week_of:
        q = q.where(Payout.week_of == week_of)
    if recipient_external_id:
        q = q.where(Payout.recipient_external_id == recipient_external_id)
    total = (
        await db.execute(select(func.count()).select_from(q.subquery()))
    ).scalar() or 0
    items = (
        await db.execute(
            q.order_by(Payout.created_at.desc()).offset(offset).limit(limit)
        )
    ).scalars().all()
    return list(items), total


# ---------------------------------------------------------------------------
# Helpers de data / referencia
# ---------------------------------------------------------------------------


def _monday_of_week(dt: date) -> date:
    return dt - timedelta(days=dt.weekday())


def _friday_ordinal(friday: date) -> int:
    """Qual sexta do mes (1..5). Normalmente 1-4; meses com 5 sextas dao 5 (ainda unico)."""
    return (friday.day - 1) // 7 + 1


def build_external_reference(week_monday: date, recipient_external_id: UUID) -> str:
    """{ordinal-sexta}_{MM}_{AAAA}_{external_id} — chave de idempotencia do payout."""
    friday = week_monday + timedelta(days=4)
    return f"{_friday_ordinal(friday)}_{friday.month:02d}_{friday.year}_{recipient_external_id}"


def _bonus_source_id(week_str: str, promoter_id: UUID) -> UUID:
    """source_external_id deterministico do bonus (idempotente por semana+promotor)."""
    return uuid.uuid5(_BONUS_NS, f"bonus:{week_str}:{promoter_id}")


# ---------------------------------------------------------------------------
# Processamento semanal
# ---------------------------------------------------------------------------


async def process_weekly_batch(
    db: AsyncSession,
    *,
    week_of: str | None = None,
    force_reprocess: bool = False,
) -> PaymentBatch | None:
    """Processa as comissoes pendentes num lote semanal e gera 1 Payout por beneficiario.

    Idempotente por semana: se ja existe lote nao-falho para a semana, retorna None
    (a menos que force_reprocess). Payouts ja existentes (mesma external_reference)
    sao pulados — nunca se cria pagamento duplicado.

    NAO chama o asaas: os Payouts nascem QUEUED e sao empurrados pelo worker.
    Retorna o PaymentBatch criado, ou None se nada havia para processar.
    """
    settings = get_settings()
    week_date = date.fromisoformat(week_of) if week_of else _monday_of_week(datetime.now(BR_TZ).date())
    week_str = week_date.isoformat()

    if not force_reprocess:
        existing = (
            await db.execute(
                select(PaymentBatch).where(
                    PaymentBatch.week_of == week_str,
                    PaymentBatch.status != PaymentBatchStatus.FAILED,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            logger.info("commission.batch_already_exists", week_of=week_str, batch_id=existing.id)
            return None

    # Comissoes pendentes (lead + coordenador), ainda nao loteadas.
    pending = list(
        (
            await db.execute(
                select(Commission)
                .where(
                    Commission.status == CommissionStatus.PENDING,
                    Commission.payment_batch_id.is_(None),
                )
                .order_by(Commission.created_at.asc())
            )
        ).scalars().all()
    )
    if not pending:
        logger.info("commission.no_pending", week_of=week_str)
        return None

    batch = PaymentBatch(
        week_of=week_str,
        total_cents=0,
        bonus_cents=0,
        status=PaymentBatchStatus.PROCESSING,
    )
    db.add(batch)
    await db.flush()

    # ── BONUS FLAT por promotor (>= threshold leads que pagaram na semana) ──
    bonus_cents_total = 0
    bonus_commissions: list[Commission] = []
    if settings.bonus_threshold_count > 0 and settings.bonus_flat_cents > 0:
        lead_counts: dict[UUID, int] = {}
        for c in pending:
            if c.recipient_role == "promoter" and c.source_type == "lead":
                lead_counts[c.recipient_external_id] = lead_counts.get(c.recipient_external_id, 0) + 1
        for promoter_id, n in lead_counts.items():
            if n >= settings.bonus_threshold_count:
                bonus = Commission(
                    recipient_external_id=promoter_id,
                    recipient_role="promoter",
                    source_type="bonus",
                    source_external_id=_bonus_source_id(week_str, promoter_id),
                    amount_cents=settings.bonus_flat_cents,
                    status=CommissionStatus.PENDING,
                )
                db.add(bonus)
                bonus_commissions.append(bonus)
                bonus_cents_total += settings.bonus_flat_cents
                logger.info(
                    "commission.bonus_applied",
                    promoter=str(promoter_id),
                    leads=n,
                    threshold=settings.bonus_threshold_count,
                    bonus_cents=settings.bonus_flat_cents,
                )
        if bonus_commissions:
            await db.flush()

    all_commissions = pending + bonus_commissions

    # ── Agrega por beneficiario -> 1 Payout por pessoa ──
    by_recipient: dict[UUID, list[Commission]] = {}
    for c in all_commissions:
        by_recipient.setdefault(c.recipient_external_id, []).append(c)

    # Refs ja existentes p/ a semana (idempotencia em re-runs forcados).
    existing_refs = set(
        (
            await db.execute(
                select(Payout.external_reference).where(Payout.week_of == week_str)
            )
        ).scalars().all()
    )

    total_cents = 0
    for recipient_id, items in by_recipient.items():
        ext_ref = build_external_reference(week_date, recipient_id)
        if ext_ref in existing_refs:
            logger.warning("payout.ref_exists_skip", ref=ext_ref)
            continue
        amount = sum(c.amount_cents for c in items)
        # coordenador tem precedencia no rotulo (a mesma pessoa pode ser promotor+coordenador)
        role = "coordinator" if any(c.recipient_role == "coordinator" for c in items) else "promoter"

        db.add(
            Payout(
                external_reference=ext_ref,
                recipient_external_id=recipient_id,
                recipient_role=role,
                amount_cents=amount,
                week_of=week_str,
                payment_batch_id=batch.id,
                status=PayoutStatus.QUEUED,
            )
        )
        for c in items:
            c.status = CommissionStatus.PROCESSED
            c.payment_batch_id = batch.id
            c.external_reference = ext_ref
        total_cents += amount

    batch.total_cents = total_cents
    batch.bonus_cents = bonus_cents_total
    # COMPLETED aqui = lote AGREGADO (payouts criados/enfileirados); o pagamento em si
    # e rastreado por Payout.status (PAID/FAILED), nao pelo lote.
    batch.status = PaymentBatchStatus.COMPLETED
    await db.flush()

    logger.info(
        "commission.batch_created",
        batch_id=batch.id,
        week_of=week_str,
        total_cents=total_cents,
        bonus_cents=bonus_cents_total,
        commission_count=len(all_commissions),
        payout_count=len(by_recipient),
    )
    return batch


# ---------------------------------------------------------------------------
# Facades (compat — usadas pela camada de API)
# ---------------------------------------------------------------------------


class CommissionService:
    """Facade de comissoes."""

    @staticmethod
    async def create(
        db: AsyncSession,
        recipient_external_id: UUID,
        recipient_role: str,
        source_type: str,
        source_external_id: UUID,
        amount_cents: int,
    ) -> Commission:
        return await create_commission(
            db,
            recipient_external_id=recipient_external_id,
            recipient_role=recipient_role,
            source_type=source_type,
            source_external_id=source_external_id,
            amount_cents=amount_cents,
        )

    @staticmethod
    async def get(db: AsyncSession, commission_id: int) -> Commission | None:
        return await get_commission(db, commission_id)

    @staticmethod
    async def list(db: AsyncSession, **kwargs) -> tuple[list[Commission], int]:
        return await list_commissions(db, **kwargs)


class PaymentBatchService:
    """Facade de lotes de pagamento."""

    @staticmethod
    async def get(db: AsyncSession, batch_id: int) -> PaymentBatch | None:
        return await get_payment_batch(db, batch_id)

    @staticmethod
    async def list(db: AsyncSession, **kwargs) -> tuple[list[PaymentBatch], int]:
        return await list_payment_batches(db, **kwargs)
