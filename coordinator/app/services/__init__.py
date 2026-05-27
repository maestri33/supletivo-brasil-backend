"""Services layer — coordinator business logic."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.coordinator import Coordinator, CoordinatorStatus
from app.models.diploma import Diploma, DiplomaStatus
from app.models.enrollment_fee import EnrollmentFee, FeeStatus
from app.models.exam import Exam, ExamStatus
from app.models.student_document import StudentDocument
from app.models.training_approval import TrainingApproval, ApprovalStatus
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
        await db.execute(q.order_by(Coordinator.created_at.desc()).offset(offset).limit(limit))
    ).scalars().all()
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

    # Promote candidate to promoter when training is approved
    if approved and ta.status == ApprovalStatus.approved:
        try:
            from app.integrations import promote_to_promoter

            await promote_to_promoter(external_id=str(ta.candidate_external_id))
        except Exception:
            logger.warning(
                "training_approval.promote_error",
                approval_id=approval_id,
                candidate_external_id=str(ta.candidate_external_id),
                exc_info=True,
            )

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
        await db.execute(q.order_by(TrainingApproval.created_at.desc()).offset(offset).limit(limit))
    ).scalars().all()
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
        await db.execute(q.order_by(EnrollmentFee.created_at.desc()).offset(offset).limit(limit))
    ).scalars().all()
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


# ---------------------------------------------------------------------------
# Exam
# ---------------------------------------------------------------------------


async def create_exam(
    db: AsyncSession,
    *,
    coordinator_id: str,
    student_external_id: str,
    training_external_id: str,
    max_score: int = 100,
) -> Exam:
    exam = Exam(
        coordinator_id=coordinator_id,
        student_external_id=student_external_id,
        training_external_id=training_external_id,
        status=ExamStatus.created,
        max_score=max_score,
    )
    db.add(exam)
    await db.flush()
    logger.info("exam.created", id=exam.id)
    return exam


async def submit_exam(
    db: AsyncSession,
    exam_id: str,
) -> Exam | None:
    exam = (await db.execute(select(Exam).where(Exam.id == exam_id))).scalar_one_or_none()
    if not exam:
        return None
    exam.status = ExamStatus.submitted
    await db.flush()
    return exam


async def grade_exam(
    db: AsyncSession,
    exam_id: str,
    *,
    score: int,
    notes: str | None = None,
    ai_correction: str | None = None,
) -> Exam | None:
    exam = (await db.execute(select(Exam).where(Exam.id == exam_id))).scalar_one_or_none()
    if not exam:
        return None
    exam.score = score
    exam.status = ExamStatus.graded
    if notes:
        exam.result_notes = notes
    if ai_correction:
        exam.ai_correction = ai_correction
    await db.flush()
    logger.info("exam.graded", id=exam_id, score=score)
    return exam


async def list_exams(
    db: AsyncSession,
    *,
    coordinator_id: str | None = None,
    student_external_id: str | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[Exam], int]:
    q = select(Exam)
    if coordinator_id:
        q = q.where(Exam.coordinator_id == coordinator_id)
    if student_external_id:
        q = q.where(Exam.student_external_id == student_external_id)
    if status:
        q = q.where(Exam.status == status)
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    items = (
        await db.execute(q.order_by(Exam.created_at.desc()).offset(offset).limit(limit))
    ).scalars().all()
    return list(items), total


# ---------------------------------------------------------------------------
# Student Document
# ---------------------------------------------------------------------------


async def create_student_document(
    db: AsyncSession,
    *,
    student_external_id: str,
    coordinator_external_id: str,
    document_type: str,
    description: str,
    file_path: str | None = None,
) -> StudentDocument:
    doc = StudentDocument(
        student_external_id=student_external_id,
        coordinator_external_id=coordinator_external_id,
        document_type=document_type,
        description=description,
        file_path=file_path,
    )
    db.add(doc)
    await db.flush()
    logger.info("student_document.created", id=doc.id)
    return doc


async def submit_document_to_institution(
    db: AsyncSession,
    document_id: str,
) -> StudentDocument | None:
    from datetime import UTC, datetime

    doc = (
        await db.execute(select(StudentDocument).where(StudentDocument.id == document_id))
    ).scalar_one_or_none()
    if not doc:
        return None
    doc.submitted_to_institution = True
    doc.submitted_at = datetime.now(UTC)
    await db.flush()
    logger.info("student_document.submitted", id=document_id)
    return doc


async def list_student_documents(
    db: AsyncSession,
    *,
    student_external_id: str | None = None,
    coordinator_external_id: str | None = None,
    document_type: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[StudentDocument], int]:
    q = select(StudentDocument)
    if student_external_id:
        q = q.where(StudentDocument.student_external_id == student_external_id)
    if coordinator_external_id:
        q = q.where(StudentDocument.coordinator_external_id == coordinator_external_id)
    if document_type:
        q = q.where(StudentDocument.document_type == document_type)
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    items = (
        await db.execute(q.order_by(StudentDocument.created_at.desc()).offset(offset).limit(limit))
    ).scalars().all()
    return list(items), total


# ---------------------------------------------------------------------------
# Diploma
# ---------------------------------------------------------------------------


async def create_diploma(
    db: AsyncSession,
    *,
    student_external_id: str,
    coordinator_external_id: str,
) -> Diploma:
    diploma = Diploma(
        student_external_id=student_external_id,
        coordinator_external_id=coordinator_external_id,
        status=DiplomaStatus.PENDING.value,
    )
    db.add(diploma)
    await db.flush()
    logger.info("diploma.created", id=diploma.id)
    return diploma


async def graduate_student(
    db: AsyncSession,
    diploma_id: str,
    *,
    diploma_photo_path: str,
    history_path: str | None = None,
    notes: str | None = None,
) -> Diploma | None:
    from datetime import UTC, datetime

    diploma = (
        await db.execute(select(Diploma).where(Diploma.id == diploma_id))
    ).scalar_one_or_none()
    if not diploma:
        return None
    diploma.status = DiplomaStatus.GRADUATED.value
    diploma.diploma_photo_path = diploma_photo_path
    if history_path:
        diploma.history_path = history_path
    if notes:
        diploma.notes = notes
    diploma.graduated_at = datetime.now(UTC)
    await db.flush()

    # Trigger coordinator commission asynchronously (fire-and-forget)
    if not diploma.commission_triggered:
        try:
            from app.integrations import trigger_coordinator_commission

            result = await trigger_coordinator_commission(
                coordinator_external_id=str(diploma.coordinator_external_id),
                diploma_id=diploma.id,
            )
            if result is not None:
                diploma.commission_triggered = True
                await db.flush()
        except Exception:
            logger.warning("commission.trigger_error", diploma_id=diploma_id, exc_info=True)

    logger.info("student.graduated", id=diploma_id)
    return diploma


async def list_diplomas(
    db: AsyncSession,
    *,
    student_external_id: str | None = None,
    coordinator_external_id: str | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[Diploma], int]:
    q = select(Diploma)
    if student_external_id:
        q = q.where(Diploma.student_external_id == student_external_id)
    if coordinator_external_id:
        q = q.where(Diploma.coordinator_external_id == coordinator_external_id)
    if status:
        q = q.where(Diploma.status == status)
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    items = (
        await db.execute(q.order_by(Diploma.created_at.desc()).offset(offset).limit(limit))
    ).scalars().all()
    return list(items), total
