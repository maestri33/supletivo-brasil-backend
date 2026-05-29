"""Endpoints de gerenciamento de hubs — delegados ao servico hub via HTTP.

Todas as rotas sao autenticadas (JWT + role admin/staff). O staff atua como
proxy autenticado: valida o token e repassa a chamada ao hub.
"""

from uuid import UUID

from fastapi import APIRouter, Depends

from app.dependencies import get_current_external_id
from app.integrations.hub import HubClient
from app.schemas import CoordinatorSetPayload, HubCreatePayload

router = APIRouter(tags=["hubs"])


@router.post(
    "/hubs",
    response_model=dict,
    status_code=201,
    summary="Criar polo (delega ao hub)",
)
async def create_hub(
    body: HubCreatePayload,
    _external_id: UUID = Depends(get_current_external_id),
) -> dict:
    """Cria um polo via servico hub. Requer token staff valido."""
    client = HubClient()
    return await client.create_hub(body.name, body.brand)


@router.get(
    "/hubs",
    response_model=list[dict],
    summary="Listar todos os polos (delega ao hub)",
)
async def list_hubs(
    _external_id: UUID = Depends(get_current_external_id),
) -> list[dict]:
    """Lista todos os polos via servico hub."""
    client = HubClient()
    return await client.list_hubs()


@router.get(
    "/hubs/{hub_id}",
    response_model=dict,
    summary="Buscar polo por ID (delega ao hub)",
)
async def get_hub(
    hub_id: UUID,
    _external_id: UUID = Depends(get_current_external_id),
) -> dict:
    """Busca um polo via servico hub."""
    client = HubClient()
    return await client.get_hub(hub_id)


@router.put(
    "/hubs/{hub_id}/coordinator",
    response_model=dict,
    summary="Definir coordenador do polo (delega ao hub)",
)
async def set_coordinator(
    hub_id: UUID,
    body: CoordinatorSetPayload,
    _external_id: UUID = Depends(get_current_external_id),
) -> dict:
    """Define o coordenador de um polo via servico hub."""
    client = HubClient()
    return await client.set_coordinator(hub_id, body.coordinator_external_id)
