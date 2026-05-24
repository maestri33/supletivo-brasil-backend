# infinitepay

## Função

Middleware FastAPI sobre a API de **checkout da InfinitePay**: cria links de pagamento, recebe o webhook server-to-server de confirmação e reenvia eventos internos via fila de saída com retry. É o **único serviço autorizado** a integrar com a API da InfinitePay (§12).

## Status

**Funcional e conforme à CONVENTION (stack canônica async).** Migrado de síncrono para async na Fase 3 (2026-05-24) e validado contra Postgres real.

- Stack: FastAPI + SQLAlchemy 2.0 **`AsyncSession`** + **asyncpg** + **`httpx.AsyncClient`** + **structlog** + pydantic-settings.
- Verificação: `ruff` limpo · `pytest` **20 passed** (`sqlite+aiosqlite`) · `alembic upgrade head` (`0001→0002`) OK contra Postgres real (schema + tabelas + FKs cross-schema criados, **sem** tabela `config`).
- Config da loja (handle, preços, URLs) vem **100% do `.env`** (a antiga tabela `config` e as rotas `/config` foram removidas — igual `otp`).
- IA direta (DeepSeek via SDK `openai`) **removida**; recibo e triagem de fraude usam o app `ai` central via `integrations/ai.py`.

## Estrutura

`infinitepay/app/` — achatado conforme §3 (pacote `app`). Sem aninhamento.

```
infinitepay/
├── app/
│   ├── main.py            # FastAPI; lifespan (worker async + close_db); structlog
│   ├── config.py          # Settings (pydantic-settings); database_url asyncpg; config da loja via .env
│   ├── db.py              # create_async_engine, Base, NAMING_CONVENTION, async_session_maker,
│   │                      #   get_session, close_db, shadow auth.users
│   ├── exceptions.py      # DomainError + subclasses (Conflict, NotFound, ValidationError, IntegrationError)
│   ├── api/               # checkout, webhooks, health + router (agrega)
│   ├── models/models.py   # SQLAlchemy (Checkout, WebhookLog, OutboundJob)
│   ├── schemas/           # Pydantic v2 (checkout, webhook, health, error)
│   ├── services/          # checkout_service (negócio async) + receipt + monitor (usam app `ai`)
│   ├── integrations/      # infinitepay_client.py (httpx.AsyncClient) + ai.py (client do app `ai`)
│   ├── workers/outbound_queue.py  # fila outbound_jobs, retry exponencial, claim atômico
│   └── utils/             # validators.py, crypto.py (Fernet), logging.py (structlog)
├── alembic/               # env.py async + versions 0001, 0002
└── tests/                 # async (pytest-asyncio, httpx.AsyncClient/ASGITransport)
```

> A migração **cria o schema `infinitepay` sozinha** (em `env.py`, `CREATE SCHEMA IF NOT EXISTS`, padrão do `asaas`/`address`) — validado em DB novo (`alembic upgrade head` recria tudo até a revision `0002`).
>
> Pendências conhecidas (Fase 4): PK ainda Integer autoincrement (→ UUID); `models/models.py` monolítico → split em `models/<entidade>.py` (§3); webhook não loga IP de origem (§5).

## Endpoints

### `api/checkout.py` — `/api/v1/checkout` — tag `checkout` (desmilitarizado)

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/` | Cria link de pagamento na InfinitePay (defaults de loja vêm do `.env` quando omitidos no body) |
| GET | `/` | Lista todos os checkouts (mais recente primeiro) |
| GET | `/{external_id}/` | Consulta checkout por external_id; retorna `receipt_url` se pago, senão `checkout_url` |

### `api/webhooks.py` — `/api/v1/webhook` — tag `webhook` (público externo)

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/` | Webhook server-to-server da InfinitePay; `?external_id=` chega **cifrado** (Fernet); confirma pagamento out-of-band via `payment_check` antes de marcar pago |
| GET | `/` | Consulta status de um checkout por `?order_nsu=` (não altera nada) |

### `api/health.py` — tag `health` (desmilitarizado)

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/health` | Liveness probe |
| GET | `/ready` | Readiness probe |

## Dados

**Schema Postgres:** `infinitepay`. **PK = Integer autoincrement** (UUID na Fase 4). Colunas de data/hora são **`timestamptz`** (armazenam UTC). Nomes de constraint via `NAMING_CONVENTION` (§4).

**Shadow table cross-schema:** `auth.users(external_id UUID PK)` — declarada em `db.py`, **read-only**; o dono do schema `auth` é o app `auth` (§4). Em prod o schema `auth` já existe; na validação em DB novo cria-se um stub mínimo.

| Tabela | PK | Campos-chave | Unique/Index |
|--------|----|--------------|--------------|
| `checkouts` | `id` (Integer) | `external_id` UUID (FK→auth.users RESTRICT), `checkout_url`, `is_paid`, `receipt_url`, `installments`, `invoice_slug`, `capture_method`, `transaction_nsu`, `request_payload` JSON, `response_payload` JSON | UNIQUE+idx: external_id |
| `webhook_logs` | `id` (Integer) | `external_id` UUID (FK→auth.users SET NULL), `direction`, `kind`, `status_code`, `payload` JSON, `response` JSON | idx: external_id |
| `outbound_jobs` | `id` (Integer) | `url`, `payload` JSON, `external_id` (FK→auth.users SET NULL), `attempts`, `max_attempts`, `next_attempt_at`, `delivered_at`, `last_error` | idx: external_id, next_attempt_at |

**Migrações Alembic:** `0001` schema inicial, `0002` widen url columns para TEXT.

### Fluxo de pagamento

```
POST /checkout  → cria link na InfinitePay, persiste checkout (is_paid=false), enfileira evento "paid:false"
InfinitePay paga → POST /webhook/?external_id=<cifrado>
                 → payment_check (out-of-band) confirma → marca is_paid=true
                 → gera mensagem de recibo (app ai) + triagem de fraude (app ai)
                 → enfileira evento "paid:true" (atômico com o estado)
```

O worker async (`workers/outbound_queue.py::run_worker_loop`, no lifespan) roda a cada `WORKER_POLL_SECONDS`: entrega `outbound_jobs` vencidos com **claim atômico** (`UPDATE` antes do POST) para não duplicar entrega entre a API e um worker dedicado. Backoff exponencial `[60, 300, 1800, 7200, 43200, 86400]`s.

### Atomicidade e auditoria

- O **enqueue** (`outbound_queue.enqueue(db, ...)`) insere o job na sessão do caller e é commitado **junto** com o estado durável (checkout criado / marcado pago) pela rota — atômico.
- A **auditoria de webhooks** (`WebhookLog`) usa **sessão própria** com commit imediato (`_log_event`): o log de uma falha sobrevive ao rollback da request; best-effort por design (uma falha de auditoria nunca derruba o caminho do dinheiro).

## Integrações

| Serviço | Client | Notas |
|---------|--------|-------|
| **InfinitePay checkout API** (`api.checkout.infinitepay.io`) | `integrations/infinitepay_client.py` — **`httpx.AsyncClient`** | `POST /links` (criar checkout), `POST /payment_check` (confirmar pagamento out-of-band) |
| **App `ai` central** (`http://ai:8000`) | `integrations/ai.py` — **`httpx.AsyncClient`** | `POST /api/v1/text/chat` — mensagem de recibo (`services/receipt.py`) + triagem de fraude flash/pro (`services/monitor.py`). Sem tool calling. Falha → fallback (checkout nunca quebra). Habilitado por `AI_FEATURES_ENABLED` |

## Segurança do webhook

Sem HMAC, mas robusto: o `external_id` chega **cifrado (Fernet)** na query (`?external_id=`) e é decriptado em `api/webhooks.py` (token inválido → 422); a confirmação do pagamento é feita **out-of-band** via `payment_check` na InfinitePay antes de marcar pago. Pendência (§5, Fase 4): logar IP/origem.

## Tipos de endpoint (§5)

`checkout` e `health` são **desmilitarizados** (consumidos por outros apps da plataforma). `webhook.py` é **público externo** (recebe server-to-server da InfinitePay; autenticidade garantida pelo `external_id` cifrado + confirmação out-of-band).
