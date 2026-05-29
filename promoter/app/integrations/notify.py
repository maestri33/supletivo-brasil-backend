from app.integrations import BaseClient, request_with_retry


class NotifyClient(BaseClient):
    """POST /api/v1/messages/send — envia mensagem (notificacao)"""

    async def send_message(
        self,
        external_id: str,
        content: str,
        *,
        title: str | None = None,
        media_url: str | None = None,
        flags: dict | None = None,
        instruction: str | None = None,
        webhook_url: str | None = None,
    ) -> dict:
        body: dict = {"external_id": external_id, "content": content}
        if title is not None:
            body["title"] = title
        if media_url is not None:
            body["media_url"] = media_url
        if flags is not None:
            body["flags"] = flags
        if instruction is not None:
            body["instruction"] = instruction
        if webhook_url is not None:
            body["webhook_url"] = webhook_url
        resp = await request_with_retry(self.client, "POST", "/api/v1/messages/send", json=body)
        return resp.json()
