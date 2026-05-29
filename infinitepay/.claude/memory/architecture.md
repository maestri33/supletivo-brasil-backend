# Arquitetura — infinitepay

> Decisões arquiteturais com data e contexto. Fonte de verdade do
> comportamento: `wiki/infinitepay.md`.

## Papel do serviço

Middleware de checkout da InfinitePay. Três responsabilidades:
1. Criar links de pagamento (`POST /api/v1/checkout`).
2. Receber o webhook de confirmação server-to-server (`POST /api/v1/webhook`).
3. Reenviar eventos internos via fila de saída (`outbound_jobs`) com retry.

Único serviço autorizado a integrar com a InfinitePay (CONVENTION §12).

## Linha do tempo

### 2026-05-24 — Fase 3 (sync → async + .env + remoção da IA direta)
- Migrado de `psycopg2`/`httpx.Client`/`logging` cru para a stack canônica:
  `create_async_engine` + `async_sessionmaker(AsyncSession)` + `asyncpg`,
  `httpx.AsyncClient`, `structlog`. `NAMING_CONVENTION` adicionada no `db.py`.
- **Config → `.env`:** tabela `config` e rotas GET/PATCH `/config` removidas;
  tudo via `config.py::get_settings()` (espelha o app `otp`).
- **IA direta removida:** o SDK `openai`/DeepSeek saiu. `receipt.py` (mensagem
  de recibo) e `monitor.py` (triagem de fraude) **permanecem**, mas chamam o
  app `ai` central via `integrations/ai.py` (§12).
- `alembic/env.py` async + `CREATE SCHEMA IF NOT EXISTS` (a migração cria o
  schema `infinitepay` sozinha; padrão validado contra Postgres real).

### 2026-05-24 — Fase 4 (split models + PK UUID + webhook §5)
- `models/models.py` (violava §3) dividido em 1 arquivo por entidade:
  `checkout.py`, `webhook_log.py`, `outbound_job.py`. `__init__.py` reexporta
  para popular `Base.metadata` (Alembic).
- **PK Integer → UUID:** `postgresql.UUID`, gerada na app (`default=lambda:
  str(uuid4())`, `as_uuid=False`). Migração destrutiva (ambiente faz wipe).
  Datas viraram `timestamptz` com `utcnow()` (aware, em `db.py`).
- **Webhook público loga origem (§5):** `webhook_logs.source_ip` +
  `user_agent`, resolvidos em `utils/net.py` (X-Forwarded-For → X-Real-IP →
  peer). Espelhado no asaas (`webhook_event`).
- Migração `0001` foi squashada (fundiu a antiga `widen_url`: colunas de URL
  nascem `TEXT`).

### 2026-05-24 — fix: desempate por `id` em `order_by` (commit 93bde73)
- Com PK UUID (não-sequencial), `order_by(created_at)` sozinho deixa empates
  sem ordem definida. Adicionado `id` como critério secundário em todo
  `order_by` (paginação estável + FIFO determinístico). Ver `conventions.md`.

## Atomicidade e auditoria (invariantes — não quebrar)

- **Enqueue atômico:** `workers/outbound_queue.enqueue(db, ...)` insere o job
  na **sessão do caller**; o commit acontece **junto** com o estado durável
  (checkout criado / marcado pago) pela rota. Nunca commitar o job separado do
  estado de negócio.
- **Auditoria best-effort:** `WebhookLog` é gravado em **sessão própria** com
  commit imediato (`_log_event(durable=True)`), para o log de uma falha
  sobreviver ao rollback da request. Uma falha de auditoria **nunca** derruba o
  caminho do dinheiro.
- **Worker com claim atômico:** o `run_worker_loop` (lifespan, a cada
  `WORKER_POLL_SECONDS`) faz `UPDATE` de claim **antes** do POST, para não
  duplicar entrega entre a API e um worker dedicado. Backoff exponencial
  `[60, 300, 1800, 7200, 43200, 86400]` s.

## Fluxo de pagamento

```
POST /checkout  → cria link na InfinitePay, persiste checkout (is_paid=false),
                  enfileira evento "paid:false"
InfinitePay paga → POST /webhook?external_id=<cifrado Fernet>
                 → payment_check (out-of-band) confirma → is_paid=true
                 → recibo (app ai) + triagem de fraude (app ai)
                 → enfileira evento "paid:true" (atômico com o estado)
```

## Dados

Schema `infinitepay`. PK = UUID. Datas = `timestamptz` (UTC). Constraints via
`NAMING_CONVENTION`. Shadow `auth.users(external_id UUID PK)` read-only em
`db.py` (dono do schema `auth` é o app `auth`).

| Tabela | PK | Observações |
|---|---|---|
| `checkouts` | UUID | FK `external_id` → auth.users (RESTRICT), UNIQUE |
| `webhook_logs` | UUID | FK `external_id` → auth.users (SET NULL); `source_ip`, `user_agent` |
| `outbound_jobs` | UUID | fila com `attempts`/`max_attempts`/`next_attempt_at` |
