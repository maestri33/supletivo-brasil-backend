"""Prova do aluno — agendamento (aluno) e correcao (coordenador)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ExamAlreadyCorrected, ExamNotFound
from app.models import ExamResult, Student, StudentExam, StudentStatus
from app.services import student_service


async def schedule_exam(
    session: AsyncSession,
    *,
    student: Student,
    subject: str,
    scheduled_at: datetime,
) -> StudentExam:
    """Aluno agenda a proxima tentativa (EXAM_RELEASED -> EXAM_SCHEDULED)."""
    student_service.advance(
        student,
        allowed_from=(StudentStatus.EXAM_RELEASED,),
        to=StudentStatus.EXAM_SCHEDULED,
    )
    last_attempt = (
        await session.scalar(
            select(func.coalesce(func.max(StudentExam.attempt_number), 0)).where(
                StudentExam.student_id == student.id
            )
        )
    ) or 0
    exam = StudentExam(
        student_id=student.id,
        subject=subject,
        scheduled_at=scheduled_at,
        attempt_number=last_attempt + 1,
    )
    session.add(exam)
    await session.flush()
    await session.refresh(exam)
    return exam


async def grade_exam(
    session: AsyncSession,
    *,
    student: Student,
    exam_id: UUID,
    coordinator_external_id: UUID,
    result: ExamResult,
    notes: str | None,
) -> StudentExam:
    """Coordenador lanca o resultado. Reprovacao reabre p/ refazer (EXAM_FAILED ->
    EXAM_RELEASED, contagem de tentativa incrementa no proximo agendamento).
    """
    exam = await session.scalar(
        select(StudentExam).where(
            StudentExam.id == exam_id,
            StudentExam.student_id == student.id,
        )
    )
    if exam is None:
        raise ExamNotFound(f"Prova {exam_id} nao encontrada para este aluno")
    if exam.result is not None:
        raise ExamAlreadyCorrected(f"Prova {exam_id} ja foi corrigida")

    exam.result = result.value
    exam.notes = notes
    exam.corrected_by_external_id = coordinator_external_id
    exam.corrected_at = datetime.now(UTC)

    if result is ExamResult.PASSED:
        student_service.advance(
            student,
            allowed_from=(StudentStatus.EXAM_SCHEDULED,),
            to=StudentStatus.AWAITING_DOCUMENTATION_DISPATCH,
        )
    else:
        # Reprovou — volta direto pra EXAM_RELEASED para permitir reagendar.
        student_service.advance(
            student,
            allowed_from=(StudentStatus.EXAM_SCHEDULED,),
            to=StudentStatus.EXAM_RELEASED,
        )
    await session.flush()
    await session.refresh(exam)
    return exam


async def list_exams(session: AsyncSession, *, student: Student) -> list[StudentExam]:
    res = await session.scalars(
        select(StudentExam)
        .where(StudentExam.student_id == student.id)
        .order_by(desc(StudentExam.attempt_number))
    )
    return list(res.all())
