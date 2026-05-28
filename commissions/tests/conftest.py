"""Fixtures globais (async) — SQLite em arquivo, sem mock de DB.

Fornece tanto `db_session` (para testes unitários de service)
quanto `client` (para testes de integração HTTP).

Isolamento:
  1. DATABASE_URL -> sqlite+aiosqlite temporário, definido ANTES de importar app.*
  2. DATABASE_SCHEMA="" — sqlite não tem schema; em prod/Postgres é commissions.
  3. Cada teste recria as tabelas (drop+create).
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import UUID

from sqlalchemy import BigInteger
from sqlalchemy.ext.asyncio import AsyncSession

# precisa rodar ANTES de qualquer 'from app...'
_TMP_DB = Path(tempfile.mkdtemp(prefix="commissions-tests-")) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP_DB}"
os.environ["DATABASE_SCHEMA"] = ""

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app import models  # noqa: E402,F401  (popula o metadata)
from app.db import Base, async_session_maker, engine  # noqa: E402
from app.main import app  # noqa: E402

# ── SQLite compat ──────────────────────────────────────────────────────────
# SQLite autoincrement só funciona com INTEGER, não BIGINT.
# SQLite não suporta UUID nativamente — substitui PG_UUID por String.
from sqlalchemy import Integer, String  # noqa: E402
from sqlalchemy.dialects.postgresql import UUID as PG_UUID  # noqa: E402

for _t in list(Base.metadata.tables.values()):
    for _c in list(_t.columns):
        if _c.primary_key and isinstance(_c.type, BigInteger):
            _c.type = Integer()
        if isinstance(_c.type, PG_UUID):
            _c.type = String(36)  # UUID as string for SQLite compat

# Strip schema from all tables AND fix FK colspecs that reference schema.xxx
for _t in list(Base.metadata.tables.values()):
    old_key = f"{_t.schema}.{_t.name}" if _t.schema else _t.name
    _t.schema = None
    # If old key had a dot prefix (from empty string schema), remap it
    if old_key.startswith("."):
        Base.metadata.remove(_t)
        Base.metadata._add_table(_t.name, None, _t)
    # Fix FK references that previously included schema prefix
    for _c in list(_t.columns):
        for _fk in list(_c.foreign_keys):
            old_colspec = _fk._colspec
            if "." in old_colspec:
                parts = old_colspec.rsplit(".", 1)
                if len(parts) == 2 and parts[0].isidentifier():
                    # Schema-prefixed FK (e.g. "auth.users.external_id")
                    # Remove all but the last two parts (table.column)
                    # This handles "auth.users.external_id" -> "users.external_id"
                    tokens = old_colspec.split(".")
                    if len(tokens) >= 3:
                        new_colspec = ".".join(tokens[-2:])
                    else:
                        new_colspec = tokens[-1] if len(tokens) == 2 else old_colspec
                    _fk._colspec = new_colspec
Base.metadata.schema = None

# Sample UUIDs for testing
PROMOTER_ID = UUID("00000000-0000-0000-0000-000000000001")
COORDINATOR_ID = UUID("00000000-0000-0000-0000-000000000002")
LEAD_ID = UUID("00000000-0000-0000-0000-000000000010")
STUDENT_ID = UUID("00000000-0000-0000-0000-000000000020")


@pytest_asyncio.fixture(autouse=True)
async def _fresh_tables() -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """Sessão de banco isolada (SQLite) para testes unitários de service."""
    async with async_session_maker() as session:
        yield session


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Client HTTP sem auth para tests dos endpoints."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c
