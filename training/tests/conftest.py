"""Fixtures globais (async).

Isolamento (espelha o candidate):
  1. TRAINING_APP_DB_URL -> sqlite+aiosqlite, definido ANTES de importar app.*
  2. DATABASE_SCHEMA="" — sqlite nao suporta schema; em prod e' Postgres/training
  3. MEDIA_DIR -> tmpdir, para o upload nao tocar disco real
  4. Cada teste recria as tabelas (drop+create)
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from uuid import uuid4

# precisa rodar ANTES de qualquer 'from app...'
_TMP = Path(tempfile.mkdtemp(prefix="training-tests-"))
os.environ["TRAINING_APP_DB_URL"] = f"sqlite+aiosqlite:///{_TMP / 'test.db'}"
os.environ["DATABASE_SCHEMA"] = ""
os.environ["MEDIA_DIR"] = str(_TMP / "media")

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app import models  # noqa: E402,F401  (popula a metadata)
from app.db import Base, async_session_maker, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Material  # noqa: E402

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
async def make_material() -> Callable:
    """Cria uma Material direto no banco; retorna o id (str)."""

    async def _make(
        title: str = "Materia",
        text_content: str = "texto",
        question: str = "Qual?",
        expected_answer: str = "Resposta",
    ) -> str:
        material = Material(
            id=str(uuid4()),
            title=title,
            text_content=text_content,
            question=question,
            expected_answer=expected_answer,
        )
        async with async_session_maker() as session:
            session.add(material)
            await session.commit()
        return str(material.id)

    return _make
