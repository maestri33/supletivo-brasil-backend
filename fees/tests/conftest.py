"""Fixtures globais (async) — SQLite em arquivo, sem mock de DB.

Isolamento (espelha `asaas/tests/conftest.py`):
  1. DATABASE_URL -> sqlite+aiosqlite temporário, definido ANTES de importar app.*
  2. DATABASE_SCHEMA="" — sqlite não tem schema; em prod/Postgres é `fees`.
  3. Cada teste recria as tabelas (drop+create).
  4. Auth e asaas são injetados via dependency_overrides; notify é stubbado.

`PG_UUID(as_uuid=False)` cai para CHAR no sqlite (mesma estratégia do asaas),
então os models rodam sem Postgres real.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

# precisa rodar ANTES de qualquer 'from app...'
_TMP_DB = Path(tempfile.mkdtemp(prefix="fees-tests-")) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP_DB}"
os.environ["DATABASE_SCHEMA"] = ""

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app import models  # noqa: E402,F401  (popula o metadata)
from app.db import Base, async_session_maker, engine  # noqa: E402
from app.integrations import IntegrationError  # noqa: E402
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
def coordinator_id() -> UUID:
    return uuid4()


class FakeAsaas:
    """Stub do AsaasClient — sem rede. Configurável por teste."""

    def __init__(self) -> None:
        self.upfront_response: dict = {"status": "QUEUED", "asaas_id": "asa_up"}
        self.scheduled_response: dict = {"status": "SCHEDULED", "asaas_id": "asa_sch"}
        self.raise_on: set[str] = set()
        self.calls: list[tuple[str, dict]] = []

    async def pay_qrcode(self, **kwargs) -> dict:
        self.calls.append(("upfront", kwargs))
        if "upfront" in self.raise_on:
            raise IntegrationError("simulated asaas failure")
        return self.upfront_response

    async def pay_qrcode_scheduled(self, **kwargs) -> dict:
        self.calls.append(("scheduled", kwargs))
        if "scheduled" in self.raise_on:
            raise IntegrationError("simulated asaas failure")
        return self.scheduled_response

    async def get_payment(self, payment_id: str) -> dict:
        return {}


@pytest.fixture
def fake_asaas() -> FakeAsaas:
    return FakeAsaas()


@pytest.fixture(autouse=True)
def notifications(monkeypatch) -> list[tuple]:
    """Stub das notificações (evita rede) e grava as chamadas para asserção."""
    calls: list[tuple] = []

    async def _access(student: str) -> None:
        calls.append(("access_released", student))

    async def _full(student: str) -> None:
        calls.append(("fully_paid", student))

    async def _failed(coordinator: str, *, kind: str) -> None:
        calls.append(("payment_failed", coordinator, kind))

    import app.api.demilitarized.webhooks as wh

    monkeypatch.setattr(wh, "notify_student_access_released", _access)
    monkeypatch.setattr(wh, "notify_student_fully_paid", _full)
    monkeypatch.setattr(wh, "notify_coordinator_payment_failed", _failed)
    return calls


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """Sessão de banco isolada (SQLite) para testes unitários de service."""
    async with async_session_maker() as session:
        yield session


@pytest_asyncio.fixture
async def client(fake_asaas, coordinator_id) -> AsyncIterator[AsyncClient]:
    """Client autenticado: auth e asaas injetados via override."""
    from app.dependencies import get_asaas_client, get_current_coordinator

    async def _fake_asaas_dep():
        yield fake_asaas

    app.dependency_overrides[get_current_coordinator] = lambda: coordinator_id
    app.dependency_overrides[get_asaas_client] = _fake_asaas_dep
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    try:
        async with AsyncClient(transport=transport, base_url="http://testserver") as c:
            yield c
    finally:
        app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client_noauth() -> AsyncIterator[AsyncClient]:
    """Client sem override de auth — para testar o gate de coordenador."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c
