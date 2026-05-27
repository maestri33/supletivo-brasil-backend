"""HTTP integration with the commissions-service.

Coordinates creating commission records when a student graduates.
"""

from __future__ import annotations

import httpx

from app.config import get_settings
from app.utils.logging import get_logger

logger = get_logger("coordinator.integrations.commissions")


async def trigger_coordinator_commission(
    *,
    coordinator_external_id: str,
    diploma_id: str,
) -> int | None:
    """POST a new commission to the commissions-service.

    Returns the commission ID on success, None on failure (graceful degradation —
    graduation succeeds even if the commission call fails).
    """
    settings = get_settings()
    url = f"{settings.commissions_service_url.rstrip('/')}/api/v1/commissions"
    payload = {
        "recipient_external_id": coordinator_external_id,
        "recipient_role": "coordinator",
        "source_type": "graduation",
        "source_external_id": diploma_id,
        "amount_cents": settings.coordinator_commission_cents,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
        if resp.is_success:
            data = resp.json()
            commission_id = data.get("id")
            logger.info(
                "commissions.triggered",
                diploma_id=diploma_id,
                coordinator=coordinator_external_id,
                commission_id=commission_id,
            )
            return commission_id
        logger.warning(
            "commissions.failed",
            diploma_id=diploma_id,
            status=resp.status_code,
            body=resp.text[:300],
        )
        return None
    except httpx.RequestError as exc:
        logger.error(
            "commissions.error",
            diploma_id=diploma_id,
            error=str(exc),
        )
        return None
