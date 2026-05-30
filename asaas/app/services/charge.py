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

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import config_store as cfg
from ..config import get_settings
from ..exceptions import PaymentError, ValidationError
from ..integrations.asaas_client import AsaasClient, AsaasError
from ..metrics import inc_payment
from ..models import Payment
from ..utils.logging import log_event
from ..utils.qrcode import absolute_qr_url_for, save_pix_qr_png
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


async def _new_or_check_payment_id(db: AsyncSession, payment_id: str | None) -> str:
    pid = payment_id or _new_payment_id()
    if (await db.execute(select(Payment).where(Payment.payment_id == pid))).scalar_one_or_none():
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


async def create(
    db: AsyncSession,
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
    api_key = await cfg.get(db, cfg.K_ASAAS_API_KEY)
    if not api_key:
        raise PaymentError("asaas_api_key_not_set")

    try:
        cust = await customer_service.find_or_create(db, external_id, payer)
    except ValidationError as e:
        # bubble up como PaymentError pra unificar handling no router
        raise PaymentError(str(e)) from e

    due = _resolve_due_date(due_date)
    pid = await _new_or_check_payment_id(db, payment_id)

    payload = {
        "customer": cust.asaas_id,
        "billingType": "PIX",
        "value": round(float(amount), 2),
        "dueDate": due.isoformat(),
        "description": description or f"charge {pid}",
        "externalReference": pid,
    }

    async with AsaasClient(api_key) as client:
        try:
            created = await client.create_payment(payload)
        except AsaasError as e:
            raise PaymentError(f"asaas_charge_create_failed: {e.body}") from e
        try:
            qr = await client.get_payment_pix_qr_code(created["id"])
        except AsaasError as e:
            # nao bloqueia criacao — persistimos sem QR e cliente pode rebuscar via GET /qr
            log_event("charge_qr_fetch_failed", asaas_id=created.get("id"), body=str(e.body))
            qr = None

    encoded_image = (qr or {}).get("encodedImage")
    if encoded_image:
        try:
            save_pix_qr_png(pid, encoded_image)
        except Exception as exc:
            # Decode/IO falhou — nao bloqueia criacao da charge. URL publica
            # ficara None ate refresh_qr ou ate operador corrigir manualmente.
            log_event("qrcode_save_failed", payment_id=pid, error=str(exc))

    row = Payment(
        payment_id=pid,
        kind="charge",
        customer_external_id=cust.external_id,
        qrcode_payload=(qr or {}).get("payload"),
        pix_qr_image=encoded_image,
        amount=round(float(amount), 2),
        description=description,
        due_date=due,
        status="PENDING",
        asaas_id=created["id"],
    )
    db.add(row)
    await db.flush()
    log_event(
        "charge_created",
        payment_id=pid,
        asaas_id=created["id"],
        amount=row.amount,
        external_id=external_id,
    )
    return row


# ---------------- queries ----------------


async def get_by_payment_id(db: AsyncSession, payment_id: str) -> Payment | None:
    return (
        await db.execute(
            select(Payment).where(Payment.kind == "charge", Payment.payment_id == payment_id)
        )
    ).scalar_one_or_none()


async def get_by_asaas_id(db: AsyncSession, asaas_id: str) -> Payment | None:
    return (
        await db.execute(
            select(Payment).where(Payment.kind == "charge", Payment.asaas_id == asaas_id)
        )
    ).scalar_one_or_none()


async def list_all(
    db: AsyncSession,
    *,
    limit: int = 200,
    offset: int = 0,
    status: str | None = None,
    external_id: str | None = None,
) -> list[Payment]:
    limit = max(1, min(int(limit), 500))
    offset = max(0, int(offset))
    stmt = select(Payment).where(Payment.kind == "charge")
    if status is not None:
        if status not in CHARGE_STATUSES:
            raise PaymentError(f"invalid_status: {status}")
        stmt = stmt.where(Payment.status == status)
    if external_id is not None:
        stmt = stmt.where(Payment.customer_external_id == external_id)
    stmt = stmt.order_by(Payment.created_at.desc(), Payment.id.desc()).offset(offset).limit(limit)
    return list((await db.execute(stmt)).scalars().all())


async def count_by_status(db: AsyncSession) -> dict[str, int]:
    rows = (
        await db.execute(
            select(Payment.status, func.count(Payment.id))
            .where(Payment.kind == "charge")
            .group_by(Payment.status)
        )
    ).all()
    return {status: count for status, count in rows}


# ---------------- refresh QR ----------------


async def refresh_qr(db: AsyncSession, payment_id: str) -> Payment:
    row = await get_by_payment_id(db, payment_id)
    if row is None:
        raise PaymentError("not_found")
    if not row.asaas_id:
        raise PaymentError("asaas_qr_fetch_failed: no asaas_id")
    api_key = await cfg.get(db, cfg.K_ASAAS_API_KEY)
    if not api_key:
        raise PaymentError("asaas_api_key_not_set")
    async with AsaasClient(api_key) as client:
        try:
            qr = await client.get_payment_pix_qr_code(row.asaas_id)
        except AsaasError as e:
            raise PaymentError(f"asaas_qr_fetch_failed: {e.body}") from e
    row.qrcode_payload = qr.get("payload") or row.qrcode_payload
    encoded_image = qr.get("encodedImage")
    if encoded_image:
        row.pix_qr_image = encoded_image
        try:
            save_pix_qr_png(row.payment_id, encoded_image)
        except Exception as exc:
            log_event("qrcode_save_failed", payment_id=row.payment_id, error=str(exc))
    row.updated_at = datetime.now(UTC)
    await db.flush()
    return row


# ---------------- cancel ----------------


async def cancel(db: AsyncSession, payment_id: str) -> Payment:
    row = await get_by_payment_id(db, payment_id)
    if row is None:
        raise PaymentError("not_found")
    if row.status in _TERMINAL:
        if row.status == "CANCELLED":
            return row
        raise PaymentError(f"cannot_cancel_status: {row.status}")
    api_key = await cfg.get(db, cfg.K_ASAAS_API_KEY)
    if not api_key:
        raise PaymentError("asaas_api_key_not_set")
    if not row.asaas_id:
        row.status = "CANCELLED"
        row.updated_at = datetime.now(UTC)
        await db.flush()
        return row
    async with AsaasClient(api_key) as client:
        try:
            await client.delete_payment(row.asaas_id)
        except AsaasError as e:
            row.last_error = json.dumps(e.body, ensure_ascii=False)[:500]
            await db.flush()
            raise PaymentError(f"asaas_charge_delete_failed: {e.body}") from e
    row.status = "CANCELLED"
    row.updated_at = datetime.now(UTC)
    await db.flush()
    log_event("charge_cancelled", payment_id=row.payment_id, asaas_id=row.asaas_id)
    return row


# ---------------- webhook ----------------


async def apply_webhook(db: AsyncSession, payload: dict) -> Payment | None:
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
        row = await get_by_payment_id(db, external_ref)
    if row is None and asaas_id:
        row = await get_by_asaas_id(db, asaas_id)
    if row is None:
        return None
    if asaas_id and row.asaas_id != asaas_id:
        row.asaas_id = asaas_id
    if new_status is None:
        # PAYMENT_UPDATED — apenas refresh metadata sem mudar status
        row.updated_at = datetime.now(UTC)
        await db.flush()
        return None  # nao dispara notificacao
    if row.status == new_status:
        return None
    row.status = new_status
    row.updated_at = datetime.now(UTC)
    await db.flush()
    inc_payment(kind="charge", status=new_status)
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
            "qr_url": absolute_qr_url_for(row.payment_id),
            "expiration_date": None,
        }
    elif row.qrcode_payload:
        pix = {
            "payload": row.qrcode_payload,
            "encoded_image": "",
            "qr_url": None,
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
