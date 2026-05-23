"""
Fixtures globais — SQLAlchemy 2 async com Postgres real.

Fonte do Postgres de teste, em ordem de preferencia:
  1. `testcontainers[postgres]` instalado e docker daemon disponivel
     (recomendado para local — zero config).
  2. Env var `TEST_DATABASE_URL` apontando para um Postgres ja em pe
     (CI sem docker, ou dev que prefere DB dedicado).
  3. Nenhum dos dois → todos os testes que dependem de `engine` sao
     marcados como SKIP com uma mensagem clara.

Por que Postgres real? Os modelos usam PG_UUID, JSONB e schema `notify`,
nada disso e' portavel pra SQLite. Trocar por SQLite shimado escondia
bugs reais (gap #15 do production-gaps.md).
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import contextmanager
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.db import Base, get_session
from app.main import app
from app.models.template import DEFAULT_SLUG


# HTML do seed default — mesmo da migration 0002. Mantido aqui para que
# os testes nao precisem rodar alembic.
_DEFAULT_TEMPLATE_HTML = """\
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
</head>
<body>
  <h1>{{title}}</h1>
  <div>{{content}}</div>
  <p>Enviado por {{service_name}}</p>
</body>
</html>
"""


def _coerce_to_asyncpg(url: str) -> str:
    """Forca o driver asyncpg em URLs vindas do testcontainers/etc."""
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


@contextmanager
def _postgres_url_provider():
    """Resolve a URL do Postgres para os testes.

    Yield a URL como string. Se nenhuma fonte disponivel, yield None
    (caller faz pytest.skip).
    """
    env_url = os.environ.get("TEST_DATABASE_URL")
    if env_url:
        yield _coerce_to_asyncpg(env_url)
        return

    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        yield None
        return

    try:
        with PostgresContainer("postgres:16-alpine") as pg:
            yield _coerce_to_asyncpg(pg.get_connection_url())
    except Exception as exc:  # docker daemon offline ou outro erro
        pytest.skip(
            f"testcontainers falhou ao subir Postgres: {exc!r}. "
            "Garanta docker rodando OU exporte TEST_DATABASE_URL."
        )


@pytest_asyncio.fixture(scope="session")
async def engine() -> AsyncIterator[Any]:
    """Engine compartilhado para a sessao inteira.

    Cria schemas `auth` + `notify`, popula shadow `auth.users` e seed
    `default` em `notify.templates`. Limpa tudo no teardown.
    """
    with _postgres_url_provider() as url:
        if url is None:
            pytest.skip(
                "Sem fonte de Postgres para testes. Instale "
                "`testcontainers[postgres]` + docker, OU exporte "
                "TEST_DATABASE_URL=postgresql+asyncpg://user:pass@host/db"
            )

        eng = create_async_engine(url, poolclass=NullPool)
        try:
            async with eng.begin() as conn:
                await conn.execute(text("CREATE SCHEMA IF NOT EXISTS auth"))
                await conn.execute(text("CREATE SCHEMA IF NOT EXISTS notify"))
                await conn.execute(
                    text(
                        "CREATE TABLE IF NOT EXISTS auth.users ("
                        "external_id UUID PRIMARY KEY"
                        ")"
                    )
                )
                await conn.run_sync(Base.metadata.create_all)
                await conn.execute(
                    text(
                        "INSERT INTO notify.templates "
                        "(slug, name, html, version, is_active) "
                        "VALUES (:slug, :name, :html, 1, true) "
                        "ON CONFLICT (slug) DO NOTHING"
                    ),
                    {
                        "slug": DEFAULT_SLUG,
                        "name": "Template padrao",
                        "html": _DEFAULT_TEMPLATE_HTML,
                    },
                )
            yield eng
        finally:
            try:
                async with eng.begin() as conn:
                    await conn.execute(text("DROP SCHEMA IF EXISTS notify CASCADE"))
                    await conn.execute(text("DROP SCHEMA IF EXISTS auth CASCADE"))
            finally:
                await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine, monkeypatch) -> async_sessionmaker[AsyncSession]:
    """Override do `async_session_maker` em todos os modules que importaram.

    Endpoints com `Depends(get_session)` sao cobertos pelo
    `dependency_overrides` no fixture `client`. Codigo que abre propria
    session (lifespan, BG tasks, metrics_service) precisa do patch
    explicito aqui.
    """
    sm = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    monkeypatch.setattr("app.db.async_session_maker", sm)
    # main.py importa async_session_maker no nivel de modulo para /ready
    monkeypatch.setattr("app.main.async_session_maker", sm, raising=False)
    monkeypatch.setattr(
        "app.services.message_service.async_session_maker", sm, raising=False,
    )
    monkeypatch.setattr(
        "app.services.template_service.async_session_maker", sm, raising=False,
    )
    monkeypatch.setattr(
        "app.services.metrics_service.async_session_maker", sm, raising=False,
    )
    return sm


@pytest_asyncio.fixture(autouse=True)
async def _clean_between_tests(engine) -> AsyncIterator[None]:
    """Limpa tabelas mutaveis entre testes, preservando seeds de template."""
    yield
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE notify.logs RESTART IDENTITY CASCADE"))
        await conn.execute(text("TRUNCATE notify.messages RESTART IDENTITY CASCADE"))
        await conn.execute(text("TRUNCATE notify.contacts RESTART IDENTITY CASCADE"))
        # auth.users e notify.templates preservados (seeds + foreign refs)
        # Remove qualquer template custom criado pelos testes (preserva seed)
        await conn.execute(
            text("DELETE FROM notify.templates WHERE slug != :slug"),
            {"slug": DEFAULT_SLUG},
        )
        # Limpa auth.users tambem pra cada teste comecar do zero
        await conn.execute(text("DELETE FROM auth.users"))


@pytest_asyncio.fixture
async def client(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    """HTTP client com session override + sem disparar lifespan."""

    async def _get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_session] = _get_session
    # raise_app_exceptions=False: exceptions nao-tratadas viram 500 response
    # em vez de propagar — comportamento alinhado com produção (uvicorn).
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    try:
        async with AsyncClient(transport=transport, base_url="http://testserver") as c:
            yield c
    finally:
        app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def make_auth_user(
    session_factory: async_sessionmaker[AsyncSession],
):
    """Cria um external_id em `auth.users` (shadow) para satisfazer a FK.

    Retorna o UUID como string. Useful em qualquer teste que cria Contact.
    """

    async def _make(external_id: UUID | str | None = None) -> str:
        eid = UUID(str(external_id)) if external_id else uuid4()
        async with session_factory() as session:
            await session.execute(
                text("INSERT INTO auth.users (external_id) VALUES (:eid)"),
                {"eid": str(eid)},
            )
            await session.commit()
        return str(eid)

    return _make


# ── Isolamento de I/O externo ──────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _isolate_external_io(monkeypatch):
    """Mocka validacoes que tocam rede externa (WhatsApp API, DNS MX).

    - `normalize_and_validate` (phone): retorna o numero ja "normalizado"
      em formato 55+DDD+numero sem chamar Evolution API.
    - `validate_email` (DNS+SMTP): retorna formato+MX validos para
      qualquer email que contenha `@` e `.`.
    - `SMTPClient.configure_smtp` / `send_single_email`: noop, retorna
      payload faking sucesso.
    - `DeepSeekClient.edit_html_template`: retorna HTML inalterado +
      um marcador (`<!-- edited -->`) para os testes verificarem que
      passou pela IA sem precisar de API key.
    """
    from app.utils import email_validator as ev_mod
    from app.utils import phone as phone_mod

    async def fake_normalize(phone: str) -> str:
        digits = "".join(c for c in phone if c.isdigit())
        if digits.startswith("55") and len(digits) > 11:
            return digits
        return f"55{digits}"

    async def fake_validate_email(email: str, *, smtp_check: bool = False):
        ok = "@" in email and "." in email.split("@", 1)[-1]
        domain = email.rsplit("@", 1)[-1].lower() if ok else None
        result = ev_mod.EmailValidation(email=email)
        result.valid_format = ok
        result.domain = domain
        result.has_mx = ok
        result.is_valid = ok
        return result

    monkeypatch.setattr(phone_mod, "normalize_and_validate", fake_normalize)
    monkeypatch.setattr(
        "app.services.contact_service.normalize_and_validate", fake_normalize,
    )
    monkeypatch.setattr(ev_mod, "validate_email", fake_validate_email)
    monkeypatch.setattr(
        "app.services.contact_service.validate_email_full", fake_validate_email,
    )

    # SMTPClient (legacy/service mail): no-op p/ caso seja invocado
    from app.integrations import smtp as smtp_mod

    async def fake_configure_smtp(self, **_):
        return {"status": "configured"}

    async def fake_send_single_email(
        self, *, to_email, subject, sender_name, html_content
    ):
        return {
            "sent": [to_email],
            "summary": {"sent": 1, "failed": 0, "invalid": 0},
        }

    monkeypatch.setattr(smtp_mod.SMTPClient, "configure_smtp", fake_configure_smtp)
    monkeypatch.setattr(
        smtp_mod.SMTPClient, "send_single_email", fake_send_single_email,
    )

    # MailcowSMTPClient (direto): no-op — testes nao tocam SMTP real
    from app.integrations import mailcow as mailcow_mod

    async def fake_mailcow_send_email(
        self, to_email, subject, html_body, *, plain_body=None, attachments=None,
    ):
        return {
            "to": to_email,
            "subject": subject,
            "from": "noreply@example.com",
            "refused": {},
        }

    monkeypatch.setattr(
        mailcow_mod.MailcowSMTPClient, "send_email", fake_mailcow_send_email,
    )

    # DeepSeek: noop para nao precisar de API key em testes
    from app.integrations import deepseek as ds_mod

    async def fake_edit_html_template(self, current_html: str, instruction: str) -> str:
        return current_html + "\n<!-- edited by AI -->"

    monkeypatch.setattr(
        ds_mod.DeepSeekClient, "edit_html_template", fake_edit_html_template,
    )
