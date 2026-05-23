# Memória — Integrações com outros serviços

> Para **cada serviço externo** com que este fala, registre aqui:
> base URL, endpoints usados, formato de erro, política de retry,
> última vez que foi testado.

## Template de entrada

```
### <nome-do-servico>
- **Tipo:** HTTP | Webhook | Fila (RabbitMQ) | Pub/Sub (Redis)
- **Base URL / queue:** http://...
- **Endpoints / tópicos usados:**
  - GET /api/v1/...
- **Auth:** nenhuma (DMZ) | bearer | hmac
- **Retry:** 3x backoff exponencial (já no http_client)
- **Última verificação:** YYYY-MM-DD
- **Notas:** ...
```

## Integrações ativas

> **Rede (2026-05-22):** tudo roda em Docker Compose; os clientes usam
> hostnames de serviço internos (`mail`, `whats-api`, `ai`, `profiles`,
> `postgres`) na porta 8000/8080. URLs `*.local`/`10.10.10.x` são legado.

### Mailcow (SMTP direto) — canal de email atual
- **Tipo:** SMTP (STARTTLS:587) + API REST admin
- **Host:** `mail.v7m.org:587` (`MAILCOW_SMTP_*`); API `https://mail.v7m.org`
- **Cliente:** `app/integrations/mailcow.py` → `MailcowSMTPClient`
- **Envio:** `send_email(to, subject, html_body, plain_body, inline_images)` —
  `smtplib` em thread (`anyio.to_thread`), MIME multipart utf-8, imagens inline
  via **CID** (`<img src="cid:notify-img-1">`).
- **API admin:** listar mailboxes, criar/deletar app-passwords (`X-API-Key`).
- **Por quê substituiu o service `mail`:** o `mail` Docker tinha conflito de
  credenciais (`configure_smtp` sobrescrevia config válida → `535 auth failed`)
  e adicionava hop+retries que estouravam o ReadTimeout do notify.
- **Auth:** app-password (SMTP) + API key (admin).
- **Última verificação:** 2026-05-22

### Profiles — lookup de gênero p/ voz TTS
- **Tipo:** HTTP
- **Base URL:** `http://profiles:8000` (`PROFILES_BASE_URL`)
- **Cliente:** `app/integrations/profiles.py` → `ProfilesClient`
- **Endpoint:** `GET /api/v1/profiles/{external_id}` → usa `gender` (M/F).
- **Contrato de falha:** **nunca propaga erro** (404/timeout/shape inválido →
  `None` → TTS usa `elevenlabs_voice_id` default). Timeout `profiles_timeout_s`.
- **Última verificação:** 2026-05-22

### Mail Merge API (SMTP) — DEPRECATED
- **Tipo:** HTTP
- **Base URL:** `http://mail:8000` (era `http://10.10.10.150`)
- **Status:** **DEPRECATED** — mantido por compat; envio real é via Mailcow.
- **Cliente:** `app/integrations/smtp.py` → `SMTPClient`
- **Endpoints usados:**
  - `GET /vercel` — health check, retorna `{"message":"FastAPI is running on Vercel!"}`
  - `POST /configure_smtp` — configura SMTP em memória (form-encoded: `smtpHost`, `smtpPort`, `smtpUser`, `smtpPass`)
  - `POST /preview_csv` — upload CSV, retorna as 5 primeiras linhas como JSON
  - `POST /send_emails` — dispara e-mails em massa (multipart: `subject`, `senderName`, `htmlContent` + csvFile)
- **Fluxo:** configure SMTP → preview CSV → send emails. Sem configurar SMTP antes, `/send_emails` retorna 400.
- **Placeholders:** subject e htmlContent aceitam `{{coluna}}` (Jinja2) referenciando colunas do CSV.
- **CSV:** obrigatório ter coluna `Email`.
- **Entrega:** fastapi-mail, 3 tentativas com 1s de intervalo entre e-mails.
- **Auth:** nenhuma (DMZ)
- **Retry:** 3x backoff exponencial (via `request_with_retry` do `http_client`)
- **Última verificação:** 2026-05-02

### Evolution API 2.3.7 (WhatsApp)
- **Tipo:** HTTP
- **Base URL:** `http://whats-api:8080` (era `http://10.10.10.149`)
- **Cliente:** `app/integrations/whatsapp.py` → `WhatsAppClient`
- **Resolução BR (2026-05-22):** `resolve_br_number(phone)` testa as variantes
  com/sem 9º dígito via `check_numbers` e usa a registrada (cache em memória,
  TTL 1h). Evita silent-fail de entrega (Evolution 2.3.7 normaliza errado).
- **Retry de envio:** `whatsapp_max_retries` (default 3) com backoff exponencial
  1s/3s/9s — só para erros transitórios (5xx/timeout/conn). Ver `message_service`.
- **Instância ativa:** "default" — `5511920062177` (Supletivo BR)
- **Auth:** header `apikey` = `Settings.whatsapp_global_api_key` (`7A3F8C2B...`)
- **Instance:** default "default", sobreponível via `WhatsAppClient(http, instance="...")`
- **Endpoints usados:**
  - `GET /instance/status` — health global da API
  - `POST /chat/whatsappNumbers/{instance}` — verifica números (body: `{"numbers": [...]}`, resposta array plano `[{jid, exists, number, name}]`)
  - `POST /chat/fetchProfile/{instance}` — perfil do usuário (body: `{"number": "5543..."}`, resposta `{wuid, name, picture, status, isBusiness}`)
  - `POST /chat/fetchBusinessProfile/{instance}` — perfil comercial (body: `{"number": "..."}`, resposta `{address, website, category, business_hours}`)
  - `POST /call/reject/{instance}` — rejeita chamada
  - `POST /message/sendText/{instance}` — envia texto
  - `POST /message/sendMedia/{instance}` — envia mídia (campos: `mediatype`, `media`; tipos: image/video/audio/document)
  - `POST /message/sendWhatsAppAudio/{instance}` — nota de voz nativa (PTT, Opus, waveform)
  - `POST /message/sendSticker/{instance}` — sticker WebP
  - `POST /message/sendLocation/{instance}` — localização (pin no mapa)
  - `POST /message/sendContact/{instance}` — contato(s) vCard
  - `POST /message/sendPoll/{instance}` — enquete interativa (até 12 opções)
  - `POST /message/sendButtons/{instance}` — botões interativos (reply/url/copy, máx 3)
  - `POST /message/sendReaction/{instance}` — reação com emoji
  - `POST /message/sendStatus/{instance}` — status/story (texto ou imagem)
- **Body de perfil:** fetchProfile e fetchBusinessProfile recebem `{"number": "5543996648750"}` (número PURO, não JID). Campo é `number`, não `wuid`.
- **Retry:** 3x backoff exponencial (via `request_with_retry` do `http_client`)
- **Timeout audio:** 60s no `send_whatsapp_audio` (conversão para Opus)
- **Última verificação:** 2026-05-05 — todos os endpoints testados

### AI Service — Microserviço de IA
- **Tipo:** HTTP
- **Base URL:** `http://ai:8000` (era `http://10.10.10.177` / ai.local)
- **Cliente:** `app/integrations/ai.py` → `AIClient`
- **Endpoints usados:**
  - `POST /text/` — geração de texto (DeepSeek) + título
  - `POST /image/` — geração/edição de imagem (Gemini)
  - `POST /tts/` — text-to-speech (ElevenLabs)
  - `POST /json/` — JSON estruturado (DeepSeek JSON mode)
- **Fluxo interno:** O AI service chama DeepSeek/ElevenLabs/Gemini diretamente. O notify agora só chama o AI service para tudo de IA — texto, imagem, TTS.
- **Auth:** nenhuma (DMZ)
- **Retry:** 3x backoff exponencial (via `request_with_retry`)
- **Media local:** Imagens e áudios gerados são baixados do AI e salvos localmente em `data/public/` para servir via StaticFiles (Evolution precisa acessar na DMZ).
- **Última verificação:** 2026-05-12
