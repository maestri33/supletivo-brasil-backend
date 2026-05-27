"""Testes unitarios para modelos do lead service.

Cobre: Lead, LeadStatus, Checkout, Message — criacao, enums, defaults.
"""

import pytest
from uuid import uuid4

from app.models import Lead, LeadStatus, Checkout, Message
from app.db import async_session_maker


class TestLeadStatus:
    """Enum LeadStatus — valores e comportamento."""

    def test_status_values(self):
        assert LeadStatus.CAPTURED.value == "captured"
        assert LeadStatus.WAITING.value == "waiting"
        assert LeadStatus.CHECKOUT.value == "checkout"
        assert LeadStatus.COMPLETED.value == "completed"

    def test_status_from_string(self):
        assert LeadStatus("captured") == LeadStatus.CAPTURED
        assert LeadStatus("waiting") == LeadStatus.WAITING

    def test_status_invalid_raises(self):
        with pytest.raises(ValueError):
            LeadStatus("invalid")


@pytest.mark.asyncio
class TestLeadModel:
    """Model Lead — criacao, defaults, persistencia."""

    async def test_create_lead_default_status(self):
        ext_id = uuid4()
        async with async_session_maker() as session:
            lead = Lead(external_id=ext_id)
            session.add(lead)
            await session.commit()
            await session.refresh(lead)

            assert lead.id is not None
            assert lead.external_id == ext_id
            assert lead.status == LeadStatus.CAPTURED  # default
            assert lead.promoter_external_id is None
            assert lead.created_at is not None
            assert lead.updated_at is not None

    async def test_create_lead_with_promoter(self):
        ext_id = uuid4()
        promoter_id = uuid4()
        async with async_session_maker() as session:
            lead = Lead(
                external_id=ext_id,
                status=LeadStatus.WAITING,
                promoter_external_id=promoter_id,
            )
            session.add(lead)
            await session.commit()
            await session.refresh(lead)

            assert lead.status == LeadStatus.WAITING
            assert lead.promoter_external_id == promoter_id

    async def test_lead_repr(self):
        ext_id = uuid4()
        lead = Lead(external_id=ext_id, status=LeadStatus.CAPTURED)
        repr_str = repr(lead)
        assert "Lead" in repr_str
        assert "captured" in repr_str

    async def test_lead_external_id_unique(self):
        """external_id deve ser unico."""
        ext_id = uuid4()
        async with async_session_maker() as session:
            session.add(Lead(external_id=ext_id))
            await session.commit()

            session.add(Lead(external_id=ext_id))
            with pytest.raises(Exception):  # IntegrityError
                await session.commit()
            await session.rollback()


@pytest.mark.asyncio
class TestCheckoutModel:
    """Model Checkout — criacao, defaults, persistencia."""

    async def test_create_checkout_defaults(self):
        ext_id = uuid4()
        async with async_session_maker() as session:
            checkout = Checkout(external_id=ext_id)
            session.add(checkout)
            await session.commit()
            await session.refresh(checkout)

            assert checkout.id is not None
            assert checkout.external_id == ext_id
            assert checkout.is_paid is False  # default
            assert checkout.payment_method is None
            assert checkout.provider is None
            assert checkout.created_at is not None

    async def test_create_checkout_pix(self):
        from datetime import date
        ext_id = uuid4()
        async with async_session_maker() as session:
            checkout = Checkout(
                external_id=ext_id,
                payment_method="pix",
                provider="asaas",
                qrcode_payload="000201...",
                qrcode_image="/media/qrcodes/test.png",
                due_date=date(2026, 6, 15),
            )
            session.add(checkout)
            await session.commit()
            await session.refresh(checkout)

            assert checkout.payment_method == "pix"
            assert checkout.provider == "asaas"
            assert checkout.qrcode_payload == "000201..."
            assert checkout.is_paid is False

    async def test_create_checkout_credit_card(self):
        ext_id = uuid4()
        async with async_session_maker() as session:
            checkout = Checkout(
                external_id=ext_id,
                payment_method="credit_card",
                provider="infinitepay",
                checkout_url="https://infinitepay/checkout/123",
                installments=3,
                capture_method="ecommerce",
            )
            session.add(checkout)
            await session.commit()
            await session.refresh(checkout)

            assert checkout.payment_method == "credit_card"
            assert checkout.installments == 3
            assert checkout.checkout_url == "https://infinitepay/checkout/123"

    async def test_checkout_is_paid_toggle(self):
        ext_id = uuid4()
        async with async_session_maker() as session:
            checkout = Checkout(external_id=ext_id)
            session.add(checkout)
            await session.commit()

            checkout.is_paid = True
            await session.commit()
            await session.refresh(checkout)
            assert checkout.is_paid is True

    async def test_checkout_repr(self):
        checkout = Checkout(external_id=uuid4(), payment_method="pix")
        repr_str = repr(checkout)
        assert "Checkout" in repr_str
        assert "pix" in repr_str


@pytest.mark.asyncio
class TestMessageModel:
    """Model Message — criacao, defaults, persistencia."""

    async def test_create_message_outbound(self):
        ext_id = uuid4()
        async with async_session_maker() as session:
            msg = Message(
                external_id=ext_id,
                direction="out",
                channel="whatsapp",
                content="Bem-vindo!",
                status="sent",
                event="message.sent",
            )
            session.add(msg)
            await session.commit()
            await session.refresh(msg)

            assert msg.id is not None
            assert msg.direction == "out"
            assert msg.channel == "whatsapp"
            assert msg.content == "Bem-vindo!"
            assert msg.status == "sent"
            assert msg.created_at is not None

    async def test_create_message_inbound(self):
        ext_id = uuid4()
        async with async_session_maker() as session:
            msg = Message(
                external_id=ext_id,
                message_id=42,
                direction="in",
                channel="whatsapp",
                status="delivered",
                event="message.delivered",
                meta={"delivery_status": "read"},
            )
            session.add(msg)
            await session.commit()
            await session.refresh(msg)

            assert msg.message_id == 42
            assert msg.direction == "in"
            assert msg.meta == {"delivery_status": "read"}

    async def test_message_default_direction(self):
        ext_id = uuid4()
        async with async_session_maker() as session:
            msg = Message(external_id=ext_id)
            session.add(msg)
            await session.commit()
            await session.refresh(msg)

            assert msg.direction == "out"  # default
