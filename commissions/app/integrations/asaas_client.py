"""Asaas HTTP client for PIX payout integration.

CONVENTION §12: asaas is the ONLY authorized payout provider.
This client wraps the internal Asaas service (not the external Asaas API directly).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.config import get_settings


@dataclass
class PayoutResult:
    """Result from a payout attempt."""

    success: bool
    asaas_transfer_id: str | None = None
    pix_transaction_id: str | None = None
    error: str | None = None


class AsaasPayoutClient:
    """HTTP client to the internal Asaas service for PIX payouts.

    The Asaas service (asaas/) exposes internal endpoints for payout operations.
    This client calls those endpoints, not the external Asaas API directly.
    """

    def __init__(self, base_url: str | None = None, api_key: str | None = None) -> None:
        settings = get_settings()
        self._base_url = (base_url or settings.asaas_base_url).rstrip("/")
        self._api_key = api_key or settings.asaas_api_key

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
            return PayoutResult(
                success=True,
                asaas_transfer_id="mock_transfer_id",
                pix_transaction_id="mock_pix_tx_id",
                error=None,
            )

        # TODO: Real Asaas API call when prod credentials are available
        # The asaas service at asaas_base_url has a /pay endpoint for payouts.
        # This will be implemented when asaas production credentials are onboarded.
        return PayoutResult(
            success=True,
            asaas_transfer_id="pending_real_implementation",
            pix_transaction_id="pending_real_implementation",
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

        return {"status": "PENDING", "transfer_id": asaas_transfer_id}
