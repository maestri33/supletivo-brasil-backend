"""Serviço de logs — listagem (SQLAlchemy 2)."""

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contact import Contact
from app.models.log import Log
from app.models.message import Message
from app.utils.logging import get_logger

log = get_logger(__name__)


async def list_logs(
    session: AsyncSession, limit: int = 50, offset: int = 0,
) -> list[Log]:
    result = await session.scalars(
        select(Log).order_by(Log.created_at.desc()).offset(offset).limit(limit)
    )
    return list(result.all())


async def list_logs_by_message(
    session: AsyncSession, message_id: int, limit: int = 50, offset: int = 0,
) -> list[Log]:
    result = await session.scalars(
        select(Log)
        .where(Log.message_id == message_id)
        .order_by(Log.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.all())


async def list_logs_by_external_id(
    session: AsyncSession,
    external_id: UUID,
    limit: int = 100,
    offset: int = 0,
) -> list[Log]:
    """Timeline de logs por usuario.

    Inclui logs com `external_id` direto OU logs ligados a mensagens cujo
    contact aponta para esse external_id (cobre logs criados antes da
    migration 0002 que ainda nao tem external_id direto).
    """
    contact_id_stmt = (
        select(Contact.id).where(Contact.external_id == external_id).scalar_subquery()
    )
    message_ids_stmt = (
        select(Message.id).where(Message.contact_id == contact_id_stmt).scalar_subquery()
    )

    stmt = (
        select(Log)
        .where(
            or_(
                Log.external_id == external_id,
                Log.message_id.in_(message_ids_stmt),
            )
        )
        .order_by(Log.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.scalars(stmt)
    return list(result.all())
