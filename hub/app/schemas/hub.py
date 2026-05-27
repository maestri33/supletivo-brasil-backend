"""Schemas Pydantic do hub (saida e entrada da API)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

# Marcas conhecidas (enum fixo — adicionar aqui para expandir).
VALID_BRANDS = frozenset({"estacio", "wyden"})


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

    @field_validator("brand")
    @classmethod
    def brand_must_be_valid(cls, v: str) -> str:
        if v.lower() not in VALID_BRANDS:
            raise ValueError(f"Marca invalida. Aceitas: {', '.join(sorted(VALID_BRANDS))}")
        return v.lower()


class HubUpdate(BaseModel):
    """Payload para editar um polo (todos os campos opcionais)."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    brand: str | None = Field(default=None, min_length=1, max_length=40)

    @field_validator("brand")
    @classmethod
    def brand_must_be_valid_if_set(cls, v: str | None) -> str | None:
        if v is not None and v.lower() not in VALID_BRANDS:
            raise ValueError(f"Marca invalida. Aceitas: {', '.join(sorted(VALID_BRANDS))}")
        return v.lower() if v is not None else None


class CoordinatorSet(BaseModel):
    """Payload para definir o coordenador de um polo."""

    coordinator_external_id: UUID
