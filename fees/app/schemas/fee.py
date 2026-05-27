"""Schemas Pydantic v2 do serviço `fees`.

Entrada do coordenador (`FeeCreate`), leitura (`FeeRead`/`FeePaymentRead`) e o
payload do webhook interno do asaas (`AsaasPayoutWebhook`).
"""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class APIModel(BaseModel):
    """Base de leitura: lê direto de objetos ORM."""

    model_config = ConfigDict(from_attributes=True)


# ── Entrada ─────────────────────────────────────────────────────────────────


class UpfrontLeg(BaseModel):
    """Parte à vista: BR Code a pagar agora."""

    qrcode_payload: str = Field(..., min_length=20, description="BR Code copia-e-cola")
    amount: float = Field(..., gt=0, description="Valor em BRL")


class ScheduledLeg(BaseModel):
    """Parte agendada: BR Code estático + data/hora do agendamento."""

    qrcode_payload: str = Field(..., min_length=20, description="BR Code copia-e-cola")
    amount: float = Field(..., gt=0, description="Valor em BRL")
    date: str = Field(..., description="Data do agendamento, YYYY-MM-DD")
    hour: int | None = Field(default=None, ge=0, le=23, description="Hora local America/Sao_Paulo")
    minute: int | None = Field(default=None, ge=0, le=59, description="Minuto local")

    @field_validator("date")
    @classmethod
    def _valid_date(cls, v: str) -> str:
        try:
            date.fromisoformat(v)
        except ValueError as exc:
            raise ValueError("date deve estar no formato YYYY-MM-DD") from exc
        return v


class FeeCreate(BaseModel):
    """Corpo de `POST /api/v1/authenticated/fees`.

    O coordenador informa o aluno e os dois pagamentos (valores e vencimento do
    agendamento vêm aqui — decisão do produto).
    """

    student_external_id: UUID = Field(..., description="UUID do aluno (student)")
    description: str | None = Field(default=None, description="Descrição da taxa")
    upfront: UpfrontLeg
    scheduled: ScheduledLeg

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "student_external_id": "3f1c2b9e-1a2b-4c3d-8e9f-0a1b2c3d4e5f",
                "description": "Taxa de matrícula 2026/1",
                "upfront": {
                    "qrcode_payload": "00020126360014br.gov.bcb.pix0114+5542999384069...",
                    "amount": 250.0,
                },
                "scheduled": {
                    "qrcode_payload": "00020126360014br.gov.bcb.pix0114+5542999384069...",
                    "amount": 250.0,
                    "date": "2026-07-01",
                    "hour": 8,
                },
            }
        }
    )


# ── Leitura ─────────────────────────────────────────────────────────────────


class FeePaymentRead(APIModel):
    kind: str
    payment_id: str
    amount: float
    status: str
    scheduled_date: date | None = None
    asaas_id: str | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


class FeeRead(APIModel):
    id: str
    student_external_id: str
    coordinator_external_id: str
    status: str
    description: str | None = None
    payments: list[FeePaymentRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


# ── Webhook interno do asaas ────────────────────────────────────────────────


class AsaasPayoutWebhook(BaseModel):
    """Payload do out-webhook do asaas (categoria payout/scheduling).

    Formato: `{"payment_id", "kind", "external_id", "status"}`. Em payouts de QR
    Code o `external_id` vem nulo — a correlação é por `payment_id`.
    """

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    payment_id: str
    status: str
    kind: str | None = None
    external_id: str | None = None
