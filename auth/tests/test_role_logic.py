import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker


@pytest_asyncio.fixture
async def create_id(client: AsyncClient, test_engine):
    """Cria identity no banco local e atribui role inicial via Roles Service."""
    from app.models.identity import Identity

    async def _create(initial_role: str) -> str:
        test_session = async_sessionmaker(test_engine, expire_on_commit=False)
        async with test_session() as session:
            identity = Identity()
            session.add(identity)
            await session.flush()
            ext_id = str(identity.external_id)
            await session.commit()

        # Atribuir role inicial via API (que delega ao Roles Service)
        resp = await client.post(f"/api/v1/role/{ext_id}/{initial_role}")
        assert resp.status_code == 200, f"Falha ao atribuir role inicial '{initial_role}': {resp.text}"
        return ext_id

    return _create


# ── Config /roles CRUD ──────────────────────────────────

@pytest.mark.asyncio
async def test_list_role_rules(client: AsyncClient):
    resp = await client.get("/api/v1/config/roles")
    assert resp.status_code == 200
    rules = resp.json()
    assert len(rules) > 0
    to_roles = {r["to_role"] for r in rules}
    assert to_roles >= {"a", "b", "c", "x", "y", "z"}


@pytest.mark.asyncio
async def test_create_and_delete_rule(client: AsyncClient):
    resp = await client.post(
        "/api/v1/config/roles",
        json={"to_role": "test_tmp", "mode": "add"},
    )
    assert resp.status_code == 201
    rule_id = resp.json()["id"]

    resp = await client.patch(
        f"/api/v1/config/roles/{rule_id}",
        json={"requires_role": "b"},
    )
    assert resp.status_code == 200
    assert resp.json()["requires_role"] == "b"

    resp = await client.delete(f"/api/v1/config/roles/{rule_id}")
    assert resp.status_code == 204


# ── Identities ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_nonexistent_identity(client: AsyncClient):
    resp = await client.get("/api/v1/role/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_identity_with_entry_role_a(client: AsyncClient, create_id):
    ext_id = await create_id("a")
    resp = await client.get(f"/api/v1/role/{ext_id}")
    assert resp.status_code == 200
    assert resp.json()["roles"] == ["a"]


@pytest.mark.asyncio
async def test_create_identity_with_entry_role_x(client: AsyncClient, create_id):
    ext_id = await create_id("x")
    resp = await client.get(f"/api/v1/role/{ext_id}")
    assert resp.status_code == 200
    assert resp.json()["roles"] == ["x"]


@pytest.mark.asyncio
async def test_promote_a_to_b(client: AsyncClient, create_id):
    ext_id = await create_id("a")
    resp = await client.post(f"/api/v1/role/{ext_id}/up/b")
    assert resp.status_code == 200
    assert resp.json()["roles"] == ["b"]


@pytest.mark.asyncio
async def test_promote_x_to_y(client: AsyncClient, create_id):
    ext_id = await create_id("x")
    resp = await client.post(f"/api/v1/role/{ext_id}/up/y")
    assert resp.status_code == 200
    assert resp.json()["roles"] == ["y"]


@pytest.mark.asyncio
async def test_promote_fails_if_from_role_missing(client: AsyncClient, create_id):
    ext_id = await create_id("a")
    await client.post(f"/api/v1/role/{ext_id}/up/b")  # a→b, revoga a
    resp = await client.post(f"/api/v1/role/{ext_id}/up/b")  # já não tem 'a'
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_promote_fails_for_non_replace_rule(client: AsyncClient, create_id):
    ext_id = await create_id("a")
    resp = await client.post(f"/api/v1/role/{ext_id}/up/c")
    assert resp.status_code == 422  # c é add, não replace


@pytest.mark.asyncio
async def test_assign_c_requires_b(client: AsyncClient, create_id):
    ext_id = await create_id("a")
    resp = await client.post(f"/api/v1/role/{ext_id}/c")
    assert resp.status_code == 422
    await client.post(f"/api/v1/role/{ext_id}/up/b")
    resp = await client.post(f"/api/v1/role/{ext_id}/c")
    assert resp.status_code == 200
    assert set(resp.json()["roles"]) == {"b", "c"}


@pytest.mark.asyncio
async def test_assign_z_requires_y(client: AsyncClient, create_id):
    ext_id = await create_id("x")
    resp = await client.post(f"/api/v1/role/{ext_id}/z")
    assert resp.status_code == 422
    await client.post(f"/api/v1/role/{ext_id}/up/y")
    resp = await client.post(f"/api/v1/role/{ext_id}/z")
    assert resp.status_code == 200
    assert set(resp.json()["roles"]) == {"y", "z"}


@pytest.mark.asyncio
async def test_assign_duplicate_role_fails(client: AsyncClient, create_id):
    ext_id = await create_id("a")
    resp = await client.post(f"/api/v1/role/{ext_id}/a")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_assign_nonexistent_role_fails(client: AsyncClient, create_id):
    ext_id = await create_id("a")
    resp = await client.post(f"/api/v1/role/{ext_id}/nonexistent")
    assert resp.status_code == 404


# ── forbids_role ────────────────────────────────────────

@pytest.mark.asyncio
async def test_forbids_role_blocks_assignment(client: AsyncClient, create_id):
    resp = await client.post(
        "/api/v1/config/roles",
        json={"to_role": "vip", "mode": "add", "forbids_role": "b"},
    )
    assert resp.status_code == 201
    rule_id = resp.json()["id"]

    ext_id = await create_id("a")
    await client.post(f"/api/v1/role/{ext_id}/up/b")

    resp = await client.post(f"/api/v1/role/{ext_id}/vip")
    assert resp.status_code == 422

    await client.delete(f"/api/v1/config/roles/{rule_id}")


@pytest.mark.asyncio
async def test_forbids_role_allows_when_absent(client: AsyncClient, create_id):
    resp = await client.post(
        "/api/v1/config/roles",
        json={"to_role": "vip2", "mode": "add", "forbids_role": "b"},
    )
    rule_id = resp.json()["id"]

    ext_id = await create_id("x")
    resp = await client.post(f"/api/v1/role/{ext_id}/vip2")
    assert resp.status_code == 200

    await client.delete(f"/api/v1/config/roles/{rule_id}")


@pytest.mark.asyncio
async def test_forbids_role_in_promotion(client: AsyncClient, create_id):
    resp = await client.post(
        "/api/v1/config/roles",
        json={
            "from_role": "b",
            "to_role": "super",
            "mode": "replace",
            "forbids_role": "c",
        },
    )
    rule_id = resp.json()["id"]

    ext_id = await create_id("a")
    await client.post(f"/api/v1/role/{ext_id}/up/b")
    await client.post(f"/api/v1/role/{ext_id}/c")  # agora tem b + c

    resp = await client.post(f"/api/v1/role/{ext_id}/up/super")
    assert resp.status_code == 422  # 'c' ativa proíbe promoção para 'super'

    await client.delete(f"/api/v1/config/roles/{rule_id}")


# ── Multi-role accumulation ─────────────────────────────

@pytest.mark.asyncio
async def test_full_accumulation_both_lines(client: AsyncClient, create_id):
    ext_id = await create_id("a")
    await client.post(f"/api/v1/role/{ext_id}/up/b")
    await client.post(f"/api/v1/role/{ext_id}/c")
    await client.post(f"/api/v1/role/{ext_id}/x")
    await client.post(f"/api/v1/role/{ext_id}/up/y")
    await client.post(f"/api/v1/role/{ext_id}/z")

    resp = await client.get(f"/api/v1/role/{ext_id}")
    assert resp.status_code == 200
    assert set(resp.json()["roles"]) == {"b", "c", "y", "z"}
