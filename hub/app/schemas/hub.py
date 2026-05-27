"""Schemas Pydantic do hub (saida e entrada da API)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class HubRead(BaseModel):
    """Representacao de leitura do polo."""

    id: UUID
    name: str
    brand: str
    address_external_id: UUID | None
    coordinator_external_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class HubCreate(BaseModel):
    """Payload para criar um polo."""

    name: str = Field(min_length=1, max_length=120)
    brand: str = Field(min_length=1, max_length=40)


class HubUpdate(BaseModel):
    """Payload para editar um polo (todos os campos opcionais)."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    brand: str | None = Field(default=None, min_length=1, max_length=40)


class CoordinatorSet(BaseModel):
    """Payload para definir o coordenador de um polo."""

    coordinator_external_id: UUID
