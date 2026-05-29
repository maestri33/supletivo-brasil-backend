"""Schemas do fluxo WAITING — aguardando pagamento."""

from app.schemas.base import APIModel


class WaitingGetResponse(APIModel):
    status: str = "waiting"
    message: str = "Aguardando confirmacao de pagamento"
    external_id: str | None = None
