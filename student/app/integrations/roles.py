"""Integracao com o app `roles` (CONVENTION §8).

Usado para promover o aluno a `veterano` mantendo o role `student` (multi-role).
"""

from app.integrations import BaseClient, request_with_retry


class RolesClient(BaseClient):
    """POST /role/{external_id}/up/{to_role}  -> {external_id, roles: [...]}
    GET  /role/{external_id}                -> roles atuais
    """

    async def get_roles(self, external_id: str) -> dict:
        resp = await request_with_retry(self.client, "GET", f"/role/{external_id}")
        return resp.json()

    async def promote(self, external_id: str, to_role: str) -> dict:
        resp = await request_with_retry(
            self.client, "POST", f"/role/{external_id}/up/{to_role}"
        )
        return resp.json()
