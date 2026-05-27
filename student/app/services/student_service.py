"""Regras de negocio do aluno — promocao e consulta."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import StudentAlreadyExists, StudentNotFound
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
