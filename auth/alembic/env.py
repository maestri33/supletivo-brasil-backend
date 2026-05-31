import asyncio
from logging.config import fileConfig

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from app.config import get_settings
from app.db import NAMING_CONVENTION
from app.models import Base

settings = get_settings()

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
target_metadata.naming_convention = NAMING_CONVENTION


SCHEMA = settings.DB_SCHEMA or "auth"


def run_migrations_offline() -> None:
    url = settings.DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        version_table_schema=SCHEMA,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        version_table_schema=SCHEMA,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = create_async_engine(settings.DATABASE_URL)
    # Garante que o schema existe antes do primeiro upgrade num banco novo.
    async with connectable.connect() as conn:
        await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"'))
        await conn.commit()
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
