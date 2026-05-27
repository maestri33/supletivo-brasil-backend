"""Provas do aluno — aluno agenda; coordenador corrige."""

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.dependencies import require_role, require_student_with_status
from app.models import Student, StudentStatus
from app.schemas import (
    ExamGradeRequest,
    ExamScheduleRequest,
    StudentExamList,
    StudentExamRead,
)
from app.services import exam_service, notifications, student_service

router = APIRouter(prefix="/api/v1/authenticated/students", tags=["exams"])


@router.post(
    "/me/exams",
    response_model=StudentExamRead,
    status_code=status.HTTP_201_CREATED,
)
async def schedule_my_exam(
    body: ExamScheduleRequest,
    background_tasks: BackgroundTasks,
    student: Student = require_student_with_status(StudentStatus.EXAM_RELEASED),
    session: AsyncSession = Depends(get_session),
) -> StudentExamRead:
    exam = await exam_service.schedule_exam(
        session,
        student=student,
        subject=body.subject,
        scheduled_at=body.scheduled_at,
    )
    await session.commit()
    background_tasks.add_task(
        notifications.notify_status_changed,
        str(student.external_id),
        student.status,
    )
    return StudentExamRead.model_validate(exam)


@router.get("/me/exams", response_model=StudentExamList)
async def list_my_exams(
    student: Student = require_student_with_status(
        StudentStatus.EXAM_RELEASED,
        StudentStatus.EXAM_SCHEDULED,
        StudentStatus.EXAM_FAILED,
        StudentStatus.AWAITING_DOCUMENTATION_DISPATCH,
        StudentStatus.AWAITING_DIPLOMA_ISSUANCE,
        StudentStatus.AWAITING_PICKUP,
        StudentStatus.VETERAN,
    ),
    session: AsyncSession = Depends(get_session),
) -> StudentExamList:
    exams = await exam_service.list_exams(session, student=student)
    return StudentExamList(
        items=[StudentExamRead.model_validate(e) for e in exams],
        total=len(exams),
    )


@router.patch("/{student_id}/exams/{exam_id}", response_model=StudentExamRead)
async def grade_exam(
    student_id: UUID,
    exam_id: UUID,
    body: ExamGradeRequest,
    background_tasks: BackgroundTasks,
    coordinator_external_id: UUID = require_role("coordinator"),
    session: AsyncSession = Depends(get_session),
) -> StudentExamRead:
    """Endpoint do dominio student — coordenador autenticado corrige a prova."""
    student = await student_service.get_by_id(session, student_id)
    exam = await exam_service.grade_exam(
        session,
        student=student,
        exam_id=exam_id,
        coordinator_external_id=coordinator_external_id,
        result=body.result,
        notes=body.notes,
    )
    await session.commit()
    background_tasks.add_task(
        notifications.notify_status_changed,
        str(student.external_id),
        student.status,
    )
    return StudentExamRead.model_validate(exam)
