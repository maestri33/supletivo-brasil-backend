"""Alembic env — schema `lead` no Postgres central."""

import asyncio
from logging.config import fileConfig

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from app.config import settings
from app.db import Base
import app.models  # noqa: F401 — registra models no Base.metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
SCHEMA = settings.DATABASE_SCHEMA


def include_object(object, name, type_, reflected, compare_to):
    """Ignora tabelas/objetos de outros schemas (e.g. auth.users referenciada via FK)."""
    if type_ == "table" and getattr(object, "schema", None) and object.schema != SCHEMA:
        return False
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        version_table_schema=SCHEMA,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        version_table_schema=SCHEMA,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = create_async_engine(settings.DATABASE_URL)
    # A tabela alembic_version vive em `version_table_schema=SCHEMA`, então o
    # schema precisa existir antes do primeiro upgrade num banco novo (em prod
    # já existe). Cria e commita numa conexão própria — fora da transação das
    # migrations, senão o autobegin impede o commit do upgrade.
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
