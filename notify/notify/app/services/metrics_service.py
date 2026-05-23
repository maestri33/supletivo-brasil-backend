"""Servico de metricas — agregados leves para /status e /api/v1/metrics.

Tudo Postgres-side (count/group by). Sem cache — chamadas devem ficar
sub-segundo com indices em messages/contacts/logs.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session_maker
from app.models.contact import Contact
from app.models.log import Log
from app.models.message import Message
from app.models.template import Template


async def _count_by(session: AsyncSession, column) -> dict[str, int]:
    stmt = select(column, func.count()).group_by(column)
    rows = (await session.execute(stmt)).all()
    return {str(k): int(v) for k, v in rows}


async def messages_summary(
    session: AsyncSession, window_hours: int = 24,
) -> dict[str, Any]:
    """Resumo agregado das mensagens — total all-time + last N horas."""
    since = datetime.now(tz=timezone.utc) - timedelta(hours=window_hours)

    total_all = await session.scalar(select(func.count()).select_from(Message)) or 0
    total_window = await session.scalar(
        select(func.count()).select_from(Message).where(Message.created_at >= since)
    ) or 0

    by_whatsapp = await _count_by(session, Message.whatsapp_status)
    by_email = await _count_by(session, Message.email_status)

    return {
        "total": int(total_all),
        f"last_{window_hours}h": int(total_window),
        "whatsapp_by_status": by_whatsapp,
        "email_by_status": by_email,
    }


async def top_errors(
    session: AsyncSession, window_hours: int = 24, limit: int = 5,
) -> list[dict[str, Any]]:
    """Top acoes que contem 'failed' nas ultimas N horas.

    Usa LIKE no campo action — barato com indice em created_at + filtro.
    """
    since = datetime.now(tz=timezone.utc) - timedelta(hours=window_hours)
    stmt = (
        select(Log.action, func.count())
        .where(Log.created_at >= since, Log.action.like("%fail%"))
        .group_by(Log.action)
        .order_by(func.count().desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    return [{"action": a, "count": int(c)} for a, c in rows]


async def status_snapshot(window_hours: int = 24) -> dict[str, Any]:
    """Snapshot otimizado para o endpoint /status (root).

    Abre sua propria session — pode ser chamado de qualquer lugar.
    Falha silenciosa: se algo dar errado retorna {"error": ...} pra nao
    derrubar liveness.
    """
    try:
        async with async_session_maker() as session:
            contacts_total = await session.scalar(
                select(func.count()).select_from(Contact)
            ) or 0
            templates_active = await session.scalar(
                select(func.count())
                .select_from(Template)
                .where(Template.is_active.is_(True))
            ) or 0
            msgs = await messages_summary(session, window_hours=window_hours)
            errs = await top_errors(session, window_hours=window_hours, limit=5)

        return {
            "contacts": int(contacts_total),
            "templates_active": int(templates_active),
            "messages": msgs,
            "recent_errors": errs,
        }
    except Exception as exc:  # noqa: BLE001 — /status nao pode quebrar
        return {"error": "metrics_unavailable", "detail": str(exc)[:200]}
