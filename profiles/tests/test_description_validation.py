"""Testes de validação do campo description."""

from httpx import AsyncClient

VALID_CPF = "52998224725"


async def _criar(client: AsyncClient, external_id: str) -> None:
    await client.post("/api/v1/profiles", json={"external_id": external_id, "cpf": VALID_CPF})


async def _patch(client: AsyncClient, external_id: str, value: str):
    return await client.patch(f"/api/v1/profiles/{external_id}", json={"description": value})


# ── Normalização ──────────────────────────────────────────────────────


async def test_description_trim(client: AsyncClient) -> None:
    await _criar(client, "ds1")
    resp = await _patch(client, "ds1", "  texto com espaços  \t\n ")
    assert resp.status_code == 200
    assert resp.json()["description"] == "texto com espaços"


async def test_description_vazio(client: AsyncClient) -> None:
    await _criar(client, "ds2")
    resp = await _patch(client, "ds2", "")
    assert resp.status_code == 200
    assert resp.json()["description"] == ""


async def test_description_colapsa_whitespace(client: AsyncClient) -> None:
    await _criar(client, "ds3")
    resp = await _patch(client, "ds3", "linha1\n\nlinha2\t\tlinha3")
    assert resp.status_code == 200
    assert resp.json()["description"] == "linha1 linha2 linha3"


# ── Validação ─────────────────────────────────────────────────────────


async def test_description_bloqueia_markup(client: AsyncClient) -> None:
    await _criar(client, "ds4")
    resp = await _patch(client, "ds4", "<script>alert(1)</script>")
    assert resp.status_code == 422


async def test_description_bloqueia_tags(client: AsyncClient) -> None:
    await _criar(client, "ds5")
    resp = await _patch(client, "ds5", "<b>negrito</b>")
    assert resp.status_code == 422


async def test_description_bloqueia_emojis(client: AsyncClient) -> None:
    await _criar(client, "ds6")
    resp = await _patch(client, "ds6", "texto 🙂 com emoji")
    assert resp.status_code == 422


async def test_description_bloqueia_apenas_simbolos(client: AsyncClient) -> None:
    await _criar(client, "ds7")
    resp = await _patch(client, "ds7", "!!!!")
    assert resp.status_code == 422


async def test_description_texto_normal(client: AsyncClient) -> None:
    await _criar(client, "ds8")
    resp = await _patch(client, "ds8", "Descrição válida com acentos e pontuação.")
    assert resp.status_code == 200
    assert resp.json()["description"] == "Descrição válida com acentos e pontuação."
