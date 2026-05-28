"""Integracao com o app `notify` (CONVENTION §7, §13)."""

from app.integrations import BaseClient, request_with_retry


class NotifyClient(BaseClient):
    """POST /api/v1/messages/send — envia mensagem para um external_id."""

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
