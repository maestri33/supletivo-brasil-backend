"""Integração com o serviço `notify` (CONVENTION §7, §13).

Notificações da matrícula: mudança de status (matriculando) e aviso ao
coordenador quando o funil completa. Sempre via HTTP — `notify` é o dono
exclusivo da entrega (WhatsApp/SMS/email).
"""

from app.integrations import BaseClient, request_with_retry


class NotifyClient(BaseClient):
    """GET   /api/v1/contacts/{external_id} — obtém contato
    POST  /api/v1/messages/send — envia mensagem."""

    async def get_contact(self, external_id: str) -> dict:
        resp = await request_with_retry(self.client, "GET", f"/api/v1/contacts/{external_id}")
        return resp.json()

    async def send_message(
        self,
        external_id: str,
        content: str,
        *,
        title: str | None = None,
        media_url: str | None = None,
        flags: dict | None = None,
    ) -> dict:
        body: dict = {"external_id": external_id, "content": content}
        if title is not None:
            body["title"] = title
        if media_url is not None:
            body["media_url"] = media_url
        if flags is not None:
            body["flags"] = flags
        resp = await request_with_retry(self.client, "POST", "/api/v1/messages/send", json=body)
        return resp.json()
