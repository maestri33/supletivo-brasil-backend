"""Leitura de polos (desmilitarizado — §5 interna)."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.exceptions import NotFound
from app.models.hub import Hub
from app.schemas import HubRead

router = APIRouter(prefix="/api/v1", tags=["hubs"])


@router.get(
    "/hubs/{external_id}",
    response_model=HubRead,
    summary="Ler polo por external_id (uso interno entre serviços)",
)
async def get_hub_by_external_id(
    external_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> HubRead:
    result = await session.execute(select(Hub).where(Hub.id == external_id))
    hub = result.scalar_one_or_none()
    if hub is None:
        raise NotFound("Polo não encontrado")
    return HubRead.model_validate(hub)
