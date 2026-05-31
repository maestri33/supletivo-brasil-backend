"""Visao read-only dos leads do promoter — agrega do servico `lead` (CONVENTION §6).

O promoter nao guarda lead: consulta o `lead` por httpx e devolve apenas os leads
atribuidos a este promoter. Filtro defensivo client-side por `promoter_external_id`
(o endpoint do `lead` ainda nao filtra por promoter). Se o `lead` estiver fora,
`request_with_retry` levanta IntegrationError -> 502 (lead e' essencial; nao
mascaramos a falha numa lista vazia).
"""

import httpx

from app.config import get_settings
from app.integrations.lead import LeadClient

settings = get_settings()


async def list_for_promoter(external_id: str) -> list[dict]:
    async with httpx.AsyncClient(
        base_url=settings.lead_base_url, timeout=settings.http_timeout
    ) as http:
        rows = await LeadClient(http).list_by_promoter(external_id)
    return [r for r in rows if str(r.get("promoter_external_id")) == str(external_id)]
