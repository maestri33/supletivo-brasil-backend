"""Operacoes do Promoter: busca, criacao (com promocao de papel) e listagem.

Criacao: disparada pelo `coordinator` (rota desmilitarizada) apos a entrevista
que aprova o candidato. Ao criar o registro pela primeira vez, promovemos o papel
`candidate -> promoter` no servico `roles` (mesma escolha do candidate na
conclusao do funil). A promocao e' bloqueante: se o `roles` falhar, a criacao
nao e' efetivada e o coordinator pode repetir (idempotente por external_id).
"""

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.integrations.roles import RolesClient
from app.models import Promoter, PromoterStatus
from app.utils.logging import get_logger

settings = get_settings()
logger = get_logger("promoter.service")


async def get(session: AsyncSession, external_id) -> Promoter | None:
    return await session.scalar(select(Promoter).where(Promoter.external_id == str(external_id)))


async def get_or_create(
    session: AsyncSession,
    external_id,
    hub_external_id: str | None,
) -> tuple[Promoter, bool]:
    """Retorna (promoter, created). Idempotente por external_id."""
    promoter = await get(session, external_id)
    if promoter is not None:
        return promoter, False
    promoter = Promoter(
        external_id=str(external_id),
        status=PromoterStatus.ACTIVE.value,
        hub_external_id=str(hub_external_id) if hub_external_id else None,
    )
    session.add(promoter)
    await session.flush()
    return promoter, True


async def create_promoter(
    session: AsyncSession,
    external_id,
    hub_external_id: str | None,
) -> tuple[Promoter, bool]:
    """Cria o promoter e, se for novo, promove o papel candidate -> promoter.

    Nao faz commit — quem chama (a rota) commita. Se a promocao de papel falhar,
    a excecao sobe e a sessao nao e' commitada (rollback no get_session).
    """
    promoter, created = await get_or_create(session, external_id, hub_external_id)
    if created:
        async with httpx.AsyncClient(
            base_url=settings.roles_base_url, timeout=settings.http_timeout
        ) as http:
            await RolesClient(http).promote(str(external_id), "promoter")
    return promoter, created


async def list_promoters(
    session: AsyncSession,
    *,
    hub_external_id: str | None = None,
    status: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[Promoter]:
    stmt = select(Promoter)
    if hub_external_id is not None:
        stmt = stmt.where(Promoter.hub_external_id == hub_external_id)
    if status is not None:
        stmt = stmt.where(Promoter.status == status)
    # desempate por id para paginacao estavel (mesma regra do candidate/asaas)
    stmt = stmt.order_by(Promoter.created_at.desc(), Promoter.id.desc())
    stmt = stmt.limit(limit).offset(offset)
    return list(await session.scalars(stmt))


async def validate_ref(session: AsyncSession, ref) -> Promoter | None:
    """Resolve o `ref` (== external_id) para um promoter ATIVO, ou None.

    Suspenso ou inexistente => None (ref invalido para captacao).
    """
    promoter = await get(session, ref)
    if promoter is None or promoter.status != PromoterStatus.ACTIVE.value:
        return None
    return promoter
