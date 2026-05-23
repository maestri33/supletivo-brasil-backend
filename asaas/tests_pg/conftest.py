"""Harness de integracao contra Postgres real (fora de `testpaths`, roda separado).

Por que separado de tests/: o conftest principal aponta o app pra SQLite e zera o
schema das tabelas no import — incompativel com testar o comportamento de schema/commit
do Postgres (que e justamente o que o SQLite mascara). Aqui o app e importado ja
apontado pro PG, com um schema dedicado.

Uso:
    ASAAS_TEST_PG_URL='postgresql+asyncpg://teste:<senha>@10.1.20.10:5432/teste' \
        uv run pytest tests_pg/ -q

Seguranca (DB compartilhado): cria e DROPA apenas o schema ASAAS_TEST_SCHEMA
(default `asaas_test`) — nunca um schema `asaas` de producao. Sem a env var, os
testes sao pulados.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import pytest

_PG_URL = os.environ.get("ASAAS_TEST_PG_URL", "")
_SCHEMA = os.environ.get("ASAAS_TEST_SCHEMA", "asaas_test")

# Precisa rodar ANTES de qualquer `from app...` pra o engine/metadata nascerem no PG.
if _PG_URL:
    os.environ["ASAAS_APP_DB_URL"] = _PG_URL
    os.environ["DATABASE_SCHEMA"] = _SCHEMA

import pytest_asyncio  # noqa: E402


def _make_engine():
    """Engine descartavel com NullPool: conexao por uso, sem reuso entre event loops."""
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    return create_async_engine(_PG_URL, poolclass=NullPool)


async def _setup_schema() -> None:
    from sqlalchemy.schema import CreateSchema

    from app import models  # noqa: F401 — popula metadata
    from app.db import Base

    eng = _make_engine()
    async with eng.begin() as conn:
        await conn.execute(CreateSchema(_SCHEMA, if_not_exists=True))
        await conn.run_sync(Base.metadata.create_all)
    await eng.dispose()


async def _teardown_schema() -> None:
    from sqlalchemy.schema import DropSchema

    from app.db import Base

    eng = _make_engine()
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.execute(DropSchema(_SCHEMA, cascade=True, if_exists=True))
    await eng.dispose()


@pytest.fixture(scope="session", autouse=True)
def _schema_lifecycle():
    """Cria o schema dedicado no inicio e o DROPA no fim (asyncio.run isola o loop)."""
    if not _PG_URL:
        yield
        return
    asyncio.run(_setup_schema())
    yield
    asyncio.run(_teardown_schema())


@pytest_asyncio.fixture
async def db() -> AsyncIterator:
    if not _PG_URL:
        pytest.skip("ASAAS_TEST_PG_URL nao definido")
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db import Base

    eng = _make_engine()
    maker = async_sessionmaker(eng, expire_on_commit=False)
    tables = ", ".join(t.fullname for t in Base.metadata.sorted_tables)
    async with maker() as s:
        await s.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
        await s.commit()
        yield s
    await eng.dispose()


@pytest.fixture
def fake_asaas(monkeypatch):
    """Stub async do AsaasClient no modulo payment (so o HTTP do Asaas e simulado)."""
    instance = AsyncMock(name="AsaasClientStub")
    instance.__aenter__.return_value = instance
    instance.__aexit__.return_value = None
    monkeypatch.setattr("app.services.payment.AsaasClient", lambda *_a, **_k: instance)
    return instance
