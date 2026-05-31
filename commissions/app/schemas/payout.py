"""Schemas de payout (a solicitacao de pagamento por beneficiario)."""

from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict, Field

from . import APIModel


class PayoutResponse(APIModel):
    """Um payout: 1 pagamento Pix agregado por beneficiario por semana."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="ID do payout.")
    external_reference: str = Field(
        description="Chave de idempotencia ({ord-sexta}_{MM}_{AAAA}_{external_id})."
    )
    recipient_external_id: UUID = Field(description="UUID do beneficiario.")
    recipient_role: str = Field(description="promoter | coordinator.")
    amount_cents: int = Field(description="Valor agregado em centavos.")
    week_of: str = Field(description="Segunda-feira ISO da semana de referencia.")
    payment_batch_id: int | None = Field(
        default=None, description="Lote semanal que originou o payout."
    )
    status: str = Field(
        description="queued | submitted | awaiting_balance | paid | failed | cancelled."
    )
    asaas_id: str | None = Field(default=None, description="UUID da transacao no asaas.")
    asaas_status: str | None = Field(
        default=None, description="Ultimo status recebido do asaas, verbatim."
    )
    last_error: str | None = Field(default=None, description="Ultimo erro registrado.")
    created_at: datetime = Field(description="Criacao.")
    updated_at: datetime = Field(description="Ultima atualizacao.")


class PayoutListResponse(APIModel):
    """Listagem paginada de payouts."""

    items: list[PayoutResponse] = Field(default_factory=list)
    total: int = Field(default=0)
