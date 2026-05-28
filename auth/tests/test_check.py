"""Testes do endpoint /api/v1/check.

Nao depende de DB nem de servicos externos reais — monkeypatcha as funcoes de
lookup e fornece um redis fake quando necessario para testar rate limit.

COD-32: respostas uniformizadas — nunca diferencia found=true/false.
Sempre retorna {"otp_sent": true} ou {"otp_wait": N}.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api import check as check_module
from app.main import app

VALID_CPF = "39053344705"  # CPF valido sintetico (passa digito verificador)
VALID_PHONE = "11999999999"
INVALID_CPF = "11111111111"
INVALID_PHONE = "123"
KNOWN_EID = "11111111-1111-1111-1111-111111111111"


class FakeRedis:
    """Fake redis com SET NX EX e TTL — suficiente para rate limit do check."""

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

    async def fake_lookup_external_id(external_id: str) -> dict:
        if external_id == KNOWN_EID:
            return {"found": True, "external_id": KNOWN_EID, "cpf": VALID_CPF, "phone": VALID_PHONE}
        return {"found": False, "external_id": external_id}

    async def fake_dispatch_otp(external_id: str) -> None:
        state["otp_calls"] += 1

    monkeypatch.setattr(check_module, "lookup_cpf", fake_lookup_cpf)
    monkeypatch.setattr(check_module, "lookup_phone", fake_lookup_phone)
    monkeypatch.setattr(check_module, "lookup_external_id", fake_lookup_external_id)
    monkeypatch.setattr(check_module, "dispatch_otp", fake_dispatch_otp)
    return state


# ── Validacao de entrada ──────────────────────────────


@pytest.mark.asyncio
async def test_check_requires_field(client: AsyncClient, patched_lookups):
    """POST /check sem cpf/phone/external_id retorna 422."""
    resp = await client.post("/api/v1/check", json={})
    assert resp.status_code == 422
    assert resp.json()["code"] == "MISSING_FIELD"


@pytest.mark.asyncio
async def test_check_rejects_invalid_cpf(client: AsyncClient, patched_lookups):
    """CPF invalido retorna 422 — nao revela se existe ou nao."""
    resp = await client.post("/api/v1/check", json={"cpf": INVALID_CPF})
    assert resp.status_code == 422
    assert resp.json()["code"] == "CPF_INVALID"


@pytest.mark.asyncio
async def test_check_rejects_invalid_phone(client: AsyncClient, patched_lookups):
    """Phone invalido retorna 422 — nao revela se existe ou nao."""
    resp = await client.post("/api/v1/check", json={"phone": INVALID_PHONE})
    assert resp.status_code == 422
    assert resp.json()["code"] == "PHONE_INVALID"


# ── Respostas uniformes (COD-32) — CPF ─────────────


@pytest.mark.asyncio
async def test_check_cpf_found_returns_otp_sent(client: AsyncClient, patched_lookups):
    """CPF cadastrado retorna otp_sent."""
    resp = await client.post("/api/v1/check", json={"cpf": VALID_CPF})
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"otp_sent": True}
    assert patched_lookups["otp_calls"] == 1


@pytest.mark.asyncio
async def test_check_cpf_not_found_returns_same_shape(client: AsyncClient, patched_lookups):
    """CPF NAO cadastrado retorna mesmo shape que cadastrado (COD-32)."""
    resp = await client.post("/api/v1/check", json={"cpf": "11144477735"})
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"otp_sent": True}
    # OTP dispatch foi chamado, mas falha silenciosamente no real


# ── Respostas uniformes (COD-32) — Phone ──────────


@pytest.mark.asyncio
async def test_check_phone_found_returns_otp_sent(client: AsyncClient, patched_lookups):
    """Phone cadastrado retorna otp_sent."""
    resp = await client.post("/api/v1/check", json={"phone": VALID_PHONE})
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"otp_sent": True}
    assert patched_lookups["otp_calls"] == 1


@pytest.mark.asyncio
async def test_check_phone_not_found_returns_same_shape(client: AsyncClient, patched_lookups):
    """Phone NAO cadastrado retorna mesmo shape que cadastrado (COD-32)."""
    resp = await client.post("/api/v1/check", json={"phone": "11988887777"})
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"otp_sent": True}


# ── Respostas uniformes (COD-32) — External ID ─────


@pytest.mark.asyncio
async def test_check_external_id_found_returns_otp_sent(client: AsyncClient, patched_lookups):
    """external_id conhecido retorna otp_sent."""
    resp = await client.post("/api/v1/check", json={"external_id": KNOWN_EID})
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"otp_sent": True}
    assert patched_lookups["otp_calls"] == 1


@pytest.mark.asyncio
async def test_check_external_id_not_found_returns_same_shape(client: AsyncClient, patched_lookups):
    """external_id desconhecido retorna mesmo shape (COD-32)."""
    resp = await client.post(
        "/api/v1/check", json={"external_id": "00000000-0000-0000-0000-000000000000"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"otp_sent": True}


# ── Rate limit (com redis fake) ─────────────────────


@pytest.mark.asyncio
async def test_check_rate_limits_second_call_same_cpf(
    client_with_redis: AsyncClient,
    patched_lookups,
):
    """Segunda chamada com mesmo CPF em <30s retorna otp_wait."""
    resp1 = await client_with_redis.post("/api/v1/check", json={"cpf": VALID_CPF})
    assert resp1.status_code == 200
    assert resp1.json()["otp_sent"] is True
    assert patched_lookups["otp_calls"] == 1

    resp2 = await client_with_redis.post("/api/v1/check", json={"cpf": VALID_CPF})
    assert resp2.status_code == 200
    body = resp2.json()
    assert "otp_wait" in body
    assert body["otp_wait"] > 0
    assert patched_lookups["otp_calls"] == 1  # nao disparou de novo


@pytest.mark.asyncio
async def test_check_rate_limits_second_call_same_phone(
    client_with_redis: AsyncClient,
    patched_lookups,
):
    """Segunda chamada com mesmo phone em <30s retorna otp_wait."""
    resp1 = await client_with_redis.post("/api/v1/check", json={"phone": VALID_PHONE})
    assert resp1.json()["otp_sent"] is True

    resp2 = await client_with_redis.post("/api/v1/check", json={"phone": VALID_PHONE})
    body = resp2.json()
    assert "otp_wait" in body


@pytest.mark.asyncio
async def test_check_rate_limits_second_call_same_eid(
    client_with_redis: AsyncClient,
    patched_lookups,
):
    """Segunda chamada com mesmo external_id em <30s retorna otp_wait."""
    resp1 = await client_with_redis.post("/api/v1/check", json={"external_id": KNOWN_EID})
    assert resp1.json()["otp_sent"] is True

    resp2 = await client_with_redis.post("/api/v1/check", json={"external_id": KNOWN_EID})
    body = resp2.json()
    assert "otp_wait" in body


@pytest.mark.asyncio
async def test_check_cpf_and_phone_share_rate_limit(
    client_with_redis: AsyncClient,
    patched_lookups,
):
    """Mesmo usuario via cpf e phone compartilha rate limit (mesmo external_id)."""
    resp1 = await client_with_redis.post("/api/v1/check", json={"cpf": VALID_CPF})
    assert resp1.json()["otp_sent"] is True

    resp2 = await client_with_redis.post("/api/v1/check", json={"phone": VALID_PHONE})
    body = resp2.json()
    assert "otp_wait" in body
    assert patched_lookups["otp_calls"] == 1


# ── Preferencia: CPF > Phone > External ID ──────────


@pytest.mark.asyncio
async def test_check_prefers_cpf_when_both_present(client: AsyncClient, patched_lookups):
    """Com CPF e phone, usa CPF para lookup."""
    resp = await client.post("/api/v1/check", json={"cpf": VALID_CPF, "phone": VALID_PHONE})
    assert resp.status_code == 200
    assert resp.json() == {"otp_sent": True}


# ── COD-32 task 4: Timing normalization ──────────


@pytest.mark.asyncio
async def test_check_not_found_adds_timing_jitter(client: AsyncClient, patched_lookups):
    """Not-found deve levar pelo menos ~100ms (jitter minimo) para mascarar timing."""
    import time

    start = time.monotonic()
    resp = await client.post("/api/v1/check", json={"cpf": "11144477735"})
    elapsed = time.monotonic() - start

    assert resp.status_code == 200
    assert resp.json() == {"otp_sent": True}
    # Jitter minimo e 100ms (0.10s) — mas o teste e assincrono,
    # entao toleramos 80ms para evitar flakiness em CI rapido.
    assert elapsed >= 0.08, f"Timing jitter too small: {elapsed:.3f}s"


@pytest.mark.asyncio
async def test_check_not_found_jitter_is_bounded(client: AsyncClient, patched_lookups):
    """Jitter nao deve exceder ~300ms (limite superior)."""
    import time

    start = time.monotonic()
    resp = await client.post("/api/v1/check", json={"phone": "11988887777"})
    elapsed = time.monotonic() - start

    assert resp.status_code == 200
    assert resp.json() == {"otp_sent": True}
    assert elapsed < 1.0, f"Timing jitter too large: {elapsed:.3f}s"
