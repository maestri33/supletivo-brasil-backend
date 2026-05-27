"""Visao read-only das comissoes do promoter — agrega do servico `commissions`.

PENDENCIA (documentada, sem TODO orfao): o servico `commissions` ainda nao existe
(so' spec/TODO). Nao inventamos o contrato dele (CONVENTION §2). Enquanto nao
existir/estiver fora, a visao degrada para `available=False` + lista vazia, sem
quebrar o fluxo (§12). Quando `commissions` for construido, basta o client
responder — nenhum ajuste necessario aqui.
"""

import httpx

from app.config import get_settings
from app.exceptions import IntegrationError
from app.integrations.commissions import CommissionsClient
from app.utils.logging import get_logger

settings = get_settings()
logger = get_logger("promoter.commissions")


async def list_for_promoter(external_id: str) -> tuple[bool, list[dict]]:
    """Retorna (available, comissoes). available=False quando o servico nao responde."""
    try:
        async with httpx.AsyncClient(
            base_url=settings.commissions_base_url, timeout=settings.http_timeout
        ) as http:
            rows = await CommissionsClient(http).list_by_promoter(external_id)
        return True, rows
    except (IntegrationError, httpx.HTTPError) as exc:
        logger.warning("commissions_unavailable", external_id=external_id, error=str(exc))
        return False, []
