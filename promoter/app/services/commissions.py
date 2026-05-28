"""Visao read-only das comissoes do promoter — agrega do servico `commissions`.

O servico `commissions` agora existe (Parte B concluida). O client abaixo
chama via HTTP; se o servico estiver indisponivel, degrada para
available=False + lista vazia (graceful degradation).
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
