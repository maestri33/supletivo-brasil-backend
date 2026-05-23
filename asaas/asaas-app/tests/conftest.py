"""Fixtures globais.

Estrategia de isolamento:
  1. Env var `ASAAS_APP_DB_URL` definido ANTES de importar `app.*` aponta o engine
     pra um sqlite num arquivo temporario unico por sessao.
  2. Worker asyncio do payment_service e substituido por no-op pra TestClient nao
     iniciar background tasks.
  3. Cada teste comeca com tabelas limpas (drop_all + create_all).
  4. AsaasClient e patchavel via fixture `fake_asaas` que troca a classe nos 3
     namespaces que importam ela diretamente.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

# precisa rodar ANTES de qualquer 'from app...'
_TMP_DB = Path(tempfile.mkdtemp(prefix="asaas-tests-")) / "test.db"
os.environ["ASAAS_APP_DB_URL"] = f"sqlite:///{_TMP_DB}"
# SQLite nao suporta schemas. Em prod o app roda em Postgres com schema=asaas;
# nos testes, neutralizamos pra Base.metadata.create_all funcionar.
os.environ["DATABASE_SCHEMA"] = ""

from unittest.mock import MagicMock  # noqa: E402

import pytest  # noqa: E402

# Substitui o worker asyncio antes de criar o app
from app.services import payment as payment_service  # noqa: E402


async def _noop_worker(*_a, **_kw):
    return None


payment_service.worker_loop = _noop_worker  # type: ignore[assignment]

from fastapi.testclient import TestClient  # noqa: E402

from app import config_store as cfg  # noqa: E402
from app import models  # noqa: E402,F401  (popula metadata)
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402

# Garante schema=None nas tabelas, mesmo que algum import anterior tenha lido
# config.py com default antes do override do env. Idempotente.
for _t in Base.metadata.tables.values():
    _t.schema = None
Base.metadata.schema = None


@pytest.fixture(autouse=True)
def _fresh_tables():
    """Cada teste comeca com schema novinho."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def seeded_apikey(db):
    """Insere uma API key fake pra rotas que exigem config minima."""
    cfg.set_(db, cfg.K_ASAAS_API_KEY, "$aact_prod_FAKE_TEST_KEY_FOR_TESTS")
    cfg.set_(db, cfg.K_EXTERNAL_URL, "https://test.example.com/")
    db.commit()


@pytest.fixture
def seeded_token(db):
    """Insere o security_token usado pelo webhook inbound."""
    cfg.set_(db, cfg.K_ASAAS_SECURITY_TOKEN, "test-secret-token-1234")
    db.commit()
    return "test-secret-token-1234"


@pytest.fixture
def fake_asaas(monkeypatch):
    """Substitui AsaasClient nos modulos que o usam diretamente.

    Retorna uma instancia MagicMock; configure metodos via:
        fake_asaas.create_transfer.return_value = {...}
        fake_asaas.create_transfer.side_effect = AsaasError(400, {...})
    """
    instance = MagicMock(name="AsaasClientStub")
    # garante que `with AsaasClient(key) as c: ...` funcione
    instance.__enter__ = MagicMock(return_value=instance)
    instance.__exit__ = MagicMock(return_value=None)
    instance.close = MagicMock()

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
