# Integrações — infinitepay

> Toda integração externa mora em `app/integrations/` (§12). Variáveis de
> configuração em `.env` (lidas via `config.py`). O fluxo de checkout **nunca**
> quebra por falha de integração — há fallback.

## InfinitePay — API de checkout (externa)
- **Client:** `app/integrations/infinitepay_client.py` (`httpx.AsyncClient`).
- **Base URL:** `INFINITEPAY_BASE_URL` (default `https://api.checkout.infinitepay.io`).
  Timeout: `HTTP_TIMEOUT` (s).
- **Endpoints usados:**
  - `POST /links` — cria o link de checkout (`create_checkout_link`).
  - `POST /payment_check` — confirma o pagamento **out-of-band** antes de marcar
    pago (`payment_check`). Não confiamos só no payload do webhook.
- **Webhook de volta (público):** chega em `POST /api/v1/webhook` com
  `?external_id=` **cifrado (Fernet)**; decriptado em `api/webhooks.py` (token
  inválido → 422). Sem HMAC; robustez vem do `external_id` cifrado + confirmação
  out-of-band. Origem (`source_ip`/`user_agent`) gravada em `webhook_logs`.
- Este é o **único** serviço autorizado a falar com a InfinitePay (§12).

## App `ai` central (interno, plataforma)
- **Client:** `app/integrations/ai.py` (`httpx.AsyncClient`).
- **Base URL:** `AI_BASE_URL` (default `http://ai:8000`).
- **Endpoint:** `POST /api/v1/text/chat` (sem tool calling).
- **Usado por:**
  - `app/services/receipt.py` — mensagem de recibo do pagamento.
  - `app/services/monitor.py` — triagem de fraude (flash / pro).
- **Liga/desliga:** `AI_FEATURES_ENABLED` (default `false`). Modelos:
  `AI_MODEL` (`deepseek-v4-flash`) e `AI_PRO_MODEL` (`deepseek-v4-pro`).
- **Fallback:** se off ou falhar, o checkout segue normalmente (a IA é
  best-effort). É **proibido** chamar a DeepSeek/SDK `openai` direto — se
  precisar de IA, replique a lógica do app `ai` (§12).

## Eventos internos (saída — fila com retry)
- `app/workers/outbound_queue.py` entrega os `outbound_jobs` (POST `httpx`) para
  URLs internas (área desmilitarizada). Claim atômico antes do POST; backoff
  exponencial `[60, 300, 1800, 7200, 43200, 86400]` s; `max_attempts`.
- A URL de destino do backend vem de `INFINITEPAY_BACKEND_WEBHOOK`.

## Banco (cross-schema)
- Schema próprio `infinitepay`. Relacionamento com `auth` via **shadow table
  read-only** (`auth.users`, declarada em `app/db.py`) — nunca importar model de
  outro serviço.
