"""Integracao com o servico interno `asaas` (dono da integracao Asaas/PIX).

CONVENTION §12: o candidate NAO fala com a API Asaas direto — usa o app `asaas`.
"""

from app.integrations import BaseClient, request_with_retry


class AsaasClient(BaseClient):
    """POST /api/v1/pixkey        — valida no DICT + confere titular + cadastra
    GET  /api/v1/pixkey/{ext_id} — busca chave cadastrada por external_id"""

    async def create_pixkey(
        self,
        *,
        external_id: str,
        document: str,
        key: str,
        key_type: str,
    ) -> dict:
        resp = await request_with_retry(
            self.client,
            "POST",
            "/api/v1/pixkey",
            json={
                "external_id": external_id,
                "document": document,
                "key": key,
                "key_type": key_type,
            },
        )
        return resp.json()

    async def get_pixkey(self, external_id: str) -> dict:
        resp = await request_with_retry(self.client, "GET", f"/api/v1/pixkey/{external_id}")
        return resp.json()
