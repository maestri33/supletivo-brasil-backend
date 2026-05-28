"""Testes para webhooks — notify, infinitepay, asaas-charge.

Estratégia:
  - Webhooks não dependem de auth HTTP externa direta (usam BackgroundTasks
    para operações assíncronas como notify_lead_completed, notify_enrollment,
    notify_promoter_completed).
  - Testamos a mutação no DB (criação de Message, atualização de Lead/Checkout)
    e retorno HTTP.
  - BackgroundTasks são mockados pois precisariam de serviços externos.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.models import Checkout, Lead, LeadStatus

pytestmark = pytest.mark.asyncio


# ── POST /api/v1/webhook/notify/{message_id} ────────────────────────────────


class TestNotifyWebhook:
    """POST /api/v1/webhook/notify/{message_id} — callback do Notify."""

    async def test_notify_callback_message_delivered(self, client):
        """Webhook de message.delivered cria Message in + atualiza Message out."""
        eid = uuid4()

        # Primeiro, criar Message out (envio)
        from app.db import async_session_maker
        from app.models import Message as Msg

        async with async_session_maker() as session:
            session.add(
                Msg(
                    message_id=42,
                    external_id=eid,
                    direction="out",
                    channel="whatsapp",
                    status="sent",
                    event="message.sent",
                )
            )
            await session.commit()

        # Webhook de delivered
        resp = await client.post(
            "/api/v1/webhook/notify/42",
            json={
                "event": "message.delivered",
                "message_id": 42,
                "contact_id": 1,
                "external_id": str(eid),
                "type": "whatsapp",
                "whatsapp_status": "delivered",
            },
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["ok"] is True

        # Verificar Message in foi criada
        async with async_session_maker() as session:
            from sqlalchemy import select

            msgs_in = (
                (
                    await session.execute(
                        select(Msg).where(Msg.message_id == 42, Msg.direction == "in")
                    )
                )
                .scalars()
                .all()
            )
            assert len(msgs_in) == 1
            assert msgs_in[0].status == "delivered"

            # Message out foi atualizada
            msg_out = await session.scalar(
                select(Msg).where(Msg.message_id == 42, Msg.direction == "out")
            )
            assert msg_out is not None
            assert msg_out.status == "delivered"

    async def test_notify_callback_tts(self, client):
        """Webhook TTS com tts_audio_url."""
        eid = uuid4()
        resp = await client.post(
            "/api/v1/webhook/notify/99",
            json={
                "event": "tts.completed",
                "message_id": 99,
                "contact_id": 2,
                "external_id": str(eid),
                "type": "tts",
                "tts_audio_url": "https://audio.example.com/msg.mp3",
            },
        )
        assert resp.status_code == 202


# ── POST /api/v1/webhook/infinitepay ────────────────────────────────────────


class TestInfinitepayWebhook:
    """POST /api/v1/webhook/infinitepay — callback de pagamento cartão."""

    async def test_infinitepay_paid_updates_checkout_and_lead(
        self, client, make_lead, make_checkout
    ):
        """Pagamento confirmado → checkout.is_paid=true + lead → COMPLETED."""
        eid = uuid4()
        lead_id = await make_lead(external_id=eid, status="checkout")  # noqa: F841
        await make_checkout(external_id=eid, payment_method="credit_card", provider="infinitepay")

        with (
            patch(
                "app.api.demilitarized.webhooks.notify_lead_completed", new_callable=AsyncMock
            ) as mock_completed,
            patch(
                "app.api.demilitarized.webhooks.notify_enrollment", new_callable=AsyncMock
            ) as mock_enroll,
            patch(
                "app.api.demilitarized.webhooks.notify_promoter_completed", new_callable=AsyncMock
            ),
        ):
            resp = await client.post(
                "/api/v1/webhook/infinitepay",
                json={
                    "external_id": str(eid),
                    "paid": True,
                    "receipt_url": "https://receipt.example.com/123",
                    "transaction_nsu": "nsu123",
                    "capture_method": "credit_card",
                    "installments": 4,
                    "amount": 50000,
                    "paid_amount": 50000,
                },
            )
            assert resp.status_code == 202

            # Verificar checkout
            from app.db import async_session_maker
            from sqlalchemy import select

            async with async_session_maker() as session:
                checkout = await session.scalar(select(Checkout).where(Checkout.external_id == eid))
                assert checkout is not None
                assert checkout.is_paid is True
                assert checkout.receipt_url == "https://receipt.example.com/123"
                assert checkout.transaction_nsu == "nsu123"

                lead = await session.scalar(select(Lead).where(Lead.external_id == eid))
                assert lead is not None
                assert lead.status == LeadStatus.COMPLETED

            # BackgroundTasks foram registradas
            mock_completed.assert_awaited_once()
            mock_enroll.assert_awaited_once()

    async def test_infinitepay_not_paid_does_not_change_lead(
        self, client, make_lead, make_checkout
    ):
        """Webhook com paid=false não transiciona lead."""
        eid = uuid4()
        await make_lead(external_id=eid, status="checkout")
        await make_checkout(
            external_id=eid, is_paid=False, payment_method="credit_card", provider="infinitepay"
        )

        with (
            patch(
                "app.api.demilitarized.webhooks.notify_lead_completed", new_callable=AsyncMock
            ) as mock_completed,
            patch("app.api.demilitarized.webhooks.notify_enrollment", new_callable=AsyncMock),
            patch(
                "app.api.demilitarized.webhooks.notify_promoter_completed", new_callable=AsyncMock
            ),
        ):
            resp = await client.post(
                "/api/v1/webhook/infinitepay",
                json={
                    "external_id": str(eid),
                    "paid": False,
                },
            )
            assert resp.status_code == 202

            from app.db import async_session_maker
            from sqlalchemy import select

            async with async_session_maker() as session:
                lead = await session.scalar(select(Lead).where(Lead.external_id == eid))
                assert lead is not None
                assert lead.status == LeadStatus.CHECKOUT  # Nao mudou

            # Não deve ter chamado notify_lead_completed
            mock_completed.assert_not_awaited()

    async def test_infinitepay_with_promoter_triggers_notify(
        self, client, make_lead, make_checkout
    ):
        """Lead com promoter → dispara notify_promoter_completed também."""
        eid = uuid4()
        promoter_id = uuid4()
        await make_lead(external_id=eid, status="checkout", promoter_external_id=promoter_id)
        await make_checkout(external_id=eid, payment_method="credit_card", provider="infinitepay")

        with (
            patch("app.api.demilitarized.webhooks.notify_lead_completed", new_callable=AsyncMock),
            patch("app.api.demilitarized.webhooks.notify_enrollment", new_callable=AsyncMock),
            patch(
                "app.api.demilitarized.webhooks.notify_promoter_completed", new_callable=AsyncMock
            ) as mock_promo,
        ):
            await client.post(
                "/api/v1/webhook/infinitepay",
                json={
                    "external_id": str(eid),
                    "paid": True,
                },
            )
            mock_promo.assert_awaited_once()

    async def test_infinitepay_no_checkout(self, client):
        """Webhook sem checkout → retorna 202 sem erro."""
        resp = await client.post(
            "/api/v1/webhook/infinitepay",
            json={
                "external_id": str(uuid4()),
                "paid": False,
            },
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["ok"] is True


# ── POST /api/v1/webhook/asaas-charge ───────────────────────────────────────


class TestAsaasChargeWebhook:
    """POST /api/v1/webhook/asaas-charge — callback PIX asaas."""

    async def test_asaas_paid_updates_checkout_and_lead(self, client, make_lead, make_checkout):
        """PIX PAID → checkout.is_paid=true + lead → COMPLETED."""
        eid = uuid4()
        await make_lead(external_id=eid, status="checkout")
        await make_checkout(external_id=eid, payment_method="pix", provider="asaas")

        with (
            patch("app.api.demilitarized.webhooks.notify_lead_completed", new_callable=AsyncMock),
            patch("app.api.demilitarized.webhooks.notify_enrollment", new_callable=AsyncMock),
            patch(
                "app.api.demilitarized.webhooks.notify_promoter_completed", new_callable=AsyncMock
            ),
        ):
            resp = await client.post(
                "/api/v1/webhook/asaas-charge",
                json={
                    "payment_id": "pay_abc123",
                    "kind": "charge",
                    "external_id": str(eid),
                    "status": "PAID",
                },
            )
            assert resp.status_code == 202

            from app.db import async_session_maker
            from sqlalchemy import select

            async with async_session_maker() as session:
                checkout = await session.scalar(select(Checkout).where(Checkout.external_id == eid))
                assert checkout is not None
                assert checkout.is_paid is True
                assert checkout.provider_payment_id == "pay_abc123"

                lead = await session.scalar(select(Lead).where(Lead.external_id == eid))
                assert lead is not None
                assert lead.status == LeadStatus.COMPLETED

    async def test_asaas_charge_pending_no_lead_change(self, client, make_lead, make_checkout):
        """PIX PENDING → checkout continua is_paid=false, lead nao muda."""
        eid = uuid4()
        await make_lead(external_id=eid, status="checkout")
        await make_checkout(external_id=eid, is_paid=False, payment_method="pix", provider="asaas")

        with (
            patch(
                "app.api.demilitarized.webhooks.notify_lead_completed", new_callable=AsyncMock
            ) as mock_completed,
            patch("app.api.demilitarized.webhooks.notify_enrollment", new_callable=AsyncMock),
            patch(
                "app.api.demilitarized.webhooks.notify_promoter_completed", new_callable=AsyncMock
            ),
        ):
            resp = await client.post(
                "/api/v1/webhook/asaas-charge",
                json={
                    "payment_id": "pay_pending",
                    "kind": "charge",
                    "external_id": str(eid),
                    "status": "PENDING",
                },
            )
            assert resp.status_code == 202

            from app.db import async_session_maker
            from sqlalchemy import select

            async with async_session_maker() as session:
                checkout = await session.scalar(select(Checkout).where(Checkout.external_id == eid))
                assert checkout is not None
                assert checkout.is_paid is False

            mock_completed.assert_not_awaited()

    async def test_asaas_onboarding_ping(self, client):
        """Evento ASAAS_APP_ONBOARDING → 202 sem side-effect."""
        resp = await client.post(
            "/api/v1/webhook/asaas-charge",
            json={"event": "ASAAS_APP_ONBOARDING", "target": "http://example.com"},
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["onboarding"] is True

    async def test_asaas_wrong_kind_ignored(self, client):
        """kind diferente de 'charge' → ignorado."""
        resp = await client.post(
            "/api/v1/webhook/asaas-charge",
            json={
                "payment_id": "pay_abc",
                "kind": "subscription",
                "external_id": str(uuid4()),
                "status": "PAID",
            },
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["ignored"] is True

    async def test_asaas_provider_mismatch_ignored(self, client, make_lead, make_checkout):
        """Checkout com provider != asaas → ignorado."""
        eid = uuid4()
        await make_lead(external_id=eid, status="checkout")
        await make_checkout(external_id=eid, payment_method="credit_card", provider="infinitepay")

        resp = await client.post(
            "/api/v1/webhook/asaas-charge",
            json={
                "payment_id": "pay_abc",
                "kind": "charge",
                "external_id": str(eid),
                "status": "PAID",
            },
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["provider_mismatch"] is True
