"""Tests for the integration verification agent.

Uses httpx mock to simulate InfinitePay API responses — no real API calls.
Covers: full success, connectivity failure, unexpected API response.
"""

from __future__ import annotations

import pytest
import respx
from httpx import Response

from app.services.verification_agent import CheckResult, VerificationReport, run_verification

INFINITEPAY_BASE = "https://api.checkout.infinitepay.io"


@pytest.fixture
def mock_infinitepay():
    with respx.mock(base_url=INFINITEPAY_BASE) as rsps:
        yield rsps


class TestVerificationAgent:
    async def test_all_checks_pass(self, mock_infinitepay):
        """All three checks pass when API returns valid responses."""
        mock_infinitepay.get("/").mock(return_value=Response(404, json={"error": "not found"}))
        mock_infinitepay.post("/links").mock(
            return_value=Response(200, json={
                "success": True,
                "url": "https://pay.infinitepay.io/test/abc123",
                "checkout_url": "https://pay.infinitepay.io/test/abc123",
            })
        )
        mock_infinitepay.post("/payment_check").mock(
            return_value=Response(200, json={"success": True, "paid": False})
        )

        report = await run_verification()

        assert report.ok is True
        assert len(report.checks) == 3
        assert all(c.passed for c in report.checks)
        assert report.checks[0].name == "connectivity"
        assert report.checks[1].name == "create_checkout"
        assert report.checks[2].name == "payment_check"

        d = report.to_dict()
        assert d["ok"] is True
        assert len(d["checks"]) == 3
        assert all("latency_ms" in c for c in d["checks"])

    async def test_connectivity_failure(self, mock_infinitepay):
        """When connectivity fails, report shows failure and remaining checks still run."""
        mock_infinitepay.get("/").mock(side_effect=Exception("Connection refused"))
        mock_infinitepay.post("/links").mock(
            return_value=Response(200, json={"success": True, "url": "https://x.io/pay"})
        )
        mock_infinitepay.post("/payment_check").mock(
            return_value=Response(200, json={"success": True})
        )

        report = await run_verification()

        assert report.ok is False
        assert report.checks[0].passed is False
        assert report.checks[0].error is not None
        assert "Connection refused" in report.checks[0].error

    async def test_create_checkout_server_error(self, mock_infinitepay):
        """When InfinitePay returns 500, create_checkout check fails."""
        mock_infinitepay.get("/").mock(return_value=Response(200))
        mock_infinitepay.post("/links").mock(return_value=Response(500, json={"error": "internal"}))
        mock_infinitepay.post("/payment_check").mock(
            return_value=Response(200, json={"success": True})
        )

        report = await run_verification()

        assert report.ok is False
        assert report.checks[1].passed is False
        assert report.checks[1].error is not None
        assert "500" in report.checks[1].error

    async def test_create_checkout_4xx_is_ok(self, mock_infinitepay):
        """4xx from /links means endpoint is alive — check passes with error note."""
        mock_infinitepay.get("/").mock(return_value=Response(200))
        mock_infinitepay.post("/links").mock(
            return_value=Response(422, json={"detail": "validation error"})
        )
        mock_infinitepay.post("/payment_check").mock(
            return_value=Response(200, json={"success": True})
        )

        report = await run_verification()

        assert report.ok is True
        assert report.checks[1].passed is True
        assert report.checks[1].error is not None
        assert "422" in report.checks[1].error

    async def test_payment_check_failure_is_ok(self, mock_infinitepay):
        """payment_check returning error JSON still counts as passed (endpoint alive)."""
        mock_infinitepay.get("/").mock(return_value=Response(200))
        mock_infinitepay.post("/links").mock(
            return_value=Response(200, json={"success": True, "url": "https://x.io/pay"})
        )
        mock_infinitepay.post("/payment_check").mock(
            return_value=Response(400, json={"success": False, "error": "not found"})
        )

        report = await run_verification()

        assert report.ok is True
        assert report.checks[2].passed is True

    async def test_non_json_response(self, mock_infinitepay):
        """Non-JSON response from InfinitePay should fail the check."""
        mock_infinitepay.get("/").mock(return_value=Response(200))
        mock_infinitepay.post("/links").mock(
            return_value=Response(200, text="<html>error</html>")
        )
        mock_infinitepay.post("/payment_check").mock(
            return_value=Response(200, json={"success": True})
        )

        report = await run_verification()

        assert report.ok is False
        assert report.checks[1].passed is False
        assert report.checks[1].error is not None
        assert "Non-JSON" in report.checks[1].error

    async def test_timeout_handled(self, mock_infinitepay):
        """Timeout should be caught and reported, not crash."""
        import httpx
        mock_infinitepay.get("/").mock(side_effect=httpx.TimeoutException("timed out"))
        mock_infinitepay.post("/links").mock(
            return_value=Response(200, json={"success": True, "url": "https://x.io/pay"})
        )
        mock_infinitepay.post("/payment_check").mock(
            return_value=Response(200, json={"success": True})
        )

        report = await run_verification()

        assert report.ok is False
        assert report.checks[0].error is not None
        assert "Timeout" in report.checks[0].error


class TestCheckResult:
    def test_to_dict_serialization(self):
        report = VerificationReport(
            ok=False,
            checks=[
                CheckResult(name="connectivity", passed=True, latency_ms=42.5),
                CheckResult(
                    name="create_checkout", passed=False,
                    latency_ms=100.0, error="HTTP 500",
                ),
            ],
        )
        d = report.to_dict()
        assert d["ok"] is False
        assert len(d["checks"]) == 2
        assert d["checks"][0]["latency_ms"] == 42.5
        assert d["checks"][1]["error"] == "HTTP 500"
