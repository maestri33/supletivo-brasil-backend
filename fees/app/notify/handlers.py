"""Notificações de mudança de status da taxa (§11 da CONVENTION).

São disparadas como **BackgroundTasks** (assíncronas) pelos endpoints. Cada
função abre seu próprio `httpx.AsyncClient` (o client de request já foi fechado
quando a task roda) e **nunca propaga** falha de envio — só loga (§12).

Templates em `messages/*.md`. Placeholders `{{...}}` substituídos aqui.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import structlog

from app.config import get_settings
from app.integrations.notify import NotifyClient

logger = structlog.get_logger()
MESSAGES_DIR = Path(__file__).resolve().parent / "messages"


def _render(template_name: str, **vars: str) -> str:
    content = (MESSAGES_DIR / template_name).read_text(encoding="utf-8")
    for key, value in vars.items():
        content = content.replace(f"{{{{{key}}}}}", value)
    return content


async def _send(external_id: str, content: str, *, flags: dict | None = None) -> None:
    settings = get_settings()
    try:
        async with httpx.AsyncClient(
            base_url=settings.notify_base_url, timeout=settings.http_timeout
        ) as http:
            await NotifyClient(http).send_message(external_id, content, flags=flags)
        logger.info("fee_notify_sent", external_id=external_id)
    except Exception as exc:  # noqa: BLE001 — notificação nunca quebra o fluxo (§12)
        logger.warning("fee_notify_failed", external_id=external_id, error=str(exc))


async def notify_student_access_released(student_external_id: str) -> None:
    """Parte à vista paga → acesso liberado. Notifica o aluno."""
    await _send(
        student_external_id,
        _render("fee_first_paid.md"),
        flags={"tts": True},
    )


async def notify_student_fully_paid(student_external_id: str) -> None:
    """Taxa quitada (ambas as partes). Notifica o aluno."""
    await _send(student_external_id, _render("fee_fully_paid.md"))


async def notify_coordinator_payment_failed(coordinator_external_id: str, *, kind: str) -> None:
    """Uma parcela falhou no asaas. Alerta o coordenador para agir."""
    parcela = "à vista" if kind == "upfront" else "agendada"
    await _send(
        coordinator_external_id,
        _render("fee_payment_failed.md", parcela=parcela),
    )
