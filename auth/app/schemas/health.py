"""Schema de health check."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Resposta do endpoint de health check."""

    ok: bool
    detail: str | None = None
