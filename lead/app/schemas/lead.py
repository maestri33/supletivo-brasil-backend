"""Schemas de consulta/atualizacao de leads (via demilitarized)."""

from app.schemas.base import APIModel
from pydantic import Field


class LeadOut(APIModel):
    external_id: str
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    status: str | None = None


class LeadPatch(APIModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    email: str | None = None
    status: str | None = None
