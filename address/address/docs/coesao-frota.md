# Coesão do `addresses` com a frota (`/home/maestri33/backend/`)

Data: 2026-05-22 · Pergunta: o `addresses` unificado ficou coeso com os demais serviços?

## Método
Mapeei os ~24 serviços do backend, identifiquei os roots reais (vários são aninhados,
ex.: `address/address`, `auth/auth`, `profiles/profiles`) e comparei convenções
(stack, layout, config, db, main, exceptions, alembic, infra) por leitura direta + `diff`.

## A frota tem 2 famílias

**Template canônico (cluster CRUD)** — `profiles`, `notify`, `otp`, `asaas`, `roles`,
`documents` e agora `addresses`:
- Layout `app/{api,models,schemas,services,validators?,integrations?,utils}` + `api/router.py` (`api_router`).
- `config.py`: `Settings` **lowercase** (`service_name`, `version`, `env`, `log_level`,
  `port`, `database_url`, `database_schema`, `cors_origins`) + `get_settings()`/`lru_cache`.
- `db.py`: SQLAlchemy async, `NAMING_CONVENTION`, `Base` com `schema=database_schema`,
  **shadow `auth.users`** p/ FK cross-schema, `get_session`/`close_db`.
- `main.py`: `lifespan`, `configure_logging`, CORS por `cors_origins.split(",")`,
  handler `DomainError` → `{"code","message"}`.
- `exceptions.py`: `DomainError` (`.message`/`.code`) + `NotFound/Conflict/ValidationError/IntegrationError`.
- `Dockerfile` (uv, multistage, `alembic upgrade head` no boot), Alembic, `pyproject` hatchling + ruff(100/py312) + pytest(asyncio auto).
- Postgres central `v7m`, schema = nome do serviço, FK `..._external_id_fkey` → `auth.users.external_id`.

**Outliers** (convenção própria, não são o alvo):
- `auth` — config **UPPERCASE**, `fastapi_structured_logging`, erro `{"detail","code"}`, middleware Redis. É o serviço central/legado.
- `lead`, `enrollment` — layout antigo (`routers/`, `schemas.py`, `graphify-out/`).
- `staff` (Next.js), `whats` (Evolution, terceiros), `mail` (terceiros).

## Veredito: ✅ coeso com o template canônico (espelha o `profiles`)

`diff` do `addresses` contra o `profiles` nos arquivos de fundação:

| Arquivo | Resultado |
|---|---|
| `app/db.py` | idêntico (só docstring com o nome do schema) |
| `app/main.py` | idêntico (só docstring) |
| `app/utils/logging.py` | **idêntico** |
| `app/api/health.py` | idêntico (só docstring) |
| `app/api/router.py` | mesmo padrão (+ router `entities`) |
| `app/exceptions.py` | estruturalmente idêntico (docstrings de domínio adaptadas: CEP/UF/kind) |
| `alembic.ini` | **idêntico** |
| `pyproject.toml` | mesmas deps/seções (+ `python-multipart` p/ upload) |
| `Dockerfile` | idêntico (+ `mkdir -p uploads`) |
| FK em `models/` | mesmo padrão `..._external_id_fkey` → `auth.users` |

## Ajustes de coesão aplicados nesta rodada
- `exceptions.py`: removido `NotImplementedYet` (código morto — ViaCEP foi implementado)
  e adicionado `IntegrationError` (502), igual ao template. Passou a ser **usado de
  verdade**: ViaCEP indisponível → `IntegrationError` (502) no endpoint `/cep`; o fluxo
  de entidade captura e **degrada graciosamente** (salva só o zipcode).
- `utils/logging.py`: docstrings adicionadas → agora idêntico ao `profiles`.

Reverificado: `ruff` limpo, import OK, e smoke e2e real (Postgres em Docker, ViaCEP
real + ViaCEP caído): `/cep` 200/404/**502**, entidade preenche / degrada. Tudo ✅.

## Divergência intencional (mantida)
- `alembic/env.py`: cria/commita o schema **antes** das migrations (numa conexão
  própria). O template assume o schema pré-provisionado e falha em banco novo; aqui a
  migração é autossuficiente. É idempotente (`CREATE SCHEMA IF NOT EXISTS`) e não afeta
  prod. Recomendado **portar essa correção para os demais serviços** do cluster.

## Nota
- `version` varia na frota (0.1–1.0; `documents` também é 1.0.0) — não é convenção; o
  `addresses` em 1.0.0 está ok.
