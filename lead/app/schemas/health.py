"""Health check schemas."""

from app.schemas.base import APIModel


class HealthResponse(APIModel):
    status: str
    service: str = "lead"
    db: bool = True
