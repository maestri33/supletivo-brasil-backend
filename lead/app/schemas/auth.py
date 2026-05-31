"""Schemas de autenticacao publica."""

from app.schemas.base import APIModel
from pydantic import Field


class CheckRequest(APIModel):
    phone: str = Field(..., min_length=10, max_length=16)


class CheckResponse(APIModel):
    exists: bool
    status: str | None = None
    message: str | None = None
    allowed_flows: list[str] | None = None


class LoginRequest(APIModel):
    phone: str = Field(..., min_length=10, max_length=16)


class LoginResponse(APIModel):
    external_id: str
    token: str
    flow: str
    expires_in: int | None = None


class RegisterRequest(APIModel):
    phone: str = Field(..., min_length=10, max_length=16)
    name: str | None = Field(default=None, min_length=2, max_length=120)
    cpf: str | None = Field(default=None, min_length=11, max_length=14)


class RegisterResponse(APIModel):
    external_id: str
    message: str = "Registro iniciado. Complete o registro para continuar."
    flow: str
    token: str | None = None


class RefreshRequest(APIModel):
    refresh_token: str


class RefreshResponse(APIModel):
    token: str
    expires_in: int | None = None
