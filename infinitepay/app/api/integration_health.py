"""Integration health-check endpoint — verifies InfinitePay API connectivity and flow.

SECURITY (COD-91): This endpoint requires X-Internal-Api-Key header.
It creates REAL checkouts on InfinitePay production and must NEVER be public.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.deps import require_internal_api_key
from app.services.verification_agent import run_verification

logger = structlog.get_logger("infinitepay.health")
router = APIRouter()


@router.get("/health/integration")
async def integration_health(
    _api_key: str = Depends(require_internal_api_key),
):
    """Deep integration check against the InfinitePay API.

    Requires X-Internal-Api-Key header (admin-only).
    Returns 200 with {status: "ok", checks: [...]} when all checks pass.
    Returns 503 with details when any check fails.
    Never raises — always returns a structured response.
    """
    try:
        report = await run_verification()
    except Exception:  # noqa: BLE001
        logger.exception("integration_health_unexpected_error")
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "checks": [],
                "detail": "Verification agent crashed unexpectedly",
            },
        )

    if report.ok:
        return {"status": "ok", **report.to_dict()}

    return JSONResponse(
        status_code=503,
        content={"status": "degraded", **report.to_dict()},
    )
