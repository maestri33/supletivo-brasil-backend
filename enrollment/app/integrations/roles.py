"""Integração com o serviço `roles` (dono dos papéis do usuário).

Promoções no funil de matrícula: lead → enrollment (no webhook) e
enrollment → student (na liberação do coordenador). `promote` é idempotente
aqui — se o usuário já tem a role alvo, retorna o estado atual sem 422.
"""

from app.integrations import BaseClient, request_with_retry


class RolesClient(BaseClient):
    """GET  /api/v1/role/{ext_id}              — papéis atuais
    POST /api/v1/role/{ext_id}/up/{to_role}  — promove para o papel informado."""

    async def get_roles(self, external_id: str) -> dict:
        resp = await request_with_retry(self.client, "GET", f"/api/v1/role/{external_id}")
        return resp.json()

    async def promote(self, external_id: str, to_role: str) -> dict:
        """Promove para `to_role`. Se o usuário já tem a role, retorna o estado
        atual sem erro (idempotência defensiva — `roles.promote` no servidor
        levanta 422 quando a role já está ativa)."""
        current = await self.get_roles(external_id)
        if to_role in (current.get("roles") or []):
            return current
        resp = await request_with_retry(
            self.client, "POST", f"/api/v1/role/{external_id}/up/{to_role}"
        )
        return resp.json()
