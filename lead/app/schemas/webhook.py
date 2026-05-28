"""Schemas de webhooks recebidos (demilitarized).

Webhooks de terceiros usam BaseModel (nao APIModel) porque
precisam de frozen=True e extra=ignore para validacao rigorosa.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class WebhookBase(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True, frozen=True)


class NotifyWebhook(WebhookBase):
    status: str
    phone: str
    type: str | None = None
    body: str | None = None
    sent_at: str | None = None


class InfinitepayWebhook(WebhookBase):
    """Webhook padrao do InfinitePay. Usa event + data envelope."""

    event: str
    data: dict


class AsaasChargeWebhook(WebhookBase):
    """Webhook de cobranca PIX recebida via Asaas.

    Usa top-level fields (sem envelope 'event').
    """

    payment_id: str = Field(..., alias="payment")
    external_id: str = Field(..., alias="externalReference")
    status: str
