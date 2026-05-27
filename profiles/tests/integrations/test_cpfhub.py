"""Testes unitários do cliente CPFHub.

Usa httpx.MockTransport — sem rede, sem dependência da CPFHub real.
"""

from __future__ import annotations

from datetime import date

import httpx
import pytest

from app.integrations import cpfhub as cpfhub_module
from app.integrations.cpfhub import CPFHubClient, CPFHubIdentity, _parse_identity


# ── Parser ─────────────────────────────────────────────────────────


def test_parse_full_payload() -> None:
    identity = _parse_identity(
        {
            "cpf": "12345678900",
            "name": "Fulano de Tal",
            "gender": "M",
            "day": 15,
            "month": 6,
            "year": 1990,
        }
    )
    assert identity is not None
    assert identity.name == "Fulano de Tal"
    assert identity.gender == "M"
    assert identity.birth_date == date(1990, 6, 15)


def test_parse_only_name() -> None:
    identity = _parse_identity({"name": "Só Nome"})
    assert identity is not None
    assert identity.name == "Só Nome"
    assert identity.gender is None
    assert identity.birth_date is None


def test_parse_empty_returns_none() -> None:
    assert _parse_identity({}) is None
    assert _parse_identity({"name": "", "gender": "X"}) is None


def test_parse_rejects_invalid_gender() -> None:
    identity = _parse_identity({"name": "X", "gender": "Z"})
    assert identity is not None
    assert identity.name == "X"
    assert identity.gender is None


def test_parse_rejects_invalid_date() -> None:
    identity = _parse_identity({"name": "X", "day": 31, "month": 2, "year": 1990})
    assert identity is not None
    assert identity.birth_date is None


def test_parse_strips_whitespace() -> None:
    identity = _parse_identity({"name": "  Joao  "})
    assert identity is not None
    assert identity.name == "Joao"


# ── Client: success ────────────────────────────────────────────────


def _ok_payload() -> dict:
    return {
        "success": True,
        "data": {
            "cpf": "09126367939",
            "name": "Victor Vanderley Maestri",
            "nameUpper": "VICTOR VANDERLEY MAESTRI",
            "gender": "M",
            "birthDate": "31/07/1993",
            "day": 31,
            "month": 7,
            "year": 1993,
        },
    }


def _make_client_with_handler(handler) -> CPFHubClient:
    transport = httpx.MockTransport(handler)
    client = CPFHubClient(api_key="test-key", base_url="https://api.cpfhub.io")
    client._client = httpx.AsyncClient(
        transport=transport,
        headers={
            "x-api-key": "test-key",
            "Accept": "application/json",
        },
    )
    return client


async def test_lookup_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/cpf/09126367939"
        assert request.headers["x-api-key"] == "test-key"
        return httpx.Response(200, json=_ok_payload())

    client = _make_client_with_handler(handler)
    try:
        identity = await client.lookup("09126367939")
    finally:
        await client._client.aclose()

    assert identity == CPFHubIdentity(
        name="Victor Vanderley Maestri",
        gender="M",
        birth_date=date(1993, 7, 31),
    )


async def test_lookup_strips_cpf_formatting() -> None:
    seen_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        return httpx.Response(200, json=_ok_payload())

    client = _make_client_with_handler(handler)
    try:
        await client.lookup("091.263.679-39")
    finally:
        await client._client.aclose()

    assert seen_paths == ["/cpf/09126367939"]


# ── Client: failures (best-effort returns None) ────────────────────


async def test_lookup_404_returns_none() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={
                "success": False,
                "data": None,
                "error": {"message": "CPF não encontrado"},
            },
        )

    client = _make_client_with_handler(handler)
    try:
        assert await client.lookup("12345678900") is None
    finally:
        await client._client.aclose()


async def test_lookup_401_returns_none() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"success": False})

    client = _make_client_with_handler(handler)
    try:
        assert await client.lookup("12345678900") is None
    finally:
        await client._client.aclose()


async def test_lookup_invalid_cpf_length_returns_none() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=_ok_payload())

    client = _make_client_with_handler(handler)
    try:
        assert await client.lookup("123") is None
        assert await client.lookup("") is None
    finally:
        await client._client.aclose()

    assert calls == 0  # short-circuited antes do HTTP


async def test_lookup_invalid_json_returns_none() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html>boom</html>")

    client = _make_client_with_handler(handler)
    try:
        assert await client.lookup("12345678900") is None
    finally:
        await client._client.aclose()


async def test_lookup_success_false_returns_none() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"success": False, "data": None})

    client = _make_client_with_handler(handler)
    try:
        assert await client.lookup("12345678900") is None
    finally:
        await client._client.aclose()


# ── Retry ──────────────────────────────────────────────────────────


async def test_lookup_retries_on_429(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls < 3:
            return httpx.Response(429, json={"error": {"message": "rate limit"}})
        return httpx.Response(200, json=_ok_payload())

    # zera o backoff pra testar rapido
    monkeypatch.setattr(cpfhub_module, "_RETRY_DELAYS", (0.0, 0.0))

    client = _make_client_with_handler(handler)
    try:
        identity = await client.lookup("09126367939")
    finally:
        await client._client.aclose()

    assert calls == 3
    assert identity is not None
    assert identity.name == "Victor Vanderley Maestri"


async def test_lookup_gives_up_after_max_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503, json={"error": {"message": "down"}})

    monkeypatch.setattr(cpfhub_module, "_RETRY_DELAYS", (0.0, 0.0))

    client = _make_client_with_handler(handler)
    try:
        assert await client.lookup("12345678900") is None
    finally:
        await client._client.aclose()

    assert calls == 3  # 3 tentativas totais (1 + 2 retries)


async def test_lookup_retries_on_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls < 2:
            raise httpx.ConnectError("boom")
        return httpx.Response(200, json=_ok_payload())

    monkeypatch.setattr(cpfhub_module, "_RETRY_DELAYS", (0.0, 0.0))

    client = _make_client_with_handler(handler)
    try:
        identity = await client.lookup("09126367939")
    finally:
        await client._client.aclose()

    assert calls == 2
    assert identity is not None


# ── Guard: no API key ──────────────────────────────────────────────


async def test_lookup_without_api_key_returns_none() -> None:
    client = CPFHubClient(api_key="", base_url="https://api.cpfhub.io")
    async with client:
        assert await client.lookup("09126367939") is None
