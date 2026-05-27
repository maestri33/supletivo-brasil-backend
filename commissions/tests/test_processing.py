"""Tests for the processing trigger endpoint and batch creation.

Uses the `client` fixture from conftest.py — an ASGI test client
that runs the full FastAPI app over SQLite.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

_PROJECTION_PATCH = "app.integrations.asaas_client.AsaasPayoutClient.request_pix_payout"


class TestProcessing:
    """Test suite for the processing trigger endpoint."""

    async def _create_commission(self, client: AsyncClient, overrides: dict | None = None) -> dict:
        """Helper to create a commission."""
        payload = {
            "recipient_external_id": "550e8400-e29b-41d4-a716-446655440000",
            "recipient_role": "promoter",
            "source_type": "lead",
            "source_external_id": "550e8400-e29b-41d4-a716-446655440001",
            "amount_cents": 100,
        }
        if overrides:
            payload.update(overrides)
        resp = await client.post("/api/v1/commissions", json=payload)
        return resp.json()

    async def test_trigger_processing_no_commissions(self, client: AsyncClient) -> None:
        """Should return success with message when no pending commissions exist."""
        resp = await client.post(
            "/api/v1/processing/trigger",
            json={
                "week_of": "2026-05-25",
                "force_reprocess": False,
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["success"] is True
        assert data["payment_batch_id"] is None
        assert "Nenhuma comissão pendente" in data["message"]

    async def test_trigger_processing_success(self, client: AsyncClient) -> None:
        """Should process pending commissions and create a batch."""
        # Create 3 pending commissions
        for i in range(3):
            await self._create_commission(
                client,
                {
                    "amount_cents": 100,
                    "source_external_id": f"550e8400-e29b-41d4-a716-44665544000{i}",
                },
            )

        with patch(
            _PROJECTION_PATCH,
            new=AsyncMock(
                return_value=type(
                    "PayoutResult",
                    (),
                    {
                        "success": True,
                        "asaas_transfer_id": "mock-asaas-transfer-id",
                        "pix_transaction_id": "mock-pix-tx-id",
                        "error": None,
                    },
                )()
            ),
        ):
            resp = await client.post(
                "/api/v1/processing/trigger",
                json={
                    "week_of": "2026-05-25",
                    "force_reprocess": False,
                },
            )

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["success"] is True
        assert data["payment_batch_id"] is not None
        assert "processado" in data["message"].lower()

    async def test_double_processing_prevention(self, client: AsyncClient) -> None:
        """Should not create a second batch for the same week."""
        # Create commissions
        for i in range(2):
            await self._create_commission(
                client,
                {
                    "amount_cents": 100,
                    "source_external_id": f"550e8400-e29b-41d4-a716-44665544001{i}",
                },
            )

        with patch(
            _PROJECTION_PATCH,
            new=AsyncMock(
                return_value=type(
                    "PayoutResult",
                    (),
                    {
                        "success": True,
                        "asaas_transfer_id": "mock-transfer-id",
                        "pix_transaction_id": "mock-pix-tx-id",
                        "error": None,
                    },
                )()
            ),
        ):
            # First trigger
            resp1 = await client.post(
                "/api/v1/processing/trigger",
                json={"week_of": "2026-06-01", "force_reprocess": False},
            )
            assert resp1.status_code == 200
            assert resp1.json()["payment_batch_id"] is not None

            # Second trigger for same week — should not create new batch
            resp2 = await client.post(
                "/api/v1/processing/trigger",
                json={"week_of": "2026-06-01", "force_reprocess": False},
            )
            assert resp2.status_code == 200
            data2 = resp2.json()
            assert data2["payment_batch_id"] is None
            assert "já existe" in data2["message"].lower() or "nenhuma comissão pendente" in data2[
                "message"
            ].lower()

    async def test_trigger_processing_with_bonus(self, client: AsyncClient) -> None:
        """Should apply bonus when threshold is met (>= 10 commissions)."""
        # Create 10 commissions to hit the bonus threshold
        for i in range(10):
            await self._create_commission(
                client,
                {
                    "amount_cents": 100,
                    "source_external_id": f"550e8400-e29b-41d4-a716-44665544010{i}",
                },
            )

        with patch(
            _PROJECTION_PATCH,
            new=AsyncMock(
                return_value=type(
                    "PayoutResult",
                    (),
                    {
                        "success": True,
                        "asaas_transfer_id": "mock-bonus-id",
                        "pix_transaction_id": "mock-pix-tx-id",
                        "error": None,
                    },
                )()
            ),
        ):
            resp = await client.post(
                "/api/v1/processing/trigger",
                json={"week_of": "2026-06-08", "force_reprocess": False},
            )

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["success"] is True
        batch_id = data["payment_batch_id"]
        assert batch_id is not None

        # Fetch the batch to verify bonus was applied
        resp_batch = await client.get(f"/api/v1/payment-batches/{batch_id}")
        assert resp_batch.status_code == 200
        batch_data = resp_batch.json()
        # 10 * 100 = 1000 base + 10 * 50 = 500 bonus = 1500 total
        assert batch_data["bonus_cents"] == 500
        assert batch_data["total_cents"] == 1500


class TestPaymentBatches:
    """Test suite for payment batch endpoints."""

    async def test_list_payment_batches(self, client: AsyncClient) -> None:
        """Should list payment batches."""
        resp = await client.get("/api/v1/payment-batches")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "items" in data
        assert "total" in data

    async def test_get_payment_batch_not_found(self, client: AsyncClient) -> None:
        """Should return 404 for non-existent batch."""
        resp = await client.get("/api/v1/payment-batches/99999")
        assert resp.status_code == 404, resp.text
        assert "não encontrado" in resp.json()["detail"]

    async def test_get_payment_batch_success(self, client: AsyncClient) -> None:
        """Should get a payment batch by ID after creation."""
        # Create a commission and trigger processing
        resp = await client.post(
            "/api/v1/commissions",
            json={
                "recipient_external_id": "550e8400-e29b-41d4-a716-446655440000",
                "recipient_role": "promoter",
                "source_type": "lead",
                "source_external_id": "550e8400-e29b-41d4-a716-446655440001",
                "amount_cents": 100,
            },
        )
        assert resp.status_code == 201, resp.text

        with patch(
            _PROJECTION_PATCH,
            new=AsyncMock(
                return_value=type(
                    "PayoutResult",
                    (),
                    {
                        "success": True,
                        "asaas_transfer_id": "mock-transfer-id",
                        "pix_transaction_id": "mock-pix-tx-id",
                        "error": None,
                    },
                )()
            ),
        ):
            trigger_resp = await client.post(
                "/api/v1/processing/trigger",
                json={"week_of": "2026-06-15", "force_reprocess": False},
            )
        assert trigger_resp.status_code == 200
        batch_id = trigger_resp.json()["payment_batch_id"]
        assert batch_id is not None

        # Fetch the batch
        resp = await client.get(f"/api/v1/payment-batches/{batch_id}")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["id"] == batch_id
        assert data["week_of"] == "2026-06-15"
        assert data["total_cents"] >= 100
        assert "created_at" in data
