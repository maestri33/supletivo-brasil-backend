"""Schemas do Promoter — criacao (desmilitarizada), leitura e validacao de ref."""

from datetime import datetime
from uuid import UUID

from app.schemas import APIModel


class PromoterCreate(APIModel):
    """Payload da criacao desmilitarizada (chamada pelo coordinator)."""

    external_id: UUID
    hub_external_id: UUID | None = None


class PromoterOut(APIModel):
    external_id: UUID
    status: str
    hub_external_id: UUID | None = None
    ref_url: str | None = None
    created_at: datetime
    updated_at: datetime


class PromoterListResponse(APIModel):
    total: int
    promoters: list[PromoterOut]


class RefValidation(APIModel):
    """Resposta da validacao de `ref` consumida pelo `lead` na captacao."""

    valid: bool
    external_id: UUID | None = None
    hub_external_id: UUID | None = None
    status: str | None = None
