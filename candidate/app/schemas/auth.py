"""Schemas das rotas publicas de autenticacao (check/register/login/refresh)."""

from uuid import UUID

from pydantic import Field

from app.schemas import APIModel


class CheckRequest(APIModel):
    cpf: str | None = None
    phone: str | None = None
    external_id: UUID | None = None


class CheckResponse(APIModel):
    found: bool
    external_id: UUID | None = None
    valid: bool | None = None
    whatsapp_valid: bool | None = None
    otp_wait: int | None = None


class RegisterRequest(APIModel):
    phone: str = Field(..., min_length=8, max_length=20)
    cpf: str = Field(..., min_length=11, max_length=14)
    hub_external_id: UUID | None = None


class RegisterResponse(APIModel):
    external_id: UUID
    message: str


class LoginRequest(APIModel):
    external_id: UUID
    otp: str = Field(..., min_length=4, max_length=10)


class LoginResponse(APIModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    status: str


class RefreshRequest(APIModel):
    refresh_token: str


class RefreshResponse(APIModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
