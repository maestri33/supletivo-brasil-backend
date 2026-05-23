"""Camada de banco — SQLAlchemy async + Base com schema roles."""

from collections.abc import AsyncIterator

from sqlalchemy import Column, MetaData, Table
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

NAMING_CONVENTION = {
    "ix": "%(column_0_label)s_idx",
    "uq": "%(table_name)s_%(column_0_name)s_key",
    "ck": "%(table_name)s_%(constraint_name)s_check",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "pk": "%(table_name)s_pkey",
}

metadata = MetaData(
    naming_convention=NAMING_CONVENTION,
    schema=settings.DATABASE_SCHEMA,
)


class Base(DeclarativeBase):
    metadata = metadata


# Shadow auth.users — necessário pro SQLAlchemy resolver FK cross-schema.
auth_users = Table(
    "users",
    metadata,
    Column("external_id", PG_UUID(as_uuid=True), primary_key=True),
    schema="auth",
)


engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
