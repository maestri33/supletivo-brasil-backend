"""Health check response model."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Response model for health/readiness endpoints."""

    ok: bool
    detail: str | None = None
