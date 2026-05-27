"""Camada de banco — SQLAlchemy async + Base com schema hub.

Sem shadow table / FK cross-schema: o hub é registro fino e suas referências
externas (address, coordinator) são `external_id` UUID puro, nullable.
"""

from collections.abc import AsyncIterator

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


engine = create_async_engine(settings.database_url, pool_pre_ping=True)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
