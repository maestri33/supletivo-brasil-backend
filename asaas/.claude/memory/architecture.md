# Arquitetura — asaas

> Decisões com data e contexto. Fonte de verdade do comportamento: `wiki/asaas.md`.

## Papel do serviço

Middleware PIX sobre a API Asaas v3. Dois fluxos:
- **Payouts (saída):** `kind=pixkey` (chave PIX cadastrada) e `kind=qrcode`
  (BR Code copia-e-cola). Caminho do dinheiro — idempotente.
- **Charges (entrada):** `kind=charge` — cobranças PIX via Asaas `/payments`.

Único serviço autorizado a integrar com o Asaas (CONVENTION §12).

## Linha do tempo

### Fase 3 — stack async canônica
O asaas foi o app de **referência** recém-migrado (espelhado pelo infinitepay):
`create_async_engine` + `AsyncSession` + `asyncpg`, `httpx.AsyncClient`,
`structlog`, `NAMING_CONVENTION`, `alembic/env.py` async + `CREATE SCHEMA`.

### Idempotência de payout (BLOQUEIO §15 — commits 5db4eed, 2b18213)
- `submit_one` **commita o `asaas_id` antes** de o efeito externo (transferência)
  ser dado como concluído. Assim, um timeout/retry **não duplica** o payout:
  ao reprocessar, o `asaas_id` já persistido sinaliza que a transferência saiu.

### 2026-05-24 — Fase 4 (split models + PK UUID + webhook §5, commit 827b0dd)
- `models/` dividido em 1 arquivo por entidade: `config_kv`, `customer`,
  `payment`, `pix_key`, `url_verify_nonce`, `webhook_event`.
- **PK Integer → UUID** (`postgresql.UUID`, `str(uuid4())` na app) em
  webhook_event/pix_key/customer/payment; `config` e `url_verify_nonce` mantêm
  PK String (key/nonce). Datas viraram `timestamptz` com `utcnow()` aware.
- **Webhook loga origem (§5):** `webhook_event.source_ip` + `user_agent`
  (`utils/net.py`). Espelha o infinitepay.
- Migração `0001` squashada (fundiu as antigas `charge_support` e `timestamptz`).

### 2026-05-24 — fix: desempate por `id` em `order_by` (commit 93bde73)
- PK UUID não é sequencial; `order_by(created_at)` sozinho deixa empates sem
  ordem. Adicionado `id` como critério secundário em `list_all` (paginação) e no
  `tick()` do worker (FIFO do money-path). Ver `conventions.md`.

## Webhook do Asaas (entrada, público)

`POST /webhook/` (header `asaas-access-token`, validado por
`services/security_validator.py` — o "Mecanismo de Segurança" do Asaas):
1. Persiste o evento bruto em `webhook_event` (+ `source_ip`/`user_agent`).
2. Roteia: `TRANSFER_*` → bridge de payouts; `PAYMENT_*` → bridge de charges.
3. Atualiza o `Payment.status` e dispara notificação interna.

## Notificações internas (saída) — 3 destinos

Cada transição faz POST ao destino apropriado (`services/notifications.py`):
`internal_url_charge` (charges), `internal_url_scheduling` (outbound
criado/agendado), `internal_url_payout` (execução do outbound). Fallback:
`internal_url` (catch-all legacy).

## Config híbrida (.env → DB)

Config operacional (API key Asaas, URLs internas, wallet, token de segurança)
vive na tabela `asaas.config` via `config_store`. O `.env` faz **bootstrap**:
`_seed_from_env()` popula quando a tabela está vazia; depois o **DB vence**
(override por `POST /api/v1/config/*`). Padrão alinhado com o Mailcow.

## Dados

Schema `asaas`. PK UUID (exceto `config`/`url_verify_nonce`, PK String).
`timestamptz`. Sem FK cross-schema — `external_id` é fornecido pelo cliente.

| Tabela | PK | Observações |
|---|---|---|
| `config` | String (key) | config operacional (config_store) |
| `url_verify_nonce` | String (nonce) | verificação de URL externa (TTL) |
| `customer` | UUID | UNIQUE external_id, asaas_id |
| `payment` | UUID | payouts + charges; UNIQUE payment_id |
| `pix_key` | UUID | chaves PIX cadastradas |
| `webhook_event` | UUID | evento bruto + `source_ip`/`user_agent` |
