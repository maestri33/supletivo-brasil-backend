"""Operacoes de banco da Submission: criar, listar, atualizar status apos grading."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFound
from app.models import Submission, SubmissionStatus


async def create(
    session: AsyncSession,
    *,
    external_id: UUID,
    material_id: str,
    answer: str,
) -> Submission:
    sub = Submission(
        external_id=str(external_id),
        material_id=str(material_id),
        answer=answer,
        status=SubmissionStatus.PENDING.value,
    )
    session.add(sub)
    await session.flush()
    return sub


async def get(session: AsyncSession, submission_id: str) -> Submission | None:
    return await session.scalar(select(Submission).where(Submission.id == str(submission_id)))


async def get_or_404(session: AsyncSession, submission_id: str) -> Submission:
    sub = await get(session, submission_id)
    if sub is None:
        raise NotFound("Submissao nao encontrada")
    return sub


async def list_by_user(
    session: AsyncSession,
    external_id: UUID,
    *,
    limit: int = 200,
    offset: int = 0,
) -> list[Submission]:
    stmt = (
        select(Submission)
        .where(Submission.external_id == str(external_id))
        .order_by(Submission.created_at.desc(), Submission.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(await session.scalars(stmt))


async def get_last_for_material(
    session: AsyncSession, external_id: UUID, material_id: str
) -> Submission | None:
    """Ultima submissao deste (user, materia) — usado pelo endpoint de progresso."""
    stmt = (
        select(Submission)
        .where(
            Submission.external_id == str(external_id),
            Submission.material_id == str(material_id),
        )
        .order_by(Submission.created_at.desc(), Submission.id.desc())
        .limit(1)
    )
    return await session.scalar(stmt)


async def count_attempts(session: AsyncSession, external_id: UUID, material_id: str) -> int:
    stmt = select(func.count(Submission.id)).where(
        Submission.external_id == str(external_id),
        Submission.material_id == str(material_id),
    )
    return int(await session.scalar(stmt) or 0)


async def has_pending(session: AsyncSession, external_id: UUID, material_id: str) -> bool:
    """True se ja' existe submissao pendente para evitar disparar IA em duplicata."""
    stmt = select(Submission.id).where(
        Submission.external_id == str(external_id),
        Submission.material_id == str(material_id),
        Submission.status == SubmissionStatus.PENDING.value,
    )
    return (await session.scalar(stmt)) is not None


def apply_grading(sub: Submission, grade: float, justification: str, pass_threshold: float) -> None:
    """Grava nota + justificativa e decide approved/rejected pelo threshold."""
    sub.grade = grade
    sub.justification = justification
    sub.status = (
        SubmissionStatus.APPROVED.value
        if grade >= pass_threshold
        else SubmissionStatus.REJECTED.value
    )


async def approved_material_ids(session: AsyncSession, external_id: UUID) -> set[str]:
    """Conjunto de material_ids aprovados pelo trainee — usado p/ checar conclusao."""
    stmt = select(Submission.material_id).where(
        Submission.external_id == str(external_id),
        Submission.status == SubmissionStatus.APPROVED.value,
    )
    return {str(r) for r in await session.scalars(stmt)}
