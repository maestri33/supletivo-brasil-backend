"""Schemas de gerenciamento de hubs/polos."""

from uuid import UUID

from pydantic import BaseModel, Field


class HubCreatePayload(BaseModel):
    """Payload para criar um polo (delegado ao hub)."""

    name: str = Field(min_length=1, max_length=120)
    brand: str = Field(min_length=1, max_length=40)


class CoordinatorSetPayload(BaseModel):
    """Payload para definir o coordenador de um polo."""

    coordinator_external_id: UUID


class HubReadResponse(BaseModel):
    """Resposta de leitura de polo (espelha o retorno do hub)."""

    id: UUID
    name: str
    brand: str
    address_external_id: UUID | None = None
    coordinator_external_id: UUID | None = None

    model_config = {"from_attributes": True}
