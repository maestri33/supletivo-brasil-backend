"""Regras de negocio do aluno — promocao, consulta e transicoes de status."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import InvalidStatusTransition, StudentAlreadyExists, StudentNotFound
from app.models import Student, StudentStatus


async def promote(
    session: AsyncSession,
    *,
    external_id: UUID,
    study_platform: dict,
) -> Student:
    """Cria o aluno a partir do external_id da matricula.

    Idempotente: se ja existe aluno para o external_id, levanta
    StudentAlreadyExists (409) em vez de duplicar.
    """
    existing = await session.scalar(select(Student).where(Student.external_id == external_id))
    if existing is not None:
        raise StudentAlreadyExists(f"Aluno ja existe para external_id {external_id}")

    student = Student(
        external_id=external_id,
        study_platform=study_platform,
        status=StudentStatus.AWAITING_DOCUMENTS,
    )
    session.add(student)
    await session.flush()
    await session.refresh(student)
    return student


async def get_by_external_id(session: AsyncSession, external_id: UUID) -> Student:
    """Busca o aluno pelo external_id; 404 se nao houver."""
    student = await session.scalar(select(Student).where(Student.external_id == external_id))
    if student is None:
        raise StudentNotFound(f"Aluno nao encontrado para external_id {external_id}")
    return student


async def get_by_id(session: AsyncSession, student_id: UUID) -> Student:
    """Busca o aluno pelo id interno (usado por endpoints administrativos do coord)."""
    student = await session.scalar(select(Student).where(Student.id == student_id))
    if student is None:
        raise StudentNotFound(f"Aluno nao encontrado para id {student_id}")
    return student


def advance(
    student: Student,
    *,
    allowed_from: tuple[StudentStatus, ...],
    to: StudentStatus,
) -> None:
    """Transita o status do aluno, validando origem.

    Levanta InvalidStatusTransition se o status atual nao esta em allowed_from.
    Modificacao em-memoria — o caller faz commit.
    """
    if student.status not in allowed_from:
        expected = ", ".join(s.value for s in allowed_from)
        raise InvalidStatusTransition(
            f"Transicao invalida: aluno em '{student.status.value}', "
            f"esperado um de [{expected}] para ir para '{to.value}'"
        )
    student.status = to
