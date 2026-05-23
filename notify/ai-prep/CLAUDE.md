# CLAUDE.md — Memória do serviço AI

> Serviço genérico de IA — texto, imagem, TTS, JSON estruturado.
> Stack: Python 3.12 + FastAPI + uv + httpx + structlog.

## 1. Regras de ouro

1. **Não alucine.** Consulte Context7 MCP ou pergunte antes de inventar.
2. **Faça apenas o que foi pedido.** Não acrescente features extras.
3. **Antes de codar, leia.** Leia os arquivos em `.claude/memory/`.
4. **Stack fixa.** FastAPI, uv, httpx, structlog — não troque.
5. **Porta 80.** Este serviço expõe somente a porta 80.
6. **Tudo gerado vai pra /media/<tipo>/uuid.<ext>.** Imagem, áudio, etc.

## 2. Stack

| Camada | Tecnologia |
|---|---|
| Runtime | Python 3.12 + uv |
| Web | FastAPI + Uvicorn (porta 80) |
| Config | pydantic-settings + .env |
| HTTP | httpx (async) |
| Logs | structlog |

## 3. Estrutura

```
app/
├── main.py               # FastAPI + StaticFiles (/media)
├── config.py             # Settings (lê .env)
├── api/
│   ├── router.py         # Agrega todos os routers
│   ├── health.py         # GET /, /health, /ready
│   ├── text.py           # POST /text/
│   ├── image.py          # POST /image/, /image/vision
│   ├── tts.py            # POST /tts/
│   └── json_endpoint.py  # POST /json/
├── integrations/
│   ├── http_client.py    # httpx retry
│   ├── deepseek.py       # DeepSeekClient
│   ├── elevenlabs.py     # ElevenLabsClient
│   └── gemini.py         # GeminiClient
└── utils/
    ├── logging.py        # structlog
    └── media.py          # save_media()
data/public/media/
├── image/
├── audio/
└── text/
```

## 4. Endpoints

| Método | Path | Descrição |
|---|---|---|
| GET | / | Status dashboard |
| GET | /health | Health check |
| GET | /ready | Ready probe |
| POST | /text/ | Gera texto (DeepSeek) |
| POST | /image/ | Gera/edita imagem (Gemini) |
| POST | /image/vision | Descreve imagem (Gemini) |
| POST | /tts/ | Texto para voz (ElevenLabs) |
| POST | /json/ | JSON estruturado (DeepSeek) |

## 5. Comandos

```bash
uv sync
make dev    # uv run uvicorn app.main:app --host 0.0.0.0 --port 80 --reload
```
