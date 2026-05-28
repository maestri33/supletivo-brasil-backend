"""Testes do endpoint /api/v1/recover.

Nao depende de DB nem de servicos externos reais — monkeypatcha as funcoes de
lookup e fornece um redis fake quando necessario para testar rate limit.

COD-32: respostas uniformizadas — nunca diferencia found=true/false.
External_id nunca eh retornado na resposta.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api import check as check_module
from app.api import recover as recover_module
from app.main import app

VALID_CPF = "39053344705"  # CPF valido sintetico (passa digito verificador)
VALID_PHONE = "11999999999"
INVALID_CPF = "11111111111"
INVALID_PHONE = "123"
KNOWN_EID = "11111111-1111-1111-1111-111111111111"


class FakeRedis:
    """Fake redis com SET NX EX e TTL — suficiente para rate limit do recover."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._ttl: dict[str, int] = {}

    async def set(self, key: str, value: str, nx: bool = False, ex: int = 0):
        if nx and key in self._store:
            return None
        self._store[key] = value
        self._ttl[key] = ex
        return True

    async def ttl(self, key: str) -> int:
        return self._ttl.get(key, -1)


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    app.state.redis = None
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.state.redis = None


@pytest_asyncio.fixture
async def client_with_redis():
    transport = ASGITransport(app=app)
    app.state.redis = FakeRedis()
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.state.redis = None


@pytest.fixture
def patched_lookups(monkeypatch):
    """Monkeypatcha lookups e dispatch para nao bater em servicos externos."""
    state = {"otp_calls": 0}

    async def fake_lookup_cpf(cpf: str) -> dict:
        if cpf == VALID_CPF:
            return {"found": True, "external_id": KNOWN_EID, "valid": True}
        return {"found": False, "valid": True}

    async def fake_lookup_phone(phone: str) -> dict:
        if phone == VALID_PHONE:
            return {"found": True, "external_id": KNOWN_EID, "phone_valid": True}
        return {"found": False, "phone_valid": True}

    async def fake_dispatch_otp(external_id: str) -> None:
        state["otp_calls"] += 1

    monkeypatch.setattr(recover_module, "lookup_cpf", fake_lookup_cpf)
    monkeypatch.setattr(recover_module, "lookup_phone", fake_lookup_phone)
    monkeypatch.setattr(recover_module, "dispatch_otp", fake_dispatch_otp)
    monkeypatch.setattr(check_module, "dispatch_otp", fake_dispatch_otp)
    return state


# ── Validacao de entrada ──────────────────────────────


@pytest.mark.asyncio
async def test_recover_requires_cpf_or_phone(client: AsyncClient, patched_lookups):
    resp = await client.post("/api/v1/recover", json={})
    assert resp.status_code == 422
    assert resp.json()["code"] == "MISSING_FIELD"


@pytest.mark.asyncio
async def test_recover_rejects_invalid_cpf(client: AsyncClient, patched_lookups):
    resp = await client.post("/api/v1/recover", json={"cpf": INVALID_CPF})
    assert resp.status_code == 422
    assert resp.json()["code"] == "CPF_INVALID"


@pytest.mark.asyncio
async def test_recover_rejects_invalid_phone(client: AsyncClient, patched_lookups):
    resp = await client.post("/api/v1/recover", json={"phone": INVALID_PHONE})
    assert resp.status_code == 422
    assert resp.json()["code"] == "PHONE_INVALID"


# ── Lookup nao encontrado — resposta uniforme (COD-32) ─


@pytest.mark.asyncio
async def test_recover_cpf_not_found_returns_uniform(client: AsyncClient, patched_lookups):
    """CPF nao cadastrado retorna mesma resposta que cadastrado (COD-32)."""
    resp = await client.post("/api/v1/recover", json={"cpf": "11144477735"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is True
    assert body["otp_sent"] is True


@pytest.mark.asyncio
async def test_recover_phone_not_found_returns_uniform(client: AsyncClient, patched_lookups):
    """Phone nao cadastrado retorna mesma resposta que cadastrado (COD-32)."""
    resp = await client.post("/api/v1/recover", json={"phone": "11988887777"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is True
    assert body["otp_sent"] is True


# ── Happy path (sem redis = sem rate limit) ───────────


@pytest.mark.asyncio
async def test_recover_cpf_found_dispatches_otp(client: AsyncClient, patched_lookups):
    resp = await client.post("/api/v1/recover", json={"cpf": VALID_CPF})
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"found": True, "otp_sent": True}
    assert patched_lookups["otp_calls"] == 1


@pytest.mark.asyncio
async def test_recover_phone_found_dispatches_otp(client: AsyncClient, patched_lookups):
    resp = await client.post("/api/v1/recover", json={"phone": VALID_PHONE})
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"found": True, "otp_sent": True}
    assert patched_lookups["otp_calls"] == 1


# ── Rate limit (com redis fake) ───────────────────────


@pytest.mark.asyncio
async def test_recover_rate_limits_second_dispatch(
    client_with_redis: AsyncClient,
    patched_lookups,
):
    # 1a chamada: dispara OTP
    resp1 = await client_with_redis.post("/api/v1/recover", json={"cpf": VALID_CPF})
    assert resp1.status_code == 200
    assert resp1.json()["otp_sent"] is True
    assert patched_lookups["otp_calls"] == 1

    # 2a chamada imediata: rate-limited
    resp2 = await client_with_redis.post("/api/v1/recover", json={"cpf": VALID_CPF})
    assert resp2.status_code == 200
    body = resp2.json()
    assert body["found"] is True
    assert "otp_wait" in body
    assert body["otp_wait"] > 0
    # OTP NAO disparado de novo
    assert patched_lookups["otp_calls"] == 1


@pytest.mark.asyncio
async def test_recover_cpf_and_phone_share_rate_limit(
    client_with_redis: AsyncClient,
    patched_lookups,
):
    # Achar via cpf dispara OTP
    resp1 = await client_with_redis.post("/api/v1/recover", json={"cpf": VALID_CPF})
    assert resp1.json()["otp_sent"] is True

    # Achar o mesmo usuario via phone rate-limita (mesmo external_id)
    resp2 = await client_with_redis.post("/api/v1/recover", json={"phone": VALID_PHONE})
    body = resp2.json()
    assert body["found"] is True
    assert "otp_wait" in body
    assert patched_lookups["otp_calls"] == 1
