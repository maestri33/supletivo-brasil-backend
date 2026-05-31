"""Schemas das rotas publicas de autenticacao do promoter.

O promoter nao se auto-registra (e' criado pelo coordinator); por isso ha'
check/login/refresh, mas nao register. Contratos espelham o `auth`/`jwt`.
"""

from uuid import UUID

from pydantic import Field

from app.schemas import APIModel


class CheckRequest(APIModel):
    cpf: str | None = None
    phone: str | None = None
    external_id: UUID | None = None


class CheckResponse(APIModel):
    # COD-32: Resposta uniformizada — nunca diferencia found=true/false.
    # Auth service retorna {"otp_sent": true} ou {"otp_wait": N},
    # nunca expoe external_id nem found.
    otp_sent: bool | None = None
    otp_wait: int | None = None


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
