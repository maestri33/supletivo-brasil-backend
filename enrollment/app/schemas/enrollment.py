"""Schemas Pydantic do agregado enrollment (saída da API)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class EnrollmentRead(BaseModel):
    """Representação de leitura do agregado de matrícula."""

    id: UUID
    external_id: UUID
    status: str
    promoter_external_id: UUID | None
    hub_external_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
