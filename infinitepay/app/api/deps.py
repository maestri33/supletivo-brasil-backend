"""Shared FastAPI dependencies for auth and security."""

from __future__ import annotations

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from app.config import get_settings

_x_internal_api_key_header = APIKeyHeader(
    name="X-Internal-Api-Key",
    auto_error=False,
    description="Internal admin key required for sensitive endpoints (health/integration).",
)


async def require_internal_api_key(
    api_key: str | None = Security(_x_internal_api_key_header),
) -> str:
    """Dependency that enforces X-Internal-Api-Key header.

    Returns the validated key on success.
    Raises 401 if the key is missing or does not match.
    Fail-closed: if INTERNAL_API_KEY is not configured in the environment,
    ALL requests are rejected (endpoint is effectively disabled).
    """
    settings = get_settings()

    if not settings.internal_api_key:
        raise HTTPException(
            status_code=503,
            detail="Integration health check is not configured (INTERNAL_API_KEY not set)",
        )

    if not api_key or api_key != settings.internal_api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing X-Internal-Api-Key header",
        )

    return api_key
