"""Notificacoes internas (out-webhook).

Roteamento por categoria de evento (3 URLs configuraveis + fallback legado):

  kind=charge                                    -> internal_url_charge
  kind in (pixkey, qrcode), status SCHEDULED/QUEUED -> internal_url_scheduling
  kind in (pixkey, qrcode), demais               -> internal_url_payout

Fallback: internal_url (legado catch-all) quando o destino especifico nao esta setado.
Se nenhum estiver configurado, no-op silencioso (eventos ficam apenas no log).

Entrega: ate 2026-05-28 era httpx.post direto (fire-and-forget; falha = log).
Hoje enfileira em asaas.outbound_jobs e o worker faz retry com backoff (ver
[[project-asaas-webhook-before-checkout-race]] e workers/outbound_queue.py).
Usa sessao propria pra commit imediato do job — a maioria dos callsites ja
commitou seu estado antes de chamar; manter sessao do caller perderia o job
em rollback de transacao nova nao-commitada.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from .. import config_store as cfg
from ..db import async_session_maker
from ..models import Payment
from ..utils.logging import log_event
from ..workers.outbound_queue import enqueue

_SCHEDULING_STATUSES = {"SCHEDULED", "QUEUED"}


async def internal_url_for(db: AsyncSession, *, kind: str, status: str | None) -> str | None:
    """Resolve a internal URL apropriada para um evento, com fallback ao legado."""
    fallback = await cfg.get(db, cfg.K_INTERNAL_URL)
    if kind == "charge":
        return await cfg.get(db, cfg.K_INTERNAL_URL_CHARGE) or fallback
    if status in _SCHEDULING_STATUSES:
        return await cfg.get(db, cfg.K_INTERNAL_URL_SCHEDULING) or fallback
    return await cfg.get(db, cfg.K_INTERNAL_URL_PAYOUT) or fallback


def _external_id_field(payment: Payment) -> str | None:
    """Qual external_id incluir no payload conforme o kind."""
    if payment.kind == "pixkey":
        return payment.pixkey_external_id
    if payment.kind == "charge":
        return payment.customer_external_id
    # qrcode: sem external_id
    return None


async def notify_internal(db: AsyncSession, payment: Payment) -> None:
    """Enfileira notify interno (asaas.outbound_jobs). Worker entrega com retry."""
    url = await internal_url_for(db, kind=payment.kind, status=payment.status)
    if not url:
        return
    payload = {
        "payment_id": payment.payment_id,
        "kind": payment.kind,
        "external_id": _external_id_field(payment),
        "status": payment.status,
    }
    try:
        async with async_session_maker() as enq_sess:
            job_id = await enqueue(
                enq_sess,
                url=url,
                payload=payload,
                external_id=payment.payment_id,
            )
            await enq_sess.commit()
        log_event(
            "internal_notify_enqueued",
            payment_id=payment.payment_id,
            status=payment.status,
            kind=payment.kind,
            target=url,
            job_id=job_id,
        )
    except Exception as e:
        log_event(
            "internal_notify_enqueue_failed",
            payment_id=payment.payment_id,
            status=payment.status,
            kind=payment.kind,
            target=url,
            error=str(e),
        )
