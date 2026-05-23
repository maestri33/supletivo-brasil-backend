"""
Notification service — sends messages via notify (10.10.10.157).
"""

import httpx

from app.integrations import notify_client as client
from app.utils.logging import get_logger

log = get_logger(__name__)


async def send_message(
    http: httpx.AsyncClient,
    *,
    external_id: str,
    content: str,
) -> dict:
    """Send a message to a contact via notify."""
    log.info("notify.message.send", external_id=external_id)
    return await client.send_message(
        http,
        external_id=external_id,
        content=content,
    )
