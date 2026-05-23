"""Testes de validação do campo birth_date — normalização + validação."""

from httpx import AsyncClient

VALID_CPF = "52998224725"


async def _criar(client: AsyncClient, external_id: str) -> None:
    await client.post("/api/v1/profiles", json={"external_id": external_id, "cpf": VALID_CPF})


async def _patch(client: AsyncClient, external_id: str, value: str):
    return await client.patch(
        f"/api/v1/profiles/{external_id}", json={"birth_date": value}
    )


# ── Normalização ──────────────────────────────────────────────────────

async def test_birth_date_vazio(client: AsyncClient) -> None:
    """String vazia seta None — não crasha mais."""
    await _criar(client, "bd1")
    resp = await _patch(client, "bd1", "")
    assert resp.status_code == 200
    assert resp.json()["birth_info"]["birth_date"] is None


async def test_birth_date_valido(client: AsyncClient) -> None:
    await _criar(client, "bd2")
    resp = await _patch(client, "bd2", "1990-06-15")
    assert resp.status_code == 200
    assert resp.json()["birth_info"]["birth_date"] == "1990-06-15"


async def test_birth_date_formato_invalido(client: AsyncClient) -> None:
    await _criar(client, "bd3")
    resp = await _patch(client, "bd3", "15/06/1990")
    assert resp.status_code == 422


async def test_birth_date_texto(client: AsyncClient) -> None:
    await _criar(client, "bd4")
    resp = await _patch(client, "bd4", "nada")
    assert resp.status_code == 422


# ── Validação (regras existentes mantidas) ─────────────────────────────

async def test_birth_date_menor_16(client: AsyncClient) -> None:
    await _criar(client, "bd5")
    resp = await _patch(client, "bd5", "2020-01-01")
    assert resp.status_code == 422


async def test_birth_date_futuro(client: AsyncClient) -> None:
    await _criar(client, "bd6")
    resp = await _patch(client, "bd6", "2099-01-01")
    assert resp.status_code == 422


async def test_birth_date_exatamente_16(client: AsyncClient) -> None:
    """Data exata de 16 anos atrás deve passar."""
    from datetime import date
    today = date.today()
    year = today.year - 16
    # Usa o dia seguinte para garantir que completou 16
    # Se hoje for 2026-05-12, usa 2010-05-11 (um dia a menos = 16 anos + 1 dia)
    from datetime import timedelta
    d = date(year, today.month, today.day) - timedelta(days=1)
    await _criar(client, "bd7")
    resp = await _patch(client, "bd7", d.isoformat())
    assert resp.status_code == 200
