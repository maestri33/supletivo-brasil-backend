"""Fixtures globais (async).

Isolamento (espelha o conftest do asaas):
  1. DATABASE_URL -> sqlite+aiosqlite temporario, definido ANTES de importar app.*
  2. DATABASE_SCHEMA="" — sqlite nao suporta schema; em prod e Postgres schema=infinitepay.
  3. store config (handle/price/...) e Fernet key vem do env (.env em prod).
  4. RUN_INLINE_WORKER=false — sem worker em background no teste.
  5. Cada teste recria as tabelas (drop+create).
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

from cryptography.fernet import Fernet

# precisa rodar ANTES de qualquer 'from app...'
_TMP_DB = Path(tempfile.mkdtemp(prefix="infinitepay-tests-")) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP_DB}"
os.environ["DATABASE_SCHEMA"] = ""
os.environ["RUN_INLINE_WORKER"] = "false"
os.environ["WEBHOOK_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
os.environ["INFINITEPAY_HANDLE"] = "v7m"
os.environ["INFINITEPAY_PRICE"] = "100"
os.environ["INFINITEPAY_DESCRIPTION"] = "Padrao"
os.environ["INFINITEPAY_REDIRECT_URL"] = "https://example.com/pago"
os.environ["INFINITEPAY_BACKEND_WEBHOOK"] = "https://example.com/api"
os.environ["INFINITEPAY_PUBLIC_API_URL"] = "https://example.com"
os.environ["INTERNAL_API_KEY"] = "test-internal-api-key-for-tests"

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app import models  # noqa: E402,F401  (popula a metadata)
from app.db import Base, async_session_maker, engine  # noqa: E402
from app.main import app  # noqa: E402

# sqlite nao tem schema — zera em todas as tabelas (idempotente)
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


@pytest_asyncio.fixture
async def db() -> AsyncIterator:
    async with async_session_maker() as s:
        yield s


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c
