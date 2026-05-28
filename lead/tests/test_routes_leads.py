"""Testes para endpoints demilitarized de leads (CRUD)."""

import asyncio

import pytest
from uuid import uuid4


@pytest.mark.asyncio
class TestListLeads:
    """GET /api/v1/demilitarized/leads"""

    async def test_empty_list(self, client):
        resp = await client.get("/api/v1/demilitarized/leads")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_with_leads(self, client, make_lead):
        id1 = await make_lead(status="captured")
        id2 = await make_lead(status="waiting")

        resp = await client.get("/api/v1/demilitarized/leads")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 2
        external_ids = [d["external_id"] for d in data]
        assert str(id1) in external_ids
        assert str(id2) in external_ids

    # COD-19 v2
    async def test_list_ordered_by_created_at_desc(self, client, make_lead):
        id1 = await make_lead(status="captured")
        await asyncio.sleep(0.01)  # garante created_at diferente
        id2 = await make_lead(status="waiting")

        resp = await client.get("/api/v1/demilitarized/leads")
        data = resp.json()
        # O mais recente (id2) deve vir primeiro
        assert len(data) >= 2
        assert data[0]["external_id"] == str(id2)
        assert data[1]["external_id"] == str(id1)


@pytest.mark.asyncio
class TestGetLead:
    """GET /api/v1/demilitarized/leads/{external_id}"""

    async def test_get_existing_lead(self, client, make_lead):
        lead_id = await make_lead(status="captured")

        resp = await client.get(f"/api/v1/demilitarized/leads/{lead_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["external_id"] == str(lead_id)
        assert data["status"] == "captured"

    async def test_get_nonexistent_lead_returns_404(self, client):
        fake_id = uuid4()
        resp = await client.get(f"/api/v1/demilitarized/leads/{fake_id}")
        assert resp.status_code == 404
        assert "nao encontrado" in resp.json()["detail"].lower()

    async def test_get_lead_returns_all_fields(self, client, make_lead):
        lead_id = await make_lead(status="completed")

        resp = await client.get(f"/api/v1/demilitarized/leads/{lead_id}")
        data = resp.json()
        assert "id" in data
        assert "external_id" in data
        assert "status" in data
        assert "created_at" in data
        assert "updated_at" in data


@pytest.mark.asyncio
class TestPatchLead:
    """PATCH /api/v1/demilitarized/leads/{external_id}"""

    async def test_patch_status(self, client, make_lead):
        lead_id = await make_lead(status="captured")

        resp = await client.patch(
            f"/api/v1/demilitarized/leads/{lead_id}",
            json={"status": "waiting"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "waiting"

    async def test_patch_promoter(self, client, make_lead):
        lead_id = await make_lead(status="captured")
        promoter_id = str(uuid4())

        resp = await client.patch(
            f"/api/v1/demilitarized/leads/{lead_id}",
            json={"promoter_external_id": promoter_id},
        )
        assert resp.status_code == 200
        assert resp.json()["promoter_external_id"] == promoter_id

    async def test_patch_nonexistent_returns_404(self, client):
        fake_id = uuid4()
        resp = await client.patch(
            f"/api/v1/demilitarized/leads/{fake_id}",
            json={"status": "waiting"},
        )
        assert resp.status_code == 404

    # COD-19 v2
    async def test_patch_invalid_status_returns_422(self, client, make_lead):
        lead_id = await make_lead()
        resp = await client.patch(
            f"/api/v1/demilitarized/leads/{lead_id}",
            json={"status": "invalid_status"},
        )
        assert resp.status_code == 422

    async def test_patch_multiple_fields(self, client, make_lead):
        lead_id = await make_lead(status="captured")
        promoter_id = str(uuid4())

        resp = await client.patch(
            f"/api/v1/demilitarized/leads/{lead_id}",
            json={"status": "completed", "promoter_external_id": promoter_id},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["promoter_external_id"] == promoter_id

    # COD-19 v3: extra edge cases
    async def test_patch_same_promoter_is_idempotent(self, client, make_lead):
        """Patch sem alteracoes (promoter ja setado) retorna OK."""
        promoter_id = uuid4()
        lead_id = await make_lead(status="captured", promoter_external_id=promoter_id)
        resp = await client.patch(
            f"/api/v1/demilitarized/leads/{lead_id}",
            json={"status": "captured"},  # mesmo status
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "captured"


@pytest.mark.asyncio
class TestDeleteLead:
    """DELETE /api/v1/demilitarized/leads/{external_id}"""

    async def test_delete_existing_lead(self, client, make_lead):
        lead_id = await make_lead()

        resp = await client.delete(f"/api/v1/demilitarized/leads/{lead_id}")
        assert resp.status_code == 204

        # Confirm deleted
        get_resp = await client.get(f"/api/v1/demilitarized/leads/{lead_id}")
        assert get_resp.status_code == 404

    async def test_delete_nonexistent_returns_404(self, client):
        fake_id = uuid4()
        resp = await client.delete(f"/api/v1/demilitarized/leads/{fake_id}")
        assert resp.status_code == 404
