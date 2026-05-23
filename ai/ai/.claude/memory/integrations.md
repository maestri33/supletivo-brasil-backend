# Integrações — Serviço AI

## DeepSeek (api.deepseek.com)
- Tipo: REST (OpenAI-compatible) via httpx + request_with_retry
- Auth: Bearer token (DEEPSEEK_API_KEY)
- Endpoint: POST /chat/completions
- Modelo: deepseek-v4-pro
- Cache KV: gratuito, isolado por `user_id` (usa `service_name`). Métricas: `prompt_cache_hit_tokens` (grátis), `prompt_cache_miss_tokens` (cobrados)
- max_tokens: default 0 = não envia no payload (API decide, até 1M). Incluído só se > 0
- temperature: default 0.3 (bom pra JSON e consistência). Sobrescrito por request
- Timeout: 60s (normal), 120s connect + 30s read (stream)
- Retry: 3x backoff 0.5s (429/502/503/504)

### Métodos
| Método | Uso | Retorno |
|---|---|---|
| generate_text(prompt, instruction?, ...) | /text/ legado | str |
| generate_json(prompt, instruction?, schema_description?, ...) | /json/ legado | dict |
| chat(messages, ...) | /text/chat | ChatResult |
| summarize(text, format, ...) | /text/summarize | ChatResult |
| extract(text, json_schema, ...) | /text/extract | ChatResult |
| chat_stream(messages, ...) | /text/chat?stream=true | AsyncIterator[StreamChunk] |

### ChatResult (dataclass)
- content: str
- prompt_tokens, completion_tokens: int
- cache_hit_tokens, cache_miss_tokens: int
- finish_reason: str | None
- cache_hit_rate: float (propriedade)

### StreamChunk (dataclass)
- content: str (delta incremental)
- finish_reason: str | None (no último chunk)
- usage: dict | None (no último chunk)

### JSON mode
- response_format: {"type": "json_object"}
- System prompt DEVE conter instrução "Retorne APENAS um JSON valido"
- Usado por: generate_json(), extract()

## ElevenLabs (SDK elevenlabs-python)
- Tipo: SDK oficial (pip: elevenlabs>=2.46)
- Auth: AsyncElevenLabs(api_key=...)
- Método: client.text_to_speech.convert() — async generator de bytes → concatenados
- Voz: George (JBFqnCBsd6RMkjVDRZzb) — masculina narrativa, funciona com PT via language_code
- Modelo: eleven_v3 (multilingual)
- VoiceSettings: stability, similarity_boost, speed, style, use_speaker_boost
- Output: mp3_44100_128 (default)
- Timeout: gerido internamente pelo SDK
- NÃO depende de httpx (SDK gerencia próprio HTTP)

## Gemini (SDK google-genai)
- Tipo: google-genai SDK (pip: google-genai>=2.0.1)
- Auth: genai.Client(api_key=...)
- Chamadas: client.aio.models.generate_content() (async)
- Config: GenerateContentConfig com ImageConfig (aspect_ratio, image_size)
- Erros: google.genai.errors.APIError → IntegrationError
- Modelos:
  - Imagem: gemini-3.1-flash-image-preview (rápido, suporta image_size + aspect_ratio)
  - Visão: gemini-3-flash-preview (rápido, boa descrição)
- Image: response_modalities=["IMAGE"], tools opcional com GoogleSearch
- Reference: types.Part(inline_data=types.Blob(mime_type=..., data=bytes))
- Vision: types.Part(text="Descreva...") + types.Part(inline_data=...)
- Download de referências: httpx (único uso de HTTP bruto no GeminiClient)
- MIME types permitidos: image/png, image/jpeg, image/webp
