"""Integracao com o app `commissions` — dispara a comissao do coordenador
quando o aluno vira veterano (CONVENTION §12, idempotente por source_external_id).
"""

from app.integrations import BaseClient, request_with_retry


class CommissionsClient(BaseClient):
    """POST /api/v1/commissions — cria registro de comissao.

    Reenvio com o mesmo `source_external_id` retorna o registro existente
    (idempotencia no lado do `commissions`).
    """

    async def trigger_graduation(
        self,
        *,
        coordinator_external_id: str,
        source_external_id: str,
        amount_cents: int,
    ) -> dict:
        resp = await request_with_retry(
            self.client,
            "POST",
            "/api/v1/commissions",
            json={
                "recipient_external_id": coordinator_external_id,
                "recipient_role": "coordinator",
                "source_type": "graduation",
                "source_external_id": source_external_id,
                "amount_cents": amount_cents,
            },
        )
        return resp.json()
