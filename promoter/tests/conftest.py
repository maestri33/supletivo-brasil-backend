"""Fixtures globais (async).

Isolamento (espelha o candidate/asaas):
  1. PROMOTER_APP_DB_URL -> sqlite+aiosqlite, definido ANTES de importar app.*
  2. DATABASE_SCHEMA="" — sqlite nao suporta schema; em prod e' Postgres/promoter
  3. Cada teste recria as tabelas (drop+create)
  4. Auth (JWT) e integracoes HTTP sao stubadas por fixtures
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

# precisa rodar ANTES de qualquer 'from app...'
_TMP_DB = Path(tempfile.mkdtemp(prefix="promoter-tests-")) / "test.db"
os.environ["PROMOTER_APP_DB_URL"] = f"sqlite+aiosqlite:///{_TMP_DB}"
os.environ["DATABASE_SCHEMA"] = ""

from unittest.mock import AsyncMock  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app import models  # noqa: E402,F401  (popula a metadata)
from app.db import Base, async_session_maker, engine  # noqa: E402
from app.dependencies import get_current_external_id  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Promoter  # noqa: E402

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
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest_asyncio.fixture
async def make_promoter() -> Callable:
    """Cria um Promoter num dado status; retorna o external_id."""

    async def _make(status: str = "active", external_id: UUID | None = None, hub=None) -> UUID:
        external_id = external_id or uuid4()
        async with async_session_maker() as session:
            session.add(
                Promoter(
                    external_id=str(external_id),
                    status=status,
                    hub_external_id=str(hub) if hub else None,
                )
            )
            await session.commit()
        return external_id

    return _make


@pytest.fixture
def login_as() -> Callable[[UUID], None]:
    """Sobrescreve a validacao de JWT, fixando o external_id autenticado."""

    def _login(external_id: UUID) -> None:
        app.dependency_overrides[get_current_external_id] = lambda: external_id

    return _login


@pytest.fixture
def mocks(monkeypatch) -> SimpleNamespace:
    """Stub dos clients de integracao usados pelos services."""

    def make() -> AsyncMock:
        return AsyncMock()

    auth, jwt, roles = make(), make(), make()
    profiles, notify = make(), make()
    lead, commissions = make(), make()

    def factory(inst: AsyncMock) -> Callable:
        return lambda *a, **k: inst

    bindings = {
        "app.services.auth.AuthClient": auth,
        "app.services.auth.JwtClient": jwt,
        "app.services.promoter.RolesClient": roles,
        "app.services.leads.LeadClient": lead,
        "app.services.commissions.CommissionsClient": commissions,
        "app.services.notifications.NotifyClient": notify,
    }
    for path, inst in bindings.items():
        monkeypatch.setattr(path, factory(inst))

    return SimpleNamespace(
        auth=auth,
        jwt=jwt,
        roles=roles,
        profiles=profiles,
        notify=notify,
        lead=lead,
        commissions=commissions,
    )
