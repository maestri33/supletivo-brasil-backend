"""Fixtures globais para os testes do lead service.

Isolamento (segue padrao candidate/asaas):
  1. DATABASE_URL -> sqlite+aiosqlite (definido ANTES de importar app.*)
  2. DATABASE_SCHEMA="" — sqlite nao suporta schema
  3. Cada teste recria as tabelas (drop+create)
  4. Cross-schema FKs desabilitados (SQLite nao suporta)
  5. JWKS/JWT dependencies sao stubadas por fixtures
  6. JSONB/UUID/Enum do Postgres mapeados para tipos compativeis com SQLite
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import UUID, uuid4

# ── precisa rodar ANTES de qualquer 'from app...' ──────────────────────────
_TMP_DB = Path(tempfile.mkdtemp(prefix="lead-tests-")) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP_DB}"
os.environ["DATABASE_SCHEMA"] = ""

# ── SQLite type overrides: registrados antes de importar models ────────────
# Os decorators abaixo fazem o compiler do SQLite entender tipos Postgres.
from sqlalchemy import BigInteger, Enum  # noqa: E402
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID  # noqa: E402
from sqlalchemy.ext.compiler import compiles  # noqa: E402


@compiles(JSONB, "sqlite")  # type: ignore[arg-type]
def _compile_jsonb_sqlite(element, compiler, **kw):
    return compiler.visit_JSON(element, **kw)


@compiles(PG_UUID, "sqlite")  # type: ignore[arg-type]
def _compile_pguuid_sqlite(element, compiler, **kw):
    return compiler.visit_uuid(element, **kw)


@compiles(Enum, "sqlite")  # type: ignore[arg-type]
def _compile_enum_sqlite(element, compiler, **kw):
    return compiler.visit_string(element, **kw)


@compiles(BigInteger, "sqlite")  # type: ignore[arg-type]
def _compile_biginteger_sqlite(element, compiler, **kw):
    """Compile BigInteger to INTEGER so SQLite autoincrement works.

    SQLite only supports autoincrement on INTEGER PRIMARY KEY (exact type),
    not BIGINT. For test purposes INTEGER is fine — we don't need 8-byte ints.
    """
    return compiler.visit_integer(element, **kw)


# Fornece defaults para settings obrigatorias que nao sao usadas nos testes
for _env_var in (
    "INFINITEPAY_BASE_URL",
    "AUTH_BASE_URL",
    "JWT_BASE_URL",
    "NOTIFY_BASE_URL",
    "PROFILES_BASE_URL",
    "ROLES_BASE_URL",
):
    if _env_var not in os.environ:
        os.environ[_env_var] = "http://mock.local"
# PROMOTER_DEFAULT precisa ser um UUID valido (usado em UUID(settings.PROMOTER_DEFAULT))
if "PROMOTER_DEFAULT" not in os.environ:
    os.environ["PROMOTER_DEFAULT"] = "00000000-0000-0000-0000-000000000000"

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

# ── Remove auth_users shadow table (cross-schema FK target) ─────────────────
# SQLite nao suporta schema, e para testes unitarios nao precisamos validar
# FK cross-schema. Removemos a tabela shadow ANTES de importar models,
# e depois removemos a FK do model Lead para evitar que o create_all
# recrie auth.users automaticamente.
import app.db  # noqa: E402
if "users" in app.db.metadata.tables:
    _auth_users = app.db.metadata.tables["users"]
    app.db.metadata.remove(_auth_users)

from app import models  # noqa: E402,F401 (popula a metadata)
from app.db import Base, async_session_maker, engine  # noqa: E402
from app.main import app  # noqa: E402

# ── Strip cross-schema FK from Lead.external_id ──────────────────────────
# A FK → auth.users.external_id referencia tabela em outro schema que nao
# existe no SQLite. Removemos a FK constraint do metadata para que o
# create_all nao tente recriar auth.users.
_lead_table = Base.metadata.tables.get("leads")
if _lead_table is not None:
    _external_id_col = _lead_table.columns.get("external_id")
    if _external_id_col is not None:
        # Remove all FK constraints on external_id
        for _fk in list(_external_id_col.foreign_keys):
            _external_id_col.foreign_keys.remove(_fk)

# ── SQLite adaptations ──────────────────────────────────────────────────────
# Remove cross-schema FK tables e normaliza tipos
_tables_to_remove = []
for _tname, _table in list(Base.metadata.tables.items()):
    if _table.schema and _table.schema not in ("", "lead"):
        _tables_to_remove.append(_tname)
    else:
        _table.schema = None

for _tname in _tables_to_remove:
    Base.metadata.remove(Base.metadata.tables[_tname])

Base.metadata.schema = None

# Disable FK enforcement (SQLite cross-schema FKs nao sao testadas em unit)
@pytest.fixture(autouse=True)
def _disable_fks():
    """Desabilita FK enforcement no SQLite — cross-schema FKs nao sao testadas."""
    import sqlalchemy
    if hasattr(sqlalchemy, "event"):
        from sqlalchemy import event
        @event.listens_for(engine.sync_engine, "connect")
        def _set_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=OFF")
            cursor.close()


@pytest_asyncio.fixture(autouse=True)
async def _fresh_tables() -> AsyncIterator[None]:
    """Recria todas as tabelas antes/depois de cada teste."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Async HTTP client apontando para a app via ASGI transport."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest_asyncio.fixture
async def make_lead():
    """Factory: cria um Lead e retorna o external_id.

    Uso:
        lead_id = await make_lead(status="captured")
    """
    from app.models import Lead, LeadStatus

    async def _make(
        status: str = "captured",
        external_id: UUID | None = None,
        promoter_external_id: UUID | None = None,
    ) -> UUID:
        external_id = external_id or uuid4()
        async with async_session_maker() as session:
            session.add(
                Lead(
                    external_id=external_id,
                    status=LeadStatus(status),
                    promoter_external_id=promoter_external_id,
                )
            )
            await session.commit()
        return external_id

    return _make


@pytest_asyncio.fixture
async def make_checkout():
    """Factory: cria um Checkout e retorna o external_id."""
    from app.models import Checkout

    async def _make(
        external_id: UUID | None = None,
        payment_method: str = "pix",
        provider: str = "asaas",
        is_paid: bool = False,
    ) -> UUID:
        external_id = external_id or uuid4()
        async with async_session_maker() as session:
            session.add(
                Checkout(
                    external_id=external_id,
                    payment_method=payment_method,
                    provider=provider,
                    is_paid=is_paid,
                )
            )
            await session.commit()
        return external_id

    return _make
