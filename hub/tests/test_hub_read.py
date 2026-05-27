"""Testes do endpoint de leitura desmilitarizada de hubs (M2)."""

from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import text

from app.seed import DEFAULT_HUB_ID


async def test_get_hub_by_external_id(client: AsyncClient, session_factory, engine) -> None:
    """Lê o polo default semeado pela migração."""
    # A fixture conftest não semeia o default; semeamos manualmente aqui.
    async with session_factory() as session:
        await session.execute(
            text(
                f"INSERT INTO hub.hub (id, name, brand) "
                f"VALUES ('{DEFAULT_HUB_ID}', 'Polo Default', 'estacio') "
                f"ON CONFLICT (id) DO NOTHING"
            )
        )
        await session.commit()

    resp = await client.get(f"/api/v1/hubs/{DEFAULT_HUB_ID}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == DEFAULT_HUB_ID
    assert data["name"] == "Polo Default"
    assert data["brand"] == "estacio"
    assert data["address_external_id"] is None
    assert data["coordinator_external_id"] is None
    assert "created_at" in data
    assert "updated_at" in data


async def test_get_hub_not_found(client: AsyncClient) -> None:
    """UUID arbitrário → 404."""
    ghost = str(uuid4())
    resp = await client.get(f"/api/v1/hubs/{ghost}")
    assert resp.status_code == 404
    assert resp.json()["code"] == "NOT_FOUND"
