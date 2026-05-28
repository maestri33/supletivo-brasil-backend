"""Testes para os módulos de integração — request_with_retry, clientes HTTP.

Estratégia:
  - request_with_retry: testa retry em TransportError, sucesso no primeiro
    attempt, e falha 4xx (sem retry).
  - AuthClient, NotifyClient, ProfilesClient: mock httpx.AsyncClient.request
    e verifica chamadas HTTP e parsing JSON.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
import pytest

pytestmark = pytest.mark.asyncio


def _mock_response(status=200, json_data=None, is_success=True):
    """Helper: cria um Mock que simula httpx.Response."""
    m = MagicMock()
    m.status_code = status
    m.is_success = is_success
    m.json = MagicMock(return_value=json_data or {})
    if not is_success:
        m.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"{status}", request=MagicMock(), response=m
        )
    return m


# ═══════════════════════════════════════════════════════════════════════════════
# request_with_retry
# ═══════════════════════════════════════════════════════════════════════════════


class TestRequestWithRetry:
    """request_with_retry — chamada HTTP com retry e log."""

    async def test_success_on_first_attempt(self):
        from app.integrations import request_with_retry

        mock_resp = _mock_response(json_data={"ok": True})
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_resp)

        resp = await request_with_retry(mock_client, "GET", "/api/v1/test")
        assert resp is mock_resp
        mock_client.request.assert_awaited_once_with("GET", "/api/v1/test")

    async def test_retry_on_transport_error_then_success(self):
        from app.integrations import request_with_retry

        mock_resp = _mock_response(json_data={"ok": True})
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(
            side_effect=[
                httpx.TransportError("Connection reset"),
                mock_resp,
            ]
        )

        resp = await request_with_retry(mock_client, "GET", "/test", max_retries=2)
        assert resp is mock_resp
        assert mock_client.request.await_count == 2

    async def test_retry_on_timeout_then_success(self):
        from app.integrations import request_with_retry

        mock_resp = _mock_response(json_data={"ok": True})
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(
            side_effect=[
                httpx.TimeoutException("timeout"),
                mock_resp,
            ]
        )

        resp = await request_with_retry(mock_client, "GET", "/test", max_retries=2)
        assert resp is mock_resp
        assert mock_client.request.await_count == 2

    async def test_raises_on_all_retries_exhausted(self):
        from app.integrations import IntegrationError, request_with_retry

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=httpx.TransportError("Connection refused"))

        with pytest.raises(IntegrationError) as exc:
            await request_with_retry(mock_client, "GET", "/test", max_retries=3)
        assert "failed after 3 attempts" in str(exc.value)

    async def test_4xx_raises_immediately_no_retry(self):
        from app.integrations import request_with_retry

        mock_resp = _mock_response(status=400, is_success=False)
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_resp)

        with pytest.raises(httpx.HTTPStatusError):
            await request_with_retry(mock_client, "GET", "/test", max_retries=3)
        assert mock_client.request.await_count == 1


# ═══════════════════════════════════════════════════════════════════════════════
# AuthClient
# ═══════════════════════════════════════════════════════════════════════════════


class TestAuthClient:
    """AuthClient — check, login, register."""

    async def test_check_with_cpf(self):
        from app.integrations.auth import AuthClient

        mock_resp = _mock_response(json_data={"otp_sent": True})
        mock_http = AsyncMock()
        mock_http.request = AsyncMock(return_value=mock_resp)

        client = AuthClient(mock_http)
        result = await client.check(cpf="12345678901")
        assert result == {"otp_sent": True}

    async def test_check_with_phone_and_external_id(self):
        from app.integrations.auth import AuthClient

        mock_resp = _mock_response(json_data={"otp_sent": True})
        mock_http = AsyncMock()
        mock_http.request = AsyncMock(return_value=mock_resp)

        client = AuthClient(mock_http)
        result = await client.check(phone="11999999999", external_id=str(uuid4()))
        assert result == {"otp_sent": True}

    async def test_login(self):
        from app.integrations.auth import AuthClient

        mock_resp = _mock_response(json_data={"access_token": "eyJ..."})
        mock_http = AsyncMock()
        mock_http.request = AsyncMock(return_value=mock_resp)

        eid = str(uuid4())
        client = AuthClient(mock_http)
        result = await client.login(eid, "123456")
        assert result["access_token"] == "eyJ..."

    async def test_register(self):
        from app.integrations.auth import AuthClient

        eid = str(uuid4())
        mock_resp = _mock_response(json_data={"external_id": eid})
        mock_http = AsyncMock()
        mock_http.request = AsyncMock(return_value=mock_resp)

        client = AuthClient(mock_http)
        result = await client.register("11999999999", "12345678901")
        assert result["external_id"] == eid


# ═══════════════════════════════════════════════════════════════════════════════
# NotifyClient
# ═══════════════════════════════════════════════════════════════════════════════


class TestNotifyClient:
    """NotifyClient — get_contact, update_email, send_message."""

    async def test_get_contact(self):
        from app.integrations.notify import NotifyClient

        eid = str(uuid4())
        mock_resp = _mock_response(json_data={"phone": "11999999999", "email": "a@b.com"})
        mock_http = AsyncMock()
        mock_http.request = AsyncMock(return_value=mock_resp)

        client = NotifyClient(mock_http)
        result = await client.get_contact(eid)
        assert result["phone"] == "11999999999"
        assert result["email"] == "a@b.com"

    async def test_update_email(self):
        from app.integrations.notify import NotifyClient

        eid = str(uuid4())
        mock_resp = _mock_response(json_data={"email": "new@email.com"})
        mock_http = AsyncMock()
        mock_http.request = AsyncMock(return_value=mock_resp)

        client = NotifyClient(mock_http)
        result = await client.update_email(eid, "new@email.com")
        assert result["email"] == "new@email.com"

    async def test_send_message_with_webhook(self):
        from app.integrations.notify import NotifyClient

        mock_resp = _mock_response(json_data={"id": 42})
        mock_http = AsyncMock()
        mock_http.request = AsyncMock(return_value=mock_resp)

        eid = str(uuid4())
        client = NotifyClient(mock_http)
        result = await client.send_message(
            eid,
            "Hello",
            title="Welcome",
            media_url="data:image/png;base64,abc",
            webhook_url="http://callback.url",
        )
        assert result["id"] == 42
        assert client.last_message_id == 42

    async def test_send_message_with_all_options(self):
        from app.integrations.notify import NotifyClient

        mock_resp = _mock_response(json_data={"message_id": 99})
        mock_http = AsyncMock()
        mock_http.request = AsyncMock(return_value=mock_resp)

        eid = str(uuid4())
        client = NotifyClient(mock_http)
        result = await client.send_message(
            eid,
            "Hello",
            instruction="urgent",
            flags={"tts": True},
            max_retries=2,
        )
        assert result["message_id"] == 99
        assert client.last_message_id == 99


# ═══════════════════════════════════════════════════════════════════════════════
# ProfilesClient
# ═══════════════════════════════════════════════════════════════════════════════


class TestProfilesClient:
    """ProfilesClient — get_one, first_name, patch."""

    async def test_get_one(self):
        from app.integrations.profiles import ProfilesClient

        eid = str(uuid4())
        mock_resp = _mock_response(json_data={"cpf": "12345678901", "name": "João"})
        mock_http = AsyncMock()
        mock_http.request = AsyncMock(return_value=mock_resp)

        client = ProfilesClient(mock_http)
        result = await client.get_one(eid)
        assert result["cpf"] == "12345678901"

    async def test_first_name(self):
        from app.integrations.profiles import ProfilesClient

        eid = str(uuid4())
        mock_resp = _mock_response(json_data={"first_name": "Maria"})
        mock_http = AsyncMock()
        mock_http.request = AsyncMock(return_value=mock_resp)

        client = ProfilesClient(mock_http)
        result = await client.first_name(eid)
        assert result["first_name"] == "Maria"

    async def test_patch(self):
        from app.integrations.profiles import ProfilesClient

        eid = str(uuid4())
        mock_resp = _mock_response(json_data={"email": "updated@email.com"})
        mock_http = AsyncMock()
        mock_http.request = AsyncMock(return_value=mock_resp)

        client = ProfilesClient(mock_http)
        result = await client.patch(eid, email="updated@email.com")
        assert result["email"] == "updated@email.com"


# ═══════════════════════════════════════════════════════════════════════════════
# Notify Handlers
# ═══════════════════════════════════════════════════════════════════════════════


class TestNotifyHandlers:
    """notify_lead_captured, notify_promoter_captured, notify_lead_completed."""

    async def test_notify_lead_completed_sends_two_messages(self):
        """Pagamento confirmado → lead_completed + lead_receipt."""
        from app.notify.handlers import notify_lead_completed

        eid = str(uuid4())
        mock_contact_resp = _mock_response(is_success=False)

        with (
            patch("app.notify.handlers.notify_and_track", new_callable=AsyncMock) as mock_nt,
            patch("httpx.AsyncClient") as mock_client_cls,
        ):
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__.return_value.get = AsyncMock(return_value=mock_contact_resp)
            mock_client_cls.return_value = mock_ctx

            await notify_lead_completed(
                eid,
                "https://receipt.example.com/recibo.pdf",
                capture_method="credit_card",
                installments=2,
                amount_cents=50000,
            )

        assert mock_nt.await_count == 2
        calls = mock_nt.await_args_list
        assert calls[0][0][0] == eid  # first positional arg (external_id)
        assert calls[0][0][1] is not None  # second positional arg (content)
        assert "lead_completed" in str(calls[0])
        assert "lead_receipt" in str(calls[1])

    async def test_notify_lead_completed_pix_with_name(self):
        """PIX com nome do lead."""
        from app.notify.handlers import notify_lead_completed

        eid = str(uuid4())
        mock_contact_resp = AsyncMock()
        mock_contact_resp.is_success = True
        mock_contact_resp.json = AsyncMock(return_value={"first_name": "Ana"})

        with (
            patch("app.notify.handlers.notify_and_track", new_callable=AsyncMock),
            patch("httpx.AsyncClient") as mock_client_cls,
        ):
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__.return_value.get = AsyncMock(return_value=mock_contact_resp)
            mock_client_cls.return_value = mock_ctx

            await notify_lead_completed(eid, "", capture_method="pix")

    async def test_notify_promoter_captured_skips_sentinel(self):
        """promoter_id sentinel → skip sem notificacao."""
        from app.notify.handlers import notify_promoter_captured

        with patch("app.notify.handlers.notify_and_track", new_callable=AsyncMock) as mock_nt:
            await notify_promoter_captured(
                str(uuid4()),
                "11999999999",
                "00000000-0000-0000-0000-000000000000",
            )
        mock_nt.assert_not_awaited()

    async def test_notify_promoter_captured_sends_notification(self):
        """promoter_id valido → envia notificacao."""
        from app.notify.handlers import notify_promoter_captured

        eid = str(uuid4())
        promoter_id = str(uuid4())

        with (
            patch("app.notify.handlers.notify_and_track", new_callable=AsyncMock) as mock_nt,
            patch("httpx.AsyncClient") as mock_client_cls,
        ):
            mock_contact_resp = AsyncMock()
            mock_contact_resp.is_success = False
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__.return_value.get = AsyncMock(return_value=mock_contact_resp)
            mock_client_cls.return_value = mock_ctx

            await notify_promoter_captured(eid, "11999999999", promoter_id)

        mock_nt.assert_awaited_once()
        assert mock_nt.await_args[0][0] == promoter_id
