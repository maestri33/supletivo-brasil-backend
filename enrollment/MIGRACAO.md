# Migração do serviço `enrollment` — local → stack de produção

> Documento gerado ao reconciliar o código **local** (`/home/maestri33/backend/enrollment`)
> com o que está em **produção** (`root@10.1.30.20:/opt/v7m/services/enrollment`).
>
> Objetivo: deixar os dois **coesos**. A produção foi adaptada às pressas para subir;
> aqui o local foi migrado para a mesma stack de produção (que já segue o `CONVENTIONS.md`
> da casa) e recebeu de volta os extras que tinha de mais desenvolvido.

---

## 1. Resumo executivo

O local e a produção **não eram variações do mesmo código** — eram stacks tecnológicas
incompatíveis. O local rodava **Tortoise ORM + SQLite**; a produção roda
**SQLAlchemy 2.0 async + PostgreSQL + Alembic** (padrão obrigatório da stack v7m).

Decisão (aprovada): **migrar o local para a stack de produção**, espelhando os arquivos
da produção e **portando os dois extras** que o local tinha de melhor:

1. **Idempotência** no recebimento do webhook.
2. **Access-log estruturado** (`fastapi-structured-logging`, padrão da casa).

Resultado validado **ponta a ponta contra Postgres real** (sem mock): ✅ tudo passou.

---

## 2. Situação inicial — diferenças globais

| Dimensão | Local (antes) | Produção (referência) |
|---|---|---|
| ORM | **Tortoise ORM** | **SQLAlchemy 2.0 async** + asyncpg |
| Banco | **SQLite** (`sqlite://db.sqlite3`) | **PostgreSQL 16** (`v7m`, schema `enrollment`) |
| Schema/DDL | `generate_schemas=True` (auto no boot) | **Alembic** (migração `0001`) |
| Modelo | `EnrollmentWebhook` | `EnrollmentEvent` |
| Identificador | `lead_external_id` `CharField(36)` **unique** | `external_id` `UUID` **FK → `auth.users`** |
| Campos | id, lead_external_id, promoter_external_id, received_at | id, external_id, **event**, promoter_external_id, **payload JSONB**, received_at, **processed_at** |
| Endpoint webhook | `POST /api/v1/webhook/new/{id}` (com dedup) | `POST /api/v1/webhook/new/{id}` (sempre insere) |
| Endpoints de auditoria | — | `GET /api/v1/events`, `GET /api/v1/events/{id}` |
| Healthchecks | — | `/health`, `/ready`, `/status` |
| Logging | `fastapi_structured_logging` (setup + AccessLog) | `structlog` puro, **sem setup nem access-log** |
| CORS | — | habilitado |
| Infra | nenhuma | `Dockerfile`, `pyproject.toml`, `alembic/` |

**Leitura:** cada lado tinha algo que o outro não tinha. A produção é muito mais completa
(banco real, migração, FK, payload JSONB, auditoria, healthchecks, Docker); o local só
era "mais desenvolvido" em dois pontos: **dedup/idempotência** e **setup de logging
estruturado + access-log**. A migração preserva os dois.

---

## 3. Decisão de arquitetura

- **Alvo = espelhar a produção arquivo a arquivo** (mesma stack, mesmo schema, mesma
  migração `0001`, mesmos contratos de API). Isso garante coesão real e mantém paridade
  com o que está deployado.
- **Portar os extras do local como melhorias aditivas**, sem quebrar contratos:
  - Idempotência feita **em nível de aplicação** (sem alterar o schema → a migração
    continua idêntica à de produção).
  - Access-log seguindo o padrão do `CONVENTIONS.md` (igual ao serviço `auth`).
- **Não** expandir para o layout completo do `CONVENTIONS.md` (`schemas/`, `services/`,
  `api/public|authenticated|demilitarized`, `deps.py`, `exceptions.py`): isso faria o local
  **divergir** da produção. Fica como recomendação futura (seção 7).

---

## 4. Alterações aplicadas no código local

### 4.1 Removido (stack Tortoise antiga)
- `app/models.py` — modelo Tortoise `EnrollmentWebhook`.
- `app/routers/__init__.py` e `app/routers/webhooks.py` — router Tortoise.

### 4.2 Reescrito
- **`app/config.py`** — de Settings/SQLite para o config de produção
  (`service_name`, `env`, `log_level`, `database_url` Postgres, `database_schema`,
  `get_settings()` com `lru_cache`).
- **`app/main.py`** — de `RegisterTortoise` para:
  - lifespan com `engine.dispose()` (SQLAlchemy);
  - `CORSMiddleware`;
  - `/health`, `/ready` (testa `SELECT 1` no DB real), `/status`;
  - **[extra portado]** `fsl.setup_logging(...)` + `AccessLogMiddleware`.

### 4.3 Adicionado (igual à produção)
- **`app/db.py`** — engine async, `async_session_maker`, `Base`, `get_session`, e a
  *shadow table* `auth.users` (necessária para o SQLAlchemy resolver a FK cross-schema).
- **`app/models/__init__.py`** + **`app/models/enrollment_event.py`** — modelo
  `EnrollmentEvent` (SQLAlchemy) com FK `auth.users.external_id`
  (`ON DELETE RESTRICT ON UPDATE CASCADE`), `payload JSONB`, `processed_at`.
- **`app/api/__init__.py`** + **`app/api/webhooks.py`** — receptor do webhook +
  `GET /events` + `GET /events/{id}`.
- **`alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`,
  `alembic/versions/2026-05-15_initial_enrollment_schema.py`** — migração `0001`
  (idêntica à de produção).
- **`Dockerfile`** — multi-stage com `uv`; no boot roda `alembic upgrade head && uvicorn`.
- **`pyproject.toml`** — deps de produção **+ `fastapi-structured-logging`** (para o
  access-log) **+ `httpx`** (dev). `uv.lock` gerado e pinado.

### 4.4 Adicionado (helpers da casa que a produção ainda não tinha)
- **`.dockerignore`** — exclui `__pycache__`, `.venv`, `graphify-out`, etc. do build.
- **`.env.example`** — variáveis padrão (`ENV`, `LOG_LEVEL`, `DATABASE_URL`, `DATABASE_SCHEMA`).

---

## 5. Extras portados — detalhes de design

### 5.1 Idempotência (`app/api/webhooks.py`)
O local antigo deduplicava por `lead_external_id` (uma linha por lead). A produção é um
**log auditivo append-only** (`enrollment_events`) e sempre insere.

Reconciliação: idempotência **por `(external_id, event)`** em nível de aplicação —
antes de inserir, consulta se já existe um evento igual; se sim, devolve o `id` existente
com `already_exists=true` (HTTP 202) sem duplicar. Mantém o log como append-only para
eventos **diferentes** do mesmo usuário (ex.: `lead.completed` e `lead.reopened` coexistem).

- **Sem alteração de schema** → a migração permanece idêntica à de produção.
- **Compatível com o caller**: `lead/app/tools/webhooks.py` só checa `raise_for_status()`,
  então o novo campo `already_exists` não quebra nada.
- **Ressalva (documentada):** check-then-insert tem janela de corrida sob requisições
  idênticas concorrentes. Para garantia a nível de banco, uma migração futura poderia
  adicionar `UNIQUE(external_id, event)` — **somente depois** de confirmar que os dados
  de produção não têm duplicatas pré-existentes.

### 5.2 Access-log estruturado (`app/main.py`)
A produção não configurava logging. Portado o padrão da casa (`CONVENTIONS.md`, igual ao
`auth`): `fsl.setup_logging(json_logs=(env!="dev"), log_level=...)` + `AccessLogMiddleware`
com `exclude_paths_if_ok_or_missing={"/health","/ready","/status"}` — healthchecks só
aparecem no log se **falharem**. Campos custom: `service`, `env`.

---

## 6. Validação — teste E2E com dados reais (sem mock)

Seguindo o padrão da casa (Postgres real em container `<serviço>-e2e-pg`), foi criado
`enrollment-e2e-pg` (postgres:16-alpine), provisionado `auth.users` (alvo da FK), aplicada
a migração `0001` e semeados usuários reais. O app foi servido por `uvicorn` e exercitado
por HTTP real.

| Caso | Esperado | Resultado |
|---|---|---|
| `alembic upgrade head` em Postgres real | cria `enrollment_events` + FK | ✅ versão `0001` |
| `GET /health` | `{"status":"ok","service":"enrollment"}` | ✅ |
| `GET /ready` | `db: ok` (conexão real) | ✅ |
| `GET /status` | uptime/version/env | ✅ |
| `POST /webhook/new/{lead1}` (payload real) | 202, persiste evento + payload JSONB | ✅ `id=1` |
| `POST` repetido (mesmo evento) | 202, `already_exists=true`, **sem duplicar** | ✅ `id=1` |
| `POST` evento diferente (`lead.reopened`) | 202, nova linha | ✅ `id=2` |
| `POST /webhook/new/{ghost}` (user inexistente) | erro de FK, **não persiste** | ✅ HTTP 500 (FK violation) |
| `GET /events` e `?external_id=` | lista/auditoria | ✅ |
| Conferência no banco | `rows_total=3`, `lead1_completed=1` | ✅ sem duplicata |
| Access-log estruturado | campos `service/env/method/path/status_code/process_time_ms` | ✅ |

Payload real usado (de `lead/app/tools/webhooks.py`):
`POST {url}/{external_id}` com `{"promoter_external_id": "<uuid>", "event": "lead.completed"}`.

O container de teste foi **removido** ao final (estado limpo). A produção **não foi tocada**.

---

## 7. Divergências intencionais

**Divergências intencionais** (local é o superset melhorado da produção):
1. Idempotência no webhook (produção sempre insere → pode duplicar).
2. Setup de logging + access-log (produção não tem).
3. `.dockerignore`, `.env.example`, `uv.lock` (a pasta da produção não tinha).
4. `external_id` ausente em `auth.users` → resposta **409** `{"code":"UNKNOWN_EXTERNAL_ID"}`
   (a produção devolvia 500 cru). Ver seção 8.

**Recomendação remanescente:**
- Subir essas melhorias para a produção (para os dois ficarem realmente idênticos).
- Avaliar `UNIQUE(external_id, event)` para idempotência à prova de corrida (só após
  confirmar que os dados de produção não têm duplicatas pré-existentes).

---

## 8. Coesão com o restante do backend + alinhamento completo

Após a migração, foi feita uma análise de coesão do `enrollment` contra os **17 serviços
reais** do monorepo `/home/maestri33/backend/`. Resultado: **coeso com o padrão dominante**.

**Já batia (template/maioria):** `db.py` (mesma estrutura de `address`/`notify`/`otp`/
`profiles`/`roles`/`lead` — `DeclarativeBase` + shadow `auth_users` + `async_session_maker`
+ `get_session`), `Dockerfile` (CMD idêntico a todos), `config.py` (lowercase +
`case_sensitive=False`, grupo majoritário), logging (`fastapi-structured-logging`),
`/health` `/ready` `/status`, `models/` + Alembic + FK cross-schema.

**Gaps de "stub" fechados (decisão: "alinhamento completo"):**

| Item | O que foi feito | Espelha |
|---|---|---|
| `app/schemas/` | `WebhookPayload` + `EnrollmentEventRead` movidos p/ `app/schemas/enrollment_event.py` (`api/webhooks.py` agora importa de lá) | address/notify/otp/profiles/roles |
| `app/exceptions.py` | `DomainError` + `NotFound`/`Conflict`/`ValidationError` + handler global no `main.py` (`{"detail","code"}`) | auth |
| Tratamento de FK | webhook captura `IntegrityError` → `Conflict` 409 `UNKNOWN_EXTERNAL_ID` (não mais 500); `get_event` usa `NotFound` 404 | auth |
| `Makefile` | `install/test/lint/format/run/migrate/check` (via `uv run`) | auth/notify/otp/profiles |
| `tests/` | `conftest.py` (Postgres real via `testcontainers` **ou** `TEST_DATABASE_URL`, fallback SKIP) + `test_health.py` + `test_webhooks.py` | notify (molde) |
| `pyproject` | `[tool.pytest.ini_options]` com `testpaths` + `asyncio_default_fixture_loop_scope="session"` | auth/notify |

**Suíte de testes (8 casos, Postgres real, sem mock):** persistência + payload JSONB,
idempotência por `(external_id, event)`, evento diferente cria nova linha, FK desconhecida
→ 409, `GET /events/{id}` + 404, e os 3 healthchecks. **8 passed**; `ruff` limpo.

```bash
# rodar a suíte (precisa de docker p/ testcontainers, OU TEST_DATABASE_URL)
make test
# ou, usando o container e2e da casa:
docker run -d --name enrollment-e2e-pg -e POSTGRES_USER=v7m -e POSTGRES_PASSWORD=v7m \
  -e POSTGRES_DB=v7m -p 5549:5432 postgres:16-alpine
TEST_DATABASE_URL=postgresql+asyncpg://v7m:v7m@localhost:5549/v7m uv run pytest -v
```

**O que NÃO foi adotado (e por quê):** `app/services/` (regra de negócio) e
`app/integrations/` — o `enrollment` é um receptor puro sem lógica de negócio nem chamadas
de saída; criá-los seria estrutura vazia. Pode entrar quando a lógica de matrícula real
existir.

**Estado final:** o `enrollment` está no nível dos serviços maduros (`profiles`/`otp`/
`notify`) — com a única exceção de `services/`/`integrations/`, omitidos por não se aplicarem
a um stub.
