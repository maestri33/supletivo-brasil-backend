"""Fixtures globais (async) — SQLite em arquivo, sem mock de DB.

Isolamento (espelha fees/tests/conftest.py):
  1. DATABASE_URL -> sqlite+aiosqlite temporário, definido ANTES de importar app.*
  2. DATABASE_SCHEMA="" — sqlite não tem schema; em prod/Postgres é coordinator.
  3. Cada teste recria as tabelas (drop+create).
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

# precisa rodar ANTES de qualquer 'from app...'
_TMP_DB = Path(tempfile.mkdtemp(prefix="coordinator-tests-")) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP_DB}"
os.environ["DATABASE_SCHEMA"] = ""

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app import models  # noqa: E402,F401  (popula o metadata)
from app.db import Base, async_session_maker, engine  # noqa: E402
from app.main import app  # noqa: E402

# sqlite não tem schema — zera em todas as tabelas (idempotente)
for _t in Base.metadata.tables.values():
    _t.schema = None
Base.metadata.schema = None


@pytest_asyncio.fixture(autouse=True)
async def _fresh_tables() -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def coordinator_id() -> str:
    return str(uuid4())


@pytest.fixture
def student_external_id() -> str:
    return str(uuid4())


@pytest.fixture
def training_external_id() -> str:
    return str(uuid4())


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """Sessão de banco isolada (SQLite) para testes unitários de service."""
    async with async_session_maker() as session:
        yield session


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Client HTTP sem auth para tests dos endpoints públicos."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c
