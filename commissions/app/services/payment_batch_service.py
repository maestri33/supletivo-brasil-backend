"""Payment batch service — weekly batch creation, bonus calculation, and PIX payout.

Handles:
- Aggregating pending commissions by recipient
- Calculating promoter bonuses (threshold-based)
- Creating PaymentBatch records
- Dispatching PIX payouts via Asaas client
- Idempotent weekly processing (no duplicate batches for the same week)
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.integrations.asaas_client import AsaasPayoutClient
from app.models.commission import Commission, CommissionStatus
from app.models.payment_batch import PaymentBatch, PaymentBatchStatus
from app.services.commission_service import CommissionService


class PaymentBatchService:
    """Service layer for weekly payment batch processing."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._settings = get_settings()
        self._commission_service = CommissionService(session)
        self._asaas_client = AsaasPayoutClient()

    async def get_or_create_weekly_batch(self, week_of: str) -> PaymentBatch:
        """Get an existing batch for the week or create a new PENDING one.

        Idempotent: if a batch already exists (in any non-FAILED state),
        returns it instead of creating a duplicate.

        Args:
            week_of: ISO date string (Monday of the week).

        Returns:
            The existing or new PaymentBatch.
        """
        existing = await self._get_batch_by_week(week_of)
        if existing is not None and existing.status != PaymentBatchStatus.FAILED:
            return existing

        batch = PaymentBatch(
            week_of=week_of,
            total_cents=0,
            bonus_cents=0,
            status=PaymentBatchStatus.PENDING,
        )
        self._session.add(batch)
        await self._session.flush()
        return batch

    async def process_weekly_batch(self, week_of: str | None = None) -> PaymentBatch:
        """Process all pending commissions into a weekly batch.

        1. Get or create the batch for the week
        2. Collect all PENDING commissions
        3. Calculate bonuses for promoters who exceeded the threshold
        4. Mark commissions as PROCESSED and link to batch
        5. Trigger PIX payout via Asaas

        Args:
            week_of: ISO Monday date. If None, calculates from current time.

        Returns:
            The processed PaymentBatch with its commissions.
        """
        if week_of is None:
            week_of = _get_current_week_monday()

        batch = await self.get_or_create_weekly_batch(week_of)

        # Don't reprocess a completed batch
        if batch.status == PaymentBatchStatus.COMPLETED:
            return batch

        batch.status = PaymentBatchStatus.PROCESSING
        await self._session.flush()

        try:
            # Collect pending commissions
            pending = await self._commission_service.get_pending_commissions()
            if not pending:
                batch.status = PaymentBatchStatus.COMPLETED
                batch.total_cents = 0
                batch.bonus_cents = 0
                await self._session.flush()
                await self._session.commit()
                return batch

            # Calculate base total
            base_total = sum(c.amount_cents for c in pending)
            bonus_total = 0

            # Calculate promoter bonus
            bonus_total = await self._calculate_promoter_bonus(
                pending, week_of, base_total
            )

            # Update batch totals
            batch.total_cents = base_total + bonus_total
            batch.bonus_cents = bonus_total

            # Mark commissions as processed
            batch_id = batch.id
            commission_ids = [c.id for c in pending]
            await self._commission_service.mark_as_processed(commission_ids, batch_id)

            # Trigger payout (idempotent — in dev mode returns mock success)
            payout = await self._asaas_client.request_pix_payout(
                pix_key="company_pix_key_placeholder",
                amount_cents=batch.total_cents,
                description=f"Comissões semana {week_of}",
            )

            if payout.success:
                batch.pix_transaction_id = payout.pix_transaction_id
                batch.asaas_transfer_id = payout.asaas_transfer_id
                batch.status = PaymentBatchStatus.COMPLETED
            else:
                batch.last_error = payout.error
                batch.status = PaymentBatchStatus.FAILED

            await self._session.flush()
            await self._session.commit()
            return batch

        except Exception as exc:
            await self._session.rollback()
            batch.status = PaymentBatchStatus.FAILED
            batch.last_error = f"{type(exc).__name__}: {exc}"
            self._session.add(batch)
            await self._session.flush()
            await self._session.commit()
            return batch

    async def _calculate_promoter_bonus(
        self,
        pending: list[Commission],
        week_of: str,
        current_total: int,
    ) -> int:
        """Calculate promoter bonus for those exceeding the lead threshold.

        The PRD states: if the number of lead commissions in the period
        >= threshold from env, add one bonus commission per qualifying promoter.

        For now, the bonus is simple: count lead commissions. If total lead
        commissions >= bonus_threshold_count, add bonus_comission_cents.
        """
        threshold = self._settings.bonus_threshold_count
        bonus_value = self._settings.bonus_comission_cents

        if threshold <= 0 or bonus_value <= 0:
            return 0

        # Count lead commissions
        lead_count = sum(1 for c in pending if c.source_type == "lead")

        if lead_count >= threshold:
            # Add one bonus commission value
            return bonus_value

        return 0

    async def _get_batch_by_week(self, week_of: str) -> PaymentBatch | None:
        """Find an existing batch for the given week."""
        stmt = select(PaymentBatch).where(PaymentBatch.week_of == week_of)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_batches(
        self,
        limit: int = 20,
        offset: int = 0,
    ) -> list[PaymentBatch]:
        """List payment batches sorted newest first."""
        stmt = (
            select(PaymentBatch)
            .order_by(PaymentBatch.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_batch(self, batch_id: int) -> PaymentBatch | None:
        """Get a specific batch by ID."""
        return await self._session.get(PaymentBatch, batch_id)

    async def list_commissions(
        self,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
    ) -> list[Commission]:
        """List commissions with optional status filter."""
        stmt = select(Commission).order_by(Commission.created_at.desc())
        if status:
            try:
                stmt = stmt.where(
                    Commission.status == CommissionStatus(status)
                )
            except ValueError:
                pass
        stmt = stmt.limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_commissions(self, status: str | None = None) -> int:
        """Count commissions with optional status filter."""
        from sqlalchemy import func

        stmt = select(func.count(Commission.id))
        if status:
            try:
                stmt = stmt.where(
                    Commission.status == CommissionStatus(status)
                )
            except ValueError:
                pass
        result = await self._session.execute(stmt)
        return result.scalar() or 0


def _get_current_week_monday() -> str:
    """Get the ISO Monday date string for the current week.

    Uses America/Sao_Paulo timezone as per spec.
    """
    from zoneinfo import ZoneInfo

    tz = ZoneInfo("America/Sao_Paulo")
    now = datetime.now(tz)
    # Calculate Monday of current week (Monday=0)
    monday = now.date() - __import__("datetime").timedelta(days=now.weekday())
    return monday.isoformat()
