# asaas

## Função

Middleware FastAPI sobre a API Asaas v3 responsável por **pagamentos PIX** na plataforma: payouts (saída) via chave PIX cadastrada ou BR Code, e cobranças PIX (entrada) com geração de QR Code. É o único serviço autorizado a integrar com a API Asaas.

## Status

**Parcial — funcional para produção nos fluxos principais, mas com desvios de stack e um TODO de produção em aberto.**

- Endpoints implementados: todos os fluxos de config, pixkey, payment (outbound) e charge (inbound) estão presentes e cobertos.
- Migrações Alembic: 2 revisões (`0001` schema inicial, `0002` charge support) — cobertura completa dos modelos atuais.
- Testes: suite abrangente (12 arquivos de teste cobrindo routes, services, webhook, brcode, security_validator, settings e notificações).
- Desvio crítico: **ORM síncrono** (`psycopg2` + `sessionmaker` síncrono) em vez do stack canônico async (`asyncpg` + `AsyncSession`). Documentado no README como exceção intencional.

## Estrutura

**Aninhada:** `asaas/asaas/app/` — viola a convenção `<servico>/app/`. O pacote real está em `/home/maestri33/backend/asaas/asaas/app/`.

```
asaas/                    ← raiz do serviço no monorepo
└── asaas/                ← aninhamento extra (não-convencional)
    ├── app/
    │   ├── main.py
    │   ├── config.py
    │   ├── config_store.py
    │   ├── db.py
    │   ├── exceptions.py
    │   ├── api/          (config.py, payment.py, pixkey.py, charge.py, webhook.py, router.py)
    │   ├── models/       (__init__.py — todos os modelos num único arquivo)
    │   ├── schemas/      (__init__.py — todos os schemas num único arquivo)
    │   ├── services/     (charge, config_*, customer, notifications, payment, pixkey, security_validator)
    │   ├── integrations/ (asaas_client.py)
    │   └── utils/        (brcode.py, logging.py)
    ├── alembic/
    ├── tests/
    └── pyproject.toml
```

Desvio adicional: `models/` e `schemas/` usam `__init__.py` monolítico em vez de 1 arquivo por entidade.

## Endpoints

### `api/config.py` — prefixo `/api/v1/config` — tag: `config` (desmilitarizados)

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/config/url` | Registra URL pública e emite nonce de verificação de domínio |
| GET | `/config/url/verify/{nonce}` | Consome nonce e persiste a URL pública (retorna HTML) |
| POST | `/config/internal` | Registra URL interna por categoria (charge/scheduling/payout/default) com envio de onboarding |
| POST | `/config/key` | Valida API key Asaas, gera security_token e retorna instruções HTML para o painel |
| POST | `/config/key/confirm` | Registra/recria webhook oficial no Asaas apontando para `/webhook/` |
| GET | `/config/status` | Health operacional: conta, saldo, webhook, configs mascaradas e erros |

### `api/payment.py` — prefixo `/api/v1/payment` — tag: `payment` (desmilitarizados)

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/payment` | Cria pagamento PIX imediato por chave pixkey cadastrada |
| POST | `/payment/scheduled` | Agenda pagamento PIX por chave pixkey para data/hora informada |
| POST | `/payment/qrcode` | Paga BR Code (copia-e-cola) de forma imediata |
| POST | `/payment/qrcode/analyze` | Analisa BR Code sem pagar (tipo, valor, avisos) |
| POST | `/payment/qrcode/scheduled` | Agenda pagamento de QR Code estático (dinâmico bloqueado) |
| GET | `/payment` | Lista pagamentos com filtros por kind e status (paginado) |
| GET | `/payment/awaiting-balance` | Lista pagamentos em AWAITING_BALANCE |
| GET | `/payment/awaiting-balance/sum` | Soma total em BRL dos pagamentos AWAITING_BALANCE |
| POST | `/{payment_id}/cancel` | Cancela pagamento pendente/agendado (localmente ou via Asaas) |
| DELETE | `/{payment_id}` | Remove pagamento em SCHEDULED ou AWAITING_BALANCE |
| GET | `/{payment_id}` | Consulta status e metadados de um pagamento |

### `api/pixkey.py` — prefixo `/api/v1/pixkey` — tag: `pixkey` (desmilitarizados)

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/pixkey` | Valida chave no DICT Asaas, compara documento do titular e persiste |
| GET | `/pixkey` | Lista chaves PIX cadastradas (paginado) |
| GET | `/pixkey/check/{key}` | Consulta chave no DB ou no DICT sem persistir |
| GET | `/pixkey/{external_id}` | Busca chave pelo external_id |
| DELETE | `/pixkey/{external_id}` | Remove chave cadastrada |

### `api/charge.py` — prefixo `/api/v1/charge` — tag: `charge` (desmilitarizados)

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/charge/pix` | Cria cobrança PIX; find-or-create de customer no Asaas; retorna BR Code + QR PNG base64 |
| GET | `/charge` | Lista cobranças com filtros por status e external_id (paginado) |
| GET | `/{payment_id}` | Consulta cobrança completa (com BR Code e QR Code) |
| GET | `/{payment_id}/status` | Consulta apenas status (versão leve para polling) |
| POST | `/{payment_id}/qr` | Re-busca QR Code no Asaas (refresh) |
| DELETE | `/{payment_id}` | Cancela cobrança (DELETE no Asaas, transição para CANCELLED) |

### `api/webhook.py` — prefixo `/` — tag: `asaas-inbound` (públicos com autenticação por token)

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/security-validator` | Autoriza operações Asaas (Mecanismo de Segurança); valida contra DB local; recusa tipos não iniciados pelo app |
| POST | `/webhook/` | Recebe eventos Asaas; persiste raw; roteia TRANSFER_* para payment bridge e PAYMENT_* para charge bridge |

## Dados

**Schema Postgres:** `asaas` (banco central `v7m`)

### Tabelas

| Tabela | PK | Campos-chave | Unique/Index |
|--------|----|--------------|--------------|
| `config` | `key` (String) | `value` (Text), `updated_at` | PK=key |
| `url_verify_nonce` | `nonce` (String) | `target_url`, `purpose`, `created_at`, `consumed_at` | PK=nonce |
| `webhook_event` | `id` (Integer) | `event`, `payload` (Text), `received_at`, `forwarded_ok` | idx: received_at, event |
| `pix_key` | `id` (Integer) | `external_id`, `key`, `key_type`, `holder_document`, `holder_name`, `bank_name`, `validated_at`, `raw_dict` | UNIQUE: external_id, key; idx: holder_document |
| `customer` | `id` (Integer) | `external_id`, `asaas_id`, `name`, `cpf_cnpj`, `email`, `mobile_phone` | UNIQUE: external_id, asaas_id; idx: cpf_cnpj |
| `payment` | `id` (Integer) | `payment_id`, `kind`, `pixkey_external_id`, `qrcode_payload`, `customer_external_id`, `pix_qr_image`, `due_date`, `amount`, `status`, `asaas_id`, `scheduled_for`, `last_error` | UNIQUE: payment_id; idx: kind, status, asaas_id, pixkey_external_id, customer_external_id |

### Referências cross-table

- `payment.pixkey_external_id` → `pix_key.external_id` (sem FK declarada; ref por valor)
- `payment.customer_external_id` → `customer.external_id` (sem FK declarada; ref por valor)
- Sem shadow tables cross-schema — `external_id` é opaco (fornecido pelo cliente da API, não vinculado ao schema `auth`).

## Integrações

### Externas

| Serviço | Client | Operações |
|---------|--------|-----------|
| **Asaas API v3** | `integrations/asaas_client.py` (`httpx.Client` síncrono) | `GET /myAccount`, `GET /finance/balance`, CRUD webhooks, CRUD transfers (PIX out), pay QR Code, CRUD customers, CRUD payments (inbound), `GET pixQrCode` |

### Internas (out-webhooks desmilitarizados)

O serviço **não chama** outros microsserviços por iniciativa própria além das notificações de status. A cada transição de estado, faz `POST` (httpx síncrono, timeout 5s) à URL configurada:

| Evento | URL configurável via | Campo config |
|--------|---------------------|--------------|
| `kind=charge` (qualquer status) | `POST /config/internal?target=charge` | `internal_url_charge` |
| `kind=pixkey|qrcode`, status SCHEDULED/QUEUED | `target=scheduling` | `internal_url_scheduling` |
| `kind=pixkey|qrcode`, demais status | `target=payout` | `internal_url_payout` |
| fallback | `target=default` | `internal_url` |

Falhas de notificação são logadas e não propagadas (fluxo não quebra).

## Pendências

### Arquivo TODO (`/home/maestri33/backend/asaas/TODO`)

> Garanta que ao ser colocado em produção seja gerado o key que tem que ser anexado lá no dashboard do asaas, e que realmente aconteça a comunicação de criptografia para autorizar pagamentos...

Interpretação: antes do go-live, executar o fluxo completo de onboarding (`POST /config/key` + configurar Mecanismo de Segurança no painel Asaas + `POST /config/key/confirm`) e validar que o security-validator está aprovando transfers reais.

### Desvios da CONVENTION.md

| Item | Esperado | Atual | Severidade |
|------|----------|-------|------------|
| **Aninhamento** | `asaas/app/` | `asaas/asaas/app/` | Alta — viola §3 |
| **Driver PG / ORM** | `asyncpg` + `AsyncSession` (async) | `psycopg2-binary` + `sessionmaker` síncrono | Alta — viola §4; documentado no README como exceção intencional |
| **`asyncio_mode = "auto"`** | pytest-asyncio mode auto | ausente no pyproject.toml | Média |
| **structlog** | obrigatório | ausente; usa `logging` cru + wrapper `log_event` | Média — viola §2 |
| **`models/` e `schemas/` como pastas** | 1 arquivo por entidade | monolítico em `__init__.py` | Baixa |
| **`lifespan` correto** | sim | sim (ok) | — |
| **Pydantic v2** | sim | sim (ok) | — |
| **`requests` proibido** | não usar | não usa (httpx em toda chamada) | ok |
| **`os.environ` espalhado** | não usar | não usa (pydantic-settings) | ok |
| **NAMING_CONVENTION para constraints** | padrão de `address/app/db.py` | ausente na declaração de models | Baixa |
| **`hatchling` como build backend** | obrigatório | ausente no pyproject.toml (sem `[build-system]`) | Baixa |
| **worker_loop com asyncio.create_task em lifespan síncrono** | lifespan async | `asyncio.create_task` chamado dentro de `lifespan` async mas SessionLocal usado de forma síncrona no mesmo lifespan | Atenção |
