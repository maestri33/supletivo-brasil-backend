"""Testes para app/api/demilitarized/webhooks.py — Notify, InfinitePay, Asaas.

Estrategia:
  - NotifyWebhook: testa criacao de Message in + update de Message out.
  - InfinitepayWebhook: testa pagamento, out-of-order webhooks, promoter.
  - AsaasCharge: testa onboarding ping, payload invalido, provider mismatch,
    PAID flow, expiry.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


def _default_payload(overrides: dict | None = None) -> dict:
    """Helper: payload padrao para tests de webhook."""
    payload = {
        "external_id": str(uuid4()),
    }
    if overrides:
        payload.update(overrides)
    return payload


# ═══════════════════════════════════════════════════════════════════════════════
# Notify webhook
# ═══════════════════════════════════════════════════════════════════════════════


class TestNotifyWebhook:
    """POST /api/v1/webhook/notify/{message_id} — callbacks do Notify service."""

    async def test_notify_callback_creates_incoming_message(self, client: AsyncClient, make_lead):
        """Notify callback sem mensagem 'out' existente cria uma Message 'in'."""
        eid = str(uuid4())

        response = await client.post(
            f"/api/v1/webhook/notify/123",
            json={
                "event": "message.delivered",
                "message_id": 123,
                "contact_id": 456,
                "external_id": eid,
                "type": "whatsapp",
                "whatsapp_status": "delivered",
            },
        )
        assert response.status_code == 202
        data = response.json()
        assert data["ok"] is True

    async def test_notify_callback_updates_existing_message(self, client: AsyncClient, make_lead):
        """Se ja existe uma Message 'out' com mesmo message_id, atualiza status."""
        from app.db import async_session_maker
        from app.models import Message

        eid = str(uuid4())

        # Create an 'out' message first
        async with async_session_maker() as session:
            session.add(
                Message(
                    message_id=123,
                    external_id=UUID(eid),
                    direction="out",
                    channel="whatsapp",
                    status="sent",
                    event="message.sent",
                )
            )
            await session.commit()

        response = await client.post(
            f"/api/v1/webhook/notify/123",
            json={
                "event": "message.delivered",
                "message_id": 123,
                "contact_id": 456,
                "external_id": eid,
                "type": "whatsapp",
                "whatsapp_status": "delivered",
            },
        )
        assert response.status_code == 202

        # Verify the 'out' message was updated
        async with async_session_maker() as session:
            from sqlalchemy import select

            msg = await session.scalar(
                select(Message).where(Message.message_id == 123, Message.direction == "out")
            )
            assert msg is not None
            assert msg.status == "delivered"


# ═══════════════════════════════════════════════════════════════════════════════
# InfinitePay webhook
# ═══════════════════════════════════════════════════════════════════════════════


class TestInfinitepayWebhook:
    """POST /api/v1/webhook/infinitepay — pagamento cartao de credito."""

    @pytest.fixture(autouse=True)
    def _patch_background_tasks(self):
        """Prevent actual background task execution during tests."""
        with (
            patch("app.api.demilitarized.webhooks.notify_lead_completed"),
            patch("app.api.demilitarized.webhooks.notify_enrollment"),
            patch("app.api.demilitarized.webhooks.notify_promoter_completed"),
        ):
            yield

    async def test_paid_webhook_updates_checkout_and_lead(
        self, client: AsyncClient, make_lead, make_checkout
    ):
        """Pagamento confirmado → is_paid=True + lead COMPLETED."""
        eid = await make_lead(status="checkout")
        await make_checkout(external_id=eid, provider="infinitepay", is_paid=False)

        response = await client.post(
            "/api/v1/webhook/infinitepay",
            json={
                "external_id": str(eid),
                "paid": True,
                "receipt_url": "https://receipt.example.com/recibo.pdf",
                "transaction_nsu": "123456",
                "capture_method": "credit_card",
                "installments": 3,
                "paid_amount": 50000,
            },
        )
        assert response.status_code == 202
        assert response.json()["ok"] is True

        # Verify checkout was updated
        from app.db import async_session_maker
        from app.models import Checkout, Lead
        from sqlalchemy import select

        async with async_session_maker() as session:
            checkout = await session.scalar(
                select(Checkout).where(Checkout.external_id == eid)
            )
            assert checkout.is_paid is True
            assert checkout.receipt_url == "https://receipt.example.com/recibo.pdf"

            lead = await session.scalar(select(Lead).where(Lead.external_id == eid))
            assert lead.status.value == "completed"

    async def test_out_of_order_webhook_does_not_overwrite(
        self, client: AsyncClient, make_lead, make_checkout
    ):
        """Webhook com paid=False (criacao, entregue fora de ordem) nao sobrescreve paid=True."""
        eid = await make_lead(status="checkout")
        await make_checkout(external_id=eid, provider="infinitepay", is_paid=True,
                            receipt_url="https://receipt.example.com/recibo.pdf")

        # Now a paid=False webhook arrives out-of-order
        response = await client.post(
            "/api/v1/webhook/infinitepay",
            json={
                "external_id": str(eid),
                "paid": False,
            },
        )
        assert response.status_code == 202

        # Checkout should retain is_paid=True and receipt_url
        from app.db import async_session_maker
        from app.models import Checkout
        from sqlalchemy import select

        async with async_session_maker() as session:
            checkout = await session.scalar(
                select(Checkout).where(Checkout.external_id == eid)
            )
            assert checkout.is_paid is True
            assert checkout.receipt_url == "https://receipt.example.com/recibo.pdf"

    async def test_no_checkout_still_returns_ok(self, client: AsyncClient):
        """Webhook para external_id sem checkout retorna 202 OK (idempotente)."""
        eid = uuid4()

        response = await client.post(
            "/api/v1/webhook/infinitepay",
            json={
                "external_id": str(eid),
                "paid": True,
            },
        )
        assert response.status_code == 202

    async def test_paid_with_promoter_triggers_promoter_notifications(
        self, client: AsyncClient, make_lead, make_checkout
    ):
        """Pagamento com promoter → dispara notify_promoter_completed."""
        promoter_id = uuid4()
        eid = await make_lead(status="checkout", promoter_external_id=promoter_id)
        await make_checkout(external_id=eid, provider="infinitepay", is_paid=False)

        with (
            patch("app.api.demilitarized.webhooks.notify_promoter_completed") as mock_promoter,
            patch("app.api.demilitarized.webhooks.notify_enrollment"),
            patch("app.api.demilitarized.webhooks.notify_lead_completed"),
        ):
            response = await client.post(
                "/api/v1/webhook/infinitepay",
                json={
                    "external_id": str(eid),
                    "paid": True,
                    "capture_method": "credit_card",
                },
            )

        assert response.status_code == 202
        mock_promoter.assert_awaited_once_with(str(eid), str(promoter_id))


# ═══════════════════════════════════════════════════════════════════════════════
# Asaas charge webhook
# ═══════════════════════════════════════════════════════════════════════════════


class TestAsaasChargeWebhook:
    """POST /api/v1/webhook/asaas-charge — PIX charge callbacks."""

    @pytest.fixture(autouse=True)
    def _patch_background_tasks(self):
        """Prevent actual background task execution during tests."""
        with (
            patch("app.api.demilitarized.webhooks.notify_lead_completed"),
            patch("app.api.demilitarized.webhooks.notify_enrollment"),
            patch("app.api.demilitarized.webhooks.notify_promoter_completed"),
        ):
            yield

    async def test_onboarding_ping_returns_ok(self, client: AsyncClient):
        """ASAAS_APP_ONBOARDING event retorna 202 sem efeito colateral."""
        response = await client.post(
            "/api/v1/webhook/asaas-charge",
            json={
                "event": "ASAAS_APP_ONBOARDING",
                "target": "http://onboarding.webhook",
            },
        )
        assert response.status_code == 202
        data = response.json()
        assert data["ok"] is True
        assert data["onboarding"] is True

    async def test_invalid_payload_returns_ok_with_flag(self, client: AsyncClient):
        """Payload invalido retorna 202 + invalid_payload flag."""
        response = await client.post(
            "/api/v1/webhook/asaas-charge",
            json={"oops": "not a charge webhook"},
        )
        assert response.status_code == 202
        data = response.json()
        assert data["ok"] is True
        assert data["invalid_payload"] is True

    async def test_ignored_kind_returns_ok(self, client: AsyncClient):
        """kind diferente de 'charge' retorna 202 + ignored flag."""
        response = await client.post(
            "/api/v1/webhook/asaas-charge",
            json={
                "payment_id": "pay_123",
                "kind": "subscription",
                "external_id": str(uuid4()),
                "status": "PAID",
            },
        )
        assert response.status_code == 202
        data = response.json()
        assert data["ok"] is True
        assert data["ignored"] is True

    async def test_no_checkout_returns_ok(self, client: AsyncClient):
        """Asaas webhook para external_id sem checkout retorna 202."""
        response = await client.post(
            "/api/v1/webhook/asaas-charge",
            json={
                "payment_id": "pay_123",
                "kind": "charge",
                "external_id": str(uuid4()),
                "status": "PAID",
            },
        )
        assert response.status_code == 202
        data = response.json()
        assert data["checkout_missing"] is True

    async def test_provider_mismatch_returns_ok(
        self, client: AsyncClient, make_lead, make_checkout
    ):
        """Checkout de outro provider (infinitepay) recebendo webhook Asaas."""
        eid = await make_lead(status="checkout")
        await make_checkout(external_id=eid, provider="infinitepay", is_paid=False)

        response = await client.post(
            "/api/v1/webhook/asaas-charge",
            json={
                "payment_id": "pay_123",
                "kind": "charge",
                "external_id": str(eid),
                "status": "PAID",
            },
        )
        assert response.status_code == 202
        data = response.json()
        assert data["provider_mismatch"] is True

    async def test_paid_flow_updates_checkout_and_lead(
        self, client: AsyncClient, make_lead, make_checkout
    ):
        """Asaas PAID → is_paid=True + payment_id salvo + lead COMPLETED."""
        eid = await make_lead(status="checkout")
        await make_checkout(external_id=eid, provider="asaas", is_paid=False)

        response = await client.post(
            "/api/v1/webhook/asaas-charge",
            json={
                "payment_id": "pay_a1b2c3d4",
                "kind": "charge",
                "external_id": str(eid),
                "status": "PAID",
            },
        )
        assert response.status_code == 202

        from app.db import async_session_maker
        from app.models import Checkout, Lead
        from sqlalchemy import select

        async with async_session_maker() as session:
            checkout = await session.scalar(
                select(Checkout).where(Checkout.external_id == eid)
            )
            assert checkout.is_paid is True
            assert checkout.provider_payment_id == "pay_a1b2c3d4"

            lead = await session.scalar(select(Lead).where(Lead.external_id == eid))
            assert lead.status.value == "completed"

    async def test_expired_flow_does_not_complete_lead(
        self, client: AsyncClient, make_lead, make_checkout
    ):
        """EXPIRED → is_paid=False, lead nao muda."""
        eid = await make_lead(status="checkout")
        await make_checkout(external_id=eid, provider="asaas", is_paid=False)

        response = await client.post(
            "/api/v1/webhook/asaas-charge",
            json={
                "payment_id": "pay_expired",
                "kind": "charge",
                "external_id": str(eid),
                "status": "EXPIRED",
            },
        )
        assert response.status_code == 202

        from app.db import async_session_maker
        from app.models import Checkout, Lead
        from sqlalchemy import select

        async with async_session_maker() as session:
            checkout = await session.scalar(
                select(Checkout).where(Checkout.external_id == eid)
            )
            assert checkout.is_paid is False

            lead = await session.scalar(select(Lead).where(Lead.external_id == eid))
            assert lead.status.value == "checkout"  # should not change
