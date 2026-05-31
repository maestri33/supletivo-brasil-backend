"""Cliente do serviço interno `notify` (envio de notificações).

Espelha `lead/app/integrations/notify.py`: só a função usada (`send_message`).
"""

from app.integrations import BaseClient, request_with_retry


class NotifyClient(BaseClient):
    """POST /api/v1/messages/send — envia mensagem a um contato (external_id)."""

    async def send_message(
        self,
        external_id: str,
        content: str,
        *,
        title: str | None = None,
        flags: dict | None = None,
        max_retries: int = 1,
    ) -> dict:
        """Dispara uma mensagem.

        `max_retries=1` por default: POST /messages/send NÃO é idempotente —
        retry em timeout duplicaria a entrega.
        """
        body: dict = {"external_id": external_id, "content": content}
        if title is not None:
            body["title"] = title
        if flags is not None:
            body["flags"] = flags
        resp = await request_with_retry(
            self.client,
            "POST",
            "/api/v1/messages/send",
            json=body,
            max_retries=max_retries,
        )
        return resp.json()
