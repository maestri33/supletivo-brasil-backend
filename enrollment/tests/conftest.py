"""Fixtures globais — SQLAlchemy 2 async com Postgres REAL (sem mock).

Fonte do Postgres de teste, em ordem de preferência:
  1. `testcontainers[postgres]` instalado + docker daemon (zero config local).
  2. Env var `TEST_DATABASE_URL` apontando p/ um Postgres já em pé
     (ex.: o container `enrollment-e2e-pg`).
  3. Nenhum dos dois → testes que dependem de `engine` são SKIP com msg clara.

Por que Postgres real? O modelo usa PG_UUID, JSONB, schema `enrollment` e
FK cross-schema p/ `auth.users` — nada disso é portável pra SQLite. Mesmo
padrão do serviço `notify` (ver notify/tests/conftest.py).
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import contextmanager
from typing import Any
from uuid import UUID, uuid4

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

from app.db import Base, get_session
from app.main import app


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
    """Engine de sessão. Cria schemas `auth` + `enrollment` e as tabelas
    (shadow `auth.users` + `enrollment.enrollment_events`) a partir do
    metadata. Limpa tudo no teardown."""
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
                await conn.execute(text("CREATE SCHEMA IF NOT EXISTS auth"))
                await conn.execute(text("CREATE SCHEMA IF NOT EXISTS enrollment"))
                await conn.run_sync(Base.metadata.create_all)
            yield eng
        finally:
            try:
                async with eng.begin() as conn:
                    await conn.execute(text("DROP SCHEMA IF EXISTS enrollment CASCADE"))
                    await conn.execute(text("DROP SCHEMA IF EXISTS auth CASCADE"))
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
        await conn.execute(
            text("TRUNCATE enrollment.enrollment_events RESTART IDENTITY CASCADE")
        )
        await conn.execute(text("DELETE FROM auth.users"))


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


@pytest_asyncio.fixture
async def make_auth_user(session_factory):
    """Cria um external_id em `auth.users` (shadow) para satisfazer a FK.
    Retorna o UUID como string."""

    async def _make(external_id: UUID | str | None = None) -> str:
        eid = UUID(str(external_id)) if external_id else uuid4()
        async with session_factory() as session:
            await session.execute(
                text("INSERT INTO auth.users (external_id) VALUES (:eid)"),
                {"eid": str(eid)},
            )
            await session.commit()
        return str(eid)

    return _make
