"""Testes de validação do campo city."""

from httpx import AsyncClient

VALID_CPF = "52998224725"


async def _criar(client: AsyncClient, external_id: str) -> None:
    await client.post("/api/v1/profiles", json={"external_id": external_id, "cpf": VALID_CPF})


async def _patch(client: AsyncClient, external_id: str, value: str):
    return await client.patch(f"/api/v1/profiles/{external_id}", json={"city": value})


# ── Normalização ──────────────────────────────────────────────────────


async def test_city_trim_capitalize(client: AsyncClient) -> None:
    await _criar(client, "ct1")
    resp = await _patch(client, "ct1", "  sao paulo  ")
    assert resp.status_code == 200
    assert resp.json()["birth_info"]["city"] == "Sao Paulo"


async def test_city_conectivo_minusculo(client: AsyncClient) -> None:
    await _criar(client, "ct2")
    resp = await _patch(client, "ct2", "RIO DE JANEIRO")
    assert resp.status_code == 200
    assert resp.json()["birth_info"]["city"] == "Rio de Janeiro"


async def test_city_colapsa_whitespace(client: AsyncClient) -> None:
    await _criar(client, "ct3")
    resp = await _patch(client, "ct3", "belo\thorizonte")
    assert resp.status_code == 200
    assert resp.json()["birth_info"]["city"] == "Belo Horizonte"


async def test_city_vazio(client: AsyncClient) -> None:
    await _criar(client, "ct4")
    resp = await _patch(client, "ct4", "")
    assert resp.status_code == 200
    assert resp.json()["birth_info"]["city"] is None


# ── Validação ─────────────────────────────────────────────────────────


async def test_city_bloqueia_numeros_only(client: AsyncClient) -> None:
    await _criar(client, "ct5")
    resp = await _patch(client, "ct5", "12345")
    assert resp.status_code == 422


async def test_city_bloqueia_markup(client: AsyncClient) -> None:
    await _criar(client, "ct6")
    resp = await _patch(client, "ct6", "<script>")
    assert resp.status_code == 422


async def test_city_bloqueia_emojis(client: AsyncClient) -> None:
    await _criar(client, "ct7")
    resp = await _patch(client, "ct7", "São Paulo 🙂")
    assert resp.status_code == 422


async def test_city_uma_letra(client: AsyncClient) -> None:
    await _criar(client, "ct8")
    resp = await _patch(client, "ct8", "X")
    assert resp.status_code == 422


async def test_city_mais_de_100_chars(client: AsyncClient) -> None:
    await _criar(client, "ct9")
    resp = await _patch(client, "ct9", "A" * 101)
    assert resp.status_code == 422


async def test_city_com_hifen(client: AsyncClient) -> None:
    await _criar(client, "ct10")
    resp = await _patch(client, "ct10", "São João del-Rei")
    assert resp.status_code == 200


async def test_city_com_acentos(client: AsyncClient) -> None:
    await _criar(client, "ct11")
    resp = await _patch(client, "ct11", "são paulo")
    assert resp.status_code == 200
    assert resp.json()["birth_info"]["city"] == "São Paulo"
