# Sincronização com a fonte da verdade — 2026-05-22

Relatório da sincronização do código local (`/home/maestri33/backend/ai/ai`) com o
código de produção em `root@10.1.30.20:/opt/v7m/services/ai/` (**fonte da verdade**).

O local estava desatualizado. Todas as divergências foram resolvidas adotando a versão
externa byte-a-byte. Ao final, **todos os arquivos de código batem com a fonte da verdade**.

---

## 1. Método de comparação

1. Cópia da árvore externa via `tar` sobre SSH (rsync indisponível no remoto) para `/tmp/ai-external`.
2. Comparação por `md5sum` de todos os arquivos de `app/` + config (excluindo `data/`, `__pycache__`, `.env`, `uv.lock`, `.mcp.json`, `.claude/`).
3. `diff` arquivo a arquivo nos divergentes.
4. Aplicação por cópia byte-a-byte e reverificação de checksums (28/28 OK).

---

## 2. Diferenças globais (visão geral)

| Arquivo | Situação anterior | Ação |
|---|---|---|
| `Dockerfile` | **Ausente no local** | Criado (cópia do externo) |
| `app/api/health.py` | Divergente | Atualizado |
| `app/api/schemas.py` | Divergente | Atualizado |
| `app/api/tts.py` | Divergente | Atualizado |
| `app/api/v1.py` | Divergente | Atualizado |
| `app/integrations/deepseek.py` | Divergente | Atualizado |
| `app/integrations/elevenlabs.py` | Divergente | Atualizado |
| `app/integrations/gemini.py` | Divergente | Atualizado |
| Demais 20 arquivos de código | Idênticos | Sem alteração |

**Tema das mudanças do externo:** o código de produção é um *superset* do local — só
adiciona recursos e robustez, sem remover nada. Três eixos:
1. **Overrides por requisição** (modelo do DeepSeek, `json_mode`, `voice_id` do ElevenLabs).
2. **Novo endpoint `/status`**.
3. **Robustez no download de imagens do Gemini** (redirects, User-Agent, sanitização de MIME, API correta do SDK).

> Não fazem parte do código-fonte e permanecem locais: `.env`, `.mcp.json`, `uv.lock`, `.claude/`.

---

## 3. Detalhamento por arquivo

### `Dockerfile` (novo)
Imagem `python:3.12-slim`, instala deps com `uv sync --frozen`, usuário não-root `appuser`,
volume em `/app/data/public/media`, healthcheck em `/health`.
- **Atenção:** o container expõe a **porta 8000** (`EXPOSE 8000` + `--port 8000`), enquanto
  o `Makefile` (`make run`/`make dev`) e o CLAUDE.md usam a **porta 80**. O container
  pressupõe um proxy reverso na frente mapeando 80→8000. Comportamento idêntico ao da fonte da verdade.

### `app/api/health.py`
- **+** endpoint `GET /status` → `{status, service, version, uptime_seconds (int), integrations}`.
  Disponível como `/status` (alias) e `/api/v1/status` (canônico).

### `app/api/schemas.py` — `ChatRequest`
- **+** `model: str | None` — override do modelo do DeepSeek por requisição.
- **+** `json_mode: bool = False` — força `response_format=json_object`.

### `app/api/tts.py` — `TTSRequest`
- **+** `voice_id: str | None` — override do `voice_id` do ElevenLabs por requisição.
- Endpoint passa `voice_id=body.voice_id` ao cliente.

### `app/api/v1.py` — `POST /text/chat`
- `model = body.model or settings.deepseek_default_model` (antes era fixo no default).
- Passa `model=` e `json_mode=` para `ds.chat(...)`.
- Comentário documentando que **stream ainda não suporta** `model`/`json_mode` (sempre usa o default).

### `app/integrations/deepseek.py` — `DeepSeekClient.chat()`
- **+** parâmetros `model` e `json_mode`, repassados ao `_build_payload` (que já os suportava internamente).

### `app/integrations/elevenlabs.py` — `ElevenLabsClient.generate()`
- **+** parâmetro `voice_id`; usa `effective_voice_id = voice_id or self._voice_id`.
- Log `elevenlabs.audio_generated` agora inclui `voice` efetiva e `voice_override` (bool).

### `app/integrations/gemini.py`
- `_download_reference`: **+** `follow_redirects=True`, **+** header `User-Agent: v7m-ai/1.0`,
  e sanitização do MIME (`"image/jpeg; charset=binary"` → `"image/jpeg"`).
- `describe()`: troca os construtores diretos por `types.Part.from_text(...)` e
  `types.Part.from_bytes(...)` (API correta do SDK google-genai).
- Log `gemini.vision_done` agora inclui `bytes` e `mime`.

---

## 4. Testes end-to-end (dados reais, sem mock)

Ambiente local não tinha `uv` nem `.venv`. Instalado `uv 0.11.16`, rodado `uv sync`
(deps do `uv.lock`). Serviço subido com Uvicorn em `127.0.0.1:8099` (porta 80 exige root;
a porta não afeta a validação dos endpoints). Credenciais reais do `.env` local.

Modelos configurados no `.env`: DeepSeek `deepseek-v4-pro` (raciocínio) / `deepseek-v4-flash`,
Gemini `gemini-3.1-flash-image-preview` e `gemini-3-flash-preview`, ElevenLabs `eleven_v3`.

| Endpoint | Resultado |
|---|---|
| `GET /`, `/health`, `/ready` | OK — integrações reportam `configured:true` |
| `GET /status` e `/api/v1/status` (**novo**) | OK — uptime + integrações |
| `POST /text/` | OK — texto real do DeepSeek |
| `POST /json/` | OK — JSON real |
| `POST /api/v1/text/chat` (envelope) | OK — usage/latency/finish_reason |
| `POST /api/v1/text/chat` `json_mode:true` (**novo**) | OK — saída JSON válida |
| `POST /api/v1/text/chat` `model:"deepseek-v4-flash"` (**novo**) | OK — envelope reflete o modelo; 766ms vs 2521ms do pro |
| `POST /api/v1/text/chat` `stream:true` | OK — SSE `meta`→`delta`→`finish(ttft_ms)`→`[DONE]` |
| `POST /api/v1/text/summarize` (paragraph/bullets) | OK |
| `POST /api/v1/text/extract` (JSON Schema) | OK — tipos corretos (idade como int) |
| `POST /tts/` (voz padrão) | OK — MP3 128kbps real salvo |
| `POST /tts/` `voice_id` override (**novo**) | OK — log: `voice_override=True`, voz trocada |
| `POST /image/` | OK — JPEG 1024x1024 (~985KB) |
| `POST /image/vision` (URL com **redirect**) | OK — valida `follow_redirects`, MIME e `Part.from_*` |
| `POST /ocr/` | OK — texto extraído + estrutura |
| `POST /ocr/document` | OK — confiança ~0.97 |

Mídia gerada salva em `data/public/media/{audio,image}/`. As URLs retornadas usam
`PUBLIC_BASE_URL=https://ai.m33.live` (config local).

---

## 5. Observações importantes

1. **Modelo de raciocínio (DeepSeek `deepseek-v4-pro`):** consome tokens em `reasoning_content`
   antes de produzir `content`. Com `max_tokens` baixo (ex.: 80), o conteúdo final vem **vazio**
   (`finish_reason:"length"`). Não é bug — use `max_tokens` folgado (≥400) ou o `deepseek-v4-flash`.

2. **Anomalia transitória de grpc no OCR:** numa primeira execução, uma chamada ao `/ocr/`
   (Google Vision, grpc) após várias chamadas ao Gemini (google-genai, também grpc) derrubou o
   processo do Uvicorn. **Não foi reproduzível** depois (OCR isolado e via HTTP, inclusive na
   sequência vision→OCR, funcionaram). Provável conflito de estado/fork-handlers do grpc entre
   `google-genai` e `google-cloud-vision` no mesmo processo. O código de OCR é **byte-idêntico à
   fonte da verdade** (não é regressão da sincronização). Se reincidir em produção, considerar
   rodar a chamada grpc bloqueante em threadpool (`anyio.to_thread.run_sync`) — mas isso seria
   uma divergência da fonte da verdade e deve ser decidido à parte.

3. **Porta:** Dockerfile usa 8000; Makefile/CLAUDE.md usam 80 (ver seção 3, Dockerfile).

4. **Arquivo local pré-existente** fora do padrão: `app/data/public/media/audio/0f7a...mp3`
   (o padrão correto é `data/public/media/...` na raiz). Não faz parte da sincronização; deixado intacto.
