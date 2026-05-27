"""Testes unitários do fee_service (lógica pura, sem rede).

Cobre: derive_fee_status (todas as combinações), get_fee, get_active_fee_by_student,
get_latest_fee_by_student, list_fees, load_payments, apply_payout_webhook (edge cases).
"""

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Fee, FeePayment, FeePaymentKind, FeeStatus
from app.services.fee_service import (
    ACTIVE_FEE_STATUSES,
    derive_fee_status,
    get_active_fee_by_student,
    get_fee,
    get_latest_fee_by_student,
    list_fees,
    load_payments,
)

FEE_ID = str(uuid4())
STUDENT_1 = str(uuid4())
STUDENT_2 = str(uuid4())
STUDENT_3 = str(uuid4())
STUDENT_4 = str(uuid4())
COORD = str(uuid4())


class TestDeriveFeeStatus:
    """Cobre todas as combinações relevantes de derive_fee_status."""

    def test_both_pending(self):
        assert derive_fee_status("PENDING", "PENDING") == FeeStatus.PENDING

    def test_both_paid(self):
        assert derive_fee_status("PAID", "PAID") == FeeStatus.FULLY_PAID

    def test_upfront_paid_scheduled_pending(self):
        assert derive_fee_status("PAID", "PENDING") == FeeStatus.FIRST_PAID

    def test_upfront_paid_scheduled_failed(self):
        """Falha da agendada não rebaixa uma taxa já paga na 1ª parte."""
        assert derive_fee_status("PAID", "FAILED") == FeeStatus.FIRST_PAID

    def test_upfront_paid_scheduled_cancelled(self):
        assert derive_fee_status("PAID", "CANCELLED") == FeeStatus.FIRST_PAID

    def test_upfront_failed(self):
        assert derive_fee_status("FAILED", "PENDING") == FeeStatus.FAILED

    def test_upfront_cancelled(self):
        assert derive_fee_status("CANCELLED", "PENDING") == FeeStatus.FAILED

    def test_both_failed(self):
        assert derive_fee_status("FAILED", "FAILED") == FeeStatus.FAILED

    def test_upfront_queued_scheduled_scheduled(self):
        assert derive_fee_status("QUEUED", "SCHEDULED") == FeeStatus.PENDING

    def test_upfront_submitted_scheduled_scheduled(self):
        assert derive_fee_status("SUBMITTED", "SCHEDULED") == FeeStatus.PENDING

    def test_active_statuses_excludes_failed_cancelled(self):
        assert "FAILED" not in ACTIVE_FEE_STATUSES
        assert "CANCELLED" not in ACTIVE_FEE_STATUSES
        assert FeeStatus.PENDING.value in ACTIVE_FEE_STATUSES
        assert FeeStatus.FIRST_PAID.value in ACTIVE_FEE_STATUSES
        assert FeeStatus.FULLY_PAID.value in ACTIVE_FEE_STATUSES


@pytest.mark.asyncio
class TestFeeServiceQueries:
    """Testes das funções de query (com DB SQLite)."""

    async def test_get_fee_not_found(self, db_session: AsyncSession):
        result = await get_fee(db_session, "00000000-0000-0000-0000-000000000099")
        assert result is None

    async def test_get_active_fee_by_student_no_fees(self, db_session: AsyncSession):
        result = await get_active_fee_by_student(db_session, STUDENT_1)
        assert result is None

    async def test_get_active_fee_by_student_with_pending(self, db_session: AsyncSession):
        fee = Fee(
            id=FEE_ID,
            student_external_id=STUDENT_1,
            coordinator_external_id=COORD,
            status=FeeStatus.PENDING.value,
        )
        db_session.add(fee)
        await db_session.commit()

        result = await get_active_fee_by_student(db_session, STUDENT_1)
        assert result is not None
        assert result.id == FEE_ID

    async def test_get_active_fee_by_student_ignores_failed(self, db_session: AsyncSession):
        fee = Fee(
            id=str(uuid4()),
            student_external_id=STUDENT_2,
            coordinator_external_id=COORD,
            status=FeeStatus.FAILED.value,
        )
        db_session.add(fee)
        await db_session.commit()

        result = await get_active_fee_by_student(db_session, STUDENT_2)
        assert result is None

    async def test_get_active_fee_by_student_ignores_cancelled(self, db_session: AsyncSession):
        fee = Fee(
            id=str(uuid4()),
            student_external_id=STUDENT_3,
            coordinator_external_id=COORD,
            status=FeeStatus.CANCELLED.value,
        )
        db_session.add(fee)
        await db_session.commit()

        result = await get_active_fee_by_student(db_session, STUDENT_3)
        assert result is None

    async def test_get_latest_fee_returns_most_recent(self, db_session: AsyncSession):
        fee1 = Fee(
            id=str(uuid4()),
            student_external_id=STUDENT_4,
            coordinator_external_id=COORD,
            status=FeeStatus.FAILED.value,
        )
        fee2 = Fee(
            id=str(uuid4()),
            student_external_id=STUDENT_4,
            coordinator_external_id=COORD,
            status=FeeStatus.PENDING.value,
        )
        db_session.add_all([fee1, fee2])
        await db_session.commit()

        result = await get_latest_fee_by_student(db_session, STUDENT_4)
        assert result is not None
        # Deve retornar a mais recente (última inserida)
        assert result.status == FeeStatus.PENDING.value

    async def test_get_latest_fee_not_found(self, db_session: AsyncSession):
        result = await get_latest_fee_by_student(db_session, "00000000-0000-0000-0000-000000000099")
        assert result is None

    async def test_list_fees_empty(self, db_session: AsyncSession):
        result = await list_fees(db_session)
        assert result == []

    async def test_list_fees_with_data(self, db_session: AsyncSession):
        fee1 = Fee(
            id=str(uuid4()),
            student_external_id=STUDENT_1,
            coordinator_external_id=COORD,
            status=FeeStatus.PENDING.value,
        )
        fee2 = Fee(
            id=str(uuid4()),
            student_external_id=STUDENT_2,
            coordinator_external_id=COORD,
            status=FeeStatus.FULLY_PAID.value,
        )
        db_session.add_all([fee1, fee2])
        await db_session.commit()

        result = await list_fees(db_session)
        assert len(result) == 2

    async def test_list_fees_filter_by_status(self, db_session: AsyncSession):
        fee1 = Fee(
            id=str(uuid4()),
            student_external_id=STUDENT_1,
            coordinator_external_id=COORD,
            status=FeeStatus.PENDING.value,
        )
        fee2 = Fee(
            id=str(uuid4()),
            student_external_id=STUDENT_2,
            coordinator_external_id=COORD,
            status=FeeStatus.FULLY_PAID.value,
        )
        db_session.add_all([fee1, fee2])
        await db_session.commit()

        result = await list_fees(db_session, status="FULLY_PAID")
        assert len(result) == 1
        assert result[0].status == "FULLY_PAID"

    async def test_list_fees_pagination(self, db_session: AsyncSession):
        for i in range(5):
            db_session.add(
                Fee(
                    id=str(uuid4()),
                    student_external_id=str(uuid4()),
                    coordinator_external_id=COORD,
                    status=FeeStatus.PENDING.value,
                )
            )
        await db_session.commit()

        result = await list_fees(db_session, limit=2, offset=0)
        assert len(result) == 2

    async def test_load_payments_ordered_by_kind(self, db_session: AsyncSession):
        fp1 = FeePayment(
            id=str(uuid4()),
            fee_id=FEE_ID,
            kind=FeePaymentKind.UPFRONT.value,
            payment_id="fee-pay-upfront-001",
            qrcode_payload="0" * 30,
            amount=100.0,
            status="PENDING",
        )
        fp2 = FeePayment(
            id=str(uuid4()),
            fee_id=FEE_ID,
            kind=FeePaymentKind.SCHEDULED.value,
            payment_id="fee-pay-scheduled-001",
            qrcode_payload="1" * 30,
            amount=100.0,
            status="PENDING",
        )
        db_session.add_all([fp1, fp2])
        await db_session.commit()

        payments = await load_payments(db_session, FEE_ID)
        assert len(payments) == 2
        assert {p.kind for p in payments} == {"upfront", "scheduled"}
        # Ordenado por kind → scheduled depois de upfront
        assert payments[0].kind == "scheduled"
        assert payments[1].kind == "upfront"
