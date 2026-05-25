"""Integracao com o servico `documents` (RG/CNH/selfie).

O documents e' o dono do armazenamento de documentos e imagens; o candidate so
envia dados/fotos e le o estado.
"""

from app.integrations import BaseClient, request_with_retry


class DocumentsClient(BaseClient):
    """GET  /api/v1/documentos/{ext_id}                 — get_or_create do documento
    PUT  /api/v1/documentos/{ext_id}                 — atualiza campos (rg/cnh/...)
    POST /api/v1/documentos/{ext_id}/imagens/{slot}  — upload de imagem (multipart)"""

    async def get(self, external_id: str) -> dict:
        resp = await request_with_retry(self.client, "GET", f"/api/v1/documentos/{external_id}")
        return resp.json()

    async def update(self, external_id: str, payload: dict) -> dict:
        resp = await request_with_retry(
            self.client, "PUT", f"/api/v1/documentos/{external_id}", json=payload
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
            f"/api/v1/documentos/{external_id}/imagens/{slot}",
            files={"file": (filename, content, mime_type)},
        )
        return resp.json()
