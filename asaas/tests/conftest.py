"""Fixtures globais (async).

Isolamento:
  1. ASAAS_APP_DB_URL -> sqlite+aiosqlite temporario, definido ANTES de importar app.*
  2. DATABASE_SCHEMA="" — sqlite nao suporta schema; em prod e Postgres schema=asaas.
  3. worker asyncio do payment vira no-op (sem background em teste).
  4. Cada teste recria as tabelas (drop+create).
  5. AsaasClient patchavel via fixture async `fake_asaas`.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

# precisa rodar ANTES de qualquer 'from app...'
_TMP_DB = Path(tempfile.mkdtemp(prefix="asaas-tests-")) / "test.db"
os.environ["ASAAS_APP_DB_URL"] = f"sqlite+aiosqlite:///{_TMP_DB}"
os.environ["DATABASE_SCHEMA"] = ""

from unittest.mock import AsyncMock  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402

from app.services import payment as payment_service  # noqa: E402


async def _noop_worker(*_a, **_kw):
    return None


payment_service.worker_loop = _noop_worker  # type: ignore[assignment]

from httpx import ASGITransport, AsyncClient  # noqa: E402

from app import config_store as cfg  # noqa: E402
from app import models  # noqa: E402,F401  (popula metadata)
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


@pytest_asyncio.fixture
async def seeded_apikey(db):
    await cfg.set_(db, cfg.K_ASAAS_API_KEY, "$aact_prod_FAKE_TEST_KEY_FOR_TESTS")
    await cfg.set_(db, cfg.K_EXTERNAL_URL, "https://test.example.com/")
    await db.commit()


@pytest_asyncio.fixture
async def seeded_token(db):
    await cfg.set_(db, cfg.K_ASAAS_SECURITY_TOKEN, "test-secret-token-1234")
    await db.commit()
    return "test-secret-token-1234"


@pytest.fixture
def fake_asaas(monkeypatch):
    """Stub async do AsaasClient nos modulos que o usam.

    Configure via: fake_asaas.create_transfer.return_value = {...}
                   fake_asaas.create_transfer.side_effect = AsaasError(400, {...})
    """
    instance = AsyncMock(name="AsaasClientStub")
    instance.__aenter__.return_value = instance
    instance.__aexit__.return_value = None

    def _factory(*_a, **_kw):
        return instance

    for module in (
        "app.services.pixkey",
        "app.services.payment",
        "app.services.config_key",
        "app.services.charge",
        "app.services.customer",
    ):
        monkeypatch.setattr(f"{module}.AsaasClient", _factory)
    return instance
