"""Schemas de health check e agregacao de servicos."""

from pydantic import BaseModel


class ServiceHealth(BaseModel):
    """Saude de um servico na agregacao."""

    service: str
    status: str
    db: str | None = None
    detail: str | None = None


class HealthAggregateResponse(BaseModel):
    """Resposta da agregacao de health de todos os servicos."""

    services: list[ServiceHealth]
    all_ok: bool


class HealthOut(BaseModel):
    status: str
    service: str = "staff"
    db: bool = True
