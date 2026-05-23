"""Camada de banco — engine async + session maker + Base com schema lead."""

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


# ── Shadow auth.users (FK cross-schema target) ─────────────────────────────
# Sem isto, SQLAlchemy não consegue resolver FK→auth.users.external_id
# durante flush (cross-schema FK precisa da tabela alvo registrada no metadata).
# A tabela auth.users é criada/gerenciada pelo serviço auth — aqui é só
# uma "stub" visível pro ORM. Não vai pra Alembic (include_object filtra).
auth_users = Table(
    "users",
    metadata,
    Column("external_id", PG_UUID(as_uuid=True), primary_key=True),
    schema="auth",
)


engine = create_async_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=settings.ENVIRONMENT == "development" and settings.DEBUG,
)

async_session_maker = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: gera uma session por request."""
    async with async_session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
