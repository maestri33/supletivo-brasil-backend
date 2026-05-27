"""Schemas de comissões para o serviço Commissions."""

from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict, Field

from . import APIModel


class CommissionCreate(APIModel):
    """Schema para criação de uma nova comissão.

    Atributos:
        recipient_external_id: Identificador externo do receptor (promotor).
        recipient_role: Função do receptor (ex.: 'promoter', 'affiliate').
        source_type: Tipo de entidade que originou a comissão (ex.: 'lead', 'sale').
        source_external_id: Identificador externo da entidade de origem.
        amount_cents: Valor da comissão em centavos.
    """

    recipient_external_id: str = Field(
        ..., description="Identificador externo do receptor (promotor)."
    )
    recipient_role: str = Field(..., description="Função do receptor.")
    source_type: str = Field(
        ..., description="Tipo de entidade que originou a comissão."
    )
    source_external_id: str = Field(
        ..., description="Identificador externo da entidade de origem."
    )
    amount_cents: int = Field(
        ..., description="Valor da comissão em centavos.", ge=1
    )


class CommissionResponse(APIModel):
    """Schema de resposta contendo os dados de uma comissão.

    Atributos:
        id: Identificador único da comissão.
        recipient_external_id: Identificador externo do receptor.
        recipient_role: Função do receptor.
        source_type: Tipo de entidade de origem.
        source_external_id: Identificador externo da entidade de origem.
        amount_cents: Valor da comissão em centavos.
        status: Status atual da comissão (ex.: 'pending', 'paid', 'cancelled').
        payment_batch_id: Identificador do lote de pagamento associado, se houver.
        created_at: Data/hora de criação do registro.
        updated_at: Data/hora da última atualização.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Identificador único da comissão.")
    recipient_external_id: str | UUID = Field(
        description="Identificador externo do receptor."
    )
    recipient_role: str = Field(description="Função do receptor.")
    source_type: str = Field(description="Tipo de entidade de origem.")
    source_external_id: str | UUID = Field(
        description="Identificador externo da entidade de origem."
    )
    amount_cents: int = Field(
        description="Valor da comissão em centavos.", ge=1
    )
    status: str = Field(description="Status atual da comissão.")
    payment_batch_id: int | None = Field(
        default=None,
        description="Identificador do lote de pagamento associado, se houver.",
    )
    created_at: datetime = Field(description="Data/hora de criação do registro.")
    updated_at: datetime = Field(description="Data/hora da última atualização.")


class CommissionListResponse(APIModel):
    """Schema de resposta para listagem de comissões.

    Atributos:
        items: Lista de comissões retornadas.
        total: Número total de registros disponíveis.
    """

    items: list[CommissionResponse] = Field(
        default_factory=list, description="Lista de comissões retornadas."
    )
    total: int = Field(
        default=0, description="Número total de registros disponíveis."
    )
