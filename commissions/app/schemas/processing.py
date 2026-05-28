"""Schemas de processamento de comissões para o serviço Commissions."""

from datetime import datetime

from pydantic import Field

from . import APIModel


class TriggerProcessingRequest(APIModel):
    """Schema para solicitar o processamento manual de comissões.

    Atributos:
        week_of: Data de referência da semana a ser processada (formato ISO, ex.: '2026-05-25').
        force_reprocess: Se True, reprocessa comissões já liquidadas na semana.
    """

    week_of: str = Field(
        ...,
        description="Data de referência da semana a ser processada (formato ISO).",
    )
    force_reprocess: bool = Field(
        default=False,
        description="Se True, reprocessa comissões já liquidadas na semana.",
    )


class TriggerProcessingResponse(APIModel):
    """Schema de resposta para a solicitação de processamento.

    Atributos:
        success: Indica se o processamento foi iniciado com sucesso.
        payment_batch_id: Identificador do lote de pagamento gerado, se houver.
        message: Mensagem descritiva sobre o resultado da operação.
        processed_at: Data/hora em que o processamento foi acionado.
    """

    success: bool = Field(
        default=True,
        description="Indica se o processamento foi iniciado com sucesso.",
    )
    payment_batch_id: int | None = Field(
        default=None,
        description="Identificador do lote de pagamento gerado, se houver.",
    )
    message: str = Field(..., description="Mensagem descritiva sobre o resultado da operação.")
    processed_at: datetime = Field(
        default_factory=datetime.now,
        description="Data/hora em que o processamento foi acionado.",
    )
