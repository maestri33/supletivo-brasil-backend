"""Integration health-check agent for InfinitePay API.

Runs end-to-end verification of the InfinitePay checkout flow:
  1. Connectivity — can we reach the API?
  2. Create checkout — POST /links with minimal payload
  3. Validate response — checkout_url present
  4. Payment check — POST /payment_check with dummy data (expect controlled failure)

Returns a structured report: {ok: bool, checks: [{name, passed, latency_ms, error}]}.
Designed for graceful degradation — never crashes the main health endpoint.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import httpx
import structlog

from app.config import get_settings

logger = structlog.get_logger("infinitepay.verification")


@dataclass
class CheckResult:
    name: str
    passed: bool
    latency_ms: float = 0.0
    error: str | None = None


@dataclass
class VerificationReport:
    ok: bool
    checks: list[CheckResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "checks": [
                {
                    "name": c.name,
                    "passed": c.passed,
                    "latency_ms": round(c.latency_ms, 2),
                    "error": c.error,
                }
                for c in self.checks
            ],
        }


async def _timed(coro):
    """Run an async callable and return (result, elapsed_ms)."""
    start = time.monotonic()
    result = await coro
    elapsed = (time.monotonic() - start) * 1000
    return result, elapsed


async def _check_connectivity(client: httpx.AsyncClient) -> CheckResult:
    """Attempt a lightweight GET to the InfinitePay base URL."""
    name = "connectivity"
    try:
        resp, ms = await _timed(client.get("/"))
        # InfinitePay API root may return 404/405 — that's fine, we just need a response.
        if resp.status_code < 500:
            return CheckResult(name=name, passed=True, latency_ms=ms)
        return CheckResult(
            name=name,
            passed=False,
            latency_ms=ms,
            error=f"HTTP {resp.status_code} from InfinitePay base URL",
        )
    except httpx.ConnectError as e:
        return CheckResult(name=name, passed=False, error=f"Connection refused: {e}")
    except httpx.TimeoutException as e:
        return CheckResult(name=name, passed=False, error=f"Timeout: {e}")
    except Exception as e:  # noqa: BLE001
        return CheckResult(name=name, passed=False, error=str(e))


async def _check_create_checkout(client: httpx.AsyncClient) -> CheckResult:
    """POST /links with a minimal test payload.

    We use a clearly-test external_id to avoid polluting real data.
    If the API rejects the payload (e.g. invalid handle), we still consider the
    check *passed* as long as we got a structured JSON response — the point is
    to verify the endpoint is reachable and speaks JSON.
    """
    name = "create_checkout"
    settings = get_settings()
    handle = settings.handle or "test_handle"

    payload = {
        "handle": handle,
        "items": [{"description": "Integration health check", "price": 100, "quantity": 1}],
        "order_nsu": "health-check-probe-00000000",
        "redirect_url": "https://example.com/health-check",
        "customer": {
            "name": "Health Check",
            "email": "healthcheck@example.com",
            "cpf": "00000000000",
        },
    }

    try:
        resp, ms = await _timed(client.post("/links", json=payload))
        try:
            data = resp.json()
        except ValueError:
            return CheckResult(
                name=name,
                passed=False,
                latency_ms=ms,
                error=f"Non-JSON response (HTTP {resp.status_code})",
            )

        if resp.status_code >= 500:
            return CheckResult(
                name=name,
                passed=False,
                latency_ms=ms,
                error=f"HTTP {resp.status_code}: {data}",
            )

        # 4xx with structured JSON = endpoint is alive, just rejected our test data
        if resp.status_code >= 400:
            return CheckResult(
                name=name,
                passed=True,
                latency_ms=ms,
                error=f"Endpoint responded HTTP {resp.status_code} (expected for test payload)",
            )

        # 2xx — check for checkout URL
        checkout_url = data.get("url") or data.get("checkout_url")
        if checkout_url:
            return CheckResult(name=name, passed=True, latency_ms=ms)

        if data.get("success") is False:
            return CheckResult(
                name=name,
                passed=True,
                latency_ms=ms,
                error="success=false (endpoint alive, test payload rejected)",
            )

        return CheckResult(
            name=name,
            passed=False,
            latency_ms=ms,
            error=f"200 but missing checkout URL: {data}",
        )

    except httpx.ConnectError as e:
        return CheckResult(name=name, passed=False, error=f"Connection refused: {e}")
    except httpx.TimeoutException as e:
        return CheckResult(name=name, passed=False, error=f"Timeout: {e}")
    except Exception as e:  # noqa: BLE001
        return CheckResult(name=name, passed=False, error=str(e))


async def _check_payment_check(client: httpx.AsyncClient) -> CheckResult:
    """POST /payment_check with dummy data.

    We expect this to fail (no real transaction) — the check passes as long as
    the API responds with structured JSON and doesn't 500.
    """
    name = "payment_check"
    settings = get_settings()
    handle = settings.handle or "test_handle"

    payload = {
        "handle": handle,
        "order_nsu": "health-check-probe-00000000",
        "transaction_nsu": "000000000",
        "slug": "health-check-probe",
    }

    try:
        resp, ms = await _timed(client.post("/payment_check", json=payload))
        try:
            data = resp.json()
        except ValueError:
            return CheckResult(
                name=name,
                passed=False,
                latency_ms=ms,
                error=f"Non-JSON response (HTTP {resp.status_code})",
            )

        if resp.status_code >= 500:
            return CheckResult(
                name=name,
                passed=False,
                latency_ms=ms,
                error=f"HTTP {resp.status_code}: {data}",
            )

        # 4xx or 2xx with structured JSON = endpoint alive
        return CheckResult(name=name, passed=True, latency_ms=ms)

    except httpx.ConnectError as e:
        return CheckResult(name=name, passed=False, error=f"Connection refused: {e}")
    except httpx.TimeoutException as e:
        return CheckResult(name=name, passed=False, error=f"Timeout: {e}")
    except Exception as e:  # noqa: BLE001
        return CheckResult(name=name, passed=False, error=str(e))


async def run_verification() -> VerificationReport:
    """Execute all integration checks and return a structured report."""
    settings = get_settings()
    client = httpx.AsyncClient(
        base_url=settings.infinitepay_base_url,
        timeout=settings.http_timeout,
    )

    checks: list[CheckResult] = []
    try:
        checks.append(await _check_connectivity(client))
        checks.append(await _check_create_checkout(client))
        checks.append(await _check_payment_check(client))
    finally:
        await client.aclose()

    all_passed = all(c.passed for c in checks)
    report = VerificationReport(ok=all_passed, checks=checks)

    logger.info(
        "verification_complete",
        ok=report.ok,
        checks=[(c.name, c.passed) for c in checks],
    )
    return report
