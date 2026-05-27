"""Camada de banco — SQLAlchemy async + Base com schema `fees`.

Espelha o padrão de `asaas`/`enrollment`: engine async (asyncpg), naming
convention para constraints e `get_session()` como dependency FastAPI.
"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

NAMING_CONVENTION = {
    "ix": "%(column_0_label)s_idx",
    "uq": "%(table_name)s_%(column_0_name)s_key",
    "ck": "%(table_name)s_%(constraint_name)s_check",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "pk": "%(table_name)s_pkey",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION, schema=settings.database_schema)


class Base(DeclarativeBase):
    metadata = metadata


def utcnow() -> datetime:
    """Timestamp aware em UTC — default das colunas timestamptz."""
    return datetime.now(UTC)


engine = create_async_engine(settings.database_url, pool_pre_ping=True)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: uma session por request."""
    async with async_session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def close_db() -> None:
    await engine.dispose()
