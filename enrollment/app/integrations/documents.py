"""Integração com o serviço `documents` (RG e foto/selfie).

O `documents` é o dono do armazenamento; o enrollment só envia dados/fotos e
lê o estado. Slot `rg_*` para o documento de identidade e `foto` para a selfie
(mesma convenção do candidate).
"""

from app.integrations import BaseClient, request_with_retry


class DocumentsClient(BaseClient):
    """GET  /api/v1/documents/{ext_id}                — get_or_create do documento
    PUT  /api/v1/documents/{ext_id}                — atualiza campos (rg/...)
    POST /api/v1/documents/{ext_id}/images/{slot}  — upload de imagem (multipart)."""

    async def get(self, external_id: str) -> dict:
        resp = await request_with_retry(self.client, "GET", f"/api/v1/documents/{external_id}")
        return resp.json()

    async def update(self, external_id: str, payload: dict) -> dict:
        resp = await request_with_retry(
            self.client, "PUT", f"/api/v1/documents/{external_id}", json=payload
        )
        return resp.json()

    async def upload_image(
        self,
        external_id: str,
        slot: str,
        content: bytes,
        filename: str,
        mime_type: str,
    ) -> dict:
        resp = await request_with_retry(
            self.client,
            "POST",
            f"/api/v1/documents/{external_id}/images/{slot}",
            files={"file": (filename, content, mime_type)},
        )
        return resp.json()
