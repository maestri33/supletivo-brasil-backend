"""Schemas de lotes de pagamento para o serviço Commissions."""

from datetime import datetime

from pydantic import ConfigDict, Field

from . import APIModel


class PaymentBatchResponse(APIModel):
    """Schema de resposta contendo os dados de um lote de pagamento.

    Atributos:
        id: Identificador único do lote de pagamento.
        week_of: Data de referência da semana do lote.
        total_cents: Valor total do lote em centavos (comissões + bônus).
        bonus_cents: Valor total de bônus inclusos no lote em centavos.
        status: Status atual do lote (ex.: 'pending', 'processing', 'completed', 'failed').
        pix_transaction_id: Identificador da transação PIX associada, se houver.
        created_at: Data/hora de criação do registro.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Identificador único do lote de pagamento.")
    week_of: str = Field(
        description="Data de referência da semana do lote (formato ISO)."
    )
    total_cents: int = Field(
        default=0,
        description="Valor total do lote em centavos (comissões + bônus).",
        ge=0,
    )
    bonus_cents: int = Field(
        default=0,
        description="Valor total de bônus inclusos no lote em centavos.",
        ge=0,
    )
    status: str = Field(description="Status atual do lote de pagamento.")
    pix_transaction_id: str | None = Field(
        default=None,
        description="Identificador da transação PIX associada, se houver.",
    )
    created_at: datetime = Field(
        description="Data/hora de criação do registro."
    )


class PaymentBatchListResponse(APIModel):
    """Schema de resposta para listagem de lotes de pagamento.

    Atributos:
        items: Lista de lotes de pagamento retornados.
        total: Número total de registros disponíveis.
    """

    items: list[PaymentBatchResponse] = Field(
        default_factory=list,
        description="Lista de lotes de pagamento retornados.",
    )
    total: int = Field(
        default=0, description="Número total de registros disponíveis."
    )
