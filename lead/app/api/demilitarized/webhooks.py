"""Webhooks de entrada — chamados por notify, infinitepay e asaas."""

from typing import Any, Literal
from uuid import UUID

import structlog
from fastapi import APIRouter, BackgroundTasks, Body, Depends, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models import Checkout, Lead, LeadStatus, Message
from app.notify.handlers import notify_lead_completed
from app.tools.webhooks import notify_enrollment, notify_promoter_completed

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/webhook", tags=["webhooks"])


class WebhookBase(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True, frozen=True)


class NotifyWebhook(WebhookBase):
    event: str = Field(..., examples=["message.delivered"])
    message_id: int
    contact_id: int
    external_id: UUID
    type: str = Field(..., examples=["whatsapp", "email", "tts"])
    whatsapp_status: str | None = None
    email_status: str | None = None
    email_subject: str | None = None
    tts_audio_url: str | None = None


class InfinitepayWebhook(WebhookBase):
    external_id: UUID
    paid: bool
    receipt_url: str | None = None
    transaction_nsu: str | None = None
    invoice_slug: str | None = None
    capture_method: str | None = Field(default=None, examples=["pix", "credit_card", "boleto"])
    installments: int | None = Field(default=None, ge=1)
    amount: int | None = Field(default=None, description="Valor bruto em centavos")
    paid_amount: int | None = Field(default=None, description="Valor pago em centavos")
    customer_name: str | None = None
    product: str | None = None
    ai_message: str | None = None
    ai_anomaly: dict[str, Any] | None = None


@router.post("/notify/{message_id}", status_code=status.HTTP_202_ACCEPTED)
async def notify_callback(
    message_id: int,
    payload: NotifyWebhook,
    session: AsyncSession = Depends(get_session),
):
    """Callback do Notify: WhatsApp/Email/TTS — atualiza status da mensagem."""
    log = logger.bind(message_id=message_id)

    incoming = Message(
        message_id=message_id,
        external_id=payload.external_id,
        direction="in",
        channel=payload.type,
        status=payload.whatsapp_status or payload.email_status or payload.event,
        event=payload.event,
        meta={
            "contact_id": payload.contact_id,
            "whatsapp_status": payload.whatsapp_status,
            "email_status": payload.email_status,
            "email_subject": payload.email_subject,
            "tts_audio_url": payload.tts_audio_url,
        },
    )
    session.add(incoming)

    existing = await session.scalar(
        select(Message).where(Message.message_id == message_id, Message.direction == "out")
    )
    if existing:
        existing.status = payload.whatsapp_status or payload.email_status or payload.event

    await session.commit()
    # structlog: o primeiro arg posicional vira o campo "event" do log.
    # Passar event=... como kwarg conflita ("got multiple values for argument 'event'").
    # Usamos notify_event=... para evitar colisao.
    log.info("notify_webhook_processed", notify_event=payload.event)
    return {"ok": True}


@router.post("/infinitepay", status_code=status.HTTP_202_ACCEPTED)
async def infinitepay_callback(
    payload: InfinitepayWebhook,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """Callback da InfinitePay: confirma pagamento + transiciona lead → completed."""
    log = logger.bind(external_id=str(payload.external_id))

    checkout = await session.scalar(
        select(Checkout).where(Checkout.external_id == payload.external_id)
    )
    if checkout:
        # IMPORTANTE: o infinitepay-app enqueue 2 jobs por checkout — um na
        # criacao (paid=False, sem transaction_nsu/receipt_url) e outro no
        # pagamento (paid=True, com dados completos). Se o worker entregar
        # fora de ordem, o webhook de criacao sobrescreve o de pagamento e
        # perdemos transaction_nsu/receipt_url. Solucao: SO atualizamos
        # campos quando paid=True OU quando checkout ainda nao foi pago.
        if payload.paid or not checkout.is_paid:
            checkout.is_paid = payload.paid or checkout.is_paid
            checkout.receipt_url = payload.receipt_url or checkout.receipt_url
            checkout.transaction_nsu = payload.transaction_nsu or checkout.transaction_nsu
            checkout.invoice_slug = payload.invoice_slug or checkout.invoice_slug
            checkout.capture_method = payload.capture_method or checkout.capture_method
            checkout.installments = payload.installments or checkout.installments

    completed_now = False
    if payload.paid:
        lead = await session.scalar(select(Lead).where(Lead.external_id == payload.external_id))
        if lead and lead.status != LeadStatus.COMPLETED:
            lead.status = LeadStatus.COMPLETED
            completed_now = True
            promoter = lead.promoter_external_id

    await session.commit()

    if completed_now:
        log.info("lead_completed")
        external_id_str = str(payload.external_id)
        background_tasks.add_task(
            notify_lead_completed,
            external_id_str,
            payload.receipt_url or "",
            capture_method=payload.capture_method,
            installments=payload.installments,
            # InfinitePay envia paid_amount em centavos (fallback p/ amount).
            amount_cents=payload.paid_amount or payload.amount,
        )
        background_tasks.add_task(notify_enrollment, external_id_str, str(promoter or ""))
        if promoter:
            background_tasks.add_task(notify_promoter_completed, external_id_str, str(promoter))

    return {"ok": True}


# ── Asaas charge webhook ───────────────────────────────────────────────────
# Bridge do servico v7m-asaas: POST {internal_url_charge} com
#   {"payment_id": "pay_...", "kind": "charge", "external_id": "<uuid>", "status": "PAID"}
# Disparado em PENDING/PAID/EXPIRED/CANCELLED/REFUNDED.

AsaasChargeStatus = Literal["PENDING", "PAID", "EXPIRED", "CANCELLED", "REFUNDED"]


class AsaasChargeWebhook(WebhookBase):
    payment_id: str = Field(..., examples=["pay_a1b2c3d4e5f6a7b8"])
    kind: str = Field(default="charge")
    external_id: UUID
    status: AsaasChargeStatus


@router.post("/asaas-charge", status_code=status.HTTP_202_ACCEPTED)
async def asaas_charge_callback(
    background_tasks: BackgroundTasks,
    raw: dict[str, Any] = Body(...),
    session: AsyncSession = Depends(get_session),
):
    """Callback do v7m-asaas (charge bridge): atualiza Checkout PIX e,
    se PAID, transiciona Lead → COMPLETED + dispara bifurcacoes.

    Aceita dois tipos de payload:
      - `{"event": "ASAAS_APP_ONBOARDING", ...}` (validacao do asaas durante
        `POST /api/v1/config/internal`): retorna 202 OK sem efeito colateral.
      - `{"payment_id", "kind":"charge", "external_id", "status"}`: o callback
        real (status mapeado em AsaasChargeStatus).

    Nao gera receipt_url (PIX nao tem recibo equivalente ao cartao).
    """
    # 1) Onboarding ping do asaas — apenas confirma 2xx.
    if raw.get("event") == "ASAAS_APP_ONBOARDING":
        logger.info("asaas_webhook_onboarding_ack", target=raw.get("target"))
        return {"ok": True, "onboarding": True}

    # 2) Callback real — validar payload via Pydantic
    try:
        payload = AsaasChargeWebhook.model_validate(raw)
    except Exception as exc:
        logger.warning("asaas_webhook_invalid_payload", error=str(exc)[:200])
        return {"ok": True, "invalid_payload": True}

    log = logger.bind(
        external_id=str(payload.external_id),
        payment_id=payload.payment_id,
        status=payload.status,
    )

    if payload.kind != "charge":
        log.warning("asaas_webhook_ignored_kind")
        return {"ok": True, "ignored": True}

    checkout = await session.scalar(
        select(Checkout).where(Checkout.external_id == payload.external_id)
    )
    if checkout is None:
        log.warning("asaas_webhook_no_checkout")
        return {"ok": True, "checkout_missing": True}

    if checkout.provider != "asaas":
        # Lead foi criado via outro provider (ou linha legada sem provider) —
        # webhook PIX e' inesperado e nao deve mutar o checkout.
        log.warning(
            "asaas_webhook_provider_mismatch",
            checkout_provider=checkout.provider,
        )
        return {"ok": True, "provider_mismatch": True}

    # Atualiza estado do checkout (idempotente).
    checkout.is_paid = payload.status == "PAID"
    if checkout.provider_payment_id != payload.payment_id:
        checkout.provider_payment_id = payload.payment_id

    completed_now = False
    promoter: UUID | None = None
    if payload.status == "PAID":
        lead = await session.scalar(select(Lead).where(Lead.external_id == payload.external_id))
        if lead and lead.status != LeadStatus.COMPLETED:
            lead.status = LeadStatus.COMPLETED
            completed_now = True
            promoter = lead.promoter_external_id

    await session.commit()

    if completed_now:
        log.info("lead_completed")
        external_id_str = str(payload.external_id)
        # PIX usa o valor default configurado em settings (em reais).
        # NOTE: ideal seria buscar o valor real do checkout (atual ou via
        # API do asaas service), mas o asaas webhook payload nao traz o
        # amount e o lead.checkouts nao armazena. Por ora, default suffices
        # ja que toda PIX usa PIX_DEFAULT_AMOUNT no /captured.
        pix_amount_cents = int(round(settings.PIX_DEFAULT_AMOUNT * 100))
        background_tasks.add_task(
            notify_lead_completed,
            external_id_str,
            "",  # PIX nao tem receipt_url
            capture_method="pix",
            installments=1,
            amount_cents=pix_amount_cents,
        )
        background_tasks.add_task(notify_enrollment, external_id_str, str(promoter or ""))
        if promoter:
            background_tasks.add_task(notify_promoter_completed, external_id_str, str(promoter))

    return {"ok": True}
