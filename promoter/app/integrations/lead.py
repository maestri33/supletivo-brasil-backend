"""Integracao com o servico `lead` (dono do dominio de leads).

O promoter so' le: lista os leads do servico `lead`. A atribuicao do lead a um
promoter vive no `lead` (campo `promoter_external_id`), preenchida na captacao
quando a landing chama o `lead` com `ref=<external_id>`.

O endpoint atual do `lead` (`GET /api/v1/demilitarized/leads`) ainda nao filtra
por promoter; passamos o parametro (FastAPI ignora query nao declarada) e o
filtro definitivo e' aplicado no service deste servico, por seguranca.
"""

from app.integrations import BaseClient, request_with_retry


class LeadClient(BaseClient):
    """GET /api/v1/demilitarized/leads — lista leads (passa filtro por promoter)."""

    async def list_by_promoter(self, promoter_external_id: str) -> list[dict]:
        resp = await request_with_retry(
            self.client,
            "GET",
            "/api/v1/demilitarized/leads",
            params={"promoter_external_id": promoter_external_id},
        )
        data = resp.json()
        return data if isinstance(data, list) else data.get("leads", [])
