# Plan: Commissions — Milestone 1 (Espinha + modelos)

**Source PRD**: `.claude/prds/commissions.prd.md`
**Selected Milestone**: 1 — Espinha + modelos
**Complexity**: Medium

## Summary
Criar o esqueleto canônico do serviço green-field `commissions/` (estrutura espelhando `lead`, stack async espelhando `asaas`/`infinitepay`) e as **2 tabelas** da spec (`commissions`, `payment_requests`) com schema Postgres próprio. Resultado: o serviço sobe (`/health` 200) e `alembic upgrade head` cria o schema `commissions` + as 2 tabelas. Gatilho, lote semanal e payout ficam pros Milestones 2–4.

## Patterns to Mirror
| Category | Source | Pattern |
|---|---|---|
| Spine DB | [address/app/db.py](address/app/db.py) | `create_async_engine` + `async_sessionmaker` + `Base(DeclarativeBase)` + `NAMING_CONVENTION` + `MetaData(schema=settings.database_schema)` + `get_session`/`close_db` |
| Alembic async | [enrollment/alembic/env.py](enrollment/alembic/env.py) | `run_migrations_online` async + `include_object` filtra schema + `version_table_schema=SCHEMA` |
| Stack/pyproject | [infinitepay/pyproject.toml](infinitepay/pyproject.toml) | deps canônicas §2 + ruff (line 100, py312, `select=E,F,I,B,UP,N,ASYNC`) + `asyncio_mode="auto"` + hatchling `packages=["app"]` |
| Config | [lead/app/config.py](lead/app/config.py) | `BaseSettings` + `SettingsConfigDict(env_file=".env")` + `DATABASE_URL` obrigatório (sem default) + `*_BASE_URL` de integrações |
| Model | [lead/app/models/lead.py](lead/app/models/lead.py) + [lead/app/models/_mixins.py](lead/app/models/_mixins.py) | `Mapped`/`mapped_column`, `Enum(..., schema=, create_type=True, values_callable=…)`, `TimestampMixin` (`DateTime(timezone=True)`=timestamptz) |
| PK UUID | [infinitepay/.claude/CLAUDE.md](infinitepay/.claude/CLAUDE.md) (F4: PK→UUID) | **PK = `PG_UUID(as_uuid=True)` default `uuid4`** (§4), NÃO BigInteger do lead |
| main/lifespan | [lead/app/main.py](lead/app/main.py) | `@asynccontextmanager lifespan` (dispose engine no shutdown) + `include_router` + `/health` |

## Files to Change
Tudo dentro de `commissions/` (escopo restrito).

| File | Action | Why |
|---|---|---|
| `commissions/pyproject.toml` | CREATE | stack canônica §2 (espelha infinitepay), ruff, pytest-asyncio, hatchling |
| `commissions/app/__init__.py` | CREATE | pacote |
| `commissions/app/config.py` | CREATE | `Settings` + `get_settings()` cacheado; `DATABASE_URL` obrigatório; `DATABASE_SCHEMA="commissions"`; envs de negócio e integração |
| `commissions/app/db.py` | CREATE | engine async, `Base`, `NAMING_CONVENTION`, `metadata(schema)`, `get_session`, `close_db`, `utcnow` |
| `commissions/app/exceptions.py` | CREATE | `DomainError` + subclasses de domínio |
| `commissions/app/utils/__init__.py` | CREATE | pacote |
| `commissions/app/utils/logging.py` | CREATE | setup structlog (logger `"commissions"`) — espelha asaas/utils/logging |
| `commissions/app/models/__init__.py` | CREATE | importa entidades p/ `Base.metadata` (Alembic enxerga) |
| `commissions/app/models/_mixins.py` | CREATE | `TimestampMixin` timestamptz |
| `commissions/app/models/commission.py` | CREATE | tabela `commissions` (registro por evento) |
| `commissions/app/models/payment_request.py` | CREATE | tabela `payment_requests` (1 por beneficiário/lote) |
| `commissions/app/api/__init__.py` | CREATE | pacote |
| `commissions/app/api/health.py` | CREATE | `/health` desmilitarizado |
| `commissions/app/api/router.py` | CREATE | agrega routers |
| `commissions/app/main.py` | CREATE | FastAPI + lifespan (`close_db`) + structlog + router + `/health` |
| `commissions/alembic.ini` | CREATE | config alembic (script_location, sem url hardcoded) |
| `commissions/alembic/env.py` | CREATE | env async (espelha enrollment); cria schema |
| `commissions/alembic/script.py.mako` | CREATE | template padrão |
| `commissions/alembic/versions/0001_initial.py` | CREATE | `CREATE SCHEMA IF NOT EXISTS commissions` + enum types + 2 tabelas + índices/uniques |
| `commissions/tests/__init__.py` | CREATE | pacote |
| `commissions/tests/conftest.py` | CREATE | fixtures async (sqlite+aiosqlite, ASGITransport) — espelha asaas |
| `commissions/tests/test_health.py` | CREATE | smoke: `/health` 200 + metadata cria as 2 tabelas |
| `commissions/.env.example` | CREATE | placeholders (sem segredo) |
| `commissions/Makefile` | CREATE | install/dev/test/lint/fmt/migrate (espelha infinitepay) |
| `commissions/Dockerfile` | CREATE | imagem do serviço (espelha infinitepay) |
| `commissions/README.md` | CREATE | o que faz, como rodar, env vars (enxuto) |
| `commissions/TODO` | KEEP | spec — não apagar; vira `wiki/commissions.md` no Milestone 5 (§15) |

## Modelo de dados (as 2 tabelas da spec)

**`commissions`** — 1 linha por evento que gera comissão:
- `id` UUID PK (`uuid4`)
- `kind` enum `commission_kind` (`LEAD` | `STUDENT` | `BONUS`) — promotor por lead, coordenador por student, ou bônus
- `beneficiary_external_id` UUID, index (promotor ou coordenador)
- `source_external_id` UUID | None — `lead.external_id`/`student.external_id` que disparou (None p/ BONUS)
- `amount` `Numeric(12, 2)` — valor em reais (money = Numeric, **nunca float**)
- `status` enum `commission_status` (`PENDING` | `PROCESSED`), default `PENDING`, index
- `payment_request_id` UUID | None — preenchido quando agregada no lote (M3)
- `created_at`/`updated_at` (timestamptz)
- **Idempotência**: unique `(kind, source_external_id)` — garante "exatamente 1 comissão por evento" (PRD métrica). BONUS (source None) tratado no M3.

**`payment_requests`** — 1 linha por beneficiário por lote semanal:
- `id` UUID PK
- `beneficiary_external_id` UUID, index
- `beneficiary_kind` enum `beneficiary_kind` (`PROMOTER` | `COORDINATOR`)
- `amount` `Numeric(12, 2)` — soma das comissões do lote (+ bônus)
- `pix_key` str | None — resolvida no payout via promoter/coordinator (TBD enquanto stubs → nullable)
- `status` enum `payment_status` (`PENDING` | `SENT` | `PAID` | `FAILED`), default `PENDING`
- `asaas_payment_id` str | None — id do payout no asaas (M4)
- `period_key` str — janela do lote (ex. `2026-W21`) p/ idempotência do job
- `created_at`/`updated_at`
- **Idempotência**: unique `(beneficiary_external_id, period_key)` — 1 pagamento por beneficiário por período (PRD: job 2× não duplica).

> Sem shadow table: `beneficiary_external_id`/`source_external_id` são UUID simples (promoter/coordinator/student não existem ainda → FK cross-schema seria órfã; §14 simplicidade). Reavaliar quando esses serviços existirem.

## Tasks

### Task 1: Stack + pacote
- **Action**: criar `pyproject.toml` (deps §2, ruff, pytest-asyncio, hatchling) + `app/__init__.py`.
- **Mirror**: [infinitepay/pyproject.toml](infinitepay/pyproject.toml).
- **Validate**: `cd commissions && uv sync` resolve sem erro.

### Task 2: Spine (config + db + exceptions + logging)
- **Action**: `config.py` (`DATABASE_URL` obrigatório, `DATABASE_SCHEMA="commissions"`, envs de negócio/integração), `db.py`, `exceptions.py`, `utils/logging.py`.
- **Mirror**: [lead/app/config.py](lead/app/config.py), [address/app/db.py](address/app/db.py).
- **Validate**: `uv run python -c "import app.db, app.config"` OK.

### Task 3: Models + mixins
- **Action**: `models/_mixins.py` (timestamptz), `models/commission.py`, `models/payment_request.py`, `models/__init__.py` (export p/ `Base.metadata`).
- **Mirror**: [lead/app/models/lead.py](lead/app/models/lead.py) (Enum/Mapped) + PK UUID da F4.
- **Validate**: `uv run python -c "import app.models; print(sorted(app.db.Base.metadata.tables))"` lista `commissions.commissions` e `commissions.payment_requests`.

### Task 4: API mínima + main
- **Action**: `api/health.py`, `api/router.py`, `main.py` (lifespan + structlog + router).
- **Mirror**: [lead/app/main.py](lead/app/main.py).
- **Validate**: `uv run python -c "import app.main"` OK.

### Task 5: Alembic + migração 0001
- **Action**: `alembic.ini`, `alembic/env.py` (async, cria schema), `script.py.mako`, `versions/0001_initial.py` (schema + enums + 2 tabelas + uniques/índices).
- **Mirror**: [enrollment/alembic/env.py](enrollment/alembic/env.py); migração que **cria o próprio schema** (padrão asaas/address).
- **Validate**: `uv run alembic upgrade head` num Postgres limpo cria schema `commissions` + 2 tabelas; `alembic downgrade base` reverte.

### Task 6: Testes + lint + docs de spine
- **Action**: `tests/conftest.py` (async sqlite), `tests/test_health.py`, `.env.example`, `Makefile`, `Dockerfile`, `README.md`.
- **Mirror**: conftest async do asaas (sqlite+aiosqlite, ASGITransport); [infinitepay/.claude/CLAUDE.md](infinitepay/.claude/CLAUDE.md) §6 (comandos) p/ Makefile.
- **Validate**: `uv run pytest -q` verde + `uv run ruff check app && uv run ruff format --check app` limpos.

## Validation
```bash
cd commissions
uv sync
uv run ruff check app && uv run ruff format --check app
uv run pytest -q                 # sqlite — health 200 + metadata cria 2 tabelas
uv run alembic upgrade head      # Postgres real: cria schema commissions + commissions/payment_requests
uv run alembic downgrade base    # reverte limpo
```

## Risks
| Risk | Likelihood | Mitigation |
|---|---|---|
| Enum/schema do Postgres quebra nos testes sqlite | média | espelhar conftest do asaas (sqlite ignora schema; enums via `create_type`); asaas roda 190 testes sqlite assim |
| `PG_UUID(as_uuid=True)` em sqlite | média | espelhar tratamento de UUID/timestamptz do asaas (já validado sqlite + Postgres) |
| Migração não criar o schema sozinha | baixa | `CREATE SCHEMA IF NOT EXISTS` no `0001` + `env.py` (padrão address/asaas) |
| Escopo vazar pra fora de commissions/ | baixa | só criar arquivos sob `commissions/`; nenhuma edição em lead/asaas/etc neste milestone |

## Acceptance
- [ ] `uv sync`, `ruff` (check+format) e `pytest` (sqlite) verdes
- [ ] `alembic upgrade head` cria schema `commissions` + tabelas `commissions` e `payment_requests`; `downgrade base` reverte
- [ ] `/health` responde 200
- [ ] Padrões espelhados (db=address, alembic=enrollment, stack=infinitepay, model=lead+PK UUID), não reinventados
- [ ] Nada tocado fora de `commissions/`
```
