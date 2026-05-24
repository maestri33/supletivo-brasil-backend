"""Regra de negocio de checkout: cria link InfinitePay, processa webhook, enfileira saida.

Config da loja (handle, precos, URLs) vem 100% do .env via Settings — a antiga
tabela `config` foi removida (B). A sessao de negocio chega por DI (Depends(get_session))
e e commitada pela rota.

Auditoria (webhook_logs): usa a propria sessao da request. Nos caminhos que vao abortar
(erros de integracao, webhook) o log e commitado de imediato (`durable=True`), entao
sobrevive ao rollback da request. No sucesso do create, o log entra na mesma transacao
do Checkout (atomico).
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.exceptions import Conflict, IntegrationError, NotFound, ValidationError
from app.integrations.infinitepay_client import (
    InfinitePayError,
    create_checkout_link,
    payment_check,
)
from app.models import Checkout, WebhookLog
from app.services import monitor as ai_monitor
from app.services import receipt as ai_receipt
from app.utils import validators as v
from app.utils.crypto import encrypt_external_id
from app.workers import outbound_queue as queue

logger = structlog.get_logger("infinitepay")


def _store_config() -> dict:
    """Config da loja (defaults de checkout) — 100% do .env (antes era a tabela `config`)."""
    s = get_settings()
    return {
        "handle": s.handle,
        "price": s.price,
        "quantity": s.quantity,
        "description": s.description,
        "redirect_url": s.redirect_url,
        "backend_webhook": s.backend_webhook,
        "public_api_url": s.public_api_url,
    }


async def _log_event(
    db: AsyncSession,
    *,
    direction,
    kind,
    payload,
    response=None,
    status_code=None,
    external_id=None,
    source_ip=None,
    user_agent=None,
    durable: bool = False,
) -> None:
    """Audita um evento de webhook na sessao da request.

    durable=True commita de imediato (o log sobrevive a um rollback posterior) e e
    best-effort (§12): uma falha de auditoria nunca derruba o caminho do dinheiro.
    durable=False apenas adiciona — commita junto com a transacao de negocio (rota).

    source_ip/user_agent: origem do webhook publico (§5); so preenchidos no log inbound.
    """
    db.add(
        WebhookLog(
            direction=direction,
            kind=kind,
            payload=payload or {},
            response=response,
            status_code=status_code,
            external_id=external_id,
            source_ip=source_ip,
            user_agent=user_agent,
        )
    )
    if not durable:
        return
    try:
        await db.commit()
    except Exception as exc:  # noqa: BLE001 — auditoria nunca quebra o fluxo
        await db.rollback()
        logger.warning("webhook_log_failed", kind=kind, direction=direction, error=str(exc))


def _resolve_items(body: dict, cfg: dict) -> list[dict]:
    if body.get("items"):
        return v.normalize_items(body["items"])

    price = body.get("price", cfg.get("price"))
    description = body.get("description", cfg.get("description"))
    quantity = body.get("quantity", cfg.get("quantity") or 1)

    if price is None or not description:
        raise ValidationError(
            "price+description (ou items[]) obrigatorios — informe no body ou no .env"
        )
    return [v.normalize_item({"price": price, "description": description, "quantity": quantity})]


def _resolve_field(body: dict, cfg: dict, key: str, normalizer, *args) -> str:
    val = body.get(key) or cfg.get(key)
    if not val:
        raise ValidationError(f"{key} obrigatorio — informe no body ou no .env")
    return normalizer(val, *args)


async def create_checkout(db: AsyncSession, body: dict[str, Any]) -> dict:
    cfg = _store_config()

    if "public_api_url" in body:
        raise ValidationError("public_api_url nao pode ser informado aqui; configure no .env.")

    external_id = v.normalize_external_id(body.get("external_id", ""))
    handle = _resolve_field(body, cfg, "handle", v.normalize_handle)
    redirect_url = _resolve_field(body, cfg, "redirect_url", v.normalize_url, "redirect_url")
    public_api_url = cfg["public_api_url"]
    if not public_api_url:
        raise ValidationError("public_api_url nao configurado (defina INFINITEPAY_PUBLIC_API_URL).")

    customer = v.normalize_customer(body.get("customer") or {})
    address = v.normalize_address(body.get("address"))
    items = _resolve_items(body, cfg)

    existing = (
        await db.execute(select(Checkout).where(Checkout.external_id == external_id))
    ).scalar_one_or_none()
    if existing is not None:
        raise Conflict(
            f"external_id ja existe: {external_id}. "
            f"Faca um GET /checkout/{external_id}/ para conferir.",
            extra={"external_id": external_id},
        )

    ipay_payload: dict[str, Any] = {
        "handle": handle,
        "items": items,
        "order_nsu": external_id,
        "redirect_url": redirect_url,
        "webhook_url": (
            f"{public_api_url}/api/v1/webhook/?external_id={encrypt_external_id(external_id)}"
        ),
        "customer": customer,
    }
    if address:
        ipay_payload["address"] = address

    try:
        response = await create_checkout_link(ipay_payload)
    except InfinitePayError as e:
        await _log_event(
            db,
            direction="outbound",
            kind="create_link",
            payload=ipay_payload,
            response=e.payload,
            status_code=e.status_code,
            external_id=external_id,
            durable=True,
        )
        raise IntegrationError(f"Falha ao criar link na InfinitePay: {e}") from e

    checkout_url = response.get("url") or response.get("checkout_url")
    if not checkout_url:
        await _log_event(
            db,
            direction="outbound",
            kind="create_link",
            payload=ipay_payload,
            response=response,
            status_code=200,
            external_id=external_id,
            durable=True,
        )
        raise IntegrationError("InfinitePay nao retornou URL de checkout")

    db.add(
        Checkout(
            external_id=external_id,
            checkout_url=checkout_url,
            is_paid=False,
            request_payload=ipay_payload,
            response_payload=response,
        )
    )
    try:
        await db.flush()
    except IntegrityError as e:
        await db.rollback()
        raise Conflict(
            f"external_id ja existe: {external_id}. "
            f"Faca um GET /checkout/{external_id}/ para conferir.",
            extra={"external_id": external_id},
        ) from e

    # Log de sucesso entra na mesma transacao do Checkout (commit na rota).
    await _log_event(
        db,
        direction="outbound",
        kind="create_link",
        payload=ipay_payload,
        response=response,
        status_code=200,
        external_id=external_id,
    )

    backend_webhook = cfg.get("backend_webhook")
    if backend_webhook:
        customer_name = customer.get("name", "cliente") if customer else "cliente"
        product = items[0].get("description", cfg.get("description", "produto"))
        price = items[0].get("price", cfg.get("price", 0))
        await queue.enqueue(
            db,
            url=backend_webhook,
            payload={
                "external_id": external_id,
                "paid": False,
                "checkout_url": checkout_url,
                "customer_name": customer_name,
                "product": product,
                "amount": price,
                "handle": handle,
            },
            external_id=external_id,
        )

    return {"external_id": external_id, "checkout_url": checkout_url}


async def list_checkouts(db: AsyncSession) -> list[dict]:
    stmt = select(Checkout).order_by(Checkout.created_at.desc(), Checkout.id.desc())
    rows = (await db.execute(stmt)).scalars().all()
    return [_serialize(c) for c in rows]


async def get_checkout(db: AsyncSession, external_id: str) -> dict:
    external_id = v.normalize_external_id(external_id)
    c = (
        await db.execute(select(Checkout).where(Checkout.external_id == external_id))
    ).scalar_one_or_none()
    if c is None:
        raise NotFound(f"checkout nao encontrado: {external_id}")
    eid = str(c.external_id)
    if c.is_paid:
        return {"external_id": eid, "is_paid": True, "receipt_url": c.receipt_url}
    return {"external_id": eid, "is_paid": False, "checkout_url": c.checkout_url}


def _serialize(c: Checkout) -> dict:
    return {
        "external_id": str(c.external_id),
        "is_paid": c.is_paid,
        "checkout_url": c.checkout_url,
        "receipt_url": c.receipt_url,
        "invoice_slug": c.invoice_slug,
        "transaction_nsu": c.transaction_nsu,
        "capture_method": c.capture_method,
        "installments": c.installments,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


async def handle_infinitepay_webhook(
    db: AsyncSession,
    external_id: str,
    payload: dict,
    *,
    source_ip: str | None = None,
    user_agent: str | None = None,
) -> dict:
    external_id = v.normalize_external_id(external_id)
    cfg = _store_config()
    handle = cfg.get("handle")
    backend_webhook = cfg.get("backend_webhook")

    await _log_event(
        db,
        direction="inbound",
        kind="infinitepay_webhook",
        payload=payload,
        external_id=external_id,
        source_ip=source_ip,
        user_agent=user_agent,
        durable=True,
    )

    if not handle:
        raise IntegrationError("handle nao configurado")

    transaction_nsu = payload.get("transaction_nsu")
    invoice_slug = payload.get("invoice_slug")
    order_nsu = v.normalize_external_id(str(payload.get("order_nsu") or external_id))
    if order_nsu != external_id:
        raise ValidationError("order_nsu do webhook diverge do external_id da rota")

    if not transaction_nsu or not invoice_slug:
        raise ValidationError("payload de webhook incompleto (faltam transaction_nsu/invoice_slug)")

    c = (
        await db.execute(select(Checkout).where(Checkout.external_id == external_id))
    ).scalar_one_or_none()
    if c is None:
        raise NotFound(f"checkout desconhecido: {external_id}")
    if c.is_paid:
        return {"ok": True, "paid": True, "duplicate": True}

    check_payload = {
        "handle": handle,
        "order_nsu": order_nsu,
        "transaction_nsu": transaction_nsu,
        "slug": invoice_slug,
    }
    try:
        check = await payment_check(
            handle=handle,
            order_nsu=order_nsu,
            transaction_nsu=transaction_nsu,
            slug=invoice_slug,
        )
    except InfinitePayError as e:
        await _log_event(
            db,
            direction="outbound",
            kind="payment_check",
            payload=check_payload,
            response=e.payload,
            status_code=e.status_code,
            external_id=external_id,
            durable=True,
        )
        raise IntegrationError(f"Falha ao validar pagamento na InfinitePay: {e}") from e

    await _log_event(
        db,
        direction="outbound",
        kind="payment_check",
        payload=check_payload,
        response=check,
        external_id=external_id,
        durable=True,
    )

    if not check.get("success"):
        raise ValidationError("webhook nao pode ser validado")

    if not check.get("paid"):
        return {"ok": True, "paid": False}

    # Re-le na mesma sessao (estado pode ter mudado entre o load e o payment_check).
    c = (
        await db.execute(select(Checkout).where(Checkout.external_id == external_id))
    ).scalar_one_or_none()
    if c is None:
        raise NotFound(f"checkout desconhecido: {external_id}")
    if c.is_paid and c.transaction_nsu == transaction_nsu:
        return {"ok": True, "paid": True, "duplicate": True}

    c.is_paid = True
    c.receipt_url = payload.get("receipt_url")
    c.installments = payload.get("installments") or check.get("installments")
    c.invoice_slug = invoice_slug
    c.capture_method = payload.get("capture_method") or check.get("capture_method")
    c.transaction_nsu = transaction_nsu

    _rp = c.request_payload or {}
    _customer = _rp.get("customer", {})
    customer_name = _customer.get("name", "cliente")
    _items = _rp.get("items", [{}])
    product = _items[0].get("description", cfg.get("description", "produto"))
    price = _items[0].get("price", cfg.get("price", 0))
    receipt_url = payload.get("receipt_url") or ""

    if backend_webhook:
        ai_message = await ai_receipt.generate_receipt_message(
            customer_name=customer_name,
            product=product,
            price_cents=price,
            receipt_url=receipt_url,
        )

        anomaly = await ai_monitor.check_anomaly(external_id, payload)
        if anomaly.get("alert"):
            logger.warning(
                "anomaly_detected",
                external_id=external_id,
                reason=anomaly.get("reason"),
                deep_analysis=anomaly.get("deep_analysis"),
            )

        await queue.enqueue(
            db,
            url=backend_webhook,
            payload={
                "external_id": external_id,
                "paid": True,
                "receipt_url": receipt_url,
                "transaction_nsu": transaction_nsu,
                "invoice_slug": invoice_slug,
                "capture_method": payload.get("capture_method"),
                "installments": payload.get("installments"),
                "amount": payload.get("amount"),
                "paid_amount": payload.get("paid_amount"),
                "customer_name": customer_name,
                "product": product,
                "ai_message": ai_message,
                "ai_anomaly": anomaly,
            },
            external_id=external_id,
        )

    # paid-state + job enfileirado commitam juntos na rota (atomico — licao do asaas).
    return {"ok": True, "paid": True}
