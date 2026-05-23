"""Payment service: enfileira, submete ao Asaas quando houver saldo, notifica internal URL.

Status machine:
  SCHEDULED       agendado pra data/hora futura
  QUEUED          pronto pra tentar submeter
  AWAITING_BALANCE  tentou submeter mas Asaas rejeitou por saldo insuficiente
  SUBMITTING      claim local em andamento, antes da chamada externa
  SUBMITTED       Asaas aceitou (criou transfer); aguardando TRANSFER_DONE
  PAID            TRANSFER_DONE recebido
  FAILED          erro permanente (chave invalida, etc) ou TRANSFER_FAILED
  CANCELLED       usuario cancelou

Worker roda como asyncio task dentro do uvicorn:
  - a cada N segundos, puxa SCHEDULED cujo scheduled_for <= now -> QUEUED
  - pra cada QUEUED ou AWAITING_BALANCE, chama submit_one
"""

from __future__ import annotations

import asyncio
import base64
import json
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import unquote
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .. import config_store as cfg
from ..config import get_settings
from ..db import async_session_maker
from ..exceptions import PaymentError
from ..integrations.asaas_client import AsaasClient, AsaasError
from ..models import Payment, PixKey
from ..utils.brcode import analyze as analyze_brcode
from ..utils.logging import log_event
from .notifications import notify_internal as _notify_internal  # noqa: F401 — compat re-export

BR_TZ = ZoneInfo("America/Sao_Paulo")


_VALID_STATUSES = {
    "SCHEDULED",
    "QUEUED",
    "SUBMITTING",
    "SUBMITTED",
    "AWAITING_BALANCE",
    "PAID",
    "FAILED",
    "CANCELLED",
}

DELETABLE_STATUSES = {"SCHEDULED", "AWAITING_BALANCE"}

CLAIMABLE_STATUSES = ("QUEUED", "AWAITING_BALANCE")
SUBMITTING_STALE_AFTER = timedelta(minutes=10)


# ---------------- create ----------------


def _new_payment_id() -> str:
    return f"pay_{uuid.uuid4().hex[:16]}"


async def _resolve_pixkey(db: AsyncSession, external_id: str) -> PixKey:
    row = (
        await db.execute(select(PixKey).where(PixKey.external_id == external_id))
    ).scalar_one_or_none()
    if row is None:
        raise PaymentError("pixkey_not_found")
    return row


def _compute_scheduled_utc(date_str: str, hour: int | None, minute: int | None) -> datetime:
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError as e:
        raise PaymentError(f"invalid_date: {e}") from e
    h = get_settings().default_scheduled_hour if hour is None else int(hour)
    m = 0 if minute is None else int(minute)
    local = datetime(d.year, d.month, d.day, h, m, tzinfo=BR_TZ)
    return local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


async def _new_or_check_payment_id(db: AsyncSession, payment_id: str | None) -> str:
    pid = payment_id or _new_payment_id()
    if (await db.execute(select(Payment).where(Payment.payment_id == pid))).scalar_one_or_none():
        raise PaymentError("payment_id_already_exists")
    return pid


async def create_pixkey(
    db: AsyncSession,
    pixkey_external_id: str,
    amount: float,
    payment_id: str | None = None,
    description: str | None = None,
    schedule_date: str | None = None,
    hour: int | None = None,
    minute: int | None = None,
) -> Payment:
    if amount <= 0:
        raise PaymentError("invalid_amount")
    await _resolve_pixkey(db, pixkey_external_id)
    pid = await _new_or_check_payment_id(db, payment_id)
    scheduled_for = _compute_scheduled_utc(schedule_date, hour, minute) if schedule_date else None
    row = Payment(
        payment_id=pid,
        kind="pixkey",
        pixkey_external_id=pixkey_external_id,
        amount=float(amount),
        description=description,
        scheduled_for=scheduled_for,
        status="SCHEDULED" if scheduled_for else "QUEUED",
    )
    db.add(row)
    await db.flush()
    return row


async def create_qrcode(
    db: AsyncSession,
    qrcode_payload: str,
    amount: float | None,
    payment_id: str | None = None,
    description: str | None = None,
    schedule_date: str | None = None,
    hour: int | None = None,
    minute: int | None = None,
) -> Payment:
    payload = qrcode_payload.strip()
    if len(payload) < 20:
        raise PaymentError("invalid_qrcode_payload")
    analysis = analyze_brcode(payload)
    if schedule_date and not analysis["can_schedule"]:
        raise PaymentError("dynamic_qrcode_scheduling_not_supported")
    fixed = analysis["amount"]
    if fixed is not None:
        if amount is not None and round(float(amount), 2) != round(float(fixed), 2):
            raise PaymentError(f"qrcode_fixed_amount_mismatch: expected {fixed:.2f}")
        amount = fixed
    elif amount is None:
        raise PaymentError("qrcode_amount_required")
    if amount <= 0:
        raise PaymentError("invalid_amount")
    pid = await _new_or_check_payment_id(db, payment_id)
    scheduled_for = _compute_scheduled_utc(schedule_date, hour, minute) if schedule_date else None
    row = Payment(
        payment_id=pid,
        kind="qrcode",
        qrcode_payload=payload,
        amount=float(amount),
        description=description,
        scheduled_for=scheduled_for,
        status="SCHEDULED" if scheduled_for else "QUEUED",
    )
    db.add(row)
    await db.flush()
    return row


# ---------------- queries ----------------


async def get_by_payment_id(db: AsyncSession, payment_id: str) -> Payment | None:
    return (
        await db.execute(select(Payment).where(Payment.payment_id == payment_id))
    ).scalar_one_or_none()


async def list_all(
    db: AsyncSession,
    limit: int = 200,
    offset: int = 0,
    kind: str | None = None,
    status: str | None = None,
) -> list[Payment]:
    limit = max(1, min(int(limit), 500))
    offset = max(0, int(offset))
    stmt = select(Payment)
    if kind is not None:
        if kind not in ("pixkey", "qrcode"):
            raise PaymentError(f"invalid_kind: {kind}")
        stmt = stmt.where(Payment.kind == kind)
    if status is not None:
        if status not in _VALID_STATUSES:
            raise PaymentError(f"invalid_status: {status}")
        stmt = stmt.where(Payment.status == status)
    stmt = stmt.order_by(Payment.id.desc()).offset(offset).limit(limit)
    return list((await db.execute(stmt)).scalars().all())


async def list_awaiting_balance(db: AsyncSession) -> list[Payment]:
    return list(
        (
            await db.execute(
                select(Payment)
                .where(Payment.status == "AWAITING_BALANCE")
                .order_by(Payment.id.desc())
            )
        )
        .scalars()
        .all()
    )


async def count_by_status(db: AsyncSession) -> dict[str, int]:
    rows = (
        await db.execute(select(Payment.status, func.count(Payment.id)).group_by(Payment.status))
    ).all()
    return {status: count for status, count in rows}


async def count_total(db: AsyncSession) -> int:
    return (await db.execute(select(func.count()).select_from(Payment))).scalar_one() or 0


async def sum_awaiting_balance(db: AsyncSession) -> dict:
    total = (
        await db.execute(
            select(func.sum(Payment.amount)).where(Payment.status == "AWAITING_BALANCE")
        )
    ).scalar() or 0.0
    count = (
        await db.execute(
            select(func.count()).select_from(Payment).where(Payment.status == "AWAITING_BALANCE")
        )
    ).scalar_one() or 0
    return {"status": "AWAITING_BALANCE", "count": count, "total": round(float(total), 2)}


async def delete_one(db: AsyncSession, payment_id: str) -> Payment:
    row = await get_by_payment_id(db, payment_id)
    if row is None:
        raise PaymentError("not_found")
    if row.status not in DELETABLE_STATUSES:
        raise PaymentError(f"cannot_delete_status: {row.status}")
    await _mark_payment(db, row, "CANCELLED")
    await _notify_internal(db, row)
    log_event("payment_deleted", payment_id=row.payment_id)
    return row


def to_dict(row: Payment) -> dict:
    return {
        "payment_id": row.payment_id,
        "kind": row.kind,
        "external_id": row.pixkey_external_id,
        "qrcode_payload": row.qrcode_payload,
        "amount": row.amount,
        "description": row.description,
        "scheduled_for": row.scheduled_for.isoformat() if row.scheduled_for else None,
        "status": row.status,
        "asaas_id": row.asaas_id,
        "last_error": row.last_error,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


# ---------------- internal notifications ----------------
# Roteamento por categoria vive em services/notifications.py.
# _notify_internal e re-exportado no topo do arquivo para callsites legados.


# ---------------- submit to Asaas ----------------

_INSUFFICIENT_BALANCE_PATTERNS = (
    "saldo",
    "balance",
    "insufficient",
    "insuficiente",
)


def _is_insufficient_balance(body: object) -> bool:
    s = json.dumps(body, ensure_ascii=False).lower() if body is not None else ""
    return any(p in s for p in _INSUFFICIENT_BALANCE_PATTERNS)


async def _claim_for_submit(db: AsyncSession, payment: Payment) -> bool:
    """Atomically move a queued payment to SUBMITTING before calling Asaas."""
    if payment.status not in CLAIMABLE_STATUSES:
        return False
    now = datetime.now(UTC)
    result = await db.execute(
        update(Payment)
        .where(Payment.id == payment.id, Payment.status.in_(CLAIMABLE_STATUSES))
        .values(status="SUBMITTING", updated_at=now)
    )
    await db.commit()
    if result.rowcount != 1:
        await db.refresh(payment)
        return False
    await db.refresh(payment)
    log_event("payment_claimed", payment_id=payment.payment_id)
    return True


async def _mark_payment(
    db: AsyncSession,
    payment: Payment,
    status: str,
    *,
    last_error: str | None = None,
    asaas_id: str | None = None,
) -> None:
    payment.status = status
    payment.updated_at = datetime.now(UTC)
    if asaas_id is not None:
        payment.asaas_id = asaas_id
    payment.last_error = last_error
    await db.flush()


async def submit_one(db: AsyncSession, payment: Payment) -> None:
    """Tenta submeter uma Payment ao Asaas. Atualiza status in-place."""
    api_key = await cfg.get(db, cfg.K_ASAAS_API_KEY)
    if not api_key:
        payment.last_error = "waiting_asaas_api_key"
        await db.flush()
        return
    old_status = payment.status
    if not await _claim_for_submit(db, payment):
        return
    async with AsaasClient(api_key) as client:
        try:
            if payment.kind == "qrcode":
                res = await client.pay_qr_code(
                    payment.qrcode_payload,
                    payment.amount,
                    payment.description,
                )
            else:
                try:
                    pix = await _resolve_pixkey(db, payment.pixkey_external_id)
                except PaymentError as e:
                    await _mark_payment(db, payment, "FAILED", last_error=str(e))
                    return
                res = await client.create_transfer(
                    {
                        "value": round(float(payment.amount), 2),
                        "pixAddressKey": pix.key,
                        "externalReference": payment.payment_id,
                        "description": payment.description or f"payment {payment.payment_id}",
                    }
                )

            await _mark_payment(db, payment, "SUBMITTED", asaas_id=res.get("id"))
            # Commit imediato do asaas_id: o /security-validator do Asaas chega ~5s
            # depois numa transação separada e casa o pagamento por asaas_id. Sem este
            # commit, o asaas_id só seria persistido no fim do tick e o validator
            # recusaria uma transferência legítima (operation_not_found_locally).
            await db.commit()
            await _notify_internal(db, payment)
            log_event("payment_submitted", payment_id=payment.payment_id, asaas_id=payment.asaas_id)

        except AsaasError as e:
            if _is_insufficient_balance(e.body):
                was_already = old_status == "AWAITING_BALANCE"
                await _mark_payment(
                    db,
                    payment,
                    "AWAITING_BALANCE",
                    last_error=json.dumps(e.body, ensure_ascii=False)[:500],
                )
                if not was_already:
                    await _notify_internal(db, payment)
                log_event("payment_awaiting_balance", payment_id=payment.payment_id)
            else:
                await _mark_payment(
                    db, payment, "FAILED", last_error=json.dumps(e.body, ensure_ascii=False)[:500]
                )
                await _notify_internal(db, payment)
                log_event("payment_failed", payment_id=payment.payment_id, error=payment.last_error)


# ---------------- reconciliation ----------------

_ASAAS_STATUS_TO_OURS = {
    "DONE": "PAID",
    "FAILED": "FAILED",
    "BLOCKED": "FAILED",
    "CANCELLED": "CANCELLED",
}

_PIX_TRANSACTION_STATUS_TO_OURS = {
    "DONE": "PAID",
    "REFUSED": "FAILED",
    "CANCELLED": "CANCELLED",
}


async def reconcile_submitted(db: AsyncSession) -> int:
    """Pra cada SUBMITTED com asaas_id, consulta status real no Asaas.

    Necessario porque webhooks podem chegar tarde ou nao chegar
    (ex.: authToken dessincronizado, retries em backoff).
    """
    api_key = await cfg.get(db, cfg.K_ASAAS_API_KEY)
    if not api_key:
        return 0
    targets = list(
        (
            await db.execute(
                select(Payment).where(Payment.status == "SUBMITTED", Payment.asaas_id.is_not(None))
            )
        )
        .scalars()
        .all()
    )
    if not targets:
        return 0
    updated = 0
    async with AsaasClient(api_key) as client:
        for p in targets:
            try:
                if p.kind == "qrcode":
                    res = await client.get_pix_transaction(p.asaas_id)
                    mapped = _PIX_TRANSACTION_STATUS_TO_OURS.get(res.get("status"))
                    if mapped == "PAID" and res.get("transferId"):
                        p.asaas_id = res.get("transferId")
                    fail_reason = res.get("refusalReason")
                else:
                    res = await client.get_transfer(p.asaas_id)
                    mapped = _ASAAS_STATUS_TO_OURS.get(res.get("status"))
                    fail_reason = res.get("failReason")
            except AsaasError:
                continue
            if mapped and mapped != p.status:
                p.status = mapped
                p.updated_at = datetime.now(UTC)
                if mapped == "FAILED":
                    p.last_error = fail_reason or "reconciled_failed"
                await _notify_internal(db, p)
                log_event("payment_reconciled", payment_id=p.payment_id, status=mapped)
                updated += 1
    if updated:
        await db.flush()
    return updated


# ---------------- worker tick ----------------


async def tick(db: AsyncSession) -> dict:
    """Uma iteracao do worker. Retorna contadores."""
    now = datetime.now(UTC)
    moved_scheduled = 0
    submitted = 0

    stale = now - SUBMITTING_STALE_AFTER
    stuck = list(
        (
            await db.execute(
                select(Payment).where(
                    Payment.status == "SUBMITTING",
                    Payment.updated_at <= stale,
                    Payment.asaas_id.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    for p in stuck:
        p.status = "QUEUED"
        p.last_error = "requeued_stale_submitting"
        p.updated_at = now
        log_event("payment_requeued_stale_submitting", payment_id=p.payment_id)

    # SCHEDULED -> QUEUED se chegou a hora
    due = list(
        (
            await db.execute(
                select(Payment).where(Payment.status == "SCHEDULED", Payment.scheduled_for <= now)
            )
        )
        .scalars()
        .all()
    )
    for p in due:
        p.status = "QUEUED"
        p.updated_at = now
        moved_scheduled += 1
        await _notify_internal(db, p)
    if due:
        await db.flush()

    # QUEUED + AWAITING_BALANCE -> tenta
    targets = list(
        (
            await db.execute(
                select(Payment)
                .where(Payment.status.in_(["QUEUED", "AWAITING_BALANCE"]))
                .order_by(Payment.id.asc())
            )
        )
        .scalars()
        .all()
    )
    for p in targets:
        await submit_one(db, p)
        submitted += 1

    # SUBMITTED -> reconcilia com Asaas (cobre casos de webhook perdido)
    reconciled = await reconcile_submitted(db)

    return {"moved_scheduled": moved_scheduled, "submitted": submitted, "reconciled": reconciled}


async def worker_loop(interval_seconds: float = 30.0) -> None:
    while True:
        try:
            async with async_session_maker() as s:
                await tick(s)
                await s.commit()
        except Exception:
            log_event("worker_tick_error")
        await asyncio.sleep(interval_seconds)


# ---------------- webhook → payment status bridge ----------------

# eventos Asaas que mapeiam para status nossos
ASAAS_TO_STATUS = {
    "TRANSFER_DONE": "PAID",
    "TRANSFER_FAILED": "FAILED",
    "TRANSFER_BLOCKED": "FAILED",
    "TRANSFER_CANCELLED": "CANCELLED",
}


def _extract_qrcode_payment_id_from_receipt(url: str | None) -> str | None:
    if not url:
        return None
    token = unquote(str(url).rstrip("/").split("/")[-1]).strip()
    if not token:
        return None
    try:
        decoded = base64.b64decode(token, validate=False).decode("utf-8", errors="ignore")
    except Exception:
        return None
    prefix = "PIX_TRANSACTION_DONE:"
    if decoded.startswith(prefix):
        return decoded[len(prefix) :].strip() or None
    return None


_PAYOUT_KINDS = ("pixkey", "qrcode")


async def apply_webhook(db: AsyncSession, payload: dict) -> Payment | None:
    """Se o webhook (TRANSFER_*) for de uma transfer nossa, atualiza Payment.status.

    Filtra por kind in (pixkey, qrcode) — webhooks PAYMENT_* sao tratados pelo charge service.
    """
    if not isinstance(payload, dict):
        return None
    event = payload.get("event")
    new_status = ASAAS_TO_STATUS.get(event)
    if not new_status:
        return None
    transfer = payload.get("transfer") or {}
    ext_ref = transfer.get("externalReference")
    asaas_id = transfer.get("id")
    row = None
    if ext_ref:
        row = (
            await db.execute(
                select(Payment).where(
                    Payment.kind.in_(_PAYOUT_KINDS), Payment.payment_id == ext_ref
                )
            )
        ).scalar_one_or_none()
    if row is None and asaas_id:
        row = (
            await db.execute(
                select(Payment).where(Payment.kind.in_(_PAYOUT_KINDS), Payment.asaas_id == asaas_id)
            )
        ).scalar_one_or_none()
    if row is None and event == "TRANSFER_DONE":
        qr_payment_id = _extract_qrcode_payment_id_from_receipt(
            transfer.get("transactionReceiptUrl")
        )
        if qr_payment_id:
            row = (
                await db.execute(
                    select(Payment).where(
                        Payment.kind.in_(_PAYOUT_KINDS), Payment.asaas_id == qr_payment_id
                    )
                )
            ).scalar_one_or_none()
    if row is None:
        return None
    if asaas_id and row.asaas_id != asaas_id:
        row.asaas_id = asaas_id
    if row.status == new_status:
        return None
    row.status = new_status
    row.updated_at = datetime.now(UTC)
    if new_status == "FAILED":
        row.last_error = transfer.get("failReason") or f"event={event}"
    await db.flush()
    return row


async def cancel(db: AsyncSession, payment_id: str) -> Payment:
    row = await get_by_payment_id(db, payment_id)
    if row is None:
        raise PaymentError("not_found")
    if row.status in ("PAID", "FAILED", "CANCELLED"):
        return row
    if row.status in ("SCHEDULED", "QUEUED", "AWAITING_BALANCE"):
        await _mark_payment(db, row, "CANCELLED")
        await _notify_internal(db, row)
        log_event("payment_cancelled_local", payment_id=row.payment_id)
        return row
    if row.status == "SUBMITTED":
        if not row.asaas_id:
            await _mark_payment(db, row, "CANCELLED")
            await _notify_internal(db, row)
            return row
        api_key = await cfg.get(db, cfg.K_ASAAS_API_KEY)
        if not api_key:
            raise PaymentError("asaas_api_key_not_set")
        async with AsaasClient(api_key) as client:
            try:
                if row.kind == "qrcode":
                    await client.cancel_pix_transaction(row.asaas_id)
                else:
                    await client.cancel_transfer(row.asaas_id)
            except AsaasError as e:
                row.last_error = json.dumps(e.body, ensure_ascii=False)[:500]
                await db.flush()
                raise PaymentError(f"asaas_cancel_failed: {e.body}") from e
        await _mark_payment(db, row, "CANCELLED")
        await _notify_internal(db, row)
        log_event("payment_cancelled_asaas", payment_id=row.payment_id, asaas_id=row.asaas_id)
        return row
    raise PaymentError(f"cannot_cancel_status:{row.status}")
