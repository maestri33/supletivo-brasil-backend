"""Notificacoes do funil do aluno (§13) — sempre async, tolerantes a falha."""

from __future__ import annotations

from pathlib import Path

import httpx

from app.config import get_settings
from app.integrations.notify import NotifyClient
from app.models import StudentStatus
from app.utils.logging import get_logger

logger = get_logger("student.notifications")
settings = get_settings()

# Mensagens em notify/messages/<status>.md — formato: 1a linha = titulo, resto = corpo.
_MESSAGES_DIR = Path(__file__).resolve().parent.parent / "notify" / "messages"


def _load_message(status_value: str) -> tuple[str, str] | None:
    path = _MESSAGES_DIR / f"{status_value}.md"
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return None
    lines = text.splitlines()
    title = lines[0].lstrip("# ").strip()
    body = "\n".join(lines[1:]).strip()
    return title, body or title


async def notify_status_changed(external_id: str, status: StudentStatus) -> None:
    """Avisa o aluno da mudanca de status, se houver template para esse status."""
    msg = _load_message(status.value)
    if msg is None:
        return
    title, content = msg
    try:
        async with httpx.AsyncClient(
            base_url=settings.notify_base_url, timeout=settings.http_timeout
        ) as client:
            await NotifyClient(client).send_message(
                external_id=external_id, content=content, title=title
            )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "notify.status_failed",
            external_id=external_id,
            status=status.value,
            error=str(exc),
        )
