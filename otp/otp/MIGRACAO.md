# Migração / Sincronização com o código fonte-da-verdade

> **Data:** 2026-05-22
> **Origem (fonte da verdade):** `root@10.1.30.20:/opt/v7m/services/otp/` (v0.2.0)
> **Destino:** `/home/maestri33/backend/otp/otp/` (estava em v0.1.0)
>
> O código local estava **desatualizado**. Este documento registra (1) as
> diferenças globais entre os dois códigos e (2) as alterações aplicadas no
> local para deixá-lo coeso com o remoto. A fonte da verdade é o remoto.

---

## 1. Resumo executivo

O serviço sofreu uma **troca completa de stack de persistência** entre a versão
local (v0.1.0) e a remota (v0.2.0), além de ganhar **rate limit**, **cleanup
automático** e **métricas de status** mais ricas.

| Camada        | Local (v0.1.0 — antigo)        | Remoto (v0.2.0 — fonte da verdade)        |
| ------------- | ------------------------------ | ----------------------------------------- |
| ORM           | Tortoise ORM (estilo Django)   | **SQLAlchemy 2 (async)**                  |
| Migrations    | Aerich (`migrations/`)         | **Alembic** (`alembic/`)                  |
| Banco         | SQLite local (`data/app.db`)   | **PostgreSQL** (asyncpg), schema `otp`    |
| Identidade    | `external_id` = `CharField`    | **`external_id` = `UUID`** (FK p/ `auth.users`) |
| Porta         | 80                             | **8000**                                  |
| Build         | (nenhum)                       | **hatchling** + **Dockerfile**            |
| Versão        | 0.1.0                          | **0.2.0**                                 |

Funcionalidades novas no remoto que **não existiam** no local:

- **Rate limit por `external_id`** — janela curta (`OTP_RATELIMIT_WINDOW_S`,
  default 30s) + janela horária (`OTP_RATELIMIT_HOURLY_MAX`, default 5). Estoura
  `429` com header `Retry-After`.
- **Cleanup automático** — task de fundo no lifespan que purga logs antigos
  (`OTP_CLEANUP_INTERVAL_S` / `OTP_CLEANUP_RETENTION_DAYS`).
- **Controle de tentativas** — `OTPLog.attempts` + `failure_reason`; após
  `OTP_MAX_ATTEMPTS` códigos errados o OTP é invalidado (`status=failed`).
- **Métricas no `/status`** — tempo médio de verificação, breakdown de falhas
  por motivo, top external_ids com falha, rate-limits ativos.

---

## 2. Diferenças globais por arquivo

### Arquivos NOVOS no remoto (adicionados ao local)

| Arquivo                                         | Função |
| ----------------------------------------------- | ------ |
| `Dockerfile`                                     | Imagem Python 3.12-slim + uv; roda `alembic upgrade head` no start; porta 8000. |
| `alembic.ini`                                    | Config do Alembic. |
| `alembic/env.py`                                 | Env do Alembic com suporte a schema `otp` + `version_table_schema`. |
| `alembic/script.py.mako`                         | Template de migration. |
| `alembic/versions/2026-05-15_initial_otp_schema.py` | Cria `otp.otp_logs` e `otp.pending_notify` (FK p/ `auth.users`). |
| `alembic/versions/2026-05-15_0002_rate_limit_and_metrics.py` | Cria `otp.rate_limit` + colunas `attempts`/`failure_reason`. |
| `app/models/rate_limit.py`                       | Modelo `RateLimit` (PK = `external_id`). |
| `app/services/rate_limit.py`                     | `check_and_record()` (UPSERT atômico) + `reset()`. |
| `app/services/cleanup.py`                        | `run_once()` + `cleanup_loop()`. |

### Arquivos REMOVIDOS do local (não existem no remoto)

| Arquivo                                  | Motivo |
| ---------------------------------------- | ------ |
| `migrations/models/1_20260509011103_None.py` | Migration Aerich — substituída por Alembic. |
| `migrations/models/2_20260512075922_add_pending_notify.py` | Migration Aerich — substituída por Alembic. |
| `migrations/` (pasta)                    | Sistema Aerich aposentado. Movida p/ backup, não apagada. |

### Arquivos MODIFICADOS (reescritos Tortoise → SQLAlchemy)

| Arquivo                       | O que mudou |
| ----------------------------- | ----------- |
| `pyproject.toml`              | Deps: `tortoise-orm`/`aerich` → `sqlalchemy[asyncio]`/`asyncpg`/`alembic`. Removida seção `[tool.aerich]`. Adicionado `[build-system]` (hatchling). Versão 0.1.0 → 0.2.0. |
| `app/db.py`                   | Config Tortoise → `Base`/engine/`async_session_maker`/`get_session` SQLAlchemy. Tabela-sombra `auth.users` p/ resolver FK cross-schema. |
| `app/config.py`              | `database_url` SQLite → Postgres+asyncpg; novo `database_schema`; novas vars de rate limit e cleanup; porta 80 → 8000. |
| `app/main.py`                 | Remove `init_db()`; adiciona `cleanup_loop` no lifespan; handler `RateLimitExceeded` (429). |
| `app/exceptions.py`           | Nova exceção `RateLimitExceeded` (429 + `retry_after_s`). |
| `app/models/otp.py`           | Tortoise → SQLAlchemy; `external_id` UUID + FK; novas colunas `attempts`, `failure_reason`. |
| `app/models/pending_notify.py`| Tortoise → SQLAlchemy; UUID + FKs (`auth.users`, `otp.otp_logs`). |
| `app/models/__init__.py`      | Adiciona `RateLimit` ao pacote. |
| `app/schemas/otp.py`          | `external_id: str` → `UUID`; `OTPRead` ganha `attempts`/`failure_reason` + `from_attributes`. |
| `app/services/otp.py`         | Recebe `AsyncSession`; UUID; integra rate limit; lógica de `attempts`/max-attempts; `failure_reason`. |
| `app/services/queue.py`       | Reescrito p/ SQLAlchemy (`_process_one`, sessões); `failure_reason=notify_down`; `os.unlink` tolerante a ausência. |
| `app/services/otp.md`         | Tratamento do `{{rodape}}` (sem espaço trailing quando footer vazio). |
| `app/api/otp.py`              | Injeta `session` (`Depends(get_session)`); `external_id: UUID`. |
| `app/api/webhook.py`          | Injeta `session`; usa `select()`; seta `failure_reason`. |
| `app/api/health.py`           | `/ready` usa `session.execute(text("SELECT 1"))` SQLAlchemy. |
| `app/api/status.py`           | Métricas novas (avg verificação, breakdown, top failed, rate-limit ativo). |
| `app/integrations/notify_client.py` | `_url()` agora prefixa `/api/v1` no código (a env var **não** deve mais incluir `/api/v1`). |
| `Makefile`                    | Porta 80 → 8000; `make migrate` = `alembic upgrade head` (era `aerich`). |
| `.env.example`                | Postgres URL + schema; porta 8000; vars de rate limit e cleanup. |
| `tests/conftest.py`           | Fixtures Tortoise/SQLite removidas; **todos os testes legados marcados como `skip`** (suíte aguardando reescrita p/ Postgres). |

### Arquivos IDÊNTICOS nos dois (sem ação)

`app/api/deps.py`, `app/api/router.py`, `app/services/notify.py`,
`app/integrations/http_client.py`, `app/utils/logging.py`, `tests/__init__.py`,
`tests/test_otp.py`, `tests/test_health.py`, `README.md`, `scripts/dev.sh`,
`scripts/otp.service`, `.gitignore`, `.python-version`, `.mcp.json`.

---

## 3. Inconsistências que JÁ EXISTEM na fonte da verdade

Mantidas como estão para preservar coesão com o remoto (não foram "consertadas",
apenas registradas):

1. **`README.md` desatualizado** — ainda diz "Tortoise ORM", porta 80 e
   `make migrate = aerich`. Idêntico no local e no remoto.
2. **`scripts/otp.service`** — `ExecStart` na porta **80** e `WorkingDirectory=/root/otp`,
   divergindo do `Dockerfile` (porta 8000). Idêntico nos dois.
3. **`tests/test_otp.py` / `tests/test_health.py`** — continuam escritos contra
   Tortoise/SQLite e estão **todos com skip** via `conftest.py`. A suíte
   automatizada efetivamente **não cobre** a stack nova (precisa reescrita com
   `testcontainers-postgres`/`pg_tmp`).
4. **Lint** — `ruff check app` aponta **34 findings** (idêntico nos dois;
   maioria `UP017` `datetime.UTC`). Não corrigidos para não divergir da fonte.

---

## 4. Alterações aplicadas no local

- Sincronizados todos os arquivos da seção 2 (cópia byte-a-byte do remoto;
  `diff -rq` local vs remoto = **sem diferenças**, exceto `.claude/`, `.env`,
  `data/`, `uv.lock`).
- `migrations/` (Aerich) movida para backup em `/tmp` (não apagada).
- `.env` local **reescrito** para a stack nova (Postgres, porta 8000, vars de
  rate limit/cleanup). Apontado para o Postgres de teste E2E. **Ação do usuário:**
  ajustar `NOTIFY_BASE_URL`/`DATABASE_URL` para os valores reais do ambiente.
- `uv sync` executado — `uv.lock` regenerado com SQLAlchemy/asyncpg/alembic.
- `.claude/CLAUDE.md` e `.claude/memory/*` atualizados para a stack nova.
- Backups criados em `/tmp`: `otp-local-backup-FULL-*.tar.gz` (código local
  original) e `otp-aerich-migrations-removed_*` (migrations Aerich).

---

## 5. Testes de ponta a ponta (dados reais, sem mock)

Ambiente: container `otp-e2e-pg` (`postgres:16-alpine`, porta host 5552), banco
`v7m` com schemas `auth` (+ `auth.users` semeada) e `otp` (migrado via Alembic
`upgrade head` até a revisão `0002`). Serviço rodando em `uvicorn` real.

| # | Cenário                                            | Resultado |
| - | -------------------------------------------------- | --------- |
| 1 | `GET /health`                                      | ✅ `{"status":"ok"}` |
| 2 | `GET /ready` (SELECT 1 no Postgres real)           | ✅ `{"status":"ready"}` |
| 3 | `GET /api/v1/otp` (vazio e com dados)              | ✅ ordenado por `created_at` desc |
| 4 | Validação UUID inválido                            | ✅ HTTP 422 |
| 5 | `POST /check` sem OTP pendente                     | ✅ "Nenhum OTP pendente encontrado" |
| 6 | `POST /check` sucesso                              | ✅ `valid=true`; DB → `verified` + `verified_at` |
| 7 | `POST /check` expirado (TTL 300s, criado há 600s)  | ✅ "OTP expirado"; DB → `expired`/`failure_reason=expired` |
| 8 | `POST /check` max-attempts (3 erros)               | ✅ na 3ª → `failed`/`attempts=3`/`invalid_code` |
| 9 | Filtros (`status`, `external_id`) + paginação      | ✅ corretos |
| 10| Rate limit: 2º `POST /otp` em <30s                 | ✅ **429** + `Retry-After: 29` + body `retry_after_s` |
| 11| Fila: notify indisponível → `pending_notify`       | ✅ enfileirado; loop fez `retry_scheduled` (backoff) |
| 12| `POST /webhook/notify/{id}` (conhecido)            | ✅ `failed`/`notify_permanent` |
| 13| `POST /webhook/notify/{id}` (desconhecido)         | ✅ `{"ok":false}` |
| 14| `GET /status` (métricas reais)                     | ✅ avg_verification_ms, failure_breakdown, top_failed, rate_limit_active |
| 15| `cleanup.run_once()` com dados de 40 dias          | ✅ removeu 1 otp_log (+ pending via CASCADE) e 1 rate_limit órfão |
| 16| Lifespan: `queue_loop` + `cleanup_loop`            | ✅ sobem e rodam contra o Postgres real |

Log do servidor: sem 500/tracebacks. Únicos warnings = `notify.local`
inalcançável (DNS) — comportamento real esperado, pois o notify não está
configurado neste ambiente.

### Não testado (requer decisão do usuário)

- **Fluxo de geração com sucesso de envio** (`POST /otp` → `status=sent`):
  exige (a) acesso de rede ao serviço `notify` real, (b) um contato real já
  cadastrado e (c) **envio de uma mensagem OTP real para uma pessoa real**
  (efeito colateral). Por isso ficou pendente de confirmação. Todo o resto do
  caminho de geração (rate limit, persistência, render do template, tratamento
  de falha transitória → fila) **foi** exercido.

---

## 6. Como reproduzir o ambiente de teste

```bash
# 1. Postgres real (schemas auth + otp)
docker run -d --name otp-e2e-pg -e POSTGRES_USER=v7m -e POSTGRES_PASSWORD=v7m \
  -e POSTGRES_DB=v7m -p 5552:5432 postgres:16-alpine
# criar schema auth + auth.users (FK alvo) e schema otp — ver seção do README

# 2. Dependências + migrations
uv sync
uv run alembic upgrade head     # cria otp.otp_logs, pending_notify, rate_limit

# 3. Subir o serviço
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```
