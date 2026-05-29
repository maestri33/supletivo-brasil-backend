"""Integracao com o app `profiles` — dono dos dados pessoais (§11).

Usado para descobrir o gender do aluno (regra reservista obrigatorio so' p/ homem).
"""

from app.integrations import BaseClient, request_with_retry


class ProfilesClient(BaseClient):
    """GET /api/v1/profiles/{external_id} — detalhe completo (inclui gender)."""

    async def get_one(self, external_id: str) -> dict:
        resp = await request_with_retry(
            self.client, "GET", f"/api/v1/profiles/{external_id}"
        )
        return resp.json()
