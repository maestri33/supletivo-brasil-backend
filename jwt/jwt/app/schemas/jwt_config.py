"""Schemas Pydantic v2 — so' tokens, sem config CRUD."""

from pydantic import BaseModel, Field


class TokenIssueRequest(BaseModel):
    """Body para emitir tokens — external_id + roles, sem claims, sem config_id."""

    external_id: str = Field(..., min_length=1)
    roles: list[str] = Field(..., min_length=1)


class TokenRefreshRequest(BaseModel):
    """Body para renovar tokens."""

    refresh_token: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    """Resposta de emissao/refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
