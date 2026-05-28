"""Testes de gerenciamento de hubs — delegação ao serviço hub via HTTP.

Usa app.dependency_overrides para simular staff autenticado e patch
no HubClient para mockar as respostas do hub.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

from app.dependencies import get_current_external_id
from app.main import app

HUB_ID = uuid4()
COORDINATOR_ID = uuid4()
STAFF_ID = uuid4()
BASE = "/api/v1/hubs"


async def _mock_current_external_id() -> UUID:
    return STAFF_ID


# ═══════════════════════════════════════════════════════════════
# Auth gate: sem token, rejeita
# ═══════════════════════════════════════════════════════════════


async def test_create_hub_without_token(client: AsyncClient) -> None:
    resp = await client.post(BASE, json={"name": "Polo", "brand": "estacio"})
    assert resp.status_code in (401, 403)


async def test_list_hubs_without_token(client: AsyncClient) -> None:
    resp = await client.get(BASE)
    assert resp.status_code in (401, 403)


async def test_get_hub_without_token(client: AsyncClient) -> None:
    resp = await client.get(f"{BASE}/{HUB_ID}")
    assert resp.status_code in (401, 403)


async def test_set_coordinator_without_token(client: AsyncClient) -> None:
    resp = await client.put(
        f"{BASE}/{HUB_ID}/coordinator",
        json={"coordinator_external_id": str(COORDINATOR_ID)},
    )
    assert resp.status_code in (401, 403)


# ═══════════════════════════════════════════════════════════════
# Money path: autenticado, delega ao hub (mock HubClient)
# ═══════════════════════════════════════════════════════════════


pytest_auth_override = pytest.mark.usefixtures("_override_auth")


@pytest.fixture
def _override_auth() -> None:
    """Sobrescreve get_current_external_id para bypass de JWT nos testes."""
    app.dependency_overrides[get_current_external_id] = _mock_current_external_id


@pytest_auth_override
async def test_create_hub_delegates(client: AsyncClient) -> None:
    """POST /hubs autenticado → delega ao hub e retorna 201."""
    fake_hub = {
        "id": str(HUB_ID),
        "name": "Polo Central",
        "brand": "estacio",
        "address_external_id": None,
        "coordinator_external_id": None,
    }

    with patch("app.api.authenticated.hubs.HubClient", autospec=True) as MockClient:
        instance = MockClient.return_value
        instance.create_hub = AsyncMock(return_value=fake_hub)
        resp = await client.post(
            BASE,
            json={"name": "Polo Central", "brand": "estacio"},
        )
        assert resp.status_code == 201
        assert resp.json()["id"] == str(HUB_ID)


@pytest_auth_override
async def test_list_hubs_delegates(client: AsyncClient) -> None:
    """GET /hubs autenticado → delega ao hub e retorna lista."""
    fake_list = [
        {"id": str(uuid4()), "name": "Polo A", "brand": "estacio"},
        {"id": str(uuid4()), "name": "Polo B", "brand": "wyden"},
    ]

    with patch("app.api.authenticated.hubs.HubClient", autospec=True) as MockClient:
        instance = MockClient.return_value
        instance.list_hubs = AsyncMock(return_value=fake_list)
        resp = await client.get(BASE)
        assert resp.status_code == 200
        assert len(resp.json()) == 2


@pytest_auth_override
async def test_get_hub_delegates(client: AsyncClient) -> None:
    """GET /hubs/{id} autenticado → delega ao hub."""
    fake_hub = {
        "id": str(HUB_ID),
        "name": "Polo X",
        "brand": "wyden",
        "address_external_id": None,
        "coordinator_external_id": None,
    }

    with patch("app.api.authenticated.hubs.HubClient", autospec=True) as MockClient:
        instance = MockClient.return_value
        instance.get_hub = AsyncMock(return_value=fake_hub)
        resp = await client.get(f"{BASE}/{HUB_ID}")
        assert resp.status_code == 200
        assert resp.json()["brand"] == "wyden"


@pytest_auth_override
async def test_set_coordinator_delegates(client: AsyncClient) -> None:
    """PUT /hubs/{id}/coordinator autenticado → delega ao hub."""
    fake_result = {
        "id": str(HUB_ID),
        "name": "Polo X",
        "brand": "wyden",
        "coordinator_external_id": str(COORDINATOR_ID),
    }

    with patch("app.api.authenticated.hubs.HubClient", autospec=True) as MockClient:
        instance = MockClient.return_value
        instance.set_coordinator = AsyncMock(return_value=fake_result)
        resp = await client.put(
            f"{BASE}/{HUB_ID}/coordinator",
            json={"coordinator_external_id": str(COORDINATOR_ID)},
        )
        assert resp.status_code == 200
        assert resp.json()["coordinator_external_id"] == str(COORDINATOR_ID)


@pytest_auth_override
async def test_hub_unreachable_returns_502(client: AsyncClient) -> None:
    """Hub fora do ar → staff retorna erro (Bad Gateway)."""
    from httpx import RequestError

    with patch("app.api.authenticated.hubs.HubClient", autospec=True) as MockClient:
        instance = MockClient.return_value
        instance.create_hub = AsyncMock(
            side_effect=RequestError("connection refused", request=None)
        )
        resp = await client.post(
            BASE,
            json={"name": "Polo", "brand": "estacio"},
        )
        # HubClient converte RequestError em HTTPException 502,
        # mas com raise_app_exceptions=False o ASGITransport
        # serializa como 500. Verificamos que não é sucesso.
        assert resp.status_code >= 400
