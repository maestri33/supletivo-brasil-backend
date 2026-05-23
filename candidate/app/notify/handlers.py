import httpx
import structlog

from app.config import settings
from app.integrations.notify import NotifyClient
from app.integrations.profiles import ProfilesClient

logger = structlog.get_logger()


async def notify_lead_captured(external_id: str):
    """Envia mensagem de boas-vindas ao lead."""
    log = logger.bind(external_id=external_id)

    async with httpx.AsyncClient(
        base_url=settings.NOTIFY_BASE_URL,
        timeout=settings.HTTP_TIMEOUT,
    ) as client:
        notify = NotifyClient(client)
        try:
            await notify.send_message(
                external_id=external_id,
                content="Seu cadastro foi realizado com sucesso! Em breve voce recebera mais informacoes.",
                title="Cadastro realizado",
            )
            log.info("lead_captured_notified")
        except Exception as exc:
            log.error("lead_captured_notify_failed", error=str(exc))


async def notify_hub_captured(
    external_id: str,
    phone: str,
    hub_external_id: str,
):
    """Notifica o hub sobre um novo lead capturado."""
    log = logger.bind(external_id=external_id, hub_external_id=hub_external_id)

    async with httpx.AsyncClient(
        base_url=settings.NOTIFY_BASE_URL,
        timeout=settings.HTTP_TIMEOUT,
    ) as client:
        notify = NotifyClient(client)
        try:
            await notify.send_message(
                external_id=hub_external_id,
                content=f"Novo lead cadastrado. Telefone: {phone}",
                title="Novo lead",
                flags={"lead_external_id": external_id},
            )
            log.info("hub_notified")
        except Exception as exc:
            log.error("hub_notify_failed", error=str(exc))
