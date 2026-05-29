"""Health check response model."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    ok: bool
    detail: str | None = None
