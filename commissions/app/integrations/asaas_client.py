"""Asaas HTTP client for PIX payout integration.

CONVENTION §12: asaas is the ONLY authorized payout provider.
This client wraps the internal Asaas service (not the external Asaas API directly).

Endpoints used (internal asaas service, NOT the public Asaas API):
- POST /api/v1/payout          — execute a PIX payout to a beneficiary
- GET  /api/v1/payout/{id}     — check payout status
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.config import get_settings
from app.integrations import BaseClient, IntegrationError, request_with_retry

_DEFAULT_TIMEOUT = 30.0


@dataclass
class PayoutResult:
    """Result from a payout attempt."""

    success: bool
    asaas_transfer_id: str | None = None
    pix_transaction_id: str | None = None
    error: str | None = None


def _make_default_client() -> httpx.AsyncClient:
    """Create a default httpx client from settings (internal asaas service)."""
    settings = get_settings()
    return httpx.AsyncClient(
        base_url=settings.asaas_base_url,
        timeout=_DEFAULT_TIMEOUT,
    )


class AsaasPayoutClient(BaseClient):
    """HTTP client to the internal Asaas service for PIX payouts.

    The Asaas service (asaas/) exposes internal endpoints for payout operations.
    This client calls those endpoints, not the external Asaas API directly.

    In dev/test mode, returns mock success without making HTTP calls.

    If no httpx.AsyncClient is provided, one is created from settings
    (asaas_base_url) for backward compatibility with callers that don't
    use dependency injection.
    """

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        super().__init__(client or _make_default_client())

    async def request_pix_payout(
        self,
        pix_key: str,
        amount_cents: int,
        description: str = "Comissão semanal",
    ) -> PayoutResult:
        """Request a PIX payout to a beneficiary.

        This calls the internal Asaas service's payout endpoint.
        In sandbox/test mode, this is a no-op that returns success.

        Args:
            pix_key: The beneficiary's PIX key.
            amount_cents: Amount in cents.
            description: Optional description for the transfer.

        Returns:
            PayoutResult with operation outcome.
        """
        # — In dev/test mode, skip real API call —
        if get_settings().env in ("dev", "test"):
            self.log.info("payout_mock", pix_key=pix_key, amount_cents=amount_cents)
            return PayoutResult(
                success=True,
                asaas_transfer_id="mock_transfer_id",
                pix_transaction_id="mock_pix_tx_id",
                error=None,
            )

        # Real call to internal asaas service
        body = {
            "pix_key": pix_key,
            "amount_cents": amount_cents,
            "description": description,
        }

        try:
            resp = await request_with_retry(
                self.client, "POST", "/api/v1/payout", json=body
            )
            data = resp.json()
            self.log.info(
                "payout_success",
                transfer_id=data.get("transfer_id"),
                pix_tx=data.get("pix_transaction_id"),
            )
            return PayoutResult(
                success=True,
                asaas_transfer_id=data.get("transfer_id"),
                pix_transaction_id=data.get("pix_transaction_id"),
            )
        except IntegrationError as exc:
            self.log.error("payout_failed", error=str(exc))
            return PayoutResult(
                success=False,
                error=str(exc),
            )

    async def get_payout_status(self, asaas_transfer_id: str) -> dict:
        """Check the status of a previously submitted payout transfer.

        Args:
            asaas_transfer_id: The Asaas transfer ID to check.

        Returns:
            Dict with status information from the Asaas service.
        """
        if get_settings().env in ("dev", "test"):
            return {"status": "CONFIRMED", "transfer_id": asaas_transfer_id}

        try:
            resp = await request_with_retry(
                self.client, "GET", f"/api/v1/payout/{asaas_transfer_id}"
            )
            return resp.json()
        except IntegrationError as exc:
            self.log.error(
                "payout_status_failed",
                transfer_id=asaas_transfer_id,
                error=str(exc),
            )
            return {
                "status": "ERROR",
                "transfer_id": asaas_transfer_id,
                "error": str(exc),
            }
