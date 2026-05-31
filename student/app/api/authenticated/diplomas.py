"""Diploma — coord emite (issue); aluno registra retirada (pickup) -> veterano."""

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.dependencies import require_role, require_student_with_status
from app.models import Student, StudentStatus
from app.schemas import DiplomaPickupRequest, StudentDiplomaRead
from app.services import diploma_service, notifications, student_service

router = APIRouter(prefix="/api/v1/authenticated/students", tags=["diplomas"])


@router.post(
    "/{student_id}/diploma/issue",
    response_model=StudentDiplomaRead,
    status_code=status.HTTP_201_CREATED,
)
async def issue_diploma(
    student_id: UUID,
    background_tasks: BackgroundTasks,
    coordinator_external_id: UUID = require_role("coordinator"),
    session: AsyncSession = Depends(get_session),
) -> StudentDiplomaRead:
    """Coord emite (certificado + historico) — passa para AWAITING_PICKUP."""
    student = await student_service.get_by_id(session, student_id)
    diploma = await diploma_service.issue_diploma(
        session,
        student=student,
        coordinator_external_id=coordinator_external_id,
    )
    await session.commit()
    background_tasks.add_task(
        notifications.notify_status_changed,
        str(student.external_id),
        student.status,
    )
    return StudentDiplomaRead.model_validate(diploma)


@router.post("/me/diploma/pickup", response_model=StudentDiplomaRead)
async def pickup_diploma(
    body: DiplomaPickupRequest,
    background_tasks: BackgroundTasks,
    student: Student = require_student_with_status(StudentStatus.AWAITING_PICKUP),
    session: AsyncSession = Depends(get_session),
) -> StudentDiplomaRead:
    """Aluno registra retirada com foto — vira veterano e dispara comissao do coord."""
    diploma = await diploma_service.pickup_diploma(
        session,
        student=student,
        pickup_photo_external_id=body.pickup_photo_external_id,
    )
    await session.commit()

    background_tasks.add_task(
        diploma_service.trigger_graduation_side_effects,
        student.id,
        student.external_id,
        diploma.issued_by_external_id,
    )
    background_tasks.add_task(
        notifications.notify_status_changed,
        str(student.external_id),
        student.status,
    )
    return StudentDiplomaRead.model_validate(diploma)
