"""Testes dos endpoints de escrita autenticada de hubs (M3)."""

from uuid import uuid4

from httpx import AsyncClient

BASE = "/api/v1/hubs"


async def test_create_hub_rejects_bad_brand(client: AsyncClient, staff_headers) -> None:
    """Marca invalida → 422."""
    resp = await client.post(
        BASE,
        json={"name": "Polo X", "brand": "invalida"},
        headers=staff_headers,
    )
    assert resp.status_code == 422


async def test_create_hub_with_valid_brand(client: AsyncClient, staff_headers) -> None:
    """Cria polo com marca valida → 201."""
    resp = await client.post(
        BASE,
        json={"name": "Polo Centro", "brand": "estacio"},
        headers=staff_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Polo Centro"
    assert data["brand"] == "estacio"
    assert "id" in data


async def test_create_hub_normalizes_brand_lowercase(client: AsyncClient, staff_headers) -> None:
    """Marca em maiusculo e normalizada para lowercase."""
    resp = await client.post(
        BASE,
        json={"name": "Polo Norte", "brand": "WYDEN"},
        headers=staff_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["brand"] == "wyden"


async def test_update_hub(client: AsyncClient, staff_headers, make_hub) -> None:
    """Edita nome do polo → 200."""
    hub_id = await make_hub(name="Original", brand="estacio")
    resp = await client.patch(
        f"{BASE}/{hub_id}",
        json={"name": "Renomeado"},
        headers=staff_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renomeado"
    assert resp.json()["brand"] == "estacio"


async def test_update_hub_rejects_bad_brand(client: AsyncClient, staff_headers, make_hub) -> None:
    """Edicao com marca invalida → 422."""
    hub_id = await make_hub(name="X", brand="estacio")
    resp = await client.patch(
        f"{BASE}/{hub_id}",
        json={"brand": "fakebrand"},
        headers=staff_headers,
    )
    assert resp.status_code == 422


async def test_set_coordinator(client: AsyncClient, staff_headers, make_hub) -> None:
    """Define coordenador do polo → 200."""
    hub_id = await make_hub(name="Com Coord", brand="wyden")
    coord_id = str(uuid4())
    resp = await client.put(
        f"{BASE}/{hub_id}/coordinator",
        json={"coordinator_external_id": coord_id},
        headers=staff_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["coordinator_external_id"] == coord_id


async def test_set_coordinator_not_found(client: AsyncClient, staff_headers) -> None:
    """Coordenador em polo inexistente → 404."""
    resp = await client.put(
        f"{BASE}/{uuid4()}/coordinator",
        json={"coordinator_external_id": str(uuid4())},
        headers=staff_headers,
    )
    assert resp.status_code == 404


async def test_write_without_auth_rejected(client: AsyncClient) -> None:
    """POST sem token → 403 (HTTPBearer exige Authorization header)."""
    from app.dependencies import get_current_external_id
    from app.main import app

    # Store the override function so we can restore it
    override_fn = app.dependency_overrides.pop(get_current_external_id, None)
    try:
        resp = await client.post(
            BASE,
            json={"name": "Polo", "brand": "estacio"},
        )
        assert resp.status_code == 401
    finally:
        if override_fn is not None:
            app.dependency_overrides[get_current_external_id] = override_fn


async def test_list_hubs(client: AsyncClient, make_hub) -> None:
    """Listagem retorna todos os polos ordenados por nome."""
    await make_hub(name="Zeta", brand="estacio")
    await make_hub(name="Alpha", brand="wyden")
    resp = await client.get(BASE)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    names = [h["name"] for h in data]
    # Ordenado por nome
    assert names == sorted(names)
