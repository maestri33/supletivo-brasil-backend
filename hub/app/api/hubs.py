"""API de hubs (polos).

Rotas desmilitarizadas (read) + rotas autenticadas (write, staff-only).
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.dependencies import get_current_external_id
from app.exceptions import NotFound
from app.models.hub import Hub
from app.schemas import CoordinatorSet, HubCreate, HubRead, HubUpdate

# ── Desmilitarizado (§5 interna) ────────────────────────────────
public = APIRouter(prefix="/api/v1", tags=["hubs"])


@public.get(
    "/hubs/{external_id}",
    response_model=HubRead,
    summary="Ler polo por external_id (uso interno entre servicos)",
)
async def get_hub_by_external_id(
    external_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> HubRead:
    result = await session.execute(select(Hub).where(Hub.id == external_id))
    hub = result.scalar_one_or_none()
    if hub is None:
        raise NotFound("Polo nao encontrado")
    return HubRead.model_validate(hub)


# ── Autenticado (staff only) ────────────────────────────────────
authenticated = APIRouter(
    prefix="/api/v1", tags=["hubs"], dependencies=[Depends(get_current_external_id)]
)


@authenticated.post(
    "/hubs",
    response_model=HubRead,
    status_code=201,
    summary="Criar polo (staff)",
)
async def create_hub(
    body: HubCreate,
    session: AsyncSession = Depends(get_session),
) -> HubRead:
    hub = Hub(name=body.name, brand=body.brand)
    session.add(hub)
    await session.commit()
    await session.refresh(hub)
    return HubRead.model_validate(hub)


@authenticated.patch(
    "/hubs/{id}",
    response_model=HubRead,
    summary="Editar polo (staff)",
)
async def update_hub(
    id: UUID,
    body: HubUpdate,
    session: AsyncSession = Depends(get_session),
) -> HubRead:
    hub = await session.scalar(select(Hub).where(Hub.id == id))
    if hub is None:
        raise NotFound("Polo nao encontrado")
    if body.name is not None:
        hub.name = body.name
    if body.brand is not None:
        hub.brand = body.brand
    await session.commit()
    await session.refresh(hub)
    return HubRead.model_validate(hub)


@authenticated.put(
    "/hubs/{id}/coordinator",
    response_model=HubRead,
    summary="Definir coordenador do polo (staff)",
)
async def set_coordinator(
    id: UUID,
    body: CoordinatorSet,
    session: AsyncSession = Depends(get_session),
) -> HubRead:
    hub = await session.scalar(select(Hub).where(Hub.id == id))
    if hub is None:
        raise NotFound("Polo nao encontrado")
    hub.coordinator_external_id = body.coordinator_external_id
    await session.commit()
    await session.refresh(hub)
    return HubRead.model_validate(hub)
