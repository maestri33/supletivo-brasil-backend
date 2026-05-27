"""Schemas de cobranca PIX (charge)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CustomerInline(BaseModel):
    """Dados do pagador para criar customer no Asaas quando external_id e novo."""

    name: str = Field(..., min_length=1, description="Nome do pagador")
    cpf_cnpj: str = Field(..., description="CPF (11 digitos) ou CNPJ (14 digitos), so digitos")
    email: str | None = Field(default=None, description="Email do pagador")
    mobile_phone: str | None = Field(
        default=None,
        description="Telefone do pagador. Formato preferido +55DDDXXXXXXXXX.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Joao Pagador",
                "cpf_cnpj": "12345678901",
                "email": "joao@example.com",
                "mobile_phone": "+554****9999",
            }
        }
    )


class ChargeCreateRequest(BaseModel):
    external_id: str = Field(
        ..., min_length=1,
        description=(
            "Identificador do pagador (cliente). Find-or-create: se nao existir customer "
            "com esse external_id, payer e obrigatorio para cria-lo."
        ),
    )
    amount: float = Field(..., gt=0, description="Valor em BRL")
    description: str | None = Field(default=None, description="Descricao enviada ao Asaas")
    due_date: str | None = Field(
        default=None,
        description=(
            "YYYY-MM-DD. Quando a cobranca vence. "
            "Default = hoje + ASAAS_APP_CHARGE_DEFAULT_DUE_DAYS dias."
        ),
    )
    payment_id: str | None = Field(
        default=None, description="ID idempotente opcional fornecido pelo cliente"
    )
    payer: CustomerInline | None = Field(
        default=None,
        description=(
            "Dados do pagador. Obrigatorio se external_id ainda nao tem customer registrado. "
            "Ignorado nas chamadas subsequentes (use endpoint /api/v1/customer para atualizar)."
        ),
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "external_id": "aluno_42",
                "amount": 250.00,
                "description": "Mensalidade junho/2026",
                "due_date": "2026-06-05",
                "payer": {
                    "name": "Maria Aluna",
                    "cpf_cnpj": "07426367980",
                    "email": "maria@example.com",
                },
            }
        }
    )


class ChargePixData(BaseModel):
    payload: str = Field(..., description="BR Code copia-e-cola (Pix)")
    encoded_image: str = Field(..., description="PNG base64 do QR Code")
    expiration_date: str | None = Field(
        default=None, description="ISO 8601 do vencimento do QR Code"
    )


class ChargeResponse(BaseModel):
    """Cobranca PIX criada ou consultada."""

    payment_id: str = Field(..., description="ID local (pay_...)")
    external_id: str = Field(..., description="external_id do customer (pagador)")
    amount: float = Field(..., description="Valor em BRL")
    description: str | None = Field(default=None)
    due_date: str | None = Field(default=None, description="YYYY-MM-DD")
    status: str = Field(..., description="PENDING | PAID | EXPIRED | CANCELLED | REFUNDED")
    asaas_id: str | None = Field(default=None, description="ID da cobranca no Asaas")
    pix: ChargePixData | None = Field(
        default=None, description="BR Code + QR Code (null se ainda nao buscado)"
    )
    last_error: str | None = Field(default=None)
    created_at: str | None = Field(default=None)
    updated_at: str | None = Field(default=None)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "payment_id": "pay_a1b2c3d4e5f6a7b8",
                "external_id": "aluno_42",
                "amount": 250.00,
                "description": "Mensalidade junho/2026",
                "due_date": "2026-06-05",
                "status": "PENDING",
                "asaas_id": "pay_8120829379393283",
                "pix": {
                    "payload": "00020126360014br.gov.bcb.pix...",
                    "encoded_image": "iVBORw0KGgoAAAANSUhEUgA...",
                    "expiration_date": "2026-06-05T23:59:59",
                },
                "last_error": None,
                "created_at": "2026-05-15T16:00:00",
                "updated_at": "2026-05-15T16:00:00",
            }
        }
    )


class CustomerResponse(BaseModel):
    external_id: str
    asaas_id: str
    name: str
    cpf_cnpj: str
    email: str | None = None
    mobile_phone: str | None = None
    created_at: str | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "external_id": "aluno_42",
                "asaas_id": "cus_000005113863",
                "name": "Maria Aluna",
                "cpf_cnpj": "07426367980",
                "email": "maria@example.com",
                "mobile_phone": None,
                "created_at": "2026-05-15T15:50:00",
            }
        }
    )
