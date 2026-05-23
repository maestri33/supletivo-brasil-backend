# Arquitetura — Serviço AI

## Decisões

### Stateless
O serviço não tem banco de dados. Cada request é independente.
Arquivos gerados (imagem, áudio) são persistidos em disco apenas para serving via StaticFiles.

### Rotas canônicas + aliases legacy
Todas as rotas são definidas SEM prefixo nos routers individuais (`app/api/*.py`).
O `router.py` centraliza o roteamento: inclui cada router DUAS vezes — uma com o prefixo
canônico `/api/v1/...` e outra com o alias legacy. Mesmo código, sem duplicação.

Exemplo:
- `POST /api/v1/text/` (canônico) e `POST /text/` (legacy) → mesma função `generate_text`
- `POST /api/v1/text/chat` (canônico) e `POST /v1/text/chat` (legacy) → mesma função `chat`

### Dois contratos coexistindo
- **v0 (legado):** contratos originais, sem envelope. Mantidos por backward compat.
  Endpoints: `/text/`, `/json/`, `/image/`, `/image/vision`, `/tts/`
- **v1 (novo):** envelope `APIResponse[T]` com métricas (provider, model, latency_ms, usage, finish_reason).
  Endpoints: `/text/chat`, `/text/summarize`, `/text/extract`

### Especialização vs genericidade
- `/text/` mantido genérico (backward compat).
- Novos endpoints são especializados: `/text/chat` (multi-turn + stream), `/text/summarize` (formatos), `/text/extract` (JSON Schema real).
- `/json/` mantido como está mas `/text/extract` oferece garantia estrutural via JSON Schema (não free-text `schema_description`).

### Envelope v1
```json
{
  "provider": "deepseek",
  "model": "deepseek-v4-pro",
  "latency_ms": 412.3,
  "usage": {"prompt_tokens": 100, "completion_tokens": 50, "cache_hit_tokens": 200, "cache_miss_tokens": 0},
  "finish_reason": "stop",
  "data": { ... }
}
```
Health endpoints (`/`, `/health`, `/ready`) NÃO usam envelope.

### Streaming SSE
`/text/chat` com `stream: true` retorna `text/event-stream`:
```
data: {"type":"meta","provider":"deepseek","model":"deepseek-v4-pro"}
data: {"type":"delta","content":"Olá"}
data: {"type":"finish","finish_reason":"stop","usage":{...},"ttft_ms":412.3}
data: [DONE]
```
Implementado com `StreamingResponse` + `sse_generator()` async. Sem dependências extras.

### Media path
`data/public/media/<tipo>/<uuid>.<ext>` — determinístico e servido via `/media/...`.
Limpeza de arquivos antigos é manual por enquanto (`make clean`).

### Retry
3 tentativas com backoff exponencial (0.5s base) para erros 429/502/503/504.
Timeout: 60s texto/JSON, 120s imagem/TTS, 120s stream (30s entre chunks).

### Sem request_id
Serviço interno da rede — request_id adicionaria complexidade desnecessária.
Rastreabilidade fica por conta de logs estruturados (structlog) e métricas no envelope.
