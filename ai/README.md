# ai

Serviço genérico de IA: endpoints HTTP para texto (DeepSeek), imagem (Gemini),
TTS (ElevenLabs), JSON estruturado e OCR (Google Cloud Vision). Stateless — sem
banco de dados próprio. Doc completa: `../wiki/ai.md`.

## Rodar

```bash
cd ai/ai                  # aninhamento ai/ai/app (desvio §3)
uv sync
cp .env.example .env      # varie DEEPSEEK_API_KEY, GEMINI_API_KEY, etc.
uv run uvicorn app.main:app --host 0.0.0.0 --port 80 --reload
```

## Testes / lint

```bash
uv run pytest -q           # testes ausentes (gap de qualidade)
uv run ruff check . && uv run ruff format --check .
```

## Variáveis (`.env`)

| Var | Obrigatória | Descrição |
|-----|:-:|-----------|
| `DEEPSEEK_API_KEY` | ✅ | API key DeepSeek |
| `GEMINI_API_KEY` | | API key Google Gemini (imagem) |
| `ELEVENLABS_API_KEY` | | API key ElevenLabs (TTS) |
| `GOOGLE_APPLICATION_CREDENTIALS` | | Credenciais Google Cloud Vision (OCR) |

## Endpoints (todos desmilitarizados)

- **Texto:** `POST /api/v1/text/`, `POST /api/v1/text/chat` (SSE stream), `/summarize`, `/extract`
- **JSON:** `POST /api/v1/json/` (DeepSeek JSON mode)
- **Imagem:** `POST /api/v1/image/`, `POST /api/v1/image/vision`
- **TTS:** `POST /api/v1/tts/`
- **OCR:** `POST /api/v1/ocr/`, `POST /api/v1/ocr/document`
- **Saúde:** `/api/v1/health`, `/api/v1/ready`, `/api/v1/status`
