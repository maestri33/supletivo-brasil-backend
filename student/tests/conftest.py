"""Fixtures async — sqlite temporario, schema zerado, tabelas recriadas por teste.

Ordem importa: as env vars sao definidas ANTES de qualquer 'from app...'.
sqlite nao tem schema; em prod e Postgres/schema=student.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import UUID, uuid4

_TMP_DB = Path(tempfile.mkdtemp(prefix="student-tests-")) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP_DB}"
os.environ["DATABASE_SCHEMA"] = ""
os.environ["JWT_BASE_URL"] = "http://jwt.test"

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app import models  # noqa: E402,F401  (popula metadata)
from app.db import Base, async_session_maker, engine  # noqa: E402
from app.dependencies import get_token_payload  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Student, StudentStatus  # noqa: E402

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


@pytest.fixture(autouse=True)
def _stub_integrations(monkeypatch: pytest.MonkeyPatch) -> None:
    """Desativa chamadas HTTP reais nos testes — todos os clients viram noop.

    Estado mutavel exposto via `_gender_holder` para o teste sobrescrever.
    """
    from app.services import diploma_service, document_service, notifications

    async def _fake_gender(external_id):  # noqa: ARG001
        return None

    async def _noop_validate(student_id, document_id):  # noqa: ARG001
        return None

    async def _noop_notify(external_id, status):  # noqa: ARG001
        return None

    async def _noop_side_effects(student_id, external_id, coord_id):  # noqa: ARG001
        return None

    monkeypatch.setattr(document_service, "_safe_get_gender", _fake_gender)
    monkeypatch.setattr(document_service, "validate_document_async", _noop_validate)
    monkeypatch.setattr(notifications, "notify_status_changed", _noop_notify)
    monkeypatch.setattr(
        diploma_service, "trigger_graduation_side_effects", _noop_side_effects
    )


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app, raise_app_exceptions=True)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest.fixture
def auth_as():
    """Sobrescreve a validacao de JWT, injetando um payload fake."""

    def _set(*, external_id: UUID, roles: list[str]) -> None:
        app.dependency_overrides[get_token_payload] = lambda: {
            "external_id": str(external_id),
            "roles": roles,
            "exp": 9999999999,
        }

    return _set


@pytest_asyncio.fixture
async def make_student():
    """Cria um Student no DB direto, com o status pedido."""

    async def _make(*, external_id: UUID | None = None, status: StudentStatus) -> Student:
        external_id = external_id or uuid4()
        async with async_session_maker() as session:
            student = Student(
                external_id=external_id,
                study_platform={},
                status=status,
            )
            session.add(student)
            await session.commit()
            await session.refresh(student)
        return student

    return _make
