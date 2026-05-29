"""Schemas de leitura do Candidate (rotas desmilitarizadas: listar/filtrar)."""

from datetime import datetime
from uuid import UUID

from app.schemas import APIModel


class CandidateOut(APIModel):
    external_id: UUID
    status: str
    hub_external_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class CandidateListResponse(APIModel):
    total: int
    candidates: list[CandidateOut]
