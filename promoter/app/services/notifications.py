"""Notificacoes do promoter (§11) — sempre assincronas e tolerantes a falha.

Agendadas via BackgroundTasks; nunca quebram o fluxo principal se o notify
estiver fora (apenas logam). Pergunta do §11 respondida: ao virar promoter,
avisamos o proprio (boas-vindas + link de captacao) e o hub (novo promoter).
"""

import httpx

from app.config import get_settings
from app.integrations.notify import NotifyClient
from app.utils.logging import get_logger

settings = get_settings()
logger = get_logger("promoter.notifications")


def ref_url(external_id: str) -> str:
    """Link de captacao que o promoter divulga."""
    return f"{settings.landing_base_url.rstrip('/')}/ref={external_id}"


async def notify_promoter_created(external_id: str, hub_external_id: str | None) -> None:
    """Boas-vindas ao novo promoter (com seu link) + aviso ao hub."""
    async with httpx.AsyncClient(
        base_url=settings.notify_base_url, timeout=settings.http_timeout
    ) as client:
        notify = NotifyClient(client)
        try:
            await notify.send_message(
                external_id=external_id,
                content=(
                    "Parabens, voce agora e' um promotor! "
                    f"Divulgue seu link para captar leads: {ref_url(external_id)}"
                ),
                title="Voce virou promotor",
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("notify_promoter_failed", external_id=external_id, error=str(exc))

        if hub_external_id:
            try:
                await notify.send_message(
                    external_id=hub_external_id,
                    content="Um novo promotor foi aprovado no seu polo.",
                    title="Novo promotor",
                    flags={"promoter_external_id": external_id},
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("notify_hub_failed", external_id=external_id, error=str(exc))
