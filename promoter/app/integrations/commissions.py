"""Integracao com o servico `commissions` (dono do dominio de comissoes).

ATENCAO: o servico `commissions` ainda nao existe (apenas spec/TODO). Nao
inventamos o contrato dele (CONVENTION §2). Este client assume um endpoint de
listagem por promoter; quando `commissions` for construido, ajuste a rota/parsing.
Ate la', o service degrada para "indisponivel" sem quebrar o fluxo (§12).
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
