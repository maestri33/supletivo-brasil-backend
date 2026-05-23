# Fase 3+ — Migração infinitepay (handoff p/ sessão dedicada)

> Análise por agente (read-only, 2026-05-23). Espelhar **`asaas`** (recém-migrado, mesmo padrão) + `address`/`lead`.
> **Estado real:** NADA de F3/F4 feito — só o achatamento (Fase 2). Código 100% antigo: psycopg2 sync, `httpx.Client` sync, logging cru, PK Integer, sem DI, IA embutida.

## Decisões travadas (2026-05-23, via /plan)
1. **IA: remover SÓ a direta** (DeepSeek via SDK `openai`). **MANTER** `receipt.py` (mensagem de recibo) + `monitor.py` (triagem de fraude) — já usam o app `ai` via `/text/chat`; mover o client p/ `integrations/ai.py` (§12) e torná-lo async.
2. **config → `.env`**: remover a tabela `config` + endpoints GET/PATCH `/config`; toda config via `.env` (igual otp).
3. **PK Integer→UUID → Fase 4** (igual asaas; mexe em dados). Reescrita em sessão dedicada.

## Estado atual (arquivo:linha)
- DB síncrono: `config.py:10` (`+psycopg2`), `db.py:3,10-11` (`create_engine`/`sessionmaker`/`Session`), `db.py:14-24` (`session_scope()`), `alembic/env.py:1,44` (sync). Sem `NAMING_CONVENTION`.
- `httpx.Client` sync: `integrations/infinitepay_client.py:13-15`, `workers/outbound_queue.py:24` (`httpx.post`), `ai/ai_service_client.py:77`.
- logging cru: `utils/logging.py`, `main.py:24,27`, `workers/outbound_queue.py:1,12`, `services/checkout_service.py:331-333`, `ai/monitor.py:12,17`. `structlog` declarado (`pyproject.toml:14`) mas não usado.
- PK Integer: `models/models.py:36,55,90,113` (+ migração `2026-05-15_initial_infinitepay_schema.py:33,49,75,95`).
- Sem DI: rotas chamam services sync direto (sem `Depends(get_session)`).
- `models/models.py` viola §3 ("nunca `models.py`").

## Ordem de execução (A→E)
### A. Remover IA direta (PRIMEIRO — encolhe o código antes do async)
- **Deletar:** `app/ai/client.py`, `app/ai/analytics.py`, `app/ai/reporter.py`, `app/ai/tools.py`, `app/api/ask.py`, `app/api/report.py`, `app/schemas/ask.py`, `app/schemas/report.py`, `app/ai/TODO`.
- `app/api/router.py:4,5,13,14` — remover includes `ask`/`report`.
- `pyproject.toml:16` — remover `openai`.
- `app/config.py:33-41` — remover `deepseek_*` (manter o `ai_base_url`/equivalente que `receipt`/`monitor` usam).
- `app/main.py:66-71,85` — remover tag/menção da IA analítica no OpenAPI.
- **MANTER:** `app/ai/receipt.py` + `app/ai/monitor.py` (usam app `ai`). Mover `app/ai/ai_service_client.py` → `app/integrations/ai.py` (§12) e convertê-lo p/ `httpx.AsyncClient`. Reorganizar `receipt`/`monitor` p/ fora de `app/ai/` (a pasta `app/ai/` deve sumir; usar `services/` ou `integrations/`).
- `services/checkout_service.py:320-343` — manter as chamadas a `receipt`/`monitor`, mas async; revisar campos `ai_message`/`ai_anomaly` no enqueue (`:358-359`).
- Resolve TODOs: `app/ai/TODO`, `ai/client.py:9`, `api/ask.py:20`, `api/report.py:7`.

### B. config → `.env`
- Remover tabela `config` (`models/models.py:34`) + `api/config.py` (GET/PATCH) + `services/config_service.py` (get/patch). Settings lê do `.env` (igual otp). Resolve TODOs `models.py:34`, `api/config.py:9`.

### C. F3 async (espelhar `asaas/app/db.py` + `asaas/alembic/env.py` + `address/app/db.py`)
- `pyproject.toml`: −`psycopg2-binary` +`asyncpg>=0.30`; dev +`pytest-asyncio` (`asyncio_mode="auto"`).
- `config.py:10`: `postgresql+asyncpg://...`.
- `db.py` (reescrever): `create_async_engine` + `async_sessionmaker(class_=AsyncSession, expire_on_commit=False)` + `get_session()` async + `close_db()` + **`NAMING_CONVENTION`** (copiar `address/app/db.py:18-26`) + `MetaData(naming_convention=..., schema=...)`. Mover shadow `auth_users` p/ `db.py` (como `address/app/db.py:34-39`).
- `alembic/env.py` (reescrever): async + `CREATE SCHEMA IF NOT EXISTS` (espelhar `asaas/alembic/env.py` — padrão JÁ validado contra Postgres real).
- Converter `session_scope()` → `async with get_session()` + `await` e `Depends(get_session)` nas rotas:
  - `services/checkout_service.py` (linhas 60,75,102,116,129,177,183,212,218,239,256,273,294).
  - `services/config_service.py` (o que sobrar após B).
  - `workers/outbound_queue.py` — `threading.Thread` (`:59`) → task asyncio; `httpx.post` (`:24`) → `AsyncClient`; queries (`:33,48,66,85,101,122`) async.
  - `api/webhooks.py:33-36` — remover `run_in_executor` (gambiarra); chamar service async direto.
  - `main.py:22-25` — `seed_from_env` no lifespan → `await`.
  - `lru_cache` em `config.py:44` permanece (padrão §3).

### D. httpx.Client → AsyncClient
- `integrations/infinitepay_client.py:13` (espelhar `asaas/app/integrations/asaas_client.py:35`), `workers/outbound_queue.py:24`, e o ex-`ai_service_client` (agora `integrations/ai.py`).

### E. logging → structlog
- `utils/logging.py` (espelhar `ai/app/utils/logging.py`); trocar call-sites de `logging` por `structlog.get_logger`.

## Diferido (Fase 4 / depois)
- **PK Integer→UUID** (`models/models.py:36,55,90,113` + migração destrutiva). Confirmar se há dados de prod (ambiente faz wipe pós-deploy → talvez simplifique).
- `models/models.py` → `models/<entidade>.py` (§3).
- Webhook não loga IP/origem (`webhooks.py:24` / `checkout_service.py:218`) — §5.
- Criar `CLAUDE.md`/`README.md` do serviço; reescrever `wiki/infinitepay.md` (stale; fonte de verdade §15).
- Reativar teste `test_health_and_lock_flow` (`pyproject.toml:36`).

## Webhook (nota — está OK)
Sem HMAC, mas: `external_id` chega cifrado (Fernet), decriptado em `api/webhooks.py:26` (token inválido → 422), + confirmação out-of-band via `payment_check` antes de marcar pago (`checkout_service.py:248-289`). Robusto. Só falta logar IP (§5, diferido).

## Fechamento (CONVENTION)
Reler `CONVENTION.md` + `wiki/infinitepay.md` antes → reescrever (ordem A→E) → **agente de conformidade §15** → `ruff` limpo + testes → atualizar `wiki/infinitepay.md`. 1 app = 1 PR. Branch: `chore/padronizacao`.
- DB de teste (tailnet) p/ validar migração: host `10.1.20.10:5432`, db/role `teste` (não-superuser). Senha em `/root/.teste-db.env` (CT 210, chmod 600). **Pedir autorização antes de qualquer `DROP SCHEMA`** (DB compartilhado).
