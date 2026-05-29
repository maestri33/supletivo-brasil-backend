"""Integracao com o servico `documents` — armazenamento real das fotos/PDFs."""

from app.integrations import BaseClient, request_with_retry


class DocumentsClient(BaseClient):
    """GET  /api/v1/documents/{ext_id}                — metadado do registro
    POST /api/v1/documents/{ext_id}/images/{slot}  — upload multipart
    GET  /api/v1/documents/{ext_id}/images/{slot}  — binario da imagem
    """

    async def get(self, external_id: str) -> dict:
        resp = await request_with_retry(self.client, "GET", f"/api/v1/documents/{external_id}")
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

    def image_url(self, external_id: str, slot: str) -> str:
        """URL absoluta da imagem para passar ao `ai` baixar server-side."""
        base = str(self.client.base_url).rstrip("/")
        return f"{base}/api/v1/documents/{external_id}/images/{slot}"
