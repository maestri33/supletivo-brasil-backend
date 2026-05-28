"""Schemas de usuario — UserRead, UserCreate."""

from datetime import datetime
from uuid import UUID

from app.schemas import APIModel


class UserCreate(APIModel):
    """Dados para criacao de usuario (via provisionamento interno)."""

    role: str
    cpf: str
    phone: str


class UserRead(APIModel):
    """Representacao publica de um usuario."""

    external_id: UUID
    created_at: datetime
