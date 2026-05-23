from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings

settings = get_settings()

NAMING_CONVENTION = {
    "ix": "%(column_0_label)s_idx",
    "uq": "%(table_name)s_%(column_0_name)s_key",
    "ck": "%(table_name)s_%(constraint_name)s_check",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "pk": "%(table_name)s_pkey",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION, schema=settings.DB_SCHEMA or None)

engine = create_async_engine(settings.DATABASE_URL)

async_session = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    """Cria tabelas se nao existirem (dev apenas — producao usa Alembic)."""
    from app.models.user import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
