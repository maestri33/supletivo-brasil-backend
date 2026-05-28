"""Coordinator schemas."""

from datetime import datetime

from app.schemas import APIModel


class CoordinatorCreate(APIModel):
    """Schema para criar um coordenador."""

    external_id: str
    hub_external_id: str


class CoordinatorUpdate(APIModel):
    """Schema para atualizar status do coordenador."""

    status: str


class CoordinatorResponse(APIModel):
    """Schema de resposta com dados completos do coordenador."""

    id: str
    external_id: str
    hub_external_id: str
    status: str
    created_at: datetime
    updated_at: datetime
