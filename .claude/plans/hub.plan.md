# Plan: Hub (Polo) — Milestone 1

**Source PRD**: `.claude/prds/hub.prd.md`
**Selected Milestone**: #1 — Spine + schema + migração + seed default
**Complexity**: Small

## Summary
Criar o serviço `hub` do zero (green-field), espelhando a **estrutura** do `enrollment`/`lead` e a
**stack canônica** do `asaas`. Este milestone entrega só a *spine*: scaffolding do app, `config`/`db`/
`main`/`exceptions`, o model `Hub` (registro fino, PK UUID), a migração Alembic inicial que cria o
schema `hub` **e semeia 1 polo default**, e os testes de saúde. Sem rotas de negócio ainda (M2/M3).

## Patterns to Mirror
| Category | Source | Pattern |
|---|---|---|
| Estrutura/diretórios | `enrollment/app/*`, `lead/app/*` | `app/` plano: `config.py`, `db.py`, `main.py`, `exceptions.py`, `models/`, `api/`, `tests/` |
| DB spine | `enrollment/app/db.py:18-52` | `NAMING_CONVENTION`, `MetaData(schema=...)`, `Base`, `create_async_engine`, `get_session()` |
| Config | `enrollment/app/config.py:9-27` | `Settings(BaseSettings)` + `get_settings()` cacheado — **porém `database_url` obrigatório** (sem default `v7m:v7m`, igual `otp`/`asaas` na Fase 1) |
| Main/lifespan/health | `enrollment/app/main.py:27-88` | `lifespan`, `fastapi-structured-logging`, handler `DomainError`, `/health` `/ready` `/status` |
| Exceções | `enrollment/app/exceptions.py:9-43` | `DomainError` + `NotFound`/`Conflict`/`ValidationError` |
| Model (UUID + timestamptz) | `address/app/models/address.py:13-57`, `lead/app/models/_mixins.py:9-20` | `Mapped`/`mapped_column`, `PG_UUID(as_uuid=True)`, `DateTime(timezone=True)` + `TimestampMixin` |
| Migração + schema | `asaas/alembic/versions/2026-05-15_initial_asaas_schema.py:36-71` | `CREATE SCHEMA IF NOT EXISTS`, `op.create_table(..., schema=SCHEMA)`, índices |
| Alembic env async | `enrollment/alembic/env.py:1-66` | engine async, `include_schemas`, `version_table_schema`, `include_object` |
| Testes async | `enrollment/tests/conftest.py`, `enrollment/tests/test_health.py` | Postgres real (testcontainers/`TEST_DATABASE_URL`), `ASGITransport`, override `get_session` |
| pyproject | `enrollment/pyproject.toml:1-35` | hatchling `packages=["app"]`, stack canônica, ruff `line-length=100`, `asyncio_mode="auto"` |

> Sem FK cross-schema no hub (decisão do PRD): **não** copiar a shadow `auth_users` do `enrollment/app/db.py:33-39`. As refs (`address_external_id`, `coordinator_external_id`) são UUID puro, nullable.

## Files to Change
| File | Action | Why |
|---|---|---|
| `hub/pyproject.toml` | CREATE | stack canônica (espelha enrollment) |
| `hub/.env.example` | CREATE | `DATABASE_URL`/`DATABASE_SCHEMA` placeholders (sem segredo) |
| `hub/.gitignore` | CREATE | `.venv`, `__pycache__`, `.ruff_cache`, `.env` (§9) |
| `hub/Dockerfile` | CREATE | 1 container/serviço (espelha enrollment) |
| `hub/Makefile` | CREATE | `install/dev/run/test/lint/fmt` + alembic (espelha asaas) |
| `hub/alembic.ini` | CREATE | config Alembic (espelha enrollment) |
| `hub/app/__init__.py` | CREATE | pacote |
| `hub/app/config.py` | CREATE | `Settings` — `database_url` obrigatório, `database_schema="hub"` |
| `hub/app/db.py` | CREATE | engine async, `Base`, `NAMING_CONVENTION`, `get_session()` (sem shadow table) |
| `hub/app/exceptions.py` | CREATE | `DomainError` + subclasses |
| `hub/app/main.py` | CREATE | FastAPI, lifespan, logging, `/health` `/ready` `/status` |
| `hub/app/models/__init__.py` | CREATE | importa `Hub` (p/ Alembic autogenerate) |
| `hub/app/models/hub.py` | CREATE | model `Hub` (PK UUID, name, brand, refs nullable, timestamps) |
| `hub/alembic/env.py` | CREATE | env async (espelha enrollment) |
| `hub/alembic/script.py.mako` | CREATE | template (espelha enrollment) |
| `hub/alembic/versions/0001_initial_hub_schema.py` | CREATE | cria schema `hub` + tabela `hub` + **seed do polo default** |
| `hub/tests/__init__.py` | CREATE | pacote de testes |
| `hub/tests/conftest.py` | CREATE | fixtures async (espelha enrollment) |
| `hub/tests/test_health.py` | CREATE | `/health` `/ready` `/status` |
| `hub/tests/test_hub_seed.py` | CREATE | valida que a migração semeia exatamente 1 polo default |

## Tasks

### Task 1: Scaffolding + spine (config/db/exceptions)
- **Action**: criar `pyproject.toml`, `.env.example`, `.gitignore`, `Dockerfile`, `Makefile`, `alembic.ini`, `app/__init__.py`, `app/config.py`, `app/db.py`, `app/exceptions.py`.
- **Mirror**: `enrollment/pyproject.toml`, `enrollment/app/{config,db,exceptions}.py`. Schema = `hub`. `database_url` **sem default** (campo obrigatório). `db.py` **sem** shadow `auth_users`.
- **Validate**: `cd hub && uv sync && uv run ruff check .`

### Task 2: Model `Hub` (registro fino)
- **Action**: criar `app/models/hub.py` e `app/models/__init__.py`. Colunas:
  `id` UUID PK (`default=uuid4`), `name` String not null, `brand` String not null
  (validação enum `estacio|wyden|...` fica no schema Pydantic em M3 — aqui só a coluna),
  `address_external_id` UUID nullable, `coordinator_external_id` UUID nullable,
  `created_at`/`updated_at` timestamptz via `TimestampMixin`.
- **Mirror**: `address/app/models/address.py` (UUID/timestamptz) + `lead/app/models/_mixins.py` (TimestampMixin). PK UUID conforme §4.
- **Validate**: `uv run ruff check . && uv run python -c "import app.models"`

### Task 3: main.py + health
- **Action**: criar `app/main.py` (FastAPI, lifespan que dá `engine.dispose()`, logging estruturado, handler `DomainError`, `/health` `/ready` `/status`). Sem routers de negócio neste milestone.
- **Mirror**: `enrollment/app/main.py:27-88`.
- **Validate**: `uv run python -c "import app.main"`

### Task 4: Alembic + migração inicial com seed
- **Action**: criar `alembic/env.py`, `alembic/script.py.mako`, `alembic/versions/0001_initial_hub_schema.py`.
  A migração: `CREATE SCHEMA IF NOT EXISTS hub` → `create_table("hub", ...)` → **seed** de 1 linha default
  com **UUID fixo/determinístico** (`name="Polo Default"`, `brand="estacio"`, refs `NULL`) via
  `op.execute(INSERT ... ON CONFLICT (id) DO NOTHING)` (idempotente).
- **Mirror**: `asaas/alembic/versions/2026-05-15_initial_asaas_schema.py:36-71` (schema+create_table) e `enrollment/alembic/env.py` (env async).
- **Validate**: `uv run alembic upgrade head` contra Postgres real (testcontainers ou `TEST_DATABASE_URL`); conferir 1 linha em `hub.hub`. `downgrade` derruba a tabela.

### Task 5: Testes
- **Action**: criar `tests/__init__.py`, `tests/conftest.py`, `tests/test_health.py`, `tests/test_hub_seed.py`.
  `conftest` espelha enrollment (Postgres real, `ASGITransport`, override `get_session`). `test_hub_seed` aplica a migração (ou cria via metadata + roda o seed) e afirma 1 polo default com os valores esperados.
- **Mirror**: `enrollment/tests/conftest.py`, `enrollment/tests/test_health.py`.
- **Validate**: `uv run pytest -q`

## Validation
```bash
cd hub
uv sync
uv run ruff check . && uv run ruff format --check .
uv run python -c "import app.main"      # boot importável
uv run pytest -q                         # health + seed (Postgres real via testcontainers/TEST_DATABASE_URL)
uv run alembic upgrade head              # cria schema hub + semeia polo default
```

## Risks
| Risk | Likelihood | Mitigation |
|---|---|---|
| `database_url` com default inseguro (`v7m:v7m`) herdado do template | Média | tornar **obrigatório** (sem default), como `otp`/`asaas` na Fase 1 |
| Seed não-idempotente (re-run duplica/erra) | Média | UUID fixo + `INSERT ... ON CONFLICT (id) DO NOTHING` |
| `asyncpg` recusa `datetime` aware em coluna naive (bug que mordeu o asaas) | Baixa | colunas `DateTime(timezone=True)` desde o início (já no padrão dos mixins) |
| Testes exigem Postgres real (sqlite não tem UUID/JSONB/schema) | Média | testcontainers OU `TEST_DATABASE_URL`; skip claro se ausente (padrão enrollment) |
| `fastapi-structured-logging` é lib fora da tabela §2 | Baixa | já é o padrão do spine `enrollment`; registrar no `CLAUDE.md` do hub (M4) |

## Acceptance
- [ ] Estrutura `hub/app/...` espelha `enrollment`/`lead`; arquivos no lugar certo (§3)
- [ ] `ruff check`/`format` limpos; `import app.main` OK
- [ ] `alembic upgrade head` cria schema `hub` + semeia **exatamente 1** polo default
- [ ] `pytest` verde (health + seed)
- [ ] Padrões espelhados (enrollment/asaas/address), não reinventados
- [ ] Sem ruído (§9): nada de `__pycache__`/`.venv`/`.env` versionados; sem TODO órfão

---
> Fora deste milestone (vai pra M2/M3/M4): rotas desmilitarizadas (read by id), rotas autenticadas (staff cria/edita), `schemas/` Pydantic com validação de `brand`, `services/`, fechamento §15 (wiki/hub.md + `.claude/`).
> Open questions do PRD a confirmar antes/no M3: valores definitivos do default; `brand` como `Enum` PG vs `String`+Pydantic (plano assume String+Pydantic); quem escreve o polo (assumido: staff autenticado).
