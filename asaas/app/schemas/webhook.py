"""Schemas de webhook do Asaas — notificacoes internas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class InternalNotification(BaseModel):
    """Payload enviado ao webhook interno (internal_url_*) a cada transicao de status.

    Roteamento por target:
      - kind=charge                          -> internal_url_charge
      - kind in (pixkey, qrcode), status SCHEDULED/QUEUED -> internal_url_scheduling
      - kind in (pixkey, qrcode), demais     -> internal_url_payout
    Fallback: internal_url (legado catch-all) quando o target especifico nao esta setado.
    """

    payment_id: str = Field(..., description="ID do pagamento (pay_...)")
    kind: str = Field(..., description='"pixkey" | "qrcode" | "charge"')
    external_id: str | None = Field(
        default=None,
        description=(
            "external_id da pixkey (kind=pixkey) ou do customer (kind=charge). "
            "null para kind=qrcode."
        ),
    )
    status: str = Field(
        ...,
        description=(
            "Novo status. Outbound: SCHEDULED | QUEUED | SUBMITTED | PAID | etc. "
            "Charge: PENDING | PAID | EXPIRED | CANCELLED | REFUNDED."
        ),
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example: pixkey": {
                "payment_id": "pay_a1b2c3d4e5f6a7b8",
                "kind": "pixkey",
                "external_id": "victor_celular",
                "status": "SUBMITTED",
            },
            "example: qrcode": {
                "payment_id": "pay_97584b93e49e4da4",
                "kind": "qrcode",
                "external_id": None,
                "status": "SCHEDULED",
            },
            "example: charge": {
                "payment_id": "pay_abc123",
                "kind": "charge",
                "external_id": "aluno_42",
                "status": "PAID",
            },
        }
    )
