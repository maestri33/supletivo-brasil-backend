"""Lógica de negócio do hub (polo)."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFound
from app.models.hub import Hub
from app.schemas.hub import HubCreate, HubUpdate


async def create_hub(session: AsyncSession, data: HubCreate) -> Hub:
    """Cria um novo polo (uso interno via staff).

    Não valida endereço/coordenador (external_id puro). Esses serviços
    validam seus próprios IDs quando forem consultados.
    """
    hub = Hub(
        name=data.name,
        brand=data.brand,
        address_external_id=data.address_external_id,
        coordinator_external_id=data.coordinator_external_id,
    )
    session.add(hub)
    await session.flush()
    return hub


async def list_hubs(session: AsyncSession, brand: str | None = None) -> list[Hub]:
    """Lista todos os polos, opcionalmente filtrados por marca."""
    stmt = select(Hub)
    if brand:
        stmt = stmt.where(Hub.brand == brand)
    stmt = stmt.order_by(Hub.name)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_hub_by_id(session: AsyncSession, hub_id: UUID) -> Hub:
    """Busca polo por ID; levanta NotFound se não existir."""
    result = await session.execute(select(Hub).where(Hub.id == hub_id))
    hub = result.scalar_one_or_none()
    if hub is None:
        raise NotFound("Polo não encontrado")
    return hub


async def update_hub(session: AsyncSession, hub_id: UUID, data: HubUpdate) -> Hub:
    """Atualiza parcialmente um polo (uso interno via staff)."""
    hub = await get_hub_by_id(session, hub_id)

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(hub, field, value)

    await session.flush()
    return hub
