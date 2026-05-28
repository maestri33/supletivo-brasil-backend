"""Integracao com o servico `notify` — envia mensagens (best-effort, CONVENTION §13).

Falha de notify NUNCA quebra o fluxo: o caller envolve em try/except + log.
"""

import httpx

from app.config import get_settings
from app.integrations import BaseClient, request_with_retry


class NotifyClient(BaseClient):
    async def send_message(
        self,
        external_id: str,
        content: str,
        *,
        title: str | None = None,
        flags: dict | None = None,
    ) -> dict:
        body: dict = {"external_id": external_id, "content": content}
        if title is not None:
            body["title"] = title
        if flags is not None:
            body["flags"] = flags
        resp = await request_with_retry(self.client, "POST", "/api/v1/messages/send", json=body)
        return resp.json()


def notify_http_client() -> httpx.AsyncClient:
    s = get_settings()
    return httpx.AsyncClient(base_url=s.notify_base_url, timeout=s.http_timeout)
