"""Integracao com o servico `commissions` (dono do dominio de comissoes).

O servico `commissions` agora existe (Parte B concluida). O endpoint assume
/api/v1/demilitarized/commissions com filtro por promoter_external_id.
Degrada para indisponivel se o servico nao responder (§12).
"""

from app.integrations import BaseClient, request_with_retry


class CommissionsClient(BaseClient):
    """GET /api/v1/demilitarized/commissions — lista comissoes por promoter."""

    async def list_by_promoter(self, promoter_external_id: str) -> list[dict]:
        resp = await request_with_retry(
            self.client,
            "GET",
            "/api/v1/demilitarized/commissions",
            params={"promoter_external_id": promoter_external_id},
        )
        data = resp.json()
        return data if isinstance(data, list) else data.get("commissions", [])
