"""Schemas de pagamento Pix (payment)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PaymentResponse(BaseModel):
    """Pagamento Pix criado ou consultado."""

    payment_id: str = Field(
        ..., description="ID idempotente do pagamento (gerado ou fornecido pelo cliente)"
    )
    kind: str = Field(..., description='"pixkey" | "qrcode"')
    external_id: str | None = Field(default=None, description="external_id da pixkey (kind=pixkey)")
    qrcode_payload: str | None = Field(
        default=None, description="BR Code copia-e-cola (kind=qrcode)"
    )
    amount: float = Field(..., description="Valor em BRL")
    description: str | None = Field(default=None, description="Descricao enviada ao Asaas")
    scheduled_for: str | None = Field(
        default=None,
        description="Datetime ISO 8601 UTC do disparo agendado. Null para pagamentos imediatos.",
    )
    status: str = Field(
        ...,
        description=(
            "SCHEDULED \u2192 QUEUED \u2192 SUBMITTING \u2192 SUBMITTED \u2192 "
            "PAID | FAILED | CANCELLED | AWAITING_BALANCE"
        ),
    )
    asaas_id: str | None = Field(
        default=None, description="UUID da transferencia/transacao no Asaas"
    )
    last_error: str | None = Field(
        default=None, description="Ultimo erro registrado (ex: insufficient_balance)"
    )
    created_at: str | None = Field(default=None, description="Timestamp ISO 8601 de criacao")
    updated_at: str | None = Field(
        default=None, description="Timestamp ISO 8601 da ultima atualizacao"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "payment_id": "diandra_salario_202604",
                "kind": "pixkey",
                "external_id": "diandra_celular",
                "qrcode_payload": None,
                "amount": 0.03,
                "description": "Pagamento salario abril/2026",
                "scheduled_for": None,
                "status": "PAID",
                "asaas_id": "bc46e593-0a72-4495-a2f8-b4ad499791c0",
                "last_error": None,
                "created_at": "2026-04-24T17:35:24",
                "updated_at": "2026-04-24T17:35:36",
            }
        }
    )


class QRCodeAnalyzeResponse(BaseModel):
    """Analise TLV de um BR Code PIX sem efetuar pagamento."""

    valid_tlv: bool = Field(..., description="True se o payload foi parseado como TLV valido")
    kind: str = Field(..., description='"static" ou "dynamic"')
    point_of_initiation_method: str | None = Field(
        default=None, description="Tag 01: 11=estatico reutilizavel, 12=uso unico"
    )
    amount: float | None = Field(
        default=None, description="Valor fixo (tag 54) ou null se variavel"
    )
    allows_amount_edit: bool = Field(
        ..., description="True quando o QR nao tem valor fixo e aceita amount customizado"
    )
    can_schedule: bool = Field(
        ..., description="True para QR estatico; False para QR dinamico (nao pode agendar)"
    )
    pix_key: str | None = Field(default=None, description="Chave Pix embutida (apenas QR estatico)")
    dynamic_url: str | None = Field(
        default=None, description="URL de payload dinamico (apenas QR dinamico)"
    )
    merchant_name: str | None = Field(default=None, description="Nome do recebedor (tag 59)")
    merchant_city: str | None = Field(default=None, description="Cidade do recebedor (tag 60)")
    reference: str | None = Field(
        default=None, description="Referencia adicional (tag 62, subtag 05)"
    )
    has_crc: bool = Field(..., description="True se o CRC16 (tag 63) esta presente no payload")
    warnings: list[str] = Field(
        default_factory=list,
        description="Avisos: amount_not_fixed, dynamic_qrcode_may_expire, etc.",
    )
    raw_fields: dict[str, str] = Field(
        default_factory=dict, description="Todos os campos TLV raiz extraidos (tag -> valor)"
    )
    merchant_account_fields: dict[str, str] = Field(
        default_factory=dict, description="Subtags da Merchant Account Information (tag 26)"
    )
    additional_data_fields: dict[str, str] = Field(
        default_factory=dict, description="Subtags de Additional Data Field Template (tag 62)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "valid_tlv": True,
                "kind": "static",
                "point_of_initiation_method": "11",
                "amount": 0.03,
                "allows_amount_edit": False,
                "can_schedule": True,
                "pix_key": "+554****1770",
                "dynamic_url": None,
                "merchant_name": "Diandra S",
                "merchant_city": "GUARAPUAVA",
                "reference": None,
                "has_crc": True,
                "warnings": [],
                "raw_fields": {
                    "00": "01",
                    "01": "11",
                    "26": "...",
                    "52": "0000",
                    "53": "986",
                    "54": "0.03",
                    "58": "BR",
                    "59": "Diandra S",
                    "60": "GUARAPUAVA",
                    "63": "ABCD",
                },
                "merchant_account_fields": {"00": "br.gov.bcb.pix", "01": "+554****1770"},
                "additional_data_fields": {},
            }
        }
    )
