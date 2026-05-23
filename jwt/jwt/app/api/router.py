"""Router agregador — health, tokens e JWKS."""

from fastapi import APIRouter

from app.api import health, tokens

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(tokens.router, prefix="/api/v1/tokens", tags=["tokens"])
api_router.include_router(tokens.jwks_router, tags=["jwks"])
