"""Notificacoes internas (out-webhook).

Roteamento por categoria de evento (3 URLs configuraveis + fallback legado):

  kind=charge                                    -> internal_url_charge
  kind in (pixkey, qrcode), status SCHEDULED/QUEUED -> internal_url_scheduling
  kind in (pixkey, qrcode), demais               -> internal_url_payout

Fallback: internal_url (legado catch-all) quando o destino especifico nao esta setado.
Se nenhum estiver configurado, no-op silencioso (eventos ficam apenas no log).
"""

from __future__ import annotations

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from .. import config_store as cfg
from ..models import Payment
from ..utils.logging import log_event

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
    """Dispara POST a internal URL apropriada. Falhas sao logadas mas nao propagadas."""
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
        async with httpx.AsyncClient(timeout=5.0) as cli:
            r = await cli.post(url, json=payload)
            log_event(
                "internal_notify",
                payment_id=payment.payment_id,
                status=payment.status,
                kind=payment.kind,
                status_code=r.status_code,
                target=url,
            )
    except Exception as e:
        log_event(
            "internal_notify_failed",
            payment_id=payment.payment_id,
            status=payment.status,
            kind=payment.kind,
            target=url,
            error=str(e),
        )
