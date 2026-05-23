"""Schemas Pydantic do agregado enrollment_event (in/out da API)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class WebhookPayload(BaseModel):
    """Corpo esperado do webhook do lead em `lead.completed`."""

    promoter_external_id: UUID | None = None
    event: str = "lead.completed"


class EnrollmentEventRead(BaseModel):
    """Representação de leitura de um evento (audit)."""

    id: int
    external_id: UUID
    event: str
    promoter_external_id: UUID | None
    payload: dict[str, Any]
    received_at: datetime
    processed_at: datetime | None

    model_config = {"from_attributes": True}
