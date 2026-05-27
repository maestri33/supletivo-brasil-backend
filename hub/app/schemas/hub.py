"""Schemas Pydantic do hub (saída da API)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class HubRead(BaseModel):
    """Representação de leitura do polo."""

    id: UUID
    name: str
    brand: str
    address_external_id: UUID | None
    coordinator_external_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
