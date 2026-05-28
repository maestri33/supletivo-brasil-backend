"""Tests for the commissions service — commission creation and listing."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.commission import CommissionStatus
from app.services.commission_service import CommissionService

from .conftest import COORDINATOR_ID, LEAD_ID, PROMOTER_ID, STUDENT_ID


@pytest.mark.asyncio
async def test_create_lead_commission(db_session: AsyncSession):
    """Commission is created for a promoter when a lead completes."""
    service = CommissionService(db_session)
    commission = await service.create_commission(
        recipient_external_id=PROMOTER_ID,
        recipient_role="promoter",
        source_type="lead",
        source_external_id=LEAD_ID,
    )

    assert commission.id is not None
    assert commission.recipient_external_id == PROMOTER_ID
    assert commission.recipient_role == "promoter"
    assert commission.source_type == "lead"
    assert commission.source_external_id == LEAD_ID
    assert commission.status == CommissionStatus.PENDING
    assert commission.amount_cents == 100  # Default from config
    assert commission.payment_batch_id is None


@pytest.mark.asyncio
async def test_create_coordinator_commission(db_session: AsyncSession):
    """Commission is created for a coordinator when a student completes."""
    service = CommissionService(db_session)
    commission = await service.create_commission(
        recipient_external_id=COORDINATOR_ID,
        recipient_role="coordinator",
        source_type="student_completion",
        source_external_id=STUDENT_ID,
    )

    assert commission.id is not None
    assert commission.recipient_role == "coordinator"
    assert commission.amount_cents == 50  # Default from config


@pytest.mark.asyncio
async def test_idempotent_commission_creation(db_session: AsyncSession):
    """Creating a commission for the same source returns the existing one."""
    service = CommissionService(db_session)
    c1 = await service.create_commission(
        recipient_external_id=PROMOTER_ID,
        recipient_role="promoter",
        source_type="lead",
        source_external_id=LEAD_ID,
    )

    c2 = await service.create_commission(
        recipient_external_id=PROMOTER_ID,
        recipient_role="promoter",
        source_type="lead",
        source_external_id=LEAD_ID,
    )

    assert c1.id == c2.id


@pytest.mark.asyncio
async def test_create_with_custom_amount(db_session: AsyncSession):
    """A custom amount_cents can override the env default."""
    service = CommissionService(db_session)
    commission = await service.create_commission(
        recipient_external_id=PROMOTER_ID,
        recipient_role="promoter",
        source_type="lead",
        source_external_id=LEAD_ID,
        amount_cents=999,
    )

    assert commission.amount_cents == 999


@pytest.mark.asyncio
async def test_get_pending_commissions(db_session: AsyncSession):
    """Only PENDING commissions (not in any batch) are returned."""
    service = CommissionService(db_session)

    c1 = await service.create_commission(
        recipient_external_id=PROMOTER_ID,
        recipient_role="promoter",
        source_type="lead",
        source_external_id=LEAD_ID,
    )

    # Mark c1 as processed
    await service.mark_as_processed([c1.id], batch_id=1)

    # Create a second pending commission
    LEAD_ID_2 = "00000000-0000-0000-0000-000000000011"
    from uuid import UUID

    await service.create_commission(
        recipient_external_id=PROMOTER_ID,
        recipient_role="promoter",
        source_type="lead",
        source_external_id=UUID(LEAD_ID_2),
    )

    pending = await service.get_pending_commissions()
    assert len(pending) == 1
    assert pending[0].id != c1.id
