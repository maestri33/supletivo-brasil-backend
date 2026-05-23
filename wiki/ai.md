# ai

## Função

Serviço genérico de IA: expõe endpoints HTTP para geração de texto, imagem, áudio (TTS), JSON estruturado e OCR, delegando a provedores externos (DeepSeek, Gemini, ElevenLabs, Google Cloud Vision). Stateless — sem banco de dados próprio.

## Status

**Parcial — funcional em produção, mas sem testes automatizados e sem Alembic (serviço é stateless, portanto sem migração; isso é correto). Todos os endpoints declarados estão implementados. Ausência de testes é o principal gap de qualidade.**

## Estrutura

Aninhado incorretamente: `ai/ai/app/` — viola a convenção que exige `ai/app/` (sem dobrar o nome do serviço). O pacote funciona porque o `pyproject.toml` está em `ai/ai/`, mas o aninhamento `ai/ai/` é desvio explícito da CONVENTION §3.

```
ai/ai/           ← raiz real do serviço (deveria ser ai/)
└── app/
    ├── main.py
    ├── config.py
    ├── api/         (health, text, image, tts, json_endpoint, ocr, v1, schemas, router)
    ├── integrations/ (deepseek, elevenlabs, gemini, ocr, http_client)
    └── utils/       (logging, media)
data/public/media/   ← arquivos gerados (image/, audio/, text/)
```

Não há `models/`, `schemas/` (pasta), `services/`, `alembic/` — correto para serviço stateless.

## Endpoints

### `health.py` — desmilitarizados
| Método | Rota canônica | Descrição |
|---|---|---|
| GET | `/api/v1/` | Status geral + uptime + estado das integrações |
| GET | `/api/v1/health` | Healthcheck simples `{status: ok}` |
| GET | `/api/v1/ready` | Readiness — retorna `degraded` se alguma API key estiver ausente |
| GET | `/api/v1/status` | Status detalhado com uptime em segundos |

### `text.py` — desmilitarizado (legado, sem envelope)
| Método | Rota canônica | Descrição |
|---|---|---|
| POST | `/api/v1/text/` | Geração de texto livre via DeepSeek; body `{prompt, instruction?, temperature?, max_tokens?}` → `{text}` |

### `json_endpoint.py` — desmilitarizado (legado, sem envelope)
| Método | Rota canônica | Descrição |
|---|---|---|
| POST | `/api/v1/json/` | Geração de JSON estruturado via DeepSeek JSON mode; body `{prompt, instruction?, schema_description?, temperature?, max_tokens?}` → `{data: dict}` |

### `image.py` — desmilitarizado (legado, sem envelope)
| Método | Rota canônica | Descrição |
|---|---|---|
| POST | `/api/v1/image/` | Gera 1–4 imagens em paralelo via Gemini; body `{prompt, reference_url?, aspect_ratio?, image_size?, google_search?, num_images?}` → `{images: [{url, filename, mime_type}]}` |
| POST | `/api/v1/image/vision` | Descreve imagem via Gemini Vision; body `{image_url}` → `{description}` |

### `tts.py` — desmilitarizado (legado, sem envelope)
| Método | Rota canônica | Descrição |
|---|---|---|
| POST | `/api/v1/tts/` | Text-to-speech via ElevenLabs; body `{text, voice_id?, speed?, stability?, ...}` → `{url, filename}` |

### `ocr.py` — desmilitarizado (legado, sem envelope)
| Método | Rota canônica | Descrição |
|---|---|---|
| POST | `/api/v1/ocr/` | OCR genérico em imagem via Google Cloud Vision; multipart `file + language_hints?` → `{text, locale, pages}` |
| POST | `/api/v1/ocr/document` | OCR otimizado para documentos densos (PDF/TIFF); mesmo contrato |

### `v1.py` — desmilitarizado (novos, com envelope `APIResponse[T]`)
| Método | Rota canônica | Descrição |
|---|---|---|
| POST | `/api/v1/text/chat` | Chat multi-turn DeepSeek; suporta SSE stream; body `{messages, temperature?, max_tokens?, stream?, model?, json_mode?}` → envelope com `ChatData` ou `StreamingResponse` |
| POST | `/api/v1/text/summarize` | Sumarização em paragraph/bullets/headline via DeepSeek → envelope com `SummarizeData` |
| POST | `/api/v1/text/extract` | Extração estruturada via JSON Schema real → envelope com `ExtractData` |

Todos os endpoints têm aliases legados sem prefixo `/api/v1` (ex.: `/text/`, `/tts/`, `/v1/text/chat`) registrados em `router.py`.

## Dados

**Sem banco de dados / sem schema Postgres.** O serviço é stateless.

Arquivos gerados são persistidos em disco em `data/public/media/<tipo>/<uuid>.<ext>` e servidos como estáticos em `/media/*` via `StaticFiles`. Não há tabelas, FKs, shadow tables nem Alembic.

## Integrações

### Externas
| Serviço | Módulo | Protocolo | Auth |
|---|---|---|---|
| **DeepSeek** | `integrations/deepseek.py` | REST httpx (retry 3×, backoff 0.5 s) | Bearer token (`DEEPSEEK_API_KEY`) |
| **ElevenLabs** | `integrations/elevenlabs.py` | SDK oficial `elevenlabs` v2.46 async | `ELEVENLABS_API_KEY` |
| **Gemini** | `integrations/gemini.py` | SDK `google-genai` v2.0.1 async | `GEMINI_API_KEY` |
| **Google Cloud Vision** | `integrations/ocr.py` | SDK `google-cloud-vision` síncrono | `GOOGLE_VISION_API_KEY` ou service account JSON |

### Internas
Nenhuma. O serviço não chama outros microsserviços da plataforma via httpx.

O cliente HTTP compartilhado (`http_client.py`) fornece `get_http_client()` (Depends FastAPI) e `request_with_retry()` com retry em 429/502/503/504.

## Pendências

### TODO no wiki
- `backend/wiki/TODO`: criar `ai.md` após o app estar funcional e aprovado. **Concluído com este arquivo.**

### TODOs no código
- `app/api/v1.py` (linha 73): comentário inline — stream não suporta `model` override nem `json_mode`; indicado como melhoria futura mas sem `TODO` formal.

### Desvios da CONVENTION
| # | Desvio | Severidade | Detalhe |
|---|---|---|---|
| 1 | **Aninhamento** `ai/ai/app` | Alta | CONVENTION §3 proíbe `servico/servico/app`; o correto é `ai/app`. |
| 2 | **Sem testes** | Alta | CONVENTION §2 e checklist §15 exigem `pytest + pytest-asyncio`; não existe diretório `tests/`. |
| 3 | **`schemas/` como arquivo** | Média | `api/schemas.py` em vez de pasta `schemas/`. Schemas dos endpoints legados estão inline nos arquivos de rota (ex.: `TextRequest` em `text.py`), não em `schemas/`. |
| 4 | **OCR síncrono** | Média | `VisionOCRClient` usa SDK Google Cloud Vision síncrono (bloqueante); CONVENTION §4 exige async para toda I/O. |
| 5 | **`models/` e `services/` ausentes** | Baixa | Aceitável para serviço stateless, mas a ausência de `services/` significa que lógica de orquestração está nos endpoints — ok dado o escopo simples. |
| 6 | **Sem `README.md`** | Baixa | CONVENTION §3 lista `README.md` como arquivo obrigatório. |
