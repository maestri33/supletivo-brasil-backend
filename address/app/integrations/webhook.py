"""Webhook de eventos de Address — best-effort.

Portado do código original (LOCAL). Toda criação/alteração/deleção de Address
dispara um POST para `WEBHOOK_URL`. Falhas são logadas e ignoradas (não quebram
a operação principal).
"""

import httpx

from app.config import get_settings
from app.utils.logging import get_logger

settings = get_settings()
log = get_logger(__name__)


async def notify(event: str, payload: dict) -> None:
    if not settings.webhook_url:
        return
    try:
        async with httpx.AsyncClient(timeout=settings.webhook_timeout_seconds) as client:
            await client.post(
                settings.webhook_url,
                json={"event": event, "payload": payload},
            )
    except Exception:
        log.warning("webhook.failed", event=event)
