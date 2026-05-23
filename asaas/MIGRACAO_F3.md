# Fase 3 — Migração asaas (psycopg2→asyncpg + async)

> Gerado por análise (agente, 2026-05-23). Guia da reescrita. **Espelhar `lead`/`enrollment`/`address`** — os `db.py` deles são idênticos e são a referência async.
> Decisões tomadas: **F3 = só async** (PK→UUID virou item da Fase 4, não entra aqui — mexe em dados de prod). Reescrita a ser feita em sessão nova.
>
> **Decisões travadas (2026-05-23, via /plan):**
> 1. **`database_url` obrigatório** — remover o default `v7m:v7m` (`config.py:24`); passa a vir do `.env` (mesmo padrão do `otp`/Fase 1, serviço vai pra prod). Atualizar `.env.example`, `README.md` e `CLAUDE.md §5`.
> 2. **Testes em PR seguinte** (NÃO na F3) — F3 entrega só o código async; a suíte (sqlite síncrono + `TestClient`) migra depois p/ async + `httpx.AsyncClient`. ⚠️ asaas **não fecha** (§15) até esse PR de testes.

## Veredito
Não é só "trocar driver". Converter para **async**: `db.py` + 10 services + 6 routers + lifespan + worker + BackgroundTask + `alembic/env.py` + `AsaasClient` (httpx) + suíte de testes.

## 3 bloqueios acoplados (vão JUNTOS no PR async)
1. **psycopg2 → asyncpg** — `pyproject.toml:11`, `db.py:10-11`, `config.py:24` (default `+psycopg2`), `README.md:28`.
2. **httpx sync → async** — `integrations/asaas_client.py:33` (`httpx.Client`). Sem isso o I/O de rede bloqueia o event loop (timeout 30s) e o `/security-validator` (prazo ~5s do Asaas) pode **cancelar pagamentos legítimos**. Migrar `_request` + todos os métodos para `AsyncClient`/`await`; call sites `await`.
3. **structlog** — `utils/logging.py` usa `logging` cru (§2 proíbe). O wrapper `log_event` já gera JSON → só trocar a base para `structlog.get_logger()`.

Conserta bug latente: `worker_loop` (`payment.py:477`) é `async` mas usa `SessionLocal`+`AsaasClient` síncronos dentro do loop do uvicorn (`main.py:181`) → hoje já trava a cada 30s.

## db.py (espelhar `address/app/db.py`)
- `create_async_engine(settings.database_url, pool_pre_ping=True)`
- `async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)` — `expire_on_commit=False` evita `MissingGreenlet` ao ler atributos após `commit` (ou montar dict antes do commit)
- `class Base(DeclarativeBase): metadata = metadata`
- `metadata = MetaData(naming_convention=NAMING_CONVENTION, schema=settings.database_schema)` — **copiar o dict `NAMING_CONVENTION` de `address/app/db.py:18-22`** (hoje ausente, §4)
- `async def get_session()` com `await session.rollback()` no except + `raise`
- add `async def close_db(): await engine.dispose()` e chamar no shutdown do lifespan

## Conversão por arquivo (padrão: `def`→`async def`, `db: Session`→`AsyncSession`, `await`)
- `db.query(M).filter().first()/.all()` → `await db.execute(select(M).where())` + `.scalar_one_or_none()`/`.scalars().all()`
- `db.get/flush/commit/refresh/delete` → `await ...`
- `func.count/sum` → `(await db.execute(select(func...))).scalar()`
- **services**: `payment.py` (maior, ~25 queries: `_resolve_pixkey:69`, `get_by_payment_id:167`, `list_all:179`, `count_*:201-216`, `_claim_for_submit:273`, `reconcile_submitted:389`, `tick:436-461`, `apply_webhook:534`), `charge.py` (~10), `pixkey.py` (~6), `customer.py` (~4), `security_validator.py:68`, `config_url.py:35,48`, `config_store.py:46-66` (+ `seed_from_env:84`, `all_status:109`)
- **routers** `api/*.py`: handlers `async`, `await` services, `await` commit/rollback (`api/payment.py:147,179`, `api/charge.py:73,176`, `api/config.py`, `api/pixkey.py:66`, `api/webhook.py:77,97`)
- **`main.py` lifespan:164-185** → `async with async_session_maker()` + `await cfg.seed_from_env(session)` + `await close_db()` no finally; remover `init_db` no-op
- **`worker_loop:477`** e **`_submit_bg` (api/payment.py:134)** → `async with async_session_maker()` + `await tick(s)` + `await s.commit()`

## alembic/env.py
- `run_migrations_online` atual é síncrono (`engine_from_config`+`connection.connect()`, `env.py:44-59`) → **quebra** com URL asyncpg. Migrar para template **async**: `async_engine_from_config` + `connection.run_sync(do_run_migrations)` + `asyncio.run(...)` (espelhar `lead`/`enrollment`). NÃO derivar URL psycopg2 só p/ migração (reintroduz lib proibida). `offline`, `include_object`, `version_table_schema`, `include_schemas=True` ficam iguais.

## pyproject.toml
- **remover** `psycopg2-binary`; **add** `asyncpg>=0.30`, garantir `sqlalchemy[asyncio]>=2.0`, **add** `structlog>=24.4`
- add `[build-system]` hatchling + `[tool.hatch.build.targets.wheel] packages=["app"]`
- dev: add `pytest-asyncio` + `asyncio_mode="auto"`; **apagar `pytest.ini`** (duplica `[tool.pytest.ini_options]` do pyproject); regenerar `uv.lock`

## Diferido (NÃO entra na F3)
- **PK→UUID (§4)** — models são Integer autoincrement (`models/__init__.py:38,54,74,99` + migração inicial `:86,99`). Mexe em dados de prod → **Fase 4** (com migração de dados própria).
- **Testes** — ⏭️ **PR seguinte** (decisão 2026-05-23, fora da F3): conftest async (`conftest.py:21` hoje sqlite síncrono, não funciona com `AsyncSession`), suite `TestClient`→`httpx.AsyncClient`+`pytest-asyncio`. DB de teste: `sqlite+aiosqlite` **não** cobre `schema=` do Postgres → avaliar PG de teste descartável (toca a infra docker-compose, ainda inexistente).
- **TODO de produção** (`asaas/TODO`): validar fluxo da security key no painel Asaas (`POST /config/key` → colar no dashboard → `/config/key/confirm` → `/security-validator` aprova). §1: confirmar com usuário e resolver/apagar.

## Gaps menores (limpeza / F4)
- `models/` e `schemas/` monolíticos (`__init__.py`) → 1 arquivo por entidade (§3); reescrever entidades em `Mapped`/`mapped_column` (§8) acompanha o async
- sem `api/health.py` (healthz embutido em `main.py:212`); `config_store.py` solto em `app/`
- dup `_new_payment_id`/`_new_or_check_payment_id` (`payment.py:64,86` = `charge.py:55,59`) → `utils/` (§10)
- webhooks não logam IP de origem (`api/webhook.py:75`; `/security-validator` não persiste) — §5
- `README.md:17` documenta a "exceção sync" (remover pós-F3) e aponta `CONVENTIONS.md` (arquivo real: `CONVENTION.md`)
- `wiki/asaas.md` desatualizada (descreve aninhamento `asaas/asaas/app/` já inexistente) → reescrever como fonte de verdade quando o app fechar (§15)

## Fluxo de fechamento (CONVENTION)
Reler `CONVENTION.md` + `wiki/asaas.md` antes → reescrever → **agente de conformidade** compara código × `CONVENTION §15` item a item → `ruff` limpo + testes → atualizar `wiki/asaas.md`. 1 app = 1 PR.
