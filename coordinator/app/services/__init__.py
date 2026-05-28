"""Services layer — coordinator business logic.

Funcoes de exam, student_document e diploma migraram para o servico `student`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.coordinator import Coordinator, CoordinatorStatus
from app.models.enrollment_fee import EnrollmentFee, FeeStatus
from app.models.training_approval import ApprovalStatus, TrainingApproval
from app.utils.logging import get_logger

logger = get_logger("coordinator.service")


# ---------------------------------------------------------------------------
# Coordinator CRUD
# ---------------------------------------------------------------------------


async def create_coordinator(
    db: AsyncSession,
    *,
    external_id: str,
    hub_external_id: str,
) -> Coordinator:
    coordinator = Coordinator(
        external_id=external_id,
        hub_external_id=hub_external_id,
        status=CoordinatorStatus.active,
    )
    db.add(coordinator)
    await db.flush()
    logger.info("coordinator.created", id=coordinator.id)
    return coordinator


async def get_coordinator(db: AsyncSession, coordinator_id: str) -> Coordinator | None:
    return (
        await db.execute(select(Coordinator).where(Coordinator.id == coordinator_id))
    ).scalar_one_or_none()


async def get_coordinator_by_external_id(db: AsyncSession, external_id: str) -> Coordinator | None:
    return (
        await db.execute(select(Coordinator).where(Coordinator.external_id == external_id))
    ).scalar_one_or_none()


async def list_coordinators(
    db: AsyncSession,
    *,
    hub_external_id: str | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[Coordinator], int]:
    q = select(Coordinator)
    if hub_external_id:
        q = q.where(Coordinator.hub_external_id == hub_external_id)
    if status:
        q = q.where(Coordinator.status == status)
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    items = (
        (await db.execute(q.order_by(Coordinator.created_at.desc()).offset(offset).limit(limit)))
        .scalars()
        .all()
    )
    return list(items), total


async def update_coordinator_status(
    db: AsyncSession,
    coordinator_id: str,
    status: CoordinatorStatus,
) -> Coordinator | None:
    c = await get_coordinator(db, coordinator_id)
    if not c:
        return None
    c.status = status
    await db.flush()
    logger.info("coordinator.updated", id=coordinator_id, status=status.value)
    return c


# ---------------------------------------------------------------------------
# Training Approval
# ---------------------------------------------------------------------------


async def create_training_approval(
    db: AsyncSession,
    *,
    coordinator_id: str,
    candidate_external_id: str,
    training_external_id: str,
) -> TrainingApproval:
    ta = TrainingApproval(
        coordinator_id=coordinator_id,
        candidate_external_id=candidate_external_id,
        training_external_id=training_external_id,
        status=ApprovalStatus.pending,
    )
    db.add(ta)
    await db.flush()
    logger.info("training_approval.created", id=ta.id)
    return ta


async def review_training_approval(
    db: AsyncSession,
    approval_id: str,
    *,
    approved: bool,
    reason: str | None = None,
) -> TrainingApproval | None:
    ta = (
        await db.execute(select(TrainingApproval).where(TrainingApproval.id == approval_id))
    ).scalar_one_or_none()
    if not ta:
        return None
    ta.status = ApprovalStatus.approved if approved else ApprovalStatus.rejected
    if reason:
        ta.reason = reason
    await db.flush()
    logger.info("training_approval.reviewed", id=approval_id, status=ta.status.value)
    return ta


async def list_training_approvals(
    db: AsyncSession,
    *,
    coordinator_id: str | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[TrainingApproval], int]:
    q = select(TrainingApproval)
    if coordinator_id:
        q = q.where(TrainingApproval.coordinator_id == coordinator_id)
    if status:
        q = q.where(TrainingApproval.status == status)
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    items = (
        (
            await db.execute(
                q.order_by(TrainingApproval.created_at.desc()).offset(offset).limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return list(items), total


# ---------------------------------------------------------------------------
# Enrollment Fee
# ---------------------------------------------------------------------------


async def create_enrollment_fee(
    db: AsyncSession,
    *,
    coordinator_id: str,
    student_external_id: str,
    description: str,
    amount: Decimal,
    due_date: str | None = None,
) -> EnrollmentFee:
    fee = EnrollmentFee(
        coordinator_id=coordinator_id,
        student_external_id=student_external_id,
        description=description,
        amount=amount,
        due_date=date.fromisoformat(due_date) if due_date else None,
        status=FeeStatus.pending,
    )
    db.add(fee)
    await db.flush()
    logger.info("enrollment_fee.created", id=fee.id)
    return fee


async def list_enrollment_fees(
    db: AsyncSession,
    *,
    coordinator_id: str | None = None,
    student_external_id: str | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[EnrollmentFee], int]:
    q = select(EnrollmentFee)
    if coordinator_id:
        q = q.where(EnrollmentFee.coordinator_id == coordinator_id)
    if student_external_id:
        q = q.where(EnrollmentFee.student_external_id == student_external_id)
    if status:
        q = q.where(EnrollmentFee.status == status)
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    items = (
        (await db.execute(q.order_by(EnrollmentFee.created_at.desc()).offset(offset).limit(limit)))
        .scalars()
        .all()
    )
    return list(items), total


async def pay_enrollment_fee(
    db: AsyncSession,
    fee_id: str,
    payment_external_id: str,
) -> EnrollmentFee | None:
    fee = (
        await db.execute(select(EnrollmentFee).where(EnrollmentFee.id == fee_id))
    ).scalar_one_or_none()
    if not fee:
        return None
    fee.status = FeeStatus.paid
    fee.payment_external_id = payment_external_id
    await db.flush()
    logger.info("enrollment_fee.paid", id=fee_id)
    return fee
