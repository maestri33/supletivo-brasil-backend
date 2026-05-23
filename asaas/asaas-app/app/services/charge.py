"""Charge service — cobrancas PIX recebidas via Asaas.

Fluxo de criacao:
  1. find_or_create_customer(external_id, payer)
  2. POST /v3/payments {customer, billingType: PIX, value, dueDate, description, externalReference}
  3. GET /v3/payments/{id}/pixQrCode -> {payload (BR Code), encodedImage (PNG base64)}
  4. Persiste Payment(kind=charge, status=PENDING) com asaas_id, qrcode_payload, pix_qr_image
  5. Notifica internal_url_charge

Webhook (PAYMENT_*):
  PAYMENT_CONFIRMED, PAYMENT_RECEIVED -> PAID
  PAYMENT_OVERDUE                      -> EXPIRED
  PAYMENT_DELETED                      -> CANCELLED
  PAYMENT_RESTORED                     -> PENDING
  PAYMENT_REFUNDED                     -> REFUNDED
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import config_store as cfg
from ..config import get_settings
from ..exceptions import PaymentError, ValidationError
from ..integrations.asaas_client import AsaasClient, AsaasError
from ..models import Payment
from ..utils.logging import log_event
from . import customer as customer_service

CHARGE_STATUSES = ("PENDING", "PAID", "EXPIRED", "CANCELLED", "REFUNDED")
_TERMINAL = {"PAID", "EXPIRED", "CANCELLED", "REFUNDED"}

# Asaas PAYMENT_* event -> nosso status
ASAAS_TO_CHARGE_STATUS = {
    "PAYMENT_CREATED": "PENDING",
    "PAYMENT_UPDATED": None,  # no-op (so atualiza metadata)
    "PAYMENT_CONFIRMED": "PAID",
    "PAYMENT_RECEIVED": "PAID",
    "PAYMENT_OVERDUE": "EXPIRED",
    "PAYMENT_DELETED": "CANCELLED",
    "PAYMENT_RESTORED": "PENDING",
    "PAYMENT_REFUNDED": "REFUNDED",
    "PAYMENT_RECEIVED_IN_CASH_UNDONE": "PENDING",
}


# ---------------- create ----------------


def _new_payment_id() -> str:
    return f"pay_{uuid.uuid4().hex[:16]}"


def _new_or_check_payment_id(db: Session, payment_id: str | None) -> str:
    pid = payment_id or _new_payment_id()
    if db.query(Payment).filter(Payment.payment_id == pid).first():
        raise PaymentError("payment_id_already_exists")
    return pid


def _resolve_due_date(due_date: str | None) -> date:
    if not due_date:
        return date.today() + timedelta(days=get_settings().charge_default_due_days)
    try:
        parsed = datetime.strptime(due_date, "%Y-%m-%d").date()
    except ValueError as e:
        raise PaymentError(f"invalid_due_date: {e}") from e
    if parsed < date.today():
        raise PaymentError(f"invalid_due_date: {due_date} is in the past")
    return parsed


def create(
    db: Session,
    *,
    external_id: str,
    amount: float,
    description: str | None,
    due_date: str | None,
    payment_id: str | None,
    payer: customer_service.PayerData | None,
) -> Payment:
    if amount is None or amount <= 0:
        raise PaymentError("invalid_amount")
    api_key = cfg.get(db, cfg.K_ASAAS_API_KEY)
    if not api_key:
        raise PaymentError("asaas_api_key_not_set")

    try:
        cust = customer_service.find_or_create(db, external_id, payer)
    except ValidationError as e:
        # bubble up como PaymentError pra unificar handling no router
        raise PaymentError(str(e)) from e

    due = _resolve_due_date(due_date)
    pid = _new_or_check_payment_id(db, payment_id)

    payload = {
        "customer": cust.asaas_id,
        "billingType": "PIX",
        "value": round(float(amount), 2),
        "dueDate": due.isoformat(),
        "description": description or f"charge {pid}",
        "externalReference": pid,
    }

    client = AsaasClient(api_key)
    try:
        try:
            created = client.create_payment(payload)
        except AsaasError as e:
            raise PaymentError(f"asaas_charge_create_failed: {e.body}") from e
        try:
            qr = client.get_payment_pix_qr_code(created["id"])
        except AsaasError as e:
            # nao bloqueia criacao — persistimos sem QR e cliente pode rebuscar via GET /qr
            log_event("charge_qr_fetch_failed", asaas_id=created.get("id"), body=str(e.body))
            qr = None
    finally:
        client.close()

    row = Payment(
        payment_id=pid,
        kind="charge",
        customer_external_id=cust.external_id,
        qrcode_payload=(qr or {}).get("payload"),
        pix_qr_image=(qr or {}).get("encodedImage"),
        amount=round(float(amount), 2),
        description=description,
        due_date=due,
        status="PENDING",
        asaas_id=created["id"],
    )
    db.add(row)
    db.flush()
    log_event(
        "charge_created",
        payment_id=pid,
        asaas_id=created["id"],
        amount=row.amount,
        external_id=external_id,
    )
    return row


# ---------------- queries ----------------


def get_by_payment_id(db: Session, payment_id: str) -> Payment | None:
    return (
        db.query(Payment)
        .filter(Payment.kind == "charge", Payment.payment_id == payment_id)
        .one_or_none()
    )


def get_by_asaas_id(db: Session, asaas_id: str) -> Payment | None:
    return (
        db.query(Payment)
        .filter(Payment.kind == "charge", Payment.asaas_id == asaas_id)
        .one_or_none()
    )


def list_all(
    db: Session,
    *,
    limit: int = 200,
    offset: int = 0,
    status: str | None = None,
    external_id: str | None = None,
) -> list[Payment]:
    limit = max(1, min(int(limit), 500))
    offset = max(0, int(offset))
    q = db.query(Payment).filter(Payment.kind == "charge")
    if status is not None:
        if status not in CHARGE_STATUSES:
            raise PaymentError(f"invalid_status: {status}")
        q = q.filter(Payment.status == status)
    if external_id is not None:
        q = q.filter(Payment.customer_external_id == external_id)
    return q.order_by(Payment.id.desc()).offset(offset).limit(limit).all()


def count_by_status(db: Session) -> dict[str, int]:
    rows = (
        db.query(Payment.status, func.count(Payment.id))
        .filter(Payment.kind == "charge")
        .group_by(Payment.status)
        .all()
    )
    return {status: count for status, count in rows}


# ---------------- refresh QR ----------------


def refresh_qr(db: Session, payment_id: str) -> Payment:
    row = get_by_payment_id(db, payment_id)
    if row is None:
        raise PaymentError("not_found")
    if not row.asaas_id:
        raise PaymentError("asaas_qr_fetch_failed: no asaas_id")
    api_key = cfg.get(db, cfg.K_ASAAS_API_KEY)
    if not api_key:
        raise PaymentError("asaas_api_key_not_set")
    client = AsaasClient(api_key)
    try:
        try:
            qr = client.get_payment_pix_qr_code(row.asaas_id)
        except AsaasError as e:
            raise PaymentError(f"asaas_qr_fetch_failed: {e.body}") from e
    finally:
        client.close()
    row.qrcode_payload = qr.get("payload") or row.qrcode_payload
    row.pix_qr_image = qr.get("encodedImage") or row.pix_qr_image
    row.updated_at = datetime.now(UTC)
    db.flush()
    return row


# ---------------- cancel ----------------


def cancel(db: Session, payment_id: str) -> Payment:
    row = get_by_payment_id(db, payment_id)
    if row is None:
        raise PaymentError("not_found")
    if row.status in _TERMINAL:
        if row.status == "CANCELLED":
            return row
        raise PaymentError(f"cannot_cancel_status: {row.status}")
    api_key = cfg.get(db, cfg.K_ASAAS_API_KEY)
    if not api_key:
        raise PaymentError("asaas_api_key_not_set")
    if not row.asaas_id:
        row.status = "CANCELLED"
        row.updated_at = datetime.now(UTC)
        db.flush()
        return row
    client = AsaasClient(api_key)
    try:
        try:
            client.delete_payment(row.asaas_id)
        except AsaasError as e:
            row.last_error = json.dumps(e.body, ensure_ascii=False)[:500]
            db.flush()
            raise PaymentError(f"asaas_charge_delete_failed: {e.body}") from e
    finally:
        client.close()
    row.status = "CANCELLED"
    row.updated_at = datetime.now(UTC)
    db.flush()
    log_event("charge_cancelled", payment_id=row.payment_id, asaas_id=row.asaas_id)
    return row


# ---------------- webhook ----------------


def apply_webhook(db: Session, payload: dict) -> Payment | None:
    """Mapeia evento PAYMENT_* a Payment(kind=charge). Retorna o row atualizado ou None."""
    if not isinstance(payload, dict):
        return None
    event = payload.get("event")
    if not event or not event.startswith("PAYMENT_"):
        return None
    if event not in ASAAS_TO_CHARGE_STATUS:
        return None
    new_status = ASAAS_TO_CHARGE_STATUS[event]
    asaas_payment = payload.get("payment") or {}
    asaas_id = asaas_payment.get("id")
    external_ref = asaas_payment.get("externalReference")
    row: Payment | None = None
    if external_ref:
        row = get_by_payment_id(db, external_ref)
    if row is None and asaas_id:
        row = get_by_asaas_id(db, asaas_id)
    if row is None:
        return None
    if asaas_id and row.asaas_id != asaas_id:
        row.asaas_id = asaas_id
    if new_status is None:
        # PAYMENT_UPDATED — apenas refresh metadata sem mudar status
        row.updated_at = datetime.now(UTC)
        db.flush()
        return None  # nao dispara notificacao
    if row.status == new_status:
        return None
    row.status = new_status
    row.updated_at = datetime.now(UTC)
    db.flush()
    log_event(
        "charge_status_changed",
        payment_id=row.payment_id,
        status=new_status,
        asaas_event=event,
    )
    return row


# ---------------- to_dict ----------------


def to_dict(row: Payment) -> dict:
    pix = None
    if row.qrcode_payload and row.pix_qr_image:
        pix = {
            "payload": row.qrcode_payload,
            "encoded_image": row.pix_qr_image,
            "expiration_date": None,
        }
    elif row.qrcode_payload:
        pix = {
            "payload": row.qrcode_payload,
            "encoded_image": "",
            "expiration_date": None,
        }
    return {
        "payment_id": row.payment_id,
        "external_id": row.customer_external_id,
        "amount": row.amount,
        "description": row.description,
        "due_date": row.due_date.isoformat() if row.due_date else None,
        "status": row.status,
        "asaas_id": row.asaas_id,
        "pix": pix,
        "last_error": row.last_error,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
