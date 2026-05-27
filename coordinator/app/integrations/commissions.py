"""HTTP integration with the commissions-service.

Coordinates creating commission records when a student graduates.
"""

from __future__ import annotations

import httpx

from app.utils.logging import get_logger

logger = get_logger("coordinator.integrations.commissions")


async def trigger_graduation_commission(
    *,
    commissions_base_url: str,
    coordinator_external_id: str,
    diploma_id: str,
    amount_cents: int = 50,
    timeout: float = 10.0,
) -> bool:
    """POST a new commission to the commissions-service.

    Returns True on success (2xx), False on error (logged).
    """
    url = f"{commissions_base_url.rstrip('/')}/api/v1/commissions"
    payload = {
        "recipient_external_id": coordinator_external_id,
        "recipient_role": "coordinator",
        "source_type": "graduation",
        "source_external_id": diploma_id,
        "amount_cents": amount_cents,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload)
        if resp.status_code in (200, 201):
            logger.info(
                "commissions.triggered",
                diploma_id=diploma_id,
                coordinator=coordinator_external_id,
            )
            return True
        logger.warning(
            "commissions.failed",
            diploma_id=diploma_id,
            status=resp.status_code,
            body=resp.text[:300],
        )
        return False
    except httpx.RequestError as exc:
        logger.error(
            "commissions.error",
            diploma_id=diploma_id,
            error=str(exc),
        )
        return False
