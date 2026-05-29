"""Schemas do fluxo COMPLETED."""

from app.schemas.base import APIModel


class CompletedGetResponse(APIModel):
    status: str = "completed"
    message: str = "Matricula concluida com sucesso"
    external_id: str | None = None
