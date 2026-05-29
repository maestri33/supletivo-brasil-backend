"""Schemas de leitura dos leads do promoter (agregados do servico `lead`).

Passthrough tolerante: o promoter nao e' dono do dominio de lead (CONVENTION §6),
so' expoe uma visao read-only filtrada pelo seu external_id.
"""

from uuid import UUID

from app.schemas import APIModel


class LeadView(APIModel):
    external_id: UUID
    status: str
    created_at: str | None = None
    updated_at: str | None = None


class LeadListResponse(APIModel):
    total: int
    leads: list[LeadView]
