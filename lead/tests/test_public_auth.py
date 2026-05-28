"""Testes para endpoints públicos de autenticação (check, register, login, refresh).

Estratégia:
  - Mock httpx.AsyncClient no nível de request_with_retry (integrations/__init__.py)
    para evitar chamadas reais para auth/jwt.
  - Testa validação de payload, tratamento de erros e fluxos de sucesso.
  - SQLite in-memory via conftest.py (chamadas ao DB são reais).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
import pytest


pytestmark = pytest.mark.asyncio


# ── Helpers ──────────────────────────────────────────────────────────────────


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ── POST /api/v1/public/check ───────────────────────────────────────────────


class TestCheck:
    """POST /api/v1/public/check — verifica lead e dispara OTP."""

    async def test_check_with_cpf(self, client):
        """Deve passar cpf para auth e retornar otp_sent."""
        with patch("app.api.public.auth.AuthClient.check", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = {"otp_sent": True}
            resp = await client.post("/api/v1/public/check", json={"cpf": "12345678901"})
            assert resp.status_code == 200
            data = resp.json()
            assert data.get("otp_sent") is True
            mock_check.assert_awaited_once_with(cpf="12345678901", phone=None, external_id=None)

    async def test_check_with_phone(self, client):
        """Deve passar phone para auth e retornar otp_sent."""
        with patch("app.api.public.auth.AuthClient.check", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = {"otp_sent": True}
            resp = await client.post("/api/v1/public/check", json={"phone": "11999999999"})
            assert resp.status_code == 200
            data = resp.json()
            assert data.get("otp_sent") is True
            mock_check.assert_awaited_once_with(cpf=None, phone="11999999999", external_id=None)

    async def test_check_with_external_id(self, client):
        """Deve passar external_id para auth."""
        eid = str(uuid4())
        with patch("app.api.public.auth.AuthClient.check", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = {"otp_sent": True}
            resp = await client.post("/api/v1/public/check", json={"external_id": eid})
            assert resp.status_code == 200
            mock_check.assert_awaited_once_with(cpf=None, phone=None, external_id=eid)

    async def test_check_without_any_field_returns_422(self, client):
        """Sem cpf, phone nem external_id → 422."""
        resp = await client.post("/api/v1/public/check", json={})
        assert resp.status_code == 422

    async def test_check_propagates_auth_4xx(self, client):
        """Auth retornando 4xx (ex: PHONE_INVALID) deve propagar status."""
        with patch("app.api.public.auth.AuthClient.check", new_callable=AsyncMock) as mock_check:
            mock_check.side_effect = httpx.HTTPStatusError(
                "400 Bad Request",
                request=httpx.Request("POST", "/api/v1/check"),
                response=httpx.Response(400, json={"detail": "PHONE_INVALID"}),
            )
            resp = await client.post("/api/v1/public/check", json={"phone": "123"})
            assert resp.status_code == 400

    async def test_check_returns_502_on_transport_error(self, client):
        """Falha de transporte → 502 BAD_GATEWAY."""
        with patch("app.api.public.auth.AuthClient.check", new_callable=AsyncMock) as mock_check:
            mock_check.side_effect = httpx.TransportError("Connection refused")
            resp = await client.post("/api/v1/public/check", json={"phone": "11999999999"})
            assert resp.status_code == 502


# ── POST /api/v1/public/register ────────────────────────────────────────────


class TestRegister:
    """POST /api/v1/public/register — cadastra novo lead."""

    async def test_register_success(self, client):
        """Registro com phone+cpf cria lead e retorna external_id."""
        external_id = uuid4()
        with (
            patch("app.api.public.auth.AuthClient.register", new_callable=AsyncMock) as mock_reg,
            patch(
                "app.api.public.auth.notify_lead_captured", new_callable=AsyncMock
            ) as mock_notify,
            patch(
                "app.api.public.auth.notify_promoter_captured", new_callable=AsyncMock
            ) as mock_notify_promo,
        ):
            mock_reg.return_value = {"external_id": str(external_id)}

            resp = await client.post(
                "/api/v1/public/register",
                json={"phone": "11999999999", "cpf": "12345678901"},
            )

            assert resp.status_code == 201
            data = resp.json()
            assert data["external_id"] == str(external_id)
            assert "Cadastro realizado" in data["message"]

            # Verifica se lead foi criado no DB
            from app.models import Lead, LeadStatus
            from app.db import async_session_maker
            from sqlalchemy import select

            async with async_session_maker() as session:
                lead = (
                    await session.execute(select(Lead).where(Lead.external_id == external_id))
                ).scalar_one_or_none()
                assert lead is not None
                assert lead.status == LeadStatus.CAPTURED

            # Notificações devem ter sido disparadas
            mock_notify.assert_awaited_once()
            mock_notify_promo.assert_awaited_once()

    async def test_register_with_reference(self, client):
        """Registro com ref=... associa o promoter_external_id."""
        external_id = uuid4()
        ref_id = uuid4()
        with (
            patch("app.api.public.auth.AuthClient.register", new_callable=AsyncMock) as mock_reg,
            patch("app.api.public.auth.notify_lead_captured", new_callable=AsyncMock),
            patch("app.api.public.auth.notify_promoter_captured", new_callable=AsyncMock),
        ):
            mock_reg.return_value = {"external_id": str(external_id)}
            resp = await client.post(
                "/api/v1/public/register",
                json={"phone": "11999999999", "cpf": "12345678901", "ref": str(ref_id)},
            )
            assert resp.status_code == 201

            from app.models import Lead
            from app.db import async_session_maker
            from sqlalchemy import select

            async with async_session_maker() as session:
                lead = (
                    await session.execute(select(Lead).where(Lead.external_id == external_id))
                ).scalar_one_or_none()
                assert lead is not None
                assert lead.promoter_external_id == ref_id

    async def test_register_propagates_auth_4xx(self, client):
        """Auth retornando 4xx (ex: CPF_ALREADY_EXISTS) deve propagar."""
        with patch("app.api.public.auth.AuthClient.register", new_callable=AsyncMock) as mock_reg:
            mock_reg.side_effect = httpx.HTTPStatusError(
                "409 Conflict",
                request=httpx.Request("POST", "/api/v1/register"),
                response=httpx.Response(409, json={"detail": "CPF_ALREADY_EXISTS"}),
            )
            resp = await client.post(
                "/api/v1/public/register",
                json={"phone": "11999999999", "cpf": "12345678901"},
            )
            assert resp.status_code == 409

    async def test_register_returns_502_on_transport_error(self, client):
        """Falha de transporte no auth → 502."""
        with patch("app.api.public.auth.AuthClient.register", new_callable=AsyncMock) as mock_reg:
            mock_reg.side_effect = httpx.TransportError("Connection refused")
            resp = await client.post(
                "/api/v1/public/register",
                json={"phone": "11999999999", "cpf": "12345678901"},
            )
            assert resp.status_code == 502

    async def test_register_idempotent(self, client):
        """Registrar mesmo external_id 2x retorna 201 sem criar novo lead."""
        external_id = uuid4()
        with (
            patch("app.api.public.auth.AuthClient.register", new_callable=AsyncMock) as mock_reg,
            patch(
                "app.api.public.auth.notify_lead_captured", new_callable=AsyncMock
            ) as mock_notify,
            patch("app.api.public.auth.notify_promoter_captured", new_callable=AsyncMock),
        ):
            mock_reg.return_value = {"external_id": str(external_id)}

            # 1a chamada
            resp1 = await client.post(
                "/api/v1/public/register",
                json={"phone": "11999999999", "cpf": "12345678901"},
            )
            assert resp1.status_code == 201

            # 2a chamada (mesma response do auth)
            mock_reg.return_value = {"external_id": str(external_id)}
            resp2 = await client.post(
                "/api/v1/public/register",
                json={"phone": "11999999999", "cpf": "12345678901"},
            )
            assert resp2.status_code == 201
            assert resp2.json()["external_id"] == str(external_id)

            # Notify só deve ser chamado uma vez (na criação)
            assert mock_notify.await_count == 1

            from app.models import Lead
            from app.db import async_session_maker
            from sqlalchemy import select

            async with async_session_maker() as session:
                leads = (
                    (await session.execute(select(Lead).where(Lead.external_id == external_id)))
                    .scalars()
                    .all()
                )
                assert len(leads) == 1  # Apenas 1 lead


# ── POST /api/v1/public/login ───────────────────────────────────────────────


class TestLogin:
    """POST /api/v1/public/login — valida OTP e retorna tokens."""

    async def test_login_success(self, client):
        """Login com OTP valido retorna tokens + status do lead."""
        with patch("app.api.public.auth.AuthClient.login", new_callable=AsyncMock) as mock_login:
            mock_login.return_value = {
                "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJleHAiOjk5OTk5OTk5OTksInJvbGVzIjpbImxlYWQiXSwiZXh0ZXJuYWxfaWQiOiIxMjM0NTY3OC0xMjM0LTEyMzQtMTIzNC0xMjM0NTY3ODkxMjM0In0.test",
                "refresh_token": "rt_test",
            }

            eid = uuid4()
            resp = await client.post(
                "/api/v1/public/login",
                json={"external_id": str(eid), "otp": "123456"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["access_token"].startswith("eyJ")
            assert data["refresh_token"] == "rt_test"
            assert data["token_type"] == "bearer"

    async def test_login_propagates_auth_4xx(self, client):
        """OTP invalido → propaga 4xx do auth."""
        with patch("app.api.public.auth.AuthClient.login", new_callable=AsyncMock) as mock_login:
            mock_login.side_effect = httpx.HTTPStatusError(
                "401 Unauthorized",
                request=httpx.Request("POST", "/api/v1/login"),
                response=httpx.Response(401, json={"detail": "INVALID_OTP"}),
            )
            eid = uuid4()
            resp = await client.post(
                "/api/v1/public/login",
                json={"external_id": str(eid), "otp": "000000"},
            )
            assert resp.status_code == 401


# ── POST /api/v1/public/refresh ─────────────────────────────────────────────


class TestRefresh:
    """POST /api/v1/public/refresh — renova tokens JWT."""

    async def test_refresh_success(self, client):
        """Refresh com token valido retorna novos tokens."""
        with patch(
            "app.api.public.auth.JwtClient.refresh_token", new_callable=AsyncMock
        ) as mock_refresh:
            mock_refresh.return_value = {
                "access_token": "eyJnew_access",
                "refresh_token": "rt_new",
            }
            resp = await client.post(
                "/api/v1/public/refresh",
                json={"refresh_token": "rt_old"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["access_token"] == "eyJnew_access"
            assert data["refresh_token"] == "rt_new"
            assert data["token_type"] == "bearer"

    async def test_refresh_invalid_token(self, client):
        """Refresh token invalido → 4xx."""
        with patch(
            "app.api.public.auth.JwtClient.refresh_token", new_callable=AsyncMock
        ) as mock_refresh:
            mock_refresh.side_effect = httpx.HTTPStatusError(
                "401 Unauthorized",
                request=httpx.Request("POST", "/api/v1/refresh"),
                response=httpx.Response(401, json={"detail": "TOKEN_EXPIRED"}),
            )
            resp = await client.post(
                "/api/v1/public/refresh",
                json={"refresh_token": "rt_invalid"},
            )
            assert resp.status_code == 401
