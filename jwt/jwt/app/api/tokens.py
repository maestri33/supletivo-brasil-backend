"""Endpoints de emissao, refresh e JWKS — zero config, zero banco."""

from fastapi import APIRouter

from app.schemas.jwt_config import TokenIssueRequest, TokenRefreshRequest, TokenResponse
from app.services import token_service

router = APIRouter()


@router.post("/issue", response_model=TokenResponse)
async def issue_token(payload: TokenIssueRequest) -> TokenResponse:
    """Emite access + refresh token. So' external_id + roles."""
    result = await token_service.issue_token(payload.external_id, payload.roles)
    return TokenResponse(**result)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(payload: TokenRefreshRequest) -> TokenResponse:
    """Renova tokens com refresh token."""
    result = await token_service.refresh_token(payload.refresh_token)
    return TokenResponse(**result)


# JWKS — na raiz, sem prefixo /api/v1
jwks_router = APIRouter()


@jwks_router.get("/.well-known/jwks.json")
async def get_jwks() -> dict:
    """Chave publica no formato JWKS (RFC 7517)."""
    return await token_service.get_jwks()
