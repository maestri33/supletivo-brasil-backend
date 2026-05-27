"""
HTTP client for the notify service (10.10.10.157).

Only `send_message` is used by the OTP service.
"""

from typing import Any

import httpx

from app.config import get_settings
from app.exceptions import IntegrationError, NotifyPermanentError, NotifyTransientError
from app.integrations.http_client import request_with_retry


def _safe_json(resp: httpx.Response) -> dict | list:
    """Parse JSON safely — returns dict on non-JSON body."""
    try:
        return resp.json()
    except ValueError:
        return {"error": resp.text.strip() or f"HTTP {resp.status_code}"}


def _url(path: str) -> str:
    # notify expoe os endpoints sob /api/v1/* — incluir o prefixo aqui evita
    # 404 em chamadas tipo /messages/send.
    return f"{get_settings().notify_base_url}/api/v1{path}"


async def send_message(
    client: httpx.AsyncClient,
    *,
    external_id: str,
    content: str,
    media_url: str | None = None,
    flags: dict | None = None,
    instruction: str | None = None,
) -> dict:
    """Send a message to a contact via notify."""
    settings = get_settings()
    body: dict[str, Any] = {
        "external_id": external_id,
        "title": "Código de Verificação",
        "content": content,
        "webhook_url": f"{settings.webhook_base_url}/webhook/notify",
    }
    if media_url:
        body["media_url"] = media_url
    if flags:
        body["flags"] = flags
    if instruction:
        body["instruction"] = instruction
    try:
        resp = await request_with_retry(
            client, "POST", _url("/messages/send"), json=body, max_attempts=1, timeout=30.0
        )
    except IntegrationError as exc:
        raise NotifyTransientError(str(exc)) from exc
    if resp.status_code >= 500:
        detail = _safe_json(resp)
        raise NotifyTransientError(f"Notify send_message failed ({resp.status_code}): {detail}")
    if resp.status_code >= 400:
        detail = _safe_json(resp)
        raise NotifyPermanentError(f"Notify send_message failed ({resp.status_code}): {detail}")
    return _safe_json(resp)
