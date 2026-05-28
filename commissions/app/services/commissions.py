"""Commissions CRUD e logica de processamento semanal."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Commission, CommissionStatus, PaymentBatch, PaymentBatchStatus
from app.utils.logging import get_logger

BR_TZ = ZoneInfo("America/Sao_Paulo")
logger = get_logger("commissions.service")


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
    """Cria uma nova comissao pendente e retorna o registro."""
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

    # Count
    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Fetch
    items = (
        (await db.execute(q.order_by(Commission.created_at.desc()).offset(offset).limit(limit)))
        .scalars()
        .all()
    )

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

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    items = (
        (await db.execute(q.order_by(PaymentBatch.created_at.desc()).offset(offset).limit(limit)))
        .scalars()
        .all()
    )

    return list(items), total


# ---------------------------------------------------------------------------
# Weekly processing
# ---------------------------------------------------------------------------


def _monday_of_week(dt: date) -> date:
    """Return the Monday of the ISO week containing dt."""
    return dt - timedelta(days=dt.weekday())


async def process_weekly_batch(
    db: AsyncSession,
    *,
    week_of: str | None = None,
    force_reprocess: bool = False,
) -> PaymentBatch | None:
    """Processa comissoes pendentes da semana, aplica bonus se threshold atingido.

    Args:
        week_of: ISO date string da segunda-feira (ex: '2026-05-25').
                 Se None, usa a semana atual.
        force_reprocess: Se True, reprocessa comissoes ja liquidadas na semana.

    Returns:
        PaymentBatch criado, ou None se nao havia comissoes pendentes.
    """
    settings = get_settings()

    if week_of:
        week_date = date.fromisoformat(week_of)
    else:
        week_date = _monday_of_week(date.today())

    week_str = week_date.isoformat()

    # Check if a batch already exists for this week
    if not force_reprocess:
        existing = (
            await db.execute(
                select(PaymentBatch).where(
                    PaymentBatch.week_of == week_str,
                    PaymentBatch.status.in_(
                        [PaymentBatchStatus.PENDING, PaymentBatchStatus.PROCESSING]
                    ),
                )
            )
        ).scalar_one_or_none()
        if existing:
            logger.info("commission.batch_already_exists", week_of=week_str, batch_id=existing.id)
            return None

    # Find pending commissions this week (Mon 00:00 to Sun 23:59 BRT)
    # Convert to UTC for DB comparison (DB stores in UTC with timezone)
    week_start_local = datetime(week_date.year, week_date.month, week_date.day, tzinfo=BR_TZ)
    week_end_local = week_start_local + timedelta(days=7)
    _ = week_end_local  # used by week_end filter below

    pending = (
        (
            await db.execute(
                select(Commission)
                .where(
                    Commission.status == CommissionStatus.PENDING,
                    Commission.recipient_role == "promoter",
                )
                .order_by(Commission.created_at.asc())
            )
        )
        .scalars()
        .all()
    )

    # Also get coordinator commissions (any status=pending)
    coordinator_pending = (
        (
            await db.execute(
                select(Commission)
                .where(
                    Commission.status == CommissionStatus.PENDING,
                    Commission.recipient_role == "coordinator",
                )
                .order_by(Commission.created_at.asc())
            )
        )
        .scalars()
        .all()
    )

    all_pending = list(pending) + list(coordinator_pending)

    if not all_pending:
        logger.info("commission.no_pending", week_of=week_str)
        return None

    # Calculate totals
    promoter_commissions = [c for c in all_pending if c.recipient_role == "promoter"]
    total_base = sum(c.amount_cents for c in all_pending)
    bonus_cents = 0

    promoter_count = len(promoter_commissions)
    if promoter_count >= settings.bonus_threshold_count:
        # Bonus: extra per lead above threshold
        bonus_cents = promoter_count * settings.bonus_comission_cents
        logger.info(
            "commission.bonus_applied",
            promoter_count=promoter_count,
            threshold=settings.bonus_threshold_count,
            bonus_cents=bonus_cents,
        )

    total_cents = total_base + bonus_cents

    # Create payment batch
    batch = PaymentBatch(
        week_of=week_str,
        total_cents=total_cents,
        bonus_cents=bonus_cents,
        status=PaymentBatchStatus.PENDING,
    )
    db.add(batch)
    await db.flush()

    # Link commissions to batch and mark as processed
    for c in all_pending:
        c.status = CommissionStatus.PROCESSED
        c.payment_batch_id = batch.id

    await db.flush()

    logger.info(
        "commission.batch_created",
        batch_id=batch.id,
        week_of=week_str,
        total_cents=total_cents,
        bonus_cents=bonus_cents,
        commission_count=len(all_pending),
    )

    return batch


# ---------------------------------------------------------------------------
# Batch payment via Asaas
# ---------------------------------------------------------------------------


async def submit_batch_for_payment(
    db: AsyncSession,
    batch: PaymentBatch,
) -> str | None:
    """Submits a payment batch to Asaas for PIX payout.

    The commissions service talks to the asaas-app's REST API internally.

    Returns:
        asaas_transfer_id on success, None on failure (batch.last_error is set).
    """
    from app.integrations.asaas_client import AsaasPayoutClient

    client = AsaasPayoutClient()
    try:
        payout = await client.request_pix_payout(
            pix_key="company_pix_key_placeholder",
            amount_cents=batch.total_cents,
            description=f"Comissoes semana {batch.week_of}",
        )
        if payout.success:
            asaas_id = payout.asaas_transfer_id
            batch.pix_transaction_id = payout.pix_transaction_id
            batch.asaas_transfer_id = payout.asaas_transfer_id
            batch.status = PaymentBatchStatus.PROCESSING
            await db.flush()
            logger.info("commission.batch_submitted", batch_id=batch.id, asaas_id=asaas_id)
            return asaas_id
        else:
            batch.status = PaymentBatchStatus.FAILED
            batch.last_error = payout.error
            await db.flush()
            logger.error("commission.batch_submit_failed", batch_id=batch.id, error=payout.error)
            return None
    except Exception as e:
        batch.status = PaymentBatchStatus.FAILED
        batch.last_error = str(e)[:1000]
        await db.flush()
        logger.error("commission.batch_submit_failed", batch_id=batch.id, error=str(e))
        return None


# Convenience class for dependency injection
class CommissionService:
    """Service facade for commission operations."""

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
    """Service facade for payment batch operations."""

    @staticmethod
    async def get(db: AsyncSession, batch_id: int) -> PaymentBatch | None:
        return await get_payment_batch(db, batch_id)

    @staticmethod
    async def list(db: AsyncSession, **kwargs) -> tuple[list[PaymentBatch], int]:
        return await list_payment_batches(db, **kwargs)
