"""Endpoints que o Asaas chama no dominio publico do asaas-app."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from .. import config_store as cfg
from ..db import get_session
from ..models import WebhookEvent
from ..services import charge as charge_service
from ..services import notifications
from ..services import payment as payment_service
from ..services import security_validator as security_validator_svc
from ..services.webhook_security import verify_hmac, verify_ip_allowlist
from ..utils.logging import log_event
from ..utils.net import client_ip, user_agent

router = APIRouter(tags=["asaas-inbound"])


async def _check_token(db: AsyncSession, asaas_access_token: str | None):
    expected = await cfg.get(db, cfg.K_ASAAS_SECURITY_TOKEN)
    if not expected or asaas_access_token != expected:
        raise HTTPException(status_code=401, detail="invalid_token")


@router.post(
    "/security-validator",
    summary="Autorizar Mecanismo de Seguranca Asaas",
    response_description=(
        "APPROVED se a operacao bate com um Payment(kind=pixkey|qrcode, "
        "status=SUBMITTING|SUBMITTED) com mesmo asaas_id e amount; senao REFUSED."
    ),
)
async def security_validator(
    request: Request,
    asaas_access_token: str | None = Header(default=None, alias="asaas-access-token"),
    db: AsyncSession = Depends(get_session),
    _ip: None = Depends(verify_ip_allowlist),
    _sig: None = Depends(verify_hmac),
):
    """Valida saidas (TRANSFER, PIX_QR_CODE) contra nosso DB.

    Tipos não iniciados pelo app (BILL, MOBILE_PHONE_RECHARGE, PIX_REFUND) sao
    sempre recusados — Asaas cancela a operacao apos 3 tentativas falhas.

    Auditoria: cada decisao gera evento `security_validator_decision` no log
    com {approved, refuse_reason, op_type, op_id}.
    """
    await _check_token(db, asaas_access_token)
    body = await request.json()
    return await security_validator_svc.decide(db, body if isinstance(body, dict) else {})


@router.post(
    "/webhook/",
    summary="Receber webhook Asaas",
    response_description="Evento persistido e notificacao simplificada enviada a internal_url_*.",
)
async def receive_webhook(
    request: Request,
    asaas_access_token: str | None = Header(default=None, alias="asaas-access-token"),
    db: AsyncSession = Depends(get_session),
    _ip: None = Depends(verify_ip_allowlist),
    _sig: None = Depends(verify_hmac),
):
    """Recebe eventos Asaas, persiste e roteia para o bridge correto.

    TRANSFER_* -> payment_service.apply_webhook (payouts: pixkey, qrcode)
    PAYMENT_*  -> charge_service.apply_webhook (cobrancas PIX recebidas)

    Sempre 200 mesmo se o evento nao mapear para nada nosso (Asaas re-envia em retry).
    """
    await _check_token(db, asaas_access_token)
    body = await request.json()
    event = body.get("event") if isinstance(body, dict) else None

    row = WebhookEvent(
        event=event,
        payload=json.dumps(body, ensure_ascii=False),
        source_ip=client_ip(request),
        user_agent=user_agent(request),
    )
    db.add(row)
    await db.flush()

    payment = None
    try:
        if isinstance(event, str) and event.startswith("PAYMENT_"):
            payment = await charge_service.apply_webhook(db, body if isinstance(body, dict) else {})
        else:
            payment = await payment_service.apply_webhook(
                db, body if isinstance(body, dict) else {}
            )
        if payment is not None:
            await notifications.notify_internal(db, payment)
            log_event(
                "webhook_applied",
                payment_id=payment.payment_id,
                kind=payment.kind,
                status=payment.status,
                asaas_event=event,
            )
    except Exception:
        log_event("webhook_apply_failed", asaas_event=event)

    await db.commit()
    return {"ok": True}
