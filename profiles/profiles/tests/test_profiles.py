"""CRUD end-to-end Profile + busca por CPF — completo."""

from httpx import AsyncClient

VALID_CPF = "52998224725"


# ── POST /api/v1/profiles ─────────────────────────────────────

async def test_create_minimal(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/profiles", json={"external_id": "t1", "cpf": VALID_CPF})
    assert resp.status_code == 201
    body = resp.json()
    assert body["external_id"] == "t1"
    assert body["cpf"] == VALID_CPF
    assert body["name"] is None
    assert body["gender"] is None
    assert body["educational"] is None
    assert body["birth_info"] is None


async def test_create_duplicate_cpf(client: AsyncClient) -> None:
    await client.post("/api/v1/profiles", json={"external_id": "d1", "cpf": "10433218100"})
    resp = await client.post("/api/v1/profiles", json={"external_id": "d2", "cpf": "10433218100"})
    assert resp.status_code == 409


async def test_create_duplicate_external_id(client: AsyncClient) -> None:
    await client.post("/api/v1/profiles", json={"external_id": "dup-id", "cpf": "10433218100"})
    resp = await client.post("/api/v1/profiles", json={"external_id": "dup-id", "cpf": "96001338914"})
    assert resp.status_code == 409


async def test_create_invalid_cpf(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/profiles", json={"external_id": "inv", "cpf": "12345678901"})
    assert resp.status_code == 422


async def test_create_cpf_all_equal(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/profiles", json={"external_id": "eq", "cpf": "11111111111"})
    assert resp.status_code == 422


async def test_create_cpf_wrong_length(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/profiles", json={"external_id": "sh", "cpf": "123"})
    assert resp.status_code == 422


async def test_create_rejects_extra_fields(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/profiles", json={
        "external_id": "extra", "cpf": VALID_CPF, "name": "hacker"
    })
    assert resp.status_code == 422


# ── GET /api/v1/profiles/cpf/{cpf} ────────────────────────────

async def test_cpf_lookup_found(client: AsyncClient) -> None:
    await client.post("/api/v1/profiles", json={"external_id": "lkp", "cpf": "96001338914"})
    resp = await client.get("/api/v1/profiles/cpf/96001338914")
    assert resp.json()["found"] is True
    assert resp.json()["external_id"] == "lkp"
    assert resp.json()["valid"] is True


async def test_cpf_lookup_not_found_invalid(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/profiles/cpf/00000000000")
    assert resp.json()["found"] is False
    assert resp.json()["valid"] is False


async def test_cpf_lookup_not_found_valid(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/profiles/cpf/52998224725")
    assert resp.json()["found"] is False
    assert resp.json()["valid"] is True


# ── GET /api/v1/profiles ──────────────────────────────────────

async def test_list_empty(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/profiles")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_list_with_items(client: AsyncClient) -> None:
    await client.post("/api/v1/profiles", json={"external_id": "l1", "cpf": "08386379499"})
    resp = await client.get("/api/v1/profiles")
    assert resp.status_code == 200
    items = resp.json()
    assert any(i["external_id"] == "l1" for i in items)
    assert any(i["cpf"] == "08386379499" for i in items)
    for i in items:
        assert set(i.keys()) == {"external_id", "cpf", "name"}


# ── GET /api/v1/profiles/{external_id} ────────────────────────

async def test_get_found(client: AsyncClient) -> None:
    await client.post("/api/v1/profiles", json={"external_id": "gf", "cpf": "16155940789"})
    resp = await client.get("/api/v1/profiles/gf")
    assert resp.status_code == 200
    body = resp.json()
    assert body["external_id"] == "gf"
    assert body["cpf"] == "16155940789"
    assert "created_at" in body
    assert "updated_at" in body


async def test_get_not_found(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/profiles/no-exist")
    assert resp.status_code == 404


# ── PATCH /api/v1/profiles/{external_id}/{field} ──────────────

async def test_patch_name_normalizes(client: AsyncClient) -> None:
    await client.post("/api/v1/profiles", json={"external_id": "pn", "cpf": "02654235114"})
    resp = await client.patch("/api/v1/profiles/pn", json={"name": "victor maestri"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Victor Maestri"


async def test_patch_name_empty(client: AsyncClient) -> None:
    await client.post("/api/v1/profiles", json={"external_id": "pe", "cpf": "16155940789"})
    resp = await client.patch("/api/v1/profiles/pe", json={"name": ""})
    assert resp.status_code == 200
    assert resp.json()["name"] == ""


async def test_patch_gender_valid(client: AsyncClient) -> None:
    await client.post("/api/v1/profiles", json={"external_id": "pg", "cpf": "96001338914"})
    resp = await client.patch("/api/v1/profiles/pg", json={"gender": "m"})
    assert resp.status_code == 200
    assert resp.json()["gender"] == "M"


async def test_patch_gender_invalid(client: AsyncClient) -> None:
    await client.post("/api/v1/profiles", json={"external_id": "pgi", "cpf": "08386379499"})
    resp = await client.patch("/api/v1/profiles/pgi", json={"gender": "X"})
    assert resp.status_code == 422


async def test_patch_blood_type_valid(client: AsyncClient) -> None:
    await client.post("/api/v1/profiles", json={"external_id": "pb", "cpf": "10433218100"})
    resp = await client.patch("/api/v1/profiles/pb", json={"blood_type": "O+"})
    assert resp.status_code == 200
    assert resp.json()["blood_type"] == "O+"


async def test_patch_blood_type_invalid(client: AsyncClient) -> None:
    await client.post("/api/v1/profiles", json={"external_id": "pbi", "cpf": "02654235114"})
    resp = await client.patch("/api/v1/profiles/pbi", json={"blood_type": "XYZ"})
    assert resp.status_code == 422


async def test_patch_civil_status_valid(client: AsyncClient) -> None:
    await client.post("/api/v1/profiles", json={"external_id": "pcs", "cpf": "16155940789"})
    resp = await client.patch("/api/v1/profiles/pcs", json={"civil_status": "Married"})
    assert resp.status_code == 200
    assert resp.json()["civil_status"] == "married"


async def test_patch_civil_status_invalid(client: AsyncClient) -> None:
    await client.post("/api/v1/profiles", json={"external_id": "pcsi", "cpf": "96001338914"})
    resp = await client.patch("/api/v1/profiles/pcsi", json={"civil_status": "unknown"})
    assert resp.status_code == 422


async def test_patch_state_valid(client: AsyncClient) -> None:
    await client.post("/api/v1/profiles", json={"external_id": "ps", "cpf": "08386379499"})
    resp = await client.patch("/api/v1/profiles/ps", json={"state": "sp"})
    assert resp.status_code == 200
    assert resp.json()["birth_info"]["state"] == "SP"


async def test_patch_state_invalid(client: AsyncClient) -> None:
    await client.post("/api/v1/profiles", json={"external_id": "psi", "cpf": "10433218100"})
    resp = await client.patch("/api/v1/profiles/psi", json={"state": "XX"})
    assert resp.status_code == 422


async def test_patch_birth_date_valid(client: AsyncClient) -> None:
    await client.post("/api/v1/profiles", json={"external_id": "pbd", "cpf": "52998224725"})
    resp = await client.patch("/api/v1/profiles/pbd", json={"birth_date": "1990-06-15"})
    assert resp.status_code == 200
    assert resp.json()["birth_info"]["birth_date"] == "1990-06-15"


async def test_patch_birth_date_underage(client: AsyncClient) -> None:
    await client.post("/api/v1/profiles", json={"external_id": "pbu", "cpf": "02654235114"})
    resp = await client.patch("/api/v1/profiles/pbu", json={"birth_date": "2020-01-01"})
    assert resp.status_code == 422


async def test_patch_birth_date_future(client: AsyncClient) -> None:
    await client.post("/api/v1/profiles", json={"external_id": "pbf", "cpf": "16155940789"})
    resp = await client.patch("/api/v1/profiles/pbf", json={"birth_date": "2099-01-01"})
    assert resp.status_code == 422


async def test_patch_cpf_immutable(client: AsyncClient) -> None:
    await client.post("/api/v1/profiles", json={"external_id": "pc", "cpf": "02654235114"})
    resp = await client.patch("/api/v1/profiles/pc", json={"cpf": "96001338914"})
    assert resp.status_code == 422


async def test_patch_unknown_field(client: AsyncClient) -> None:
    await client.post("/api/v1/profiles", json={"external_id": "pu", "cpf": "08386379499"})
    resp = await client.patch("/api/v1/profiles/pu", json={"nonexistent": "x"})
    assert resp.status_code == 422


async def test_patch_not_found(client: AsyncClient) -> None:
    resp = await client.patch("/api/v1/profiles/ghost", json={"name": "Valid Name"})
    assert resp.status_code == 404


# ── DELETE /api/v1/profiles/{external_id} ─────────────────────

async def test_delete_ok(client: AsyncClient) -> None:
    await client.post("/api/v1/profiles", json={"external_id": "x1", "cpf": "52998224725"})
    resp = await client.delete("/api/v1/profiles/x1")
    assert resp.status_code == 204
    resp = await client.get("/api/v1/profiles/x1")
    assert resp.status_code == 404


async def test_delete_not_found(client: AsyncClient) -> None:
    resp = await client.delete("/api/v1/profiles/ghost")
    assert resp.status_code == 404


# ── idempotência: recriar após deletar ──────────────────────

async def test_recreate_after_delete(client: AsyncClient) -> None:
    await client.post("/api/v1/profiles", json={"external_id": "re", "cpf": "52998224725"})
    await client.delete("/api/v1/profiles/re")
    resp = await client.post("/api/v1/profiles", json={"external_id": "re", "cpf": "52998224725"})
    assert resp.status_code == 201
    assert resp.json()["external_id"] == "re"
