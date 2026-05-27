from app.integrations import BaseClient, request_with_retry


class ProfilesClient(BaseClient):
    """GET   /api/v1/profiles/{external_id} — detalhe completo
    PATCH /api/v1/profiles/{external_id} — atualiza campos"""

    async def get_one(self, external_id: str) -> dict:
        resp = await request_with_retry(self.client, "GET", f"/api/v1/profiles/{external_id}")
        return resp.json()

    async def first_name(self, external_id: str) -> dict:
        resp = await request_with_retry(
            self.client, "GET", f"/api/v1/profiles/first-name/{external_id}"
        )
        return resp.json()

    async def patch(self, external_id: str, **fields) -> dict:
        resp = await request_with_retry(
            self.client,
            "PATCH",
            f"/api/v1/profiles/{external_id}",
            json=fields,
        )
        return resp.json()
