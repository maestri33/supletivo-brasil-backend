# CLAUDE.md — Memória e regras do serviço AI

> Serviço genérico de IA — endpoints HTTP para texto, imagem, TTS e JSON.
> Claude Code EXCLUSIVO deste serviço. Não conhece outros serviços do ecossistema.

## 1. Quem é você aqui

- Você é o Claude Code **exclusivo deste serviço**. Quando precisar falar com outro serviço, faz via HTTP.
- Seu papel: **manter este serviço pequeno, claro e funcional.** Nada de abstração prematura.
- Sua missão: implementar features, corrigir bugs, manter endpoints — sempre dentro da estrutura definida.

## 2. Regras de ouro (não negociáveis)

1. **Não alucine.** Se não tem certeza de assinatura, versão de pacote ou nome de env var, **consulte Context7 MCP** ou pergunte ao usuário.
2. **Faça apenas o que foi pedido.** Não acrescente features "que ficariam legais".
3. **Antes de codar, leia.** Leia `.claude/memory/` e os arquivos em `app/`.
4. **Stack fixa.** FastAPI + httpx + structlog + uv. Não troque.
5. **Porta 80.** Este serviço expõe SOMENTE a porta 80 (HTTP).
6. **Tudo gerado vai pra `data/public/media/<tipo>/<uuid>.<ext>`.** Imagem, áudio, etc.

## 3. Stack

| Camada | Tecnologia |
|---|---|
| Runtime | Python 3.12 + uv |
| Web | FastAPI + Uvicorn (porta 80) |
| Config | pydantic-settings + .env |
| HTTP | httpx (async, retry 3x) |
| Logs | structlog |
| AI | DeepSeek (texto), Gemini (imagem), ElevenLabs (voz) |

## 4. Estrutura do projeto

```
app/
├── main.py                    # FastAPI + StaticFiles mount (/media → data/public/media)
├── config.py                  # Settings (lê .env)
├── api/
│   ├── router.py              # Agrega routers — canonical /api/v1/* + legacy aliases
│   ├── health.py              # GET /, /health, /ready (sem envelope)
│   ├── text.py                # POST /text/ (DeepSeek, legado, sem envelope)
│   ├── image.py               # POST /image/, /image/vision (Gemini, legado)
│   ├── tts.py                 # POST /tts/ (ElevenLabs, legado)
│   ├── json_endpoint.py       # POST /json/ (DeepSeek JSON mode, legado)
│   ├── v1.py                  # NOVO — /text/chat, /text/summarize, /text/extract (com envelope)
│   └── schemas.py             # NOVO — APIResponse[T], UsageStats, modelos v1
├── integrations/
│   ├── http_client.py         # httpx shared + request_with_retry (3x, backoff 0.5s)
│   ├── deepseek.py            # DeepSeekClient — texto, JSON, chat, summarize, extract, stream
│   ├── elevenlabs.py          # ElevenLabsClient — TTS (SDK oficial, async generator)
│   └── gemini.py              # GeminiClient — imagem + visão (SDK google-genai)
└── utils/
    ├── logging.py             # structlog
    └── media.py               # save_media, media_url, MEDIA_ROOT
data/public/media/
├── image/                     # /media/image/uuid.jpg
├── audio/                     # /media/audio/uuid.mp3
└── text/
```

## 5. Rotas — canonical `/api/v1/*` + aliases legacy

Todas as rotas são definidas SEM prefixo nos routers individuais. O `router.py` inclui cada router DUAS vezes — uma com prefixo canônico `/api/v1/...` e outra com o alias legacy.

### Health (sem envelope)
| Método | Canonical | Alias |
|---|---|---|
| GET | /api/v1/ | / |
| GET | /api/v1/health | /health |
| GET | /api/v1/ready | /ready |

### Endpoints legados — contratos inalterados, sem envelope
| Método | Canonical | Alias | Body |
|---|---|---|---|
| POST | /api/v1/text/ | /text/ | `{prompt, instruction?, temperature?, max_tokens?}` → `{text}` |
| POST | /api/v1/json/ | /json/ | `{prompt, instruction?, schema_description?, temperature?, max_tokens?}` → `{data: dict}` |
| POST | /api/v1/image/ | /image/ | `{prompt, reference_url?, aspect_ratio?, image_size?, google_search?, num_images?}` → `{images: [...]}` |
| POST | /api/v1/image/vision | /image/vision | `{image_url}` → `{description}` |
| POST | /api/v1/tts/ | /tts/ | `{text, speed?, stability?, ...}` → `{url, filename}` |

### Endpoints v1 — envelope APIResponse com métricas
| Método | Canonical | Alias | Body |
|---|---|---|---|
| POST | /api/v1/text/chat | /v1/text/chat | `{messages, temperature?, max_tokens?, stream?}` → Chat multi-turn + SSE |
| POST | /api/v1/text/summarize | /v1/text/summarize | `{text, format, temperature?, max_tokens?}` → paragraph/bullets/headline |
| POST | /api/v1/text/extract | /v1/text/extract | `{text, json_schema, temperature?, max_tokens?}` → JSON Schema real |

**Envelope v1:** `{provider, model, latency_ms, usage: {prompt_tokens, completion_tokens, cache_hit_tokens, cache_miss_tokens}, finish_reason, data: T}`

## 6. Serviços externos

| Serviço | SDK/Modo | Auth | Timeout |
|---|---|---|---|
| DeepSeek | REST (httpx + retry 3x) | Bearer | 60s / 120s stream |
| ElevenLabs | SDK elevenlabs v2.46 | AsyncElevenLabs(api_key=) | interno |
| Gemini | SDK google-genai v2.0.1 | genai.Client(api_key=) | interno |

**Credenciais:** todas no `.env` (NUNCA hardcoded, NUNCA em arquivo versionado).
`.env` está no `.gitignore` — não sobe pro GitHub.

## 7. Comandos

```bash
uv sync
make dev    # uv run uvicorn app.main:app --host 0.0.0.0 --port 80 --reload
make run    # uv run uvicorn app.main:app --host 0.0.0.0 --port 80
```

## 8. O que NÃO fazer

- Não adicionar banco de dados (este serviço é stateless)
- Não trocar FastAPI por outro framework
- Não logar segredo (token, API key, senha)
- Não adicionar dependência sem `uv add`
- Não escrever em inglês — este projeto é PT-BR

---

**Antes de começar qualquer tarefa**, leia também:
- `.claude/memory/architecture.md` — decisões de design, stateless, roteamento
- `.claude/memory/conventions.md` — nomenclatura, padrão HTTP, logs, schemas
- `.claude/memory/integrations.md` — detalhes de cada serviço externo (DeepSeek, ElevenLabs, Gemini)
- `.claude/CLAUDE.md` — este arquivo (regras de ouro, endpoints, stack)
