# lead

## Função

Gerencia o ciclo de vida do role **lead** no pipeline de captação: desde o cadastro público (register/OTP) até a confirmação de pagamento (COMPLETED), transitando o lead pelos status `captured → waiting → checkout → completed`. É o único serviço responsável pelo schema `lead` e pela orquestração de notificações nesse funil.

---

## Status

**Pronto / produção.**

- Todos os endpoints do funil estão implementados (public, authenticated, demilitarized e webhooks).
- 2 migrações Alembic cobrindo o schema completo (0001 schema inicial; 0002 multi-provider PIX).
- Integração com InfinitePay (cartão) e Asaas (PIX) funcional, incluindo webhooks de retorno.
- **Ausência total de testes** (`tests/` não existe) — único bloqueio para classificar como "apto a produção com cobertura".

---

## Estrutura

Localização correta: `lead/app/` — **sem aninhamento** (`lead/lead/app` não existe). Conforme CONVENTION §3.

```
lead/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── db.py
│   ├── dependencies.py
│   ├── api/
│   │   ├── public/          (auth.py, health.py)
│   │   ├── authenticated/   (captured.py, waiting.py, checkout.py, completed.py)
│   │   └── demilitarized/   (leads.py, checkouts.py, webhooks.py)
│   ├── models/              (lead.py, checkout.py, message.py, _mixins.py)
│   ├── schemas/             (base.py)
│   ├── integrations/        (auth.py, jwt.py, notify.py, infinitepay.py, asaas.py, profiles.py)
│   ├── notify/
│   │   ├── handlers.py
│   │   └── messages/        (12 templates .md)
│   └── tools/               (create_checkout.py, messaging.py, qrcode.py, webhooks.py)
├── alembic/versions/
└── pyproject.toml
```

> `schemas/` tem apenas `base.py` — schemas específicos de request/response estão embutidos nos próprios arquivos de `api/`. Desvio menor de convenção (schemas deveriam ficar em `schemas/`).

---

## Endpoints

### `api/public/auth.py` — público (sem autenticação)

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/api/v1/public/check` | Verifica existência do lead (CPF/telefone/UUID) e dispara OTP via auth |
| POST | `/api/v1/public/register` | Cadastra novo lead, cria registro em `leads` com status `captured`, dispara notificações BG |
| POST | `/api/v1/public/login` | Valida OTP e retorna tokens JWT + status atual do lead |
| POST | `/api/v1/public/refresh` | Renova access/refresh tokens via JWT service |

### `api/authenticated/*.py` — autenticado (JWT + status verificado via `require_<status>()`)

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/v1/authenticated/captured` | Retorna nome/telefone/email do lead capturado (consulta profiles + notify) |
| POST | `/api/v1/authenticated/captured` | Completa cadastro, define email, seleciona método de pagamento; avança para `waiting` (cartão) ou `checkout` (PIX síncrono) |
| GET | `/api/v1/authenticated/waiting` | Polling de status enquanto checkout de cartão é gerado em background |
| GET | `/api/v1/authenticated/checkout` | Retorna dados do checkout (URL cartão ou QR PIX) e flag `is_paid` |
| GET | `/api/v1/authenticated/completed` | Retorna status final e `receipt_url` após pagamento confirmado |

### `api/demilitarized/leads.py` — desmilitarizado (internal)

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/v1/demilitarized/leads` | Lista todos os leads |
| GET | `/api/v1/demilitarized/leads/{external_id}` | Busca lead por external_id |
| PATCH | `/api/v1/demilitarized/leads/{external_id}` | Atualiza status ou promoter do lead |
| DELETE | `/api/v1/demilitarized/leads/{external_id}` | Remove lead |

### `api/demilitarized/checkouts.py` — desmilitarizado (internal)

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/v1/demilitarized/checkouts` | Lista todos os checkouts |
| GET | `/api/v1/demilitarized/checkouts/{external_id}` | Busca checkout por external_id |
| PATCH | `/api/v1/demilitarized/checkouts/{external_id}` | Atualiza campos do checkout |
| DELETE | `/api/v1/demilitarized/checkouts/{external_id}` | Remove checkout |

### `api/demilitarized/webhooks.py` — desmilitarizado (webhooks internos originados de apps bridge)

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/api/v1/webhook/notify/{message_id}` | Callback do notify: atualiza status de mensagem enviada |
| POST | `/api/v1/webhook/infinitepay` | Callback do app infinitepay-bridge: confirma pagamento cartão, transiciona lead → `completed` |
| POST | `/api/v1/webhook/asaas-charge` | Callback do app v7m-asaas: confirma PIX pago, transiciona lead → `completed` |

### `main.py` — sem prefixo (infra)

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/health` | Liveness check |
| GET | `/ready` | Readiness check |
| GET | `/status` | Info de versão e uptime |
| — | `/api/v1/public/media/*` | Static files: QR Codes PNG e imagens (volume `lead_media`) |

---

## Dados

**Schema Postgres:** `lead`

### Tabela `lead.leads`

| Coluna | Tipo | Restrições |
|--------|------|-----------|
| `id` | BigInteger | PK autoincrement |
| `external_id` | UUID | UNIQUE, NOT NULL, FK → `auth.users.external_id` (RESTRICT/CASCADE) |
| `status` | ENUM `lead_status` | NOT NULL, default `captured`; valores: `captured`, `waiting`, `checkout`, `completed` |
| `promoter_external_id` | UUID | nullable, index |
| `created_at` / `updated_at` | timestamptz | NOT NULL, server default `now()` |

### Tabela `lead.checkouts`

| Coluna | Tipo | Notas |
|--------|------|-------|
| `id` | BigInteger | PK autoincrement |
| `external_id` | UUID | UNIQUE, FK → `auth.users.external_id` |
| `payment_method` | varchar(20) | `credit_card` \| `pix` |
| `provider` | varchar(20) | `infinitepay` \| `asaas` |
| `provider_payment_id` | varchar(255) | index; ID retornado pelo provider |
| `checkout_url` / `receipt_url` | varchar(1024) | InfinitePay |
| `invoice_slug` / `transaction_nsu` | varchar(255) | InfinitePay, indexados |
| `capture_method` / `installments` | varchar / smallint | InfinitePay |
| `qrcode_payload` / `qrcode_image` | text | BR Code e PNG base64 (PIX/Asaas) |
| `due_date` | date | Vencimento PIX |
| `is_paid` | boolean | NOT NULL, default false, index |
| `created_at` / `updated_at` | timestamptz | server default `now()` |

### Tabela `lead.messages`

| Coluna | Tipo | Notas |
|--------|------|-------|
| `id` | BigInteger | PK |
| `message_id` | integer | nullable, index; ID do notify |
| `external_id` | UUID | FK → `auth.users.external_id`, index |
| `direction` | varchar(10) | `out` (envio) \| `in` (webhook) |
| `channel` | varchar(20) | `whatsapp` \| `email` \| `tts` |
| `status` | varchar(30) | `sent` \| `delivered` \| `read` \| `failed` \| `skipped` |
| `event` | varchar(50) | nome do evento notify |
| `meta` | JSONB | dados extras do webhook |
| `created_at` / `updated_at` | timestamptz | |

### Shadow table (cross-schema)

```python
# auth.users — stub read-only para resolver FK cross-schema no SQLAlchemy
auth_users = Table("users", metadata,
    Column("external_id", PG_UUID(as_uuid=True), primary_key=True),
    schema="auth")
```

---

## Integrações

### Internas (httpx para microsserviços da plataforma)

| Client | Base URL (config) | Endpoints usados |
|--------|------------------|-----------------|
| `AuthClient` | `AUTH_BASE_URL` | `POST /check`, `POST /register`, `POST /login` |
| `JwtClient` | `JWT_BASE_URL` | `POST /refresh` |
| `NotifyClient` | `NOTIFY_BASE_URL` | `GET /contacts/{id}`, `PATCH /contacts/{id}/email`, `POST /messages/send` |
| `ProfilesClient` | `PROFILES_BASE_URL` | `GET /profiles/first-name/{id}`, `PATCH /profiles/{id}` |
| `InfinitePayClient` | `INFINITEPAY_BASE_URL` | `POST /api/v1/checkout/`, `GET /api/v1/checkout/{id}/` |
| `AsaasClient` | `ASAAS_BASE_URL` | `POST /api/v1/charge/pix`, `GET /api/v1/charge/{payment_id}` |

> `ROLES_BASE_URL` está em `settings` mas não há client implementado para ele.

### Externas

Nenhuma. Todas as integrações com Asaas (PIX) e InfinitePay (cartão) passam por microsserviços bridge internos (`v7m-asaas`, `v7m-infinitepay`), conforme CONVENTION §12.

### Webhooks de saída (outgoing)

- `WEBHOOK_ENROLLMENT_URL` — notifica matrícula confirmada (via `tools/webhooks.py`)
- `WEBHOOK_PROMOTERS_URL` — notifica promoter de lead convertido
- `NOTIFY_CALLBACK_URL` — URL que o notify usa para reportar status de entrega de mensagem

---

## Pendências

### Arquivo TODO (`/home/maestri33/backend/wiki/TODO`)

> *(O TODO do wiki geral foi encontrado; não existe arquivo `TODO` dedicado dentro de `lead/`.)*

### TODOs no código

1. **`app/api/demilitarized/webhooks.py` linha ~247** — webhook PIX do Asaas não tem o valor real da cobrança; usa `PIX_DEFAULT_AMOUNT` como fallback no recibo. Comentário: *"ideal seria buscar o valor real do checkout (atual ou via API do asaas service), mas o asaas webhook payload nao traz o amount"*.

2. **`app/integrations/__init__.py`** — `request_with_retry` usa `time.sleep()` (síncrono) no backoff entre tentativas, bloqueando o event loop. Deveria usar `await asyncio.sleep()`.

3. **`app/notify/handlers.py`** — `notify_lead_captured` faz chamadas HTTP diretas (`httpx.AsyncClient`) sem usar `NotifyClient`/`ProfilesClient` — inconsistência com o padrão do resto do serviço.

### Desvios da CONVENTION

| Item | Desvio | Severidade |
|------|--------|-----------|
| **Testes ausentes** | Diretório `tests/` não existe | ❌ Bloqueia |
| `time.sleep()` em `integrations/__init__.py` | Bloqueia event loop no retry | ⚠️ Ajustar |
| Schemas inline nos arquivos `api/` | Schemas de request/response deveriam estar em `schemas/` | ⚠️ Menor |
| `pyjwt[crypto]` em `pyproject.toml` | Lib fora da stack canônica sem justificativa registrada no `CLAUDE.md` | ⚠️ Verificar |
| `ROLES_BASE_URL` em settings sem client implementado | Dead config | ⚠️ Limpar ou implementar |
| `fastapi-structured-logging` fora da stack canônica | Usado no lugar de `structlog` puro — funcional mas não listado na CONVENTION §2 | ⚠️ Registrar no `CLAUDE.md` |
| `CLAUDE.md` ausente | Serviço não possui `CLAUDE.md` com particularidades/justificativas | ⚠️ Criar |
