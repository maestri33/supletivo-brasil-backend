"""Fixtures globais — SQLAlchemy 2 async com Postgres REAL (sem mock).

Fonte do Postgres de teste, em ordem de preferência:
  1. `testcontainers[postgres]` instalado + docker daemon (zero config local).
  2. Env var `TEST_DATABASE_URL` apontando p/ um Postgres já em pé.
  3. Nenhum dos dois → testes que dependem de `engine` são SKIP com msg clara.

Por que Postgres real? O modelo usa PG_UUID e schema `hub` — não portável p/
SQLite. Mesmo padrão dos serviços enrollment/notify.
"""

from __future__ import annotations

import os

# `database_url` é obrigatório (sem default no código). Nos testes o engine real
# vem de TEST_DATABASE_URL/testcontainers; este placeholder só permite importar
# app.config/app.db (o engine de módulo nunca conecta nos testes).
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://v7m:v7m@localhost:5432/v7m")

from collections.abc import AsyncIterator
from contextlib import contextmanager
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

import app.models  # noqa: F401  (registra os models em Base.metadata p/ create_all)
from app.db import Base, get_session
from app.main import app

SCHEMA = "hub"


def _coerce_to_asyncpg(url: str) -> str:
    """Força o driver asyncpg em URLs vindas do testcontainers/etc."""
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


@contextmanager
def _postgres_url_provider():
    env_url = os.environ.get("TEST_DATABASE_URL")
    if env_url:
        yield _coerce_to_asyncpg(env_url)
        return

    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        yield None
        return

    try:
        with PostgresContainer("postgres:16-alpine") as pg:
            yield _coerce_to_asyncpg(pg.get_connection_url())
    except Exception as exc:  # docker offline ou outro erro
        pytest.skip(
            f"testcontainers falhou ao subir Postgres: {exc!r}. "
            "Garanta docker rodando OU exporte TEST_DATABASE_URL."
        )


@pytest_asyncio.fixture(scope="session")
async def engine() -> AsyncIterator[Any]:
    """Engine de sessão. Cria o schema `hub` + tabelas a partir do metadata.
    Limpa tudo no teardown."""
    with _postgres_url_provider() as url:
        if url is None:
            pytest.skip(
                "Sem fonte de Postgres para testes. Instale "
                "`testcontainers[postgres]` + docker, OU exporte "
                "TEST_DATABASE_URL=postgresql+asyncpg://user:pass@host/db"
            )

        eng = create_async_engine(url, poolclass=NullPool)
        try:
            async with eng.begin() as conn:
                await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
                await conn.run_sync(Base.metadata.create_all)
            yield eng
        finally:
            try:
                async with eng.begin() as conn:
                    await conn.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
            finally:
                await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine, monkeypatch) -> async_sessionmaker[AsyncSession]:
    """Aponta o `async_session_maker` (usado pelo /ready) para o engine de teste."""
    sm = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    monkeypatch.setattr("app.db.async_session_maker", sm)
    monkeypatch.setattr("app.main.async_session_maker", sm, raising=False)
    return sm


@pytest_asyncio.fixture(autouse=True)
async def _clean_between_tests(engine) -> AsyncIterator[None]:
    yield
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {SCHEMA}.hub RESTART IDENTITY CASCADE"))


@pytest_asyncio.fixture
async def client(session_factory) -> AsyncIterator[AsyncClient]:
    """HTTP client com session override; não dispara lifespan."""

    async def _get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_session] = _get_session
    # raise_app_exceptions=False: exceções não-tratadas viram 500 (igual prod/uvicorn).
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    try:
        async with AsyncClient(transport=transport, base_url="http://testserver") as c:
            yield c
    finally:
        app.dependency_overrides.clear()
