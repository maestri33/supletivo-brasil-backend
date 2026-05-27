"""Testes para endpoints demilitarized de checkouts (CRUD)."""

import pytest
from uuid import uuid4


@pytest.mark.asyncio
class TestListCheckouts:
    """GET /api/v1/demilitarized/checkouts"""

    async def test_empty_list(self, client):
        resp = await client.get("/api/v1/demilitarized/checkouts")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_with_checkouts(self, client, make_checkout):
        id1 = await make_checkout(payment_method="pix", provider="asaas")
        id2 = await make_checkout(payment_method="credit_card", provider="infinitepay")

        resp = await client.get("/api/v1/demilitarized/checkouts")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 2
        eids = [d["external_id"] for d in data]
        assert str(id1) in eids
        assert str(id2) in eids


@pytest.mark.asyncio
class TestGetCheckout:
    """GET /api/v1/demilitarized/checkouts/{external_id}"""

    async def test_get_existing(self, client, make_checkout):
        cid = await make_checkout(payment_method="pix")

        resp = await client.get(f"/api/v1/demilitarized/checkouts/{cid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["external_id"] == str(cid)
        assert data["is_paid"] is False

    async def test_get_nonexistent_returns_404(self, client):
        fake_id = uuid4()
        resp = await client.get(f"/api/v1/demilitarized/checkouts/{fake_id}")
        assert resp.status_code == 404

    async def test_get_returns_all_expected_fields(self, client, make_checkout):
        cid = await make_checkout(
            payment_method="pix",
            provider="asaas",
            is_paid=True,
        )
        resp = await client.get(f"/api/v1/demilitarized/checkouts/{cid}")
        data = resp.json()
        assert data["is_paid"] is True
        assert data["payment_method"] == "pix"
        assert data["provider"] == "asaas"
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data


@pytest.mark.asyncio
class TestPatchCheckout:
    """PATCH /api/v1/demilitarized/checkouts/{external_id}"""

    async def test_patch_is_paid(self, client, make_checkout):
        cid = await make_checkout()

        resp = await client.patch(
            f"/api/v1/demilitarized/checkouts/{cid}",
            json={"is_paid": True},
        )
        assert resp.status_code == 200
        assert resp.json()["is_paid"] is True

    async def test_patch_checkout_url(self, client, make_checkout):
        cid = await make_checkout()

        resp = await client.patch(
            f"/api/v1/demilitarized/checkouts/{cid}",
            json={"checkout_url": "https://infinitepay.example.com/checkout/abc"},
        )
        assert resp.status_code == 200
        assert resp.json()["checkout_url"] == "https://infinitepay.example.com/checkout/abc"

    async def test_patch_nonexistent_returns_404(self, client):
        fake_id = uuid4()
        resp = await client.patch(
            f"/api/v1/demilitarized/checkouts/{fake_id}",
            json={"is_paid": True},
        )
        assert resp.status_code == 404

    async def test_patch_multiple_fields(self, client, make_checkout):
        cid = await make_checkout()

        resp = await client.patch(
            f"/api/v1/demilitarized/checkouts/{cid}",
            json={
                "is_paid": True,
                "receipt_url": "https://receipt.example.com/123",
                "capture_method": "ecommerce",
                "installments": 6,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_paid"] is True
        assert data["receipt_url"] == "https://receipt.example.com/123"
        assert data["capture_method"] == "ecommerce"
        assert data["installments"] == 6


@pytest.mark.asyncio
class TestDeleteCheckout:
    """DELETE /api/v1/demilitarized/checkouts/{external_id}"""

    async def test_delete_existing(self, client, make_checkout):
        cid = await make_checkout()

        resp = await client.delete(f"/api/v1/demilitarized/checkouts/{cid}")
        assert resp.status_code == 204

        # Confirm deleted
        get_resp = await client.get(f"/api/v1/demilitarized/checkouts/{cid}")
        assert get_resp.status_code == 404

    async def test_delete_nonexistent_returns_404(self, client):
        fake_id = uuid4()
        resp = await client.delete(f"/api/v1/demilitarized/checkouts/{fake_id}")
        assert resp.status_code == 404
