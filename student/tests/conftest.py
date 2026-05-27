"""Fixtures async — sqlite temporario, schema zerado, tabelas recriadas por teste.

Ordem importa: as env vars sao definidas ANTES de qualquer 'from app...'.
sqlite nao tem schema nem enforce FK cross-schema; em prod e Postgres/schema=student.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import UUID

_TMP_DB = Path(tempfile.mkdtemp(prefix="student-tests-")) / "test.db"
os.environ["STUDENT_APP_DB_URL"] = f"sqlite+aiosqlite:///{_TMP_DB}"
os.environ["DATABASE_SCHEMA"] = ""
os.environ["JWT_BASE_URL"] = "http://jwt.test"

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app import models  # noqa: E402,F401  (popula metadata)
from app.db import Base, engine  # noqa: E402
from app.dependencies import get_token_payload  # noqa: E402
from app.main import app  # noqa: E402

# sqlite nao tem schema — zera em todas as tabelas (incl. shadow auth.users)
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


@pytest_asyncio.fixture(autouse=True)
def _clear_overrides() -> AsyncIterator[None]:
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest.fixture
def auth_as():
    """Sobrescreve a validacao de JWT, injetando um payload fake (external_id + roles)."""

    def _set(*, external_id: UUID, roles: list[str]) -> None:
        app.dependency_overrides[get_token_payload] = lambda: {
            "external_id": str(external_id),
            "roles": roles,
            "exp": 9999999999,
        }

    return _set
