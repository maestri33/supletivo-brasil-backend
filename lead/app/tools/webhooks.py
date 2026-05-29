import httpx
import structlog

from app.config import settings

logger = structlog.get_logger()

# UUID sentinel para "sem promoter" (lead orgânico/sem indicação).
# Quando o lead nao tem promoter real (PROMOTER_DEFAULT), nao faz sentido
# chamar o promoter service — promoter_events tem FK em auth.users e esse UUID
# nao existe la, entao a chamada sempre falha com 500 (FK violation).
_SENTINEL_PROMOTER = "00000000-0000-0000-0000-000000000000"


def _is_sentinel(uuid_str: str | None) -> bool:
    return not uuid_str or uuid_str == _SENTINEL_PROMOTER


async def notify_enrollment(external_id: str, promoter_external_id: str):
    log = logger.bind(external_id=external_id, promoter=promoter_external_id)
    base = settings.WEBHOOK_ENROLLMENT_URL
    if not base:
        log.warning("webhook_enrollment_not_configured")
        return
    url = f"{base.rstrip('/')}/{external_id}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                url,
                json={
                    "promoter_external_id": promoter_external_id,
                    "event": "lead.completed",
                },
            )
            resp.raise_for_status()
            log.info("webhook_enrollment_sent", status=resp.status_code)
    except Exception as exc:
        log.error("webhook_enrollment_failed", error=str(exc))


async def notify_promoter_completed(external_id: str, promoter_external_id: str):
    log = logger.bind(lead=external_id, promoter=promoter_external_id)
    # Pular notificacao quando promoter e' o sentinel (lead organico).
    # Sem isso, promoter_service tenta INSERT em promoter_events com
    # promoter_external_id=00000000... e quebra FK constraint (500).
    if _is_sentinel(promoter_external_id):
        log.info("webhook_promoter_skipped_sentinel")
        return
    base = settings.WEBHOOK_PROMOTERS_URL
    if not base:
        log.warning("webhook_promoters_not_configured")
        return
    url = f"{base.rstrip('/')}/{promoter_external_id}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                url,
                json={
                    "external_id": external_id,
                    "event": "lead.completed",
                },
            )
            resp.raise_for_status()
            log.info("webhook_promoter_sent", status=resp.status_code)
    except Exception as exc:
        log.error("webhook_promoter_failed", error=str(exc))
