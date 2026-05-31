"""Schema de health (usado pelo endpoint /health)."""

from pydantic import BaseModel


class HealthOut(BaseModel):
    status: str
    service: str
