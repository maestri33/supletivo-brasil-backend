# asaas

## Função

Middleware FastAPI sobre a API Asaas v3 para **pagamentos PIX**: payouts (saída) via chave PIX cadastrada ou BR Code, e cobranças PIX (entrada) com QR Code. É o **único serviço autorizado** a integrar com a API Asaas (§12).

## Status

**Funcional e conforme à CONVENTION (stack canônica async).** Migrado de síncrono para async na Fase 3 (2026-05-23) e validado contra Postgres real.

- Stack: FastAPI + SQLAlchemy 2.0 **`AsyncSession`** + **asyncpg** + **`httpx.AsyncClient`** + **structlog** + pydantic-settings.
- Verificação: `ruff` limpo · `pytest` **183 passed** (`sqlite+aiosqlite`) · `alembic upgrade head` (`0001→0003`) OK contra Postgres real + smoke de escrita OK.
- `database_url` é **obrigatório** (sem default; vem do `.env`).

## Estrutura

`asaas/app/` — achatado conforme §3 (pacote `app`). Sem aninhamento.

```
asaas/
├── app/
│   ├── main.py            # FastAPI; lifespan (seed_from_env + worker async); structlog
│   ├── config.py          # Settings (pydantic-settings); database_url obrigatório
│   ├── db.py              # create_async_engine, Base, async_session_maker, get_session, close_db
│   ├── config_store.py    # acessores async da tabela `config` (get/set_/seed_from_env/all_status)
│   ├── exceptions.py      # DomainError + subclasses
│   ├── api/               # config, payment, pixkey, charge, webhook + router (agrega)
│   ├── models/__init__.py # SQLAlchemy (estilo Column legado; datetime = timestamptz)
│   ├── schemas/           # Pydantic v2
│   ├── services/          # lógica de negócio async (charge, payment, pixkey, customer,
│   │                      #   notifications, security_validator, config_*)
│   ├── integrations/asaas_client.py  # AsaasClient (httpx.AsyncClient)
│   └── utils/             # brcode.py, logging.py (structlog + shim log_event)
├── alembic/               # env.py async + versions 0001, 0002, 0003
└── tests/                 # async (pytest-asyncio, httpx.AsyncClient/ASGITransport)
```

> Pendências conhecidas: PK ainda Integer autoincrement (→ UUID na Fase 4); a migração inicial **não cria** o schema `asaas` (deploy precisa de `CREATE SCHEMA asaas`); TODO de produção (onboarding da security key no painel Asaas). `models/` e `schemas/` ainda monolíticos (`__init__.py`) → split na Fase 4.

## Endpoints

### `api/config.py` — `/api/v1/config` — tag `config` (desmilitarizados)

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/config/url` | Registra URL pública e emite nonce de verificação de domínio |
| GET | `/config/url/verify/{nonce}` | Consome nonce e persiste a URL pública (retorna HTML) |
| POST | `/config/internal` | Registra URL interna por categoria (charge/scheduling/payout/default) |
| POST | `/config/key` | Valida API key Asaas, gera security_token, retorna instruções HTML |
| POST | `/config/key/confirm` | Registra/recria o webhook oficial no Asaas (`/webhook/`) |
| GET | `/config/status` | Health: conta, saldo, webhook, configs mascaradas e erros |

### `api/payment.py` — `/api/v1/payment` — tag `payment` (desmilitarizados)

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/payment` | Pagamento PIX imediato por pixkey cadastrada |
| POST | `/payment/scheduled` | Agenda pagamento PIX por pixkey |
| POST | `/payment/qrcode` | Paga BR Code (copia-e-cola) imediato |
| POST | `/payment/qrcode/analyze` | Analisa BR Code sem pagar |
| POST | `/payment/qrcode/scheduled` | Agenda QR estático (dinâmico bloqueado) |
| GET | `/payment` | Lista pagamentos (filtros kind/status, paginado) |
| GET | `/payment/awaiting-balance` | Lista pagamentos em AWAITING_BALANCE |
| GET | `/payment/awaiting-balance/sum` | Soma em BRL dos AWAITING_BALANCE |
| POST | `/{payment_id}/cancel` | Cancela pagamento pendente/agendado (local ou Asaas) |
| DELETE | `/{payment_id}` | Remove pagamento em SCHEDULED ou AWAITING_BALANCE |
| GET | `/{payment_id}` | Consulta status/metadados de um pagamento |

### `api/pixkey.py` — `/api/v1/pixkey` — tag `pixkey` (desmilitarizados)

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/pixkey` | Valida chave no DICT, confere documento do titular e persiste |
| GET | `/pixkey` | Lista chaves PIX cadastradas (paginado) |
| GET | `/pixkey/check/{key}` | Consulta chave no DB ou no DICT sem persistir |
| GET | `/pixkey/{external_id}` | Busca chave pelo external_id |
| DELETE | `/pixkey/{external_id}` | Remove chave cadastrada |

### `api/charge.py` — `/api/v1/charge` — tag `charge` (desmilitarizados)

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/charge/pix` | Cria cobrança PIX; find-or-create de customer; retorna BR Code + QR PNG base64 |
| GET | `/charge` | Lista cobranças (filtros status/external_id, paginado) |
| GET | `/{payment_id}` | Consulta cobrança completa (BR Code + QR Code) |
| GET | `/{payment_id}/status` | Consulta só o status (polling leve) |
| POST | `/{payment_id}/qr` | Re-busca o QR Code no Asaas (refresh) |
| DELETE | `/{payment_id}` | Cancela cobrança (DELETE no Asaas → CANCELLED) |

### `api/webhook.py` — prefixo `/` — tag `asaas-inbound` (público, autenticado por token)

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/security-validator` | Mecanismo de Segurança Asaas; valida operação contra o DB local; recusa tipos não iniciados pelo app |
| POST | `/webhook/` | Recebe eventos Asaas; persiste raw; roteia TRANSFER_* → payment e PAYMENT_* → charge |

## Dados

**Schema Postgres:** `asaas`. **PK = Integer autoincrement** (UUID na Fase 4). Colunas de data/hora são **`timestamptz`** (armazenam UTC).

| Tabela | PK | Campos-chave | Unique/Index |
|--------|----|--------------|--------------|
| `config` | `key` (String) | `value` (Text), `updated_at` | PK=key |
| `url_verify_nonce` | `nonce` (String) | `target_url`, `purpose`, `created_at`, `consumed_at` | PK=nonce |
| `webhook_event` | `id` (Integer) | `event`, `payload` (Text), `received_at`, `forwarded_ok` | idx: received_at, event |
| `pix_key` | `id` (Integer) | `external_id`, `key`, `key_type`, `holder_document`, `holder_name`, `validated_at`, `raw_dict` | UNIQUE: external_id, key; idx: holder_document |
| `customer` | `id` (Integer) | `external_id`, `asaas_id`, `name`, `cpf_cnpj`, `email`, `mobile_phone` | UNIQUE: external_id, asaas_id; idx: cpf_cnpj |
| `payment` | `id` (Integer) | `payment_id`, `kind`, `pixkey_external_id`, `qrcode_payload`, `customer_external_id`, `pix_qr_image`, `due_date`, `amount`, `status`, `asaas_id`, `scheduled_for`, `last_error` | UNIQUE: payment_id; idx: kind, status, asaas_id, pixkey_external_id, customer_external_id |

Referências cross-table por **valor** (sem FK declarada): `payment.pixkey_external_id` → `pix_key.external_id`; `payment.customer_external_id` → `customer.external_id`. Sem shadow tables cross-schema — `external_id` é opaco (fornecido pelo cliente da API).

### Máquinas de estado

```
Payouts (kind=pixkey | qrcode):
  SCHEDULED → QUEUED → SUBMITTING → SUBMITTED → PAID
                   ↘ AWAITING_BALANCE ↗          ↘ FAILED | CANCELLED

Charges (kind=charge):
  PENDING → PAID | EXPIRED | CANCELLED | REFUNDED
```

O worker async (`services/payment.py::worker_loop`, no lifespan) roda a cada 30s: move SCHEDULED→QUEUED no horário, submete QUEUED/AWAITING_BALANCE ao Asaas e reconcilia SUBMITTED (cobre webhook perdido). Submissão usa claim atômico (`UPDATE ... SET status=SUBMITTING`) antes de chamar o Asaas.

## Integrações

| Serviço | Client | Notas |
|---------|--------|-------|
| **Asaas API v3** | `integrations/asaas_client.py` — **`httpx.AsyncClient`** | account, balance, webhooks, transfers (PIX out), pay QR Code, pix transactions, customers, payments (charges), pixQrCode |

**Notificações internas (out-webhooks desmilitarizados, async):** a cada transição de status, `POST` à URL configurada por categoria — `charge` → `internal_url_charge`; `pixkey`/`qrcode` SCHEDULED/QUEUED → `internal_url_scheduling`; demais → `internal_url_payout`; fallback `internal_url`. Falha de notificação é logada e **não** propaga (§12).

## Tipos de endpoint (§5)

Todos os `config`/`payment`/`pixkey`/`charge` são **desmilitarizados** (consumidos por outros apps da plataforma). `webhook.py` é **público externo** com verificação por `asaas-access-token` (Mecanismo de Segurança + webhook oficial do Asaas).
