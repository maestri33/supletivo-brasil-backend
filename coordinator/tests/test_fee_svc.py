"""Tests for enrollment fee service CRUD operations."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enrollment_fee import FeeStatus
from app.services import (
    create_coordinator,
    create_enrollment_fee,
    list_enrollment_fees,
    pay_enrollment_fee,
)


@pytest.fixture
async def coordinator(db_session: AsyncSession) -> str:
    c = await create_coordinator(db_session, external_id="fee-ext", hub_external_id="fee-hub")
    await db_session.commit()
    return c.id


class TestCreateEnrollmentFee:
    async def test_creates_fee(self, db_session: AsyncSession, coordinator: str) -> None:
        fee = await create_enrollment_fee(
            db_session,
            coordinator_id=coordinator,
            student_external_id="std-001",
            description="Matrícula",
            amount=Decimal("150.00"),
        )
        assert fee.id is not None
        assert fee.coordinator_id == coordinator
        assert fee.student_external_id == "std-001"
        assert fee.description == "Matrícula"
        assert fee.amount == Decimal("150.00")
        assert fee.status == FeeStatus.pending

    async def test_accepts_due_date(self, db_session: AsyncSession, coordinator: str) -> None:
        fee = await create_enrollment_fee(
            db_session,
            coordinator_id=coordinator,
            student_external_id="std-002",
            description="Segunda parcela",
            amount=Decimal("200.00"),
            due_date="2026-06-15",
        )
        assert fee.due_date is not None
        assert str(fee.due_date) == "2026-06-15"


class TestListEnrollmentFees:
    async def test_returns_all(self, db_session: AsyncSession, coordinator: str) -> None:
        await create_enrollment_fee(
            db_session, coordinator_id=coordinator,
            student_external_id="s1", description="fee1", amount=Decimal("10"),
        )
        await create_enrollment_fee(
            db_session, coordinator_id=coordinator,
            student_external_id="s2", description="fee2", amount=Decimal("20"),
        )
        await db_session.commit()

        items, total = await list_enrollment_fees(db_session)
        assert total == 2

    async def test_filters_by_student(self, db_session: AsyncSession, coordinator: str) -> None:
        await create_enrollment_fee(
            db_session, coordinator_id=coordinator,
            student_external_id="std-a", description="a", amount=Decimal("10"),
        )
        await create_enrollment_fee(
            db_session, coordinator_id=coordinator,
            student_external_id="std-b", description="b", amount=Decimal("20"),
        )
        await db_session.commit()

        items, total = await list_enrollment_fees(db_session, student_external_id="std-a")
        assert total == 1

    async def test_returns_empty(self, db_session: AsyncSession) -> None:
        items, total = await list_enrollment_fees(db_session)
        assert total == 0


class TestPayEnrollmentFee:
    async def test_pays_fee(self, db_session: AsyncSession, coordinator: str) -> None:
        fee = await create_enrollment_fee(
            db_session, coordinator_id=coordinator,
            student_external_id="std-pay", description="a pagar", amount=Decimal("100"),
        )
        await db_session.commit()

        result = await pay_enrollment_fee(db_session, fee.id, payment_external_id="pay-001")
        assert result is not None
        assert result.status == FeeStatus.paid
        assert result.payment_external_id == "pay-001"

    async def test_returns_none_for_missing(self, db_session: AsyncSession) -> None:
        result = await pay_enrollment_fee(db_session, "no-such", payment_external_id="pay-x")
        assert result is None
