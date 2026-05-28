"""Commission service — business logic for creating and managing commissions.

Handles:
- Creating commissions from lead/student completion events
- Idempotency guarantees (one commission per source_event_id)
- Bonus calculation for promoters who exceed thresholds
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.commission import Commission, CommissionStatus


class CommissionService:
    """Service layer for commission creation and querying."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._settings = get_settings()

    async def create_commission(
        self,
        recipient_external_id: UUID,
        recipient_role: str,
        source_type: str,
        source_external_id: UUID,
        amount_cents: int | None = None,
    ) -> Commission:
        """Create a new commission entry.

        Idempotent per (source_type, source_external_id) — if a commission
        already exists for the same source, returns the existing one.

        Args:
            recipient_external_id: UUID of the recipient (promoter/coordinator).
            recipient_role: Role identifier (e.g. 'promoter', 'coordinator').
            source_type: Source entity type (e.g. 'lead', 'student_completion').
            source_external_id: UUID of the source entity.
            amount_cents: Commission value in cents. Falls back to env config.

        Returns:
            The created (or existing) Commission.
        """
        # Idempotency check — unique per source
        existing = await self._get_commission_by_source(source_type, source_external_id)
        if existing is not None:
            return existing

        # Resolve amount from env if not provided
        if amount_cents is None:
            amount_cents = self._resolve_amount(recipient_role)

        commission = Commission(
            recipient_external_id=recipient_external_id,
            recipient_role=recipient_role,
            source_type=source_type,
            source_external_id=source_external_id,
            amount_cents=amount_cents,
            status=CommissionStatus.PENDING,
        )
        self._session.add(commission)
        await self._session.flush()
        return commission

    async def _get_commission_by_source(
        self,
        source_type: str,
        source_external_id: UUID,
    ) -> Commission | None:
        """Check if a commission already exists for this source event."""
        stmt = select(Commission).where(
            Commission.source_type == source_type,
            Commission.source_external_id == source_external_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    def _resolve_amount(self, recipient_role: str) -> int:
        """Determine commission amount based on recipient role and env config."""
        if recipient_role == "coordinator":
            return self._settings.coordinator_commission_cents
        return self._settings.promoter_commission_cents

    async def get_pending_commissions(self) -> list[Commission]:
        """Get all commissions with PENDING status (not yet in a batch)."""
        stmt = (
            select(Commission)
            .where(
                Commission.status == CommissionStatus.PENDING, Commission.payment_batch_id.is_(None)
            )
            .order_by(Commission.created_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_pending_leads_this_week(self, week_start_str: str) -> int:
        """Count PENDING commissions of type 'lead' within a given week.

        This is used for bonus threshold calculation: if a promoter has
        N+ leads this week, they qualify for a bonus.

        Args:
            week_start_str: ISO date string for the week's Monday.

        Returns:
            Count of lead commissions.
        """
        stmt = select(Commission).where(
            Commission.status == CommissionStatus.PENDING,
            Commission.source_type == "lead",
            Commission.payment_batch_id.is_(None),
        )
        result = await self._session.execute(stmt)
        commissions = list(result.scalars().all())
        return len(commissions)

    async def mark_as_processed(
        self,
        commission_ids: list[int],
        batch_id: int,
    ) -> int:
        """Mark a list of commissions as PROCESSED and link them to a batch.

        Returns:
            Number of commissions updated.
        """
        if not commission_ids:
            return 0

        from sqlalchemy import update

        stmt = (
            update(Commission)
            .where(Commission.id.in_(commission_ids))
            .values(
                status=CommissionStatus.PROCESSED,
                payment_batch_id=batch_id,
            )
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount

    async def update_status(
        self,
        commission_id: int,
        status: CommissionStatus,
    ) -> Commission | None:
        """Update a single commission's status."""
        commission = await self._session.get(Commission, commission_id)
        if commission is not None:
            commission.status = status
            await self._session.flush()
        return commission
