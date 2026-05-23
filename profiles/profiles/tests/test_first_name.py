"""Testes do endpoint de primeiro nome — GET /api/v1/profiles/first-name/{external_id}."""

from httpx import AsyncClient

VALID_CPF = "52998224725"


async def _setup(client: AsyncClient, external_id: str, cpf: str) -> None:
    await client.post("/api/v1/profiles", json={"external_id": external_id, "cpf": cpf})


async def _set_name(client: AsyncClient, external_id: str, name: str) -> None:
    await client.patch(f"/api/v1/profiles/{external_id}", json={"name": name})


async def test_first_name_ok(client: AsyncClient) -> None:
    await _setup(client, "fn1", "10433218100")
    await _set_name(client, "fn1", "Victor Maestri")
    resp = await client.get("/api/v1/profiles/first-name/fn1")
    assert resp.status_code == 200
    assert resp.json() == {"first_name": "Victor", "full_name": "Victor Maestri"}


async def test_first_name_three_words(client: AsyncClient) -> None:
    await _setup(client, "fn2", "96001338914")
    await _set_name(client, "fn2", "João Da Silva")
    resp = await client.get("/api/v1/profiles/first-name/fn2")
    assert resp.status_code == 200
    assert resp.json()["first_name"] == "João"


async def test_first_name_empty(client: AsyncClient) -> None:
    await _setup(client, "fn3", "08386379499")
    resp = await client.get("/api/v1/profiles/first-name/fn3")
    assert resp.status_code == 200
    assert resp.json() == {"first_name": None, "full_name": None}


async def test_first_name_single_word(client: AsyncClient) -> None:
    """Nome com 1 palavra é válido — retorna o próprio nome como first_name."""
    await _setup(client, "fn4", "02654235114")
    await _set_name(client, "fn4", "Fulano")
    resp = await client.get("/api/v1/profiles/first-name/fn4")
    assert resp.status_code == 200
    assert resp.json() == {"first_name": "Fulano", "full_name": "Fulano"}


async def test_first_name_not_found(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/profiles/first-name/ghost")
    assert resp.status_code == 404
