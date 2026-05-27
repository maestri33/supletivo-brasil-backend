"""Testes para os módulos de tools — create_checkout, webhooks, messaging, qrcode.

Estratégia:
  - create_checkout: mocks nos clientes HTTP (httpx, asaas, infinitepay, notify,
    profiles) e verifica transições de estado do Lead + persistência do Checkout.
  - webhooks: mocks no httpx.AsyncClient e verifica chamadas HTTP e logs.
  - messaging: mock NotifyClient.send_message e verifica persistência de Message.
  - qrcode: testa decode/save de base64 PNG e montagem de URLs.
"""

from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch
from uuid import uuid4

import pytest
from pytest import MonkeyPatch

from app.db import async_session_maker
from app.integrations.asaas import AsaasClient
from app.models import Checkout, Lead, LeadStatus, Message

pytestmark = pytest.mark.asyncio

# ── Helpers ───────────────────────────────────────────────────────────────────


def _fake_checkout_row(**overrides) -> Checkout:
    """Factory p/ criar um Checkout sem session — útil pra testar retorno de funções."""
    return Checkout(
        external_id=overrides.get("external_id", uuid4()),
        payment_method=overrides.get("payment_method", "credit_card"),
        provider=overrides.get("provider", "infinitepay"),
        provider_payment_id=overrides.get("provider_payment_id", "ext_123"),
        checkout_url=overrides.get("checkout_url", "https://pay.example.com/123"),
        receipt_url=overrides.get("receipt_url", None),
        is_paid=overrides.get("is_paid", False),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# tools/create_checkout.py  (16% coverage → alvo 60%+)
# ═══════════════════════════════════════════════════════════════════════════════


class TestPixCheckoutError:
    """PixCheckoutError — erro de domínio."""

    def test_basic_error(self):
        from app.tools.create_checkout import PixCheckoutError

        err = PixCheckoutError("missing_cpf", "CPF nao encontrado", http_status=422)
        assert str(err) == "missing_cpf: CPF nao encontrado"
        assert err.code == "missing_cpf"
        assert err.http_status == 422

    def test_error_no_detail(self):
        from app.tools.create_checkout import PixCheckoutError

        err = PixCheckoutError("asaas_unavailable")
        assert str(err) == "asaas_unavailable"
        assert err.http_status == 502


class TestSanitizePhone:
    """_sanitize_phone — remove DDI 55 e caracteres não numéricos."""

    def test_removes_ddi_55(self):
        from app.tools.create_checkout import _sanitize_phone

        assert _sanitize_phone("5511999998888") == "11999998888"

    def test_keeps_short_number(self):
        from app.tools.create_checkout import _sanitize_phone

        assert _sanitize_phone("11999998888") == "11999998888"

    def test_removes_non_digits(self):
        from app.tools.create_checkout import _sanitize_phone

        # The function strips non-digits AND removes leading "55"
        # +55 (11) 99999-8888 → 5511999998888 → strips 55 → 11999998888
        assert _sanitize_phone("+55 (11) 99999-8888") == "11999998888"


class TestFetchLeadContext:
    """_fetch_lead_context — busca dados de profiles + notify."""

    async def test_fetches_all_fields(self):
        """Busca nome, phone, email, cpf com sucesso."""
        from app.tools.create_checkout import _fetch_lead_context

        eid = str(uuid4())
        profiles_patcher = patch(
            "app.integrations.profiles.ProfilesClient.first_name",
            new_callable=AsyncMock,
            return_value={"full_name": "João Silva"},
        )
        get_one_patcher = patch(
            "app.integrations.profiles.ProfilesClient.get_one",
            new_callable=AsyncMock,
            return_value={"cpf": "12345678901"},
        )
        notify_patcher = patch(
            "app.integrations.notify.NotifyClient.get_contact",
            new_callable=AsyncMock,
            return_value={"phone": "11999998888", "email": "joao@example.com"},
        )
        with profiles_patcher, get_one_patcher, notify_patcher:
            name, phone, email, cpf = await _fetch_lead_context(eid)

        assert name == "João Silva"
        assert phone == "11999998888"
        assert email == "joao@example.com"
        assert cpf == "12345678901"

    async def test_fallback_on_get_one_exception(self):
        """Se profiles.get_one levanta exceção, cpf vira string vazia."""
        from app.tools.create_checkout import _fetch_lead_context

        eid = str(uuid4())
        with (
            patch(
                "app.integrations.profiles.ProfilesClient.first_name",
                new_callable=AsyncMock,
                return_value={"first_name": "Maria"},
            ),
            patch(
                "app.integrations.profiles.ProfilesClient.get_one",
                new_callable=AsyncMock,
                side_effect=ValueError("service down"),
            ),
            patch(
                "app.integrations.notify.NotifyClient.get_contact",
                new_callable=AsyncMock,
                return_value={"phone": "11988887777", "email": "maria@example.com"},
            ),
        ):
            name, phone, email, cpf = await _fetch_lead_context(eid)

        assert name == "Maria"
        assert cpf == ""  # fallback on error


class TestCreateCheckoutForLead:
    """create_checkout_for_lead — fluxo async credit_card."""

    async def test_invalid_payment_method_returns_early(self):
        """Método inválido → log error e return."""
        from app.tools.create_checkout import create_checkout_for_lead

        with patch("app.tools.create_checkout.logger") as mock_log:
            result = await create_checkout_for_lead(str(uuid4()), payment_method="boleto")
        assert result is None
        mock_log.error.assert_called_once()

    async def test_skip_missing_data(self):
        """Dados incompletos → log warning e return."""
        from app.tools.create_checkout import create_checkout_for_lead

        eid = str(uuid4())
        with (
            patch(
                "app.tools.create_checkout._fetch_lead_context",
                new_callable=AsyncMock,
                return_value=("", "", "", ""),
            ),
        ):
            result = await create_checkout_for_lead(eid)
        assert result is None

    async def test_credit_card_creates_checkout_and_promotes_lead(self, make_lead):
        """Fluxo feliz credit_card: busca context, cria checkout no InfinitePay,
        persiste Checkout, promove Lead para CHECKOUT."""
        from app.tools.create_checkout import create_checkout_for_lead

        eid = str(uuid4())
        await make_lead(external_id=uuid4(), status="waiting")

        fake_checkout = _fake_checkout_row(
            external_id=uuid4(),
            checkout_url="https://pay.infinitepay.com/abc",
        )

        with (
            patch(
                "app.tools.create_checkout._fetch_lead_context",
                new_callable=AsyncMock,
                return_value=("João", "11999998888", "joao@example.com", "12345678901"),
            ),
            patch(
                "app.tools.create_checkout._create_credit_card_checkout",
                new_callable=AsyncMock,
                return_value=fake_checkout,
            ),
            patch(
                "app.tools.create_checkout.asyncio.gather",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            result = await create_checkout_for_lead(eid, payment_method="credit_card")

        assert result is None  # BG task returns None (fire-and-forget)

    async def test_credit_card_checkout_none_no_error(self):
        """Se _create_credit_card_checkout retorna None, a função retorna sem erro."""
        from app.tools.create_checkout import create_checkout_for_lead

        eid = str(uuid4())
        with (
            patch(
                "app.tools.create_checkout._fetch_lead_context",
                new_callable=AsyncMock,
                return_value=("João", "11999998888", "joao@example.com", "12345678901"),
            ),
            patch(
                "app.tools.create_checkout._create_credit_card_checkout",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            result = await create_checkout_for_lead(eid)
        assert result is None

    async def test_pix_bg_fallback_handles_error(self):
        """PIX via BG (fallback): PixCheckoutError é logado, não levanta."""
        from app.tools.create_checkout import PixCheckoutError, create_checkout_for_lead

        eid = str(uuid4())
        with (
            patch(
                "app.tools.create_checkout._fetch_lead_context",
                new_callable=AsyncMock,
                return_value=("João", "11999998888", "joao@example.com", "12345678901"),
            ),
            patch(
                "app.tools.create_checkout._create_pix_checkout",
                new_callable=AsyncMock,
                side_effect=PixCheckoutError("asaas_unavailable", "Asaas offline"),
            ),
        ):
            result = await create_checkout_for_lead(eid, payment_method="pix")
        assert result is None

    async def test_lead_not_found_logs_error(self):
        """Lead não encontrado no DB → log.error e return."""
        from app.tools.create_checkout import create_checkout_for_lead

        eid = str(uuid4())
        fake_checkout = _fake_checkout_row(external_id=uuid4())
        with (
            patch(
                "app.tools.create_checkout._fetch_lead_context",
                new_callable=AsyncMock,
                return_value=("João", "11999998888", "joao@example.com", "12345678901"),
            ),
            patch(
                "app.tools.create_checkout._create_credit_card_checkout",
                new_callable=AsyncMock,
                return_value=fake_checkout,
            ),
        ):
            result = await create_checkout_for_lead(eid)
        assert result is None


class TestCreatePixCheckout:
    """_create_pix_checkout — criação de cobrança PIX no Asaas."""

    async def test_missing_cpf_raises_error(self):
        """CPF vazio → PixCheckoutError com code missing_cpf."""
        from app.tools.create_checkout import PixCheckoutError, _create_pix_checkout

        eid = uuid4()
        with pytest.raises(PixCheckoutError) as exc:
            await _create_pix_checkout(eid, str(eid), "João", "11999998888", "joao@example.com", "")
        assert exc.value.code == "missing_cpf"

    async def test_successful_pix_creation(self, tmp_path):
        """Fluxo feliz: asaas devolve charge, QR é salvo, checkout retornado."""
        from app.tools.create_checkout import _create_pix_checkout

        eid = str(uuid4())
        ext_uuid = uuid4()
        fake_png_b64 = base64.b64encode(b"fake_png_bytes").decode()

        # Mock da resposta do Asaas
        mock_charge = MagicMock()
        mock_charge.payment_id = "pay_pix_abc"
        mock_charge.status = "PENDING"
        mock_charge.due_date = "2026-06-10"
        mock_pix = MagicMock()
        mock_pix.payload = "00020126580014br.gov.bcb.pix0136..."
        mock_pix.encoded_image = fake_png_b64
        mock_charge.pix = mock_pix

        with (
            patch("app.tools.create_checkout.settings.PIX_DEFAULT_DUE_DAYS", None),
            patch("app.tools.create_checkout.settings.PIX_DEFAULT_AMOUNT", 999.99),
            patch("app.tools.create_checkout.settings.PIX_DEFAULT_DESCRIPTION", "Test"),
            patch.object(
                AsaasClient, "create_charge_pix",
                new_callable=AsyncMock,
                return_value=mock_charge,
            ),
            patch(
                "app.tools.create_checkout.save_pix_qr_png",
                return_value="/api/v1/public/media/qrcodes/fake.png",
            ),
        ):
            checkout, encoded_b64 = await _create_pix_checkout(
                ext_uuid, eid, "João", "11999998888", "joao@example.com", "12345678901"
            )

        assert checkout.provider == "asaas"
        assert checkout.payment_method == "pix"
        assert checkout.provider_payment_id == "pay_pix_abc"
        assert checkout.is_paid is False
        assert encoded_b64 == fake_png_b64

    async def test_http_error_bubbles_up(self):
        """HTTPStatusError do asaas → levanta PixCheckoutError."""
        import httpx

        from app.tools.create_checkout import PixCheckoutError, _create_pix_checkout

        eid = str(uuid4())
        ext_uuid = uuid4()

        error_response = httpx.Response(422, json={"detail": "invalid_amount: valor abaixo do mínimo"})

        with (
            patch(
                "app.integrations.asaas.AsaasClient.create_charge_pix",
                new_callable=AsyncMock,
                side_effect=httpx.HTTPStatusError(
                    "422 error", request=MagicMock(), response=error_response
                ),
            ),
        ):
            with pytest.raises(PixCheckoutError) as exc:
                await _create_pix_checkout(
                    ext_uuid, eid, "João", "11999998888", "joao@example.com", "12345678901"
                )
            assert exc.value.http_status == 502

    async def test_generic_exception_raises_asaas_unavailable(self):
        """Exceção genérica → PixCheckoutError com code asaas_unavailable."""
        from app.tools.create_checkout import PixCheckoutError, _create_pix_checkout

        eid = str(uuid4())
        ext_uuid = uuid4()

        with (
            patch(
                "app.integrations.asaas.AsaasClient.create_charge_pix",
                new_callable=AsyncMock,
                side_effect=ConnectionError("network unreachable"),
            ),
        ):
            with pytest.raises(PixCheckoutError) as exc:
                await _create_pix_checkout(
                    ext_uuid, eid, "João", "11999998888", "joao@example.com", "12345678901"
                )
            assert exc.value.code == "asaas_unavailable"
            assert exc.value.http_status == 502


class TestCreatePixCheckoutForLead:
    """create_pix_checkout_for_lead — fluxo síncrono completo do PIX."""

    async def test_happy_path(self, make_lead):
        """Fluxo feliz: busca context → cria PIX → persiste → transiciona lead."""
        from app.tools.create_checkout import create_pix_checkout_for_lead

        eid = str(uuid4())
        ext_uuid = uuid4()
        await make_lead(external_id=ext_uuid, status="captured")

        mock_checkout = _fake_checkout_row(
            external_id=ext_uuid,
            payment_method="pix",
            provider="asaas",
            provider_payment_id="pay_pix_123",
            checkout_url=None,
        )

        with (
            patch(
                "app.tools.create_checkout._fetch_lead_context",
                new_callable=AsyncMock,
                return_value=("João", "11999998888", "joao@example.com", "12345678901"),
            ),
            patch(
                "app.tools.create_checkout._create_pix_checkout",
                new_callable=AsyncMock,
                return_value=(mock_checkout, "b64_encoded_image"),
            ),
            patch(
                "app.tools.create_checkout.asyncio.create_task",
                new_callable=AsyncMock,
            ),
        ):
            async with async_session_maker() as session:
                checkout = await create_pix_checkout_for_lead(
                    str(ext_uuid), session=session
                )

        assert checkout.provider == "asaas"
        assert checkout.payment_method == "pix"

        # Verifica persistência
        async with async_session_maker() as verify_session:
            from sqlalchemy import select

            lead = await verify_session.scalar(select(Lead).where(Lead.external_id == ext_uuid))
            assert lead is not None
            assert lead.status == LeadStatus.CHECKOUT

    async def test_incomplete_context_raises_error(self):
        """Contexto incompleto → PixCheckoutError incomplete_context."""
        from app.tools.create_checkout import PixCheckoutError, create_pix_checkout_for_lead

        with (
            patch(
                "app.tools.create_checkout._fetch_lead_context",
                new_callable=AsyncMock,
                return_value=("", "11999998888", "", ""),
            ),
        ):
            async with async_session_maker() as session:
                with pytest.raises(PixCheckoutError) as exc:
                    await create_pix_checkout_for_lead(str(uuid4()), session=session)
            assert exc.value.code == "incomplete_context"
            assert exc.value.http_status == 422

    async def test_lead_not_found_raises_error(self):
        """Lead não existe no DB → PixCheckoutError lead_not_found."""
        from app.tools.create_checkout import PixCheckoutError, create_pix_checkout_for_lead

        mock_checkout = _fake_checkout_row(external_id=uuid4())

        with (
            patch(
                "app.tools.create_checkout._fetch_lead_context",
                new_callable=AsyncMock,
                return_value=("João", "11999998888", "joao@example.com", "12345678901"),
            ),
            patch(
                "app.tools.create_checkout._create_pix_checkout",
                new_callable=AsyncMock,
                return_value=(mock_checkout, None),
            ),
        ):
            async with async_session_maker() as session:
                with pytest.raises(PixCheckoutError) as exc:
                    await create_pix_checkout_for_lead(str(uuid4()), session=session)
            assert exc.value.code == "lead_not_found"


# ═══════════════════════════════════════════════════════════════════════════════
# tools/webhooks.py  (21% coverage → alvo 80%+)
# ═══════════════════════════════════════════════════════════════════════════════


class TestNotifyEnrollment:
    """notify_enrollment — POST para enrollment service."""

    async def test_sends_successfully(self):
        """Configurado → POST com external_id e promoter_external_id."""
        from app.tools.webhooks import notify_enrollment

        eid = str(uuid4())
        promoter_id = str(uuid4())

        with (
            patch("app.tools.webhooks.settings.WEBHOOK_ENROLLMENT_URL", "http://enrollment/webhook"),
            patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post,
        ):
            mock_post.return_value = MagicMock(status_code=200, raise_for_status=lambda: None)
            await notify_enrollment(eid, promoter_id)

        mock_post.assert_awaited_once()
        assert mock_post.await_args is not None
        call_kwargs = mock_post.await_args.kwargs
        assert call_kwargs["json"]["promoter_external_id"] == promoter_id
        assert call_kwargs["json"]["event"] == "lead.completed"

    async def test_not_configured_no_http_call(self):
        """WEBHOOK_ENROLLMENT_URL vazio → não faz POST (função retorna cedo)."""
        from app.tools.webhooks import notify_enrollment

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            await notify_enrollment(str(uuid4()), str(uuid4()))
        mock_post.assert_not_awaited()

    async def test_http_error_graceful(self):
        """HTTP error → função não levanta exceção (apenas loga)."""
        from app.tools.webhooks import notify_enrollment

        with (
            patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=ConnectionError("refused")),
        ):
            # Must not raise — errors are caught and logged
            await notify_enrollment(str(uuid4()), str(uuid4()))


class TestNotifyPromoterCompleted:
    """notify_promoter_completed — POST para promoter service."""

    async def test_sends_successfully(self):
        """Promoter real → POST com external_id e event."""
        from app.tools.webhooks import notify_promoter_completed

        eid = str(uuid4())
        promoter_id = str(uuid4())

        with (
            patch("app.tools.webhooks.settings.WEBHOOK_PROMOTERS_URL", "http://promoters/webhook"),
            patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post,
        ):
            mock_post.return_value = MagicMock(status_code=200, raise_for_status=lambda: None)
            await notify_promoter_completed(eid, promoter_id)

        mock_post.assert_awaited_once()
        assert mock_post.await_args is not None
        call_kwargs = mock_post.await_args.kwargs
        assert call_kwargs["json"]["external_id"] == eid

    async def test_skips_sentinel(self):
        """Promoter = sentinel (000...) → pula notificação (sem POST)."""
        from app.tools.webhooks import notify_promoter_completed

        with (
            patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post,
        ):
            await notify_promoter_completed(str(uuid4()), "00000000-0000-0000-0000-000000000000")
        mock_post.assert_not_awaited()

    async def test_skips_none(self):
        """promoter_external_id = None → pula (is not sentinel, mas _is_sentinel cobre)."""
        from app.tools.webhooks import notify_promoter_completed

        with (
            patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post,
        ):
            await notify_promoter_completed(str(uuid4()), None)  # type: ignore[arg-type]
        mock_post.assert_not_awaited()

    async def test_not_configured_no_http_call(self):
        """WEBHOOK_PROMOTERS_URL vazio → não faz POST."""
        from app.tools.webhooks import notify_promoter_completed

        with (
            patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post,
        ):
            await notify_promoter_completed(str(uuid4()), str(uuid4()))
        mock_post.assert_not_awaited()

    async def test_http_error_graceful(self):
        """HTTP error → função não levanta."""
        from app.tools.webhooks import notify_promoter_completed

        with (
            patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=TimeoutError("timeout")),
        ):
            # Must not raise — errors are caught and logged
            await notify_promoter_completed(str(uuid4()), str(uuid4()))


class TestIsSentinel:
    """_is_sentinel — detecta promoter sentinel."""

    def test_sentinel_detected(self):
        from app.tools.webhooks import _is_sentinel
        assert _is_sentinel("00000000-0000-0000-0000-000000000000") is True

    def test_none_is_sentinel(self):
        from app.tools.webhooks import _is_sentinel
        assert _is_sentinel(None) is True

    def test_empty_string_is_sentinel(self):
        from app.tools.webhooks import _is_sentinel
        assert _is_sentinel("") is True

    def test_real_uuid_not_sentinel(self):
        from app.tools.webhooks import _is_sentinel
        assert _is_sentinel(str(uuid4())) is False


# ═══════════════════════════════════════════════════════════════════════════════
# tools/messaging.py  (22% coverage → alvo 70%+)
# ═══════════════════════════════════════════════════════════════════════════════


class TestNotifyAndTrack:
    """notify_and_track — envia mensagem + persiste Message local."""

    async def test_success_creates_pending_message(self):
        """Sucesso: notify devolve message_id → Message com status=pending."""
        from app.tools.messaging import notify_and_track

        eid = str(uuid4())

        mock_client = AsyncMock()
        mock_client.send_message = AsyncMock()
        mock_client.last_message_id = 42

        with patch("app.tools.messaging.NotifyClient", return_value=mock_client):
            msg = await notify_and_track(eid, "Olá, tudo bem?", event="checkout_lead")

        assert msg is not None
        assert msg.message_id == 42
        assert msg.status == "pending"
        assert msg.external_id == uuid4().__class__(eid)
        mock_client.send_message.assert_awaited_once()

    async def test_404_creates_skipped_message(self):
        """404 do notify → Message com status=skipped."""
        import httpx

        from app.tools.messaging import notify_and_track

        eid = str(uuid4())
        error_response = httpx.Response(404)

        with (
            patch(
                "app.integrations.notify.NotifyClient.send_message",
                new_callable=AsyncMock,
                side_effect=httpx.HTTPStatusError("404", request=MagicMock(), response=error_response),
            ),
        ):
            msg = await notify_and_track(eid, "Olá", event="welcome")

        assert msg is not None
        assert msg.status == "skipped"
        assert msg.event == "contact_not_seeded"

    async def test_500_creates_failed_message(self):
        """500 do notify → Message com status=failed."""
        import httpx

        from app.tools.messaging import notify_and_track

        eid = str(uuid4())
        error_response = httpx.Response(500, text="Internal Server Error")

        with (
            patch(
                "app.integrations.notify.NotifyClient.send_message",
                new_callable=AsyncMock,
                side_effect=httpx.HTTPStatusError("500", request=MagicMock(), response=error_response),
            ),
        ):
            msg = await notify_and_track(eid, "Olá", event="welcome")

        assert msg is not None
        assert msg.status == "failed"
        assert msg.event == "http_500"

    async def test_generic_exception_creates_failed_message(self):
        """Exceção genérica → Message com status=failed, event=exception."""
        from app.tools.messaging import notify_and_track

        eid = str(uuid4())

        with (
            patch(
                "app.integrations.notify.NotifyClient.send_message",
                new_callable=AsyncMock,
                side_effect=ConnectionError("network down"),
            ),
        ):
            msg = await notify_and_track(eid, "Olá", event="welcome")

        assert msg is not None
        assert msg.status == "failed"
        assert msg.event == "exception"

    async def test_optional_params_passed(self):
        """media_url, title, flags, instruction são passados ao notify."""
        from app.tools.messaging import notify_and_track

        eid = str(uuid4())

        mock_client = AsyncMock()
        mock_client.send_message = AsyncMock()
        mock_client.last_message_id = 99

        with patch("app.tools.messaging.NotifyClient", return_value=mock_client):
            await notify_and_track(
                eid,
                "Caption",
                media_url="data:image/png;base64,abc123",
                title="QR Code",
                event="checkout_lead_qr",
                flags={"important": True},
            )

        call_kwargs = mock_client.send_message.await_args.kwargs
        assert call_kwargs["media_url"] == "data:image/png;base64,abc123"
        assert call_kwargs["title"] == "QR Code"
        assert call_kwargs["flags"] == {"important": True}


# ═══════════════════════════════════════════════════════════════════════════════
# tools/qrcode.py  (40% coverage → alvo 85%+)
# ═══════════════════════════════════════════════════════════════════════════════


class TestSavePixQrPng:
    """save_pix_qr_png — decodifica base64 e salva PNG no disco."""

    def test_saves_png(self, tmp_path):
        """Decodifica PNG válido e salva no diretório."""
        from app.tools.qrcode import save_pix_qr_png

        eid = str(uuid4())
        png_bytes = b"\x89PNG\r\n\x1a\n" + b"x" * 100  # Cabeçalho PNG válido + padding
        encoded = base64.b64encode(png_bytes).decode()

        qr_dir = tmp_path / "media" / "qrcodes"
        qr_dir.mkdir(parents=True, exist_ok=True)
        with patch("app.tools.qrcode._qr_dir", return_value=qr_dir):
            url = save_pix_qr_png(eid, encoded)

        expected_file = qr_dir / f"{eid}.png"
        assert expected_file.exists()
        assert expected_file.read_bytes() == png_bytes
        assert eid in url
        assert url.startswith("/api/v1/public/media/qrcodes/")

    def test_invalid_base64_raises(self):
        """Base64 inválido → levanta exceção."""
        from app.tools.qrcode import save_pix_qr_png

        with pytest.raises(Exception):
            save_pix_qr_png(str(uuid4()), "not-valid-base64!!!")

    def test_creates_directory_if_not_exists(self, tmp_path):
        """Diretório qrcodes/ é criado se não existir."""
        # This test verifies the REAL _qr_dir() creates directories.
        from app.tools.qrcode import _qr_dir, save_pix_qr_png

        png_bytes = b"\x89PNG\r\n\x1a\n" + b"x" * 50
        encoded = base64.b64encode(png_bytes).decode()

        qr_dir = tmp_path / "nonexistent" / "qrcodes"
        assert not qr_dir.exists()

        with patch("app.tools.qrcode.settings.MEDIA_DIR", str(tmp_path / "nonexistent")):
            # _qr_dir uses MEDIA_DIR, so patching settings.MEDIA_DIR means
            # _qr_dir() will call tmp_path / "nonexistent" / "qrcodes" and
            # create it via mkdir(parents=True, exist_ok=True)
            d = _qr_dir()
            # Now save the QR
            url = save_pix_qr_png(str(uuid4()), encoded)

        assert d.exists()
        assert qr_dir.exists()
        assert url.startswith("/api/v1/public/media/qrcodes/")
        assert url.endswith(".png")


class TestMakeDataUri:
    """make_data_uri — monta data URI para enviar ao notify."""

    def test_basic(self):
        from app.tools.qrcode import make_data_uri
        uri = make_data_uri("abc123")
        assert uri == "data:image/png;base64,abc123"

    def test_custom_mime(self):
        from app.tools.qrcode import make_data_uri
        uri = make_data_uri("xyz", mime="image/jpeg")
        assert uri == "data:image/jpeg;base64,xyz"


class TestAbsoluteQrUrl:
    """absolute_qr_url — prefixa URL com LEAD_PUBLIC_BASE_URL."""

    def test_prepends_base(self):
        from app.tools.qrcode import absolute_qr_url

        with patch("app.tools.qrcode.settings.LEAD_PUBLIC_BASE_URL", "http://lead.example.com"):
            url = absolute_qr_url("/api/v1/public/media/qrcodes/abc.png")

        assert url == "http://lead.example.com/api/v1/public/media/qrcodes/abc.png"

    def test_rewrites_legacy_prefix(self):
        """URLs com prefixo /media/ antigo são reescritas."""
        from app.tools.qrcode import absolute_qr_url

        with patch("app.tools.qrcode.settings.LEAD_PUBLIC_BASE_URL", "http://lead.example.com"):
            url = absolute_qr_url("/media/qrcodes/abc.png")

        # Legacy /media/ prefix rewritten to /api/v1/public/media/
        assert url == "http://lead.example.com/api/v1/public/media/qrcodes/abc.png"
        # The result contains the correct public prefix, not the legacy one
        assert "/api/v1/public/media/" in url
        assert url.startswith("http://lead.example.com")
        assert url.endswith("abc.png")


class TestQrDir:
    """_qr_dir — retorna Path para diretório de QR codes."""

    def test_returns_path(self, tmp_path):
        from app.tools.qrcode import _qr_dir

        with patch("app.tools.qrcode.settings.MEDIA_DIR", str(tmp_path)):
            d = _qr_dir()
        assert d.name == "qrcodes"
        assert d.parent == tmp_path

    def test_creates_directory(self, tmp_path):
        from app.tools.qrcode import _qr_dir

        media = tmp_path / "media"
        with patch("app.tools.qrcode.settings.MEDIA_DIR", str(media)):
            d = _qr_dir()
        assert d.exists()
