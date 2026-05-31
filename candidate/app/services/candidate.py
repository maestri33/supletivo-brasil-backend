"""Operacoes de banco do Candidate: busca, criacao e transicao de status."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Candidate, CandidateStatus


async def get(session: AsyncSession, external_id: UUID | str) -> Candidate | None:
    return await session.scalar(select(Candidate).where(Candidate.external_id == str(external_id)))


async def get_or_create(
    session: AsyncSession,
    external_id: UUID | str,
    hub_external_id: str | None,
) -> tuple[Candidate, bool]:
    """Retorna (candidate, created). Idempotente por external_id."""
    candidate = await get(session, external_id)
    if candidate is not None:
        return candidate, False
    candidate = Candidate(
        external_id=str(external_id),
        status=CandidateStatus.CAPTURED.value,
        hub_external_id=str(hub_external_id) if hub_external_id else None,
    )
    session.add(candidate)
    await session.flush()
    return candidate, True


def advance(candidate: Candidate, current: CandidateStatus, new: CandidateStatus) -> bool:
    """Avanca o status so' quando esta' exatamente em `current` (idempotente)."""
    if candidate.status == current.value:
        candidate.status = new.value
        return True
    return False


async def list_candidates(
    session: AsyncSession,
    *,
    hub_external_id: str | None = None,
    status: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[Candidate]:
    stmt = select(Candidate)
    if hub_external_id is not None:
        stmt = stmt.where(Candidate.hub_external_id == hub_external_id)
    if status is not None:
        stmt = stmt.where(Candidate.status == status)
    # desempate por id para paginacao estavel (mesma regra do asaas)
    stmt = stmt.order_by(Candidate.created_at.desc(), Candidate.id.desc())
    stmt = stmt.limit(limit).offset(offset)
    return list(await session.scalars(stmt))
