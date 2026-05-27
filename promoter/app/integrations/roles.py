"""Integracao com o servico `roles` (dono dos papeis do usuario).

Usado na criacao do promoter para promover o papel candidate -> promoter.
"""

from app.integrations import BaseClient, request_with_retry


class RolesClient(BaseClient):
    """GET  /api/v1/role/{ext_id}              — papeis atuais do usuario
    POST /api/v1/role/{ext_id}/up/{to_role}  — promove para o papel informado"""

    async def get_roles(self, external_id: str) -> dict:
        resp = await request_with_retry(self.client, "GET", f"/api/v1/role/{external_id}")
        return resp.json()

    async def promote(self, external_id: str, to_role: str) -> dict:
        resp = await request_with_retry(
            self.client, "POST", f"/api/v1/role/{external_id}/up/{to_role}"
        )
        return resp.json()
