from app.integrations import BaseClient, request_with_retry


class NotifyClient(BaseClient):
    """GET   /api/v1/contacts/{external_id} — obtem contacto
    PATCH /api/v1/contacts/{external_id}/email — atualiza email
    POST  /api/v1/messages/send — envia mensagem"""

    async def get_contact(self, external_id: str) -> dict:
        resp = await request_with_retry(self.client, "GET", f"/api/v1/contacts/{external_id}")
        return resp.json()

    async def update_email(self, external_id: str, email: str) -> dict:
        resp = await request_with_retry(
            self.client,
            "PATCH",
            f"/api/v1/contacts/{external_id}/email",
            json={"email": email},
        )
        return resp.json()

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
        max_retries: int = 1,
    ) -> dict:
        """POST /api/v1/messages/send com webhook_url opcional.

        IMPORTANTE: `max_retries=1` por default — POST /messages/send NAO e
        idempotente; retry em timeout cria entrega duplicada no WhatsApp.
        Quem precisa de retry deve faze-lo na camada de negocio (e.g., re-trigger
        do flow) apos receber o webhook callback com status=failed.
        """
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
        resp = await request_with_retry(
            self.client,
            "POST",
            "/api/v1/messages/send",
            json=body,
            max_retries=max_retries,
        )
        data = resp.json()
        self.last_message_id = data.get("id") or data.get("message_id")
        return data
