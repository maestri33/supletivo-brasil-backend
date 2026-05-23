"""Testes de validação dos campos Educational — level, série, ano, flags."""

from httpx import AsyncClient

VALID_CPF = "52998224725"


async def _criar(client: AsyncClient, external_id: str) -> None:
    await client.post("/api/v1/profiles", json={"external_id": external_id, "cpf": VALID_CPF})


async def _patch(client: AsyncClient, external_id: str, field: str, value: str):
    return await client.patch(
        f"/api/v1/profiles/{external_id}", json={field: value}
    )


# ── level ──────────────────────────────────────────────────────────────

async def test_level_valido(client: AsyncClient) -> None:
    await _criar(client, "ed-lv1")
    resp = await _patch(client, "ed-lv1", "level", "higher_complete")
    assert resp.status_code == 200
    assert resp.json()["educational"]["level"] == "higher_complete"


async def test_level_insensitive(client: AsyncClient) -> None:
    """Case-insensitive e trim."""
    await _criar(client, "ed-lv2")
    resp = await _patch(client, "ed-lv2", "level", "  HIGH_SCHOOL_COMPLETE  ")
    assert resp.status_code == 200
    assert resp.json()["educational"]["level"] == "high_school_complete"


async def test_level_invalido(client: AsyncClient) -> None:
    await _criar(client, "ed-lv3")
    resp = await _patch(client, "ed-lv3", "level", "phd")
    assert resp.status_code == 422


async def test_level_vazio(client: AsyncClient) -> None:
    await _criar(client, "ed-lv4")
    resp = await _patch(client, "ed-lv4", "level", "")
    assert resp.status_code == 200
    assert resp.json()["educational"]["level"] == ""


# ── last_elementary_year ───────────────────────────────────────────────

async def test_last_elem_valido(client: AsyncClient) -> None:
    await _criar(client, "ed-le1")
    resp = await _patch(client, "ed-le1", "last_elementary_year", "5th")
    assert resp.status_code == 200
    assert resp.json()["educational"]["last_elementary_year"] == "5th"


async def test_last_elem_invalido(client: AsyncClient) -> None:
    await _criar(client, "ed-le2")
    resp = await _patch(client, "ed-le2", "last_elementary_year", "10th")
    assert resp.status_code == 422


async def test_last_elem_vazio(client: AsyncClient) -> None:
    await _criar(client, "ed-le3")
    resp = await _patch(client, "ed-le3", "last_elementary_year", "")
    assert resp.status_code == 200


# ── last_high_school_year ──────────────────────────────────────────────

async def test_last_hs_valido(client: AsyncClient) -> None:
    await _criar(client, "ed-hs1")
    resp = await _patch(client, "ed-hs1", "last_high_school_year", "2nd_hs")
    assert resp.status_code == 200
    assert resp.json()["educational"]["last_high_school_year"] == "2nd_hs"


async def test_last_hs_invalido(client: AsyncClient) -> None:
    await _criar(client, "ed-hs2")
    resp = await _patch(client, "ed-hs2", "last_high_school_year", "4th_hs")
    assert resp.status_code == 422


async def test_last_hs_vazio(client: AsyncClient) -> None:
    await _criar(client, "ed-hs3")
    resp = await _patch(client, "ed-hs3", "last_high_school_year", "")
    assert resp.status_code == 200


# ── elementary_completed ───────────────────────────────────────────────

async def test_elem_completed_true(client: AsyncClient) -> None:
    await _criar(client, "ed-ec1")
    resp = await _patch(client, "ed-ec1", "elementary_completed", "true")
    assert resp.status_code == 200
    assert resp.json()["educational"]["elementary_completed"] is True


async def test_elem_completed_false(client: AsyncClient) -> None:
    await _criar(client, "ed-ec2")
    resp = await _patch(client, "ed-ec2", "elementary_completed", "false")
    assert resp.status_code == 200
    assert resp.json()["educational"]["elementary_completed"] is False


async def test_elem_completed_1(client: AsyncClient) -> None:
    await _criar(client, "ed-ec3")
    resp = await _patch(client, "ed-ec3", "elementary_completed", "1")
    assert resp.status_code == 200
    assert resp.json()["educational"]["elementary_completed"] is True


async def test_elem_completed_sim(client: AsyncClient) -> None:
    await _criar(client, "ed-ec4")
    resp = await _patch(client, "ed-ec4", "elementary_completed", "sim")
    assert resp.status_code == 200
    assert resp.json()["educational"]["elementary_completed"] is True


async def test_elem_completed_nao(client: AsyncClient) -> None:
    await _criar(client, "ed-ec5")
    resp = await _patch(client, "ed-ec5", "elementary_completed", "não")
    assert resp.status_code == 200
    assert resp.json()["educational"]["elementary_completed"] is False


async def test_elem_completed_vazio(client: AsyncClient) -> None:
    """String vazia seta None (campo não informado)."""
    await _criar(client, "ed-ec6")
    resp = await _patch(client, "ed-ec6", "elementary_completed", "")
    assert resp.status_code == 200
    assert resp.json()["educational"]["elementary_completed"] is None


async def test_elem_completed_invalido(client: AsyncClient) -> None:
    await _criar(client, "ed-ec7")
    resp = await _patch(client, "ed-ec7", "elementary_completed", "talvez")
    assert resp.status_code == 422


# ── elementary_year ────────────────────────────────────────────────────

async def test_elem_year_valido(client: AsyncClient) -> None:
    await _criar(client, "ed-ey1")
    resp = await _patch(client, "ed-ey1", "elementary_year", "2010")
    assert resp.status_code == 200
    assert resp.json()["educational"]["elementary_year"] == 2010


async def test_elem_year_vazio(client: AsyncClient) -> None:
    """String vazia seta None."""
    await _criar(client, "ed-ey2")
    resp = await _patch(client, "ed-ey2", "elementary_year", "")
    assert resp.status_code == 200
    assert resp.json()["educational"]["elementary_year"] is None


async def test_elem_year_fora_range(client: AsyncClient) -> None:
    await _criar(client, "ed-ey3")
    resp = await _patch(client, "ed-ey3", "elementary_year", "1800")
    assert resp.status_code == 422


async def test_elem_year_futuro(client: AsyncClient) -> None:
    await _criar(client, "ed-ey4")
    resp = await _patch(client, "ed-ey4", "elementary_year", "2099")
    assert resp.status_code == 422


async def test_elem_year_nao_numero(client: AsyncClient) -> None:
    await _criar(client, "ed-ey5")
    resp = await _patch(client, "ed-ey5", "elementary_year", "abc")
    assert resp.status_code == 422


# ── high_school_completed ──────────────────────────────────────────────

async def test_hs_completed_true(client: AsyncClient) -> None:
    await _criar(client, "ed-hc1")
    resp = await _patch(client, "ed-hc1", "high_school_completed", "yes")
    assert resp.status_code == 200
    assert resp.json()["educational"]["high_school_completed"] is True


async def test_hs_completed_vazio(client: AsyncClient) -> None:
    await _criar(client, "ed-hc2")
    resp = await _patch(client, "ed-hc2", "high_school_completed", "")
    assert resp.status_code == 200
    assert resp.json()["educational"]["high_school_completed"] is None
