"""Mecanismo de Validacao de Saque via Webhooks.

Asaas chama POST /security-validator ~5s apos cada saida (TRANSFER, PIX_QR_CODE,
BILL, MOBILE_PHONE_RECHARGE, PIX_REFUND). Nos precisamos responder:

  { "status": "APPROVED" }                                       -> Asaas executa
  { "status": "REFUSED", "refuseReason": "<motivo curto>" }     -> Asaas cancela

Se nao respondermos com APPROVED em ate 3 tentativas, a operacao e cancelada.

Regra de aprovacao (somente):
  1. type=TRANSFER       e ha um Payment(kind=pixkey, status in SUBMITTING|SUBMITTED)
                         com asaas_id == transfer.id e amount == transfer.value
  2. type=PIX_QR_CODE    e ha um Payment(kind=qrcode, ...) com mesmo match.

Demais types (BILL, MOBILE_PHONE_RECHARGE, PIX_REFUND) sao recusados porque o
app nao inicia esses fluxos hoje.

Refuse precoce, log sempre, nao explode em payload malformado.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Payment
from ..utils.logging import log_event

# Operacoes que iniciamos
_TYPE_TO_KIND = {
    "TRANSFER": "pixkey",
    "PIX_QR_CODE": "qrcode",
}

# Operacoes que NAO iniciamos — recusa categoricamente
_UNSUPPORTED_TYPES = {"BILL", "MOBILE_PHONE_RECHARGE", "PIX_REFUND"}

# Status do Payment que aceitamos validar (entre claim local e webhook de conclusao)
_VALIDATABLE_STATUSES = ("SUBMITTING", "SUBMITTED")


async def validate(db: AsyncSession, payload: dict) -> tuple[bool, str | None]:
    """Retorna (approved, refuse_reason). approved=True implica refuse_reason=None."""
    if not isinstance(payload, dict):
        return False, "invalid_payload"

    op_type = payload.get("type")
    if not op_type or not isinstance(op_type, str):
        return False, "missing_type"

    if op_type in _UNSUPPORTED_TYPES:
        return False, f"unsupported_operation_type: {op_type}"

    kind = _TYPE_TO_KIND.get(op_type)
    if kind is None:
        return False, f"unknown_type: {op_type}"

    # Payload field name segue o type: transfer.id, pixQrCode.id, ...
    payload_field = "transfer" if op_type == "TRANSFER" else "pixQrCode"
    op = payload.get(payload_field)
    if not isinstance(op, dict):
        return False, f"missing_{payload_field}_object"

    asaas_id = op.get("id")
    if not asaas_id:
        return False, "missing_id_in_payload"

    row = (
        await db.execute(
            select(Payment).where(
                Payment.asaas_id == asaas_id,
                Payment.kind == kind,
                Payment.status.in_(_VALIDATABLE_STATUSES),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return False, f"operation_not_found_locally: id={asaas_id}"

    asaas_value = op.get("value")
    if asaas_value is not None:
        local = round(float(row.amount), 2)
        remote = round(float(asaas_value), 2)
        if local != remote:
            return False, f"value_mismatch: local={local} remote={remote}"

    return True, None


async def decide(db: AsyncSession, payload: dict) -> dict:
    """Retorna o body de resposta pro Asaas + loga a decisao."""
    approved, refuse_reason = await validate(db, payload)
    op_type = payload.get("type") if isinstance(payload, dict) else None
    op_id = None
    if isinstance(payload, dict):
        op = payload.get("transfer") or payload.get("pixQrCode") or {}
        if isinstance(op, dict):
            op_id = op.get("id")
    log_event(
        "security_validator_decision",
        approved=approved,
        refuse_reason=refuse_reason,
        op_type=op_type,
        op_id=op_id,
    )
    if approved:
        return {"status": "APPROVED"}
    return {"status": "REFUSED", "refuseReason": refuse_reason or "unknown"}
