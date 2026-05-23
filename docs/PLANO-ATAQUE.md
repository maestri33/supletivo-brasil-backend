# Plano de Ataque — Alinhamento à Convenção

> Referência normativa: [`/CLAUDE.md`](../CLAUDE.md). Modelo a espelhar: **`address`**.
> Princípio: **não mudar comportamento** — só stack, estrutura e qualidade. Um serviço por vez; validar; seguir.
> Versão consolidada com a auditoria das 3 frentes (identidade · negócio · comunicação/outliers).

---

## Achado central

A dívida real **não é só de pastas** — é uma **migração de stack inacabada**:

- **Stack errada (fora do canônico):** `candidate` e `documents` em **Tortoise ORM + SQLite**; `asaas` em **SQLAlchemy síncrono + psycopg2**; `auth` com default **SQLite/aiosqlite**.
- **Resíduo SQLite→Postgres** espalhado: `data/*.db` em `profiles`, `roles`, `otp`, `asaas`, `notify` (+ `db.sqlite3`/`documents.db`).
- **Segredos e PII versionados:** chave privada, `.env`, comprovantes, CSV com e-mail real.

Os serviços **já no padrão** (async/asyncpg/SQLAlchemy 2.0 + estrutura): `address` (ref), `profiles`, `notify`, `otp`, `roles`, `enrollment`, `lead`. Estes só precisam de ajustes menores.

---

## Estado real por serviço (auditado)

| Serviço | Stack / DB | Estrutura | Veredito |
|---|---|---|---|
| `address` | async/asyncpg ✓ | ✓ referência | **REFERÊNCIA** (limpar PII em `uploads/`) |
| `profiles` | async ✓ | ✓ | menor (conftest Tortoise morto; `data/profiles.db`) |
| `notify` | async ✓ | ✓ | menor (faxina; `data/app.db`; órfão `ai-prep/`) |
| `otp` | async ✓ | ✓ | menor (docstrings em **inglês**; `otp.md` no código; `data/app.db`) |
| `roles` | async ✓ | quase | menor (`api/config.py` mal nomeado; sem health/utils; settings UPPERCASE) |
| `enrollment` | async ✓ | quase | menor (órfão `graphify-out/`; sem `router.py`/`health.py`/`services/`) |
| `lead` | async ✓ | antiga | menor (`routers/`; `schemas.py`; sem `exceptions.py`/`utils/`) |
| `ai` | stateless ✓ | divergente | menor (schemas em `api/`; `v1.py` duplica rotas; sem `exceptions.py`; pyproject) |
| `jwt` | stateless ✓ | ok | **GRAVE** (🔴 `private.pem` versionada; py3.10; `egg-info`; `stats.py` solto) |
| `auth` | 🔴 **SQLite default/aiosqlite** | sem `schemas/`/`services/`; `config/`+`config.py` | **GRAVE** (`niquests`≠httpx; structlog errado; `utils/logging.py` é Redis) |
| `asaas` | 🔴 **SÍNCRONO/psycopg2** | `models`/`schemas` colapsados em `__init__` | **GRAVE** (SQLite + backups + apps órfãos) |
| `documents` | 🔴 **Tortoise/SQLite** | ✓ aparente | **GRAVE** (tabelas em **pt-br**; pydantic v1; `.env` versionado) |
| `candidate` | 🔴 **Tortoise/SQLite** | antiga | **PIOR CASO** (sem `pyproject`; `routers/`; `models.py`/`schemas.py`) |
| `mail` | FastAPI (terceiros) | flat (`app.py`) | reempacotar (baixo-médio) |
| `staff` | Next.js 16/React 19 | ✓ limpo | **OK** (sem ação urgente) |
| `whats` | Evolution API (terceiros) | — | **FORA** (remover binário `swag` 18 MB) |

*Cross-service é sempre HTTP em `integrations/` (correto em todos); ninguém importa código de outro serviço; ninguém usa `requests`/Flask.*

---

## Ordem recomendada de execução

1. **Fase 0 — Segurança** (agora, imediato)
2. **Fase 1 — Faxina de ruído** (agora, risco zero)
3. **Fase 2 — Ajustes em quem já é async** (momentum: `lead`, `enrollment`, `roles`, `otp`, `ai`, `notify`, `profiles`)
4. **Fase 3 — Migração de stack** (pesado, um por vez: `auth` → `asaas` → `documents` → `candidate`)
5. **Fase 4 — Outliers** (`mail`, depois doc de `staff`/`whats`)

---

## Fase 0 — Segurança · *imediato*

- **`jwt/jwt/private.pem`** (chave privada RSA): remover do repositório **e rotacionar** (esteve exposta). `config._ensure_keys()` já regenera em runtime — garantir que `*.pem` fique fora e em volume/secret. Conferir `public.pem` também.
- **`documents` `.env`** versionado: remover; migrar p/ secret manager / `.env` ignorado.
- **PII / dados reais:** `address/.../uploads/*.pdf` (comprovantes), `mail/.../teste.csv` (e-mail real), binários de teste em `documents/media/` e `notify/media/`: remover do repo.
- Adicionar `.env`, `*.pem`, `uploads/`, `data/`, `media/` ao `.gitignore`.

**Pronto quando:** nenhum segredo/PII no tree; chave rotacionada.

---

## Fase 1 — Faxina de ruído · *todos · risco zero*

```bash
cd /home/maestri33/backend
find . -type d \( -name __pycache__ -o -name .ruff_cache -o -name .pytest_cache \
  -o -name .mypy_cache -o -name .venv -o -name "*.egg-info" \) -prune -exec rm -rf {} +
find . -type f \( -name "*.pyc" -o -name ".DS_Store" \) -delete
```
- **SQLite leftover:** apagar `data/*.db*` em `profiles`, `roles`, `otp`, `asaas`, `notify`; `candidate/.../db.sqlite3`; `documents.db`. (Confirmar antes que nenhum código aponta para eles — auditoria indica que não.)
- **Órfãos:** `asaas/asaas-backups/`, `asaas/*.tar.gz`, `asaas/internal-sink/`, `asaas/fastapi-mcp-demo/`, `notify/ai-prep/`, `enrollment/app/graphify-out/`, `ai/app/data/` (árvore duplicada), `whats/go/bin/swag` (18 MB).
- **Relatórios soltos** (`SYNC_REPORT.md`, `MIGRACAO.md`, `NOTAS_MIGRACAO.md`, `RELATORIO_*`, `ALTERACOES.md`): consolidar em `docs/` ou remover.
- **`.gitignore` padrão** na raiz + por serviço (cobrir caches, venv, egg-info, `.env`, `*.pem`, `data/`, `uploads/`, `media/`).
- Remover tooling versionado indevido: `.claude/settings.local.json`, `.mcp.json`, `.python-version` onde aplicável.

**Pronto quando:** `find . -name __pycache__ -o -name .venv -o -name "data/*.db"` → vazio.

---

## Fase 2 — Ajustes em quem já é async · *baixo-médio*

- **`lead`** (`lead/app`): `routers/` → `api/` (criar `router.py` + `health.py`); `schemas.py` → `schemas/`; criar `services/`, `exceptions.py`, `utils/logging.py`; realocar `tools/`+`notify/` → `integrations/`; tirar `docs/` de dentro de `app/`.
- **`enrollment`** (`enrollment/app`): remover `graphify-out/`; criar `api/router.py` + `api/health.py` (hoje inline no `main.py`); criar `services/`.
- **`roles`** (`roles/roles/app`): renomear `api/config.py` → `api/role_rules.py` (é CRUD de regras, não config); criar `api/health.py`, `utils/logging.py` (structlog); settings UPPERCASE → minúsculo + `get_settings()` lru_cache; adicionar `tests/` (há `testpaths` sem pasta).
- **`otp`** (`otp/otp/app`): docstrings/comentários **inglês → pt-br**; mover `services/otp.md` para asset/constante; montar `status.py` via `api/router.py` (não no `main.py`).
- **`ai`** (`ai/ai/app`): `api/schemas.py` → `schemas/`; consolidar `v1.py` nos arquivos de recurso (eliminar rotas duplicadas, manter aliases legados explícitos); criar `exceptions.py` (DomainError + handler); corrigir `pyproject` (hatchling, `[tool.ruff]`, descrição real, pinning). **Documentar exceção stateless** em `ai/CLAUDE.md` (sem `db.py`/`models/` por design — mas `schemas/`/`services/` exigidos).
- **`notify`** (`notify/notify`): apenas faxina (Fase 1) + acentuar docstrings pt-br.
- **`profiles`** (`profiles/profiles/app`): remover/reescrever `tests/conftest.py` (usa **Tortoise** num app SQLAlchemy — fixture morta); remover `RELATORIO_SYNC.md`.
- **`jwt`** (`jwt/jwt/app`): após Fase 0, mover `stats.py` → `utils/`/`services/`; subir `requires-python`/ruff para **3.12**; migrar build `setuptools` → **hatchling**; **documentar exceção stateless** em `jwt/CLAUDE.md`.

---

## Fase 3 — Migração de stack · *alto · um por vez, com testes*

Meta comum: SQLAlchemy 2.0 **async** + asyncpg + schema Postgres próprio + **shadow `auth.users`** + Alembic, espelhando `address/app/db.py`.

- **`auth`** (`auth/auth/app`): trocar default SQLite/`aiosqlite` → Postgres/asyncpg; `niquests` → **httpx** (inclusive o import inline em `register.py`); `fastapi-structured-logging` → **structlog**; remover `init_db()/create_all` (só Alembic); settings UPPERCASE → minúsculo; resolver `config/` vs `config.py` (fonte única); criar `schemas/`, `services/`, `api/health.py`; renomear `utils/logging.py` (é log-store Redis, não logging) → ex. `services/log_store.py`.
- **`asaas`** (`asaas/asaas-app/app`): `create_engine`/`psycopg2`/`sessionmaker(Session)` → `create_async_engine`/asyncpg/`AsyncSession`; tornar serviços async; **dividir** `models/__init__.py` (126 l.) e `schemas/__init__.py` (708 l.) em 1 arquivo por recurso; consolidar config (`config.py` + `config_store.py` + `api/config.py` + `services/config_*`).
- **`documents`** (`documents/documents/app`): Tortoise → SQLAlchemy async + Postgres + schema próprio + Alembic (substituir `generate_schemas=True`); **renomear tabelas pt-br → inglês** (`documentos`→`documents`, `carteiras_trabalho`→`work_permits`, `passaportes`→`passports`) **com migração de dados**; pydantic `class Config` → `ConfigDict` (v2); pyproject ruff/py3.12; renomear pastas de mídia em pt-br.
- **`candidate`** (`candidate/candidate/app`) — **pior caso**: Tortoise/SQLite → SQLAlchemy async/Postgres; criar `pyproject.toml` (hatchling + ruff, substituindo `requirements.txt`); `routers/`→`api/`; `models.py`→`models/`; `schemas.py`→`schemas/`; criar `db.py`, `services/`, `exceptions.py`, `alembic/`; shadow `auth.users`.

---

## Fase 4 — Outliers

- **`mail`** (`mail/FlaskPost`): **já é FastAPI** (terceiros, MIT) — sem troca de framework. Reempacotar no padrão: criar `app/{config.py (pydantic-settings), main.py, exceptions.py, api/(router+health+mail.py), schemas/, services/mail_service.py, integrations/smtp.py}`; trocar `logging` por structlog; eliminar `smtp_config` global; tornar envio **não-bloqueante** (remover `time.sleep`); decidir persistência de histórico (se sim → +DB async/Alembic). Remover `FlaskPost.png`, `teste.csv`, `vercel.json`.
- **`staff`** (`staff/dashboard-boos`): Next.js 16 + React 19 + TS, limpo e idiomático (sem `node_modules`/`.next` versionados). Sem ação urgente. Escrever `staff/CLAUDE.md` (convenção front: `src/app`, `src/components`, `src/lib`, idioma inglês no código + UI pt-br). Opcional: renomear dir (`boos`→`boss`).
- **`whats`** (`whats/evolution-api`): Evolution API de terceiros (Apache-2.0, ~17 MB). **Não refatorar.** Fixar por versão/imagem Docker (há `.gitmodules`). Já tratado na Fase 1 (remover `swag`/`.DS_Store`). Documentar em `whats/CLAUDE.md` que está fora da convenção.

---

## Exceções legítimas (registrar no `CLAUDE.md` do serviço)

- **`jwt`** e **`ai`**: stateless por design — sem `db.py`/`models/`/Alembic. (`ai` ainda deve ter `schemas/` e `services/`.)

---

## Definition of Done (por serviço)

- [ ] **Stack canônica**: SQLAlchemy 2.0 async + asyncpg (ou exceção stateless documentada); sem Tortoise/sync/SQLite
- [ ] Estrutura espelha `address` (`api/ models/ schemas/ services/` + `main/config/db/exceptions`)
- [ ] Postgres schema próprio + shadow `auth.users` + migração Alembic
- [ ] Sem ruído/órfãos/segredos; `.gitignore` cobre
- [ ] Identificadores (incl. tabelas/colunas) em inglês; docstrings/comentários pt-br **verdadeiros**
- [ ] Sem código duplicado/morto; sem rotas duplicadas
- [ ] `ruff` limpo; `pytest` passa; app sobe; smoke test ok
- [ ] `CLAUDE.md` do serviço (exceções) + `README.md` atualizado
