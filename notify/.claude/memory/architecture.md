# Memória — Arquitetura

> Decisões arquiteturais deste serviço, em ordem cronológica.
> **Toda decisão nova entra aqui** com data, contexto e consequência.

## Forma deste serviço

> ⚠️ **Atualizado em 2026-05-22** (sync com a fonte da verdade
> `10.1.30.20:/opt/v7m/services/notify`). O `CLAUDE.md` ainda descreve a forma
> antiga (porta 80, SQLite por-serviço, Aerich) — está **desatualizado**.

- Um único processo Uvicorn na porta **8000** (publicado no host em `:8157`
  via Docker Compose). Não é mais a porta 80.
- **Postgres central compartilhado** (`v7m`), com **um schema por serviço**
  (`notify`). Este serviço **não** tem banco próprio nem SQLite. Há **FK
  cross-schema para `auth.users`** (todo `Contact`/`Log` referencia um
  `external_id` de `auth`).
- ORM: **SQLAlchemy 2 async** (asyncpg). Migrations: **Alembic** (`alembic/`).
- Comunicação com o mundo externo:
  - **Síncrona:** HTTP via `app/integrations/http_client.py`.
  - **Assíncrona:** RabbitMQ via `app/integrations/messaging.py`
    (publisher) e `app/workers/` (consumers).
  - **Cache / pub-sub leve:** Redis via `app/integrations/redis_client.py`.
  - **Eventos pra terceiros:** webhooks outbound em
    `app/integrations/webhooks.py`.

## Princípios

1. **Service-per-database.** Acoplamento via API ou evento, nunca via SQL.
2. **Camadas finas.** `api/` → `services/` → `models/`. Sem mais.
3. **Erros explícitos.** Exceptions de domínio em `app/exceptions.py`,
   convertidas pra HTTPException no router.
4. **Idempotência onde dá.** Endpoints `POST` que criam algo via evento
   externo aceitam um header `Idempotency-Key`.

## Histórico de decisões

### 2026-05-22 — Migração Tortoise/Aerich/SQLite → SQLAlchemy 2/Alembic/Postgres central
- **Decisão (vinda da fonte da verdade):** persistência reescrita. Saiu
  `Tortoise ORM + Aerich + SQLite`; entrou **`SQLAlchemy 2 async + Alembic +
  Postgres central v7m` (schema `notify`)**.
- **Topologia:** deixou de ser "um banco por serviço". Agora é **um Postgres
  central** com **schema por serviço** e **FK cross-schema** de
  `notify.contacts.external_id`/`notify.logs.external_id` → `auth.users.external_id`
  (RESTRICT). `app/db.py` declara uma `Table("users", schema="auth")` sombra
  só para o SQLAlchemy resolver a FK.
- **Detalhes:** `Base(DeclarativeBase)` + `MetaData(schema="notify")` com
  naming convention; `create_async_engine` + `async_session_maker` +
  dependency `get_session()`. `init_db()` virou no-op (Alembic gerencia schema).
- **Modelos:** `Message` passou a ter **status por canal** (`whatsapp_status`
  + `email_status`); `Log.details` é **JSONB**; novo modelo **`Template`**
  (slug/version/is_active). `external_id` virou **UUID**.
- **Migrations:** `alembic/versions/0001..0003` (schema inicial; templates +
  `logs.external_id`; seeds de contexto). Rodar `alembic upgrade head`
  (o Dockerfile faz isso no boot). A pasta `migrations/` (Aerich) foi removida.
- **Porta:** 80 → **8000**.
- **Consequência:** o schema `notify` e o `auth.users` precisam existir no
  Postgres central antes do `alembic upgrade`. Testes exigem Postgres real
  (ver conventions.md). Detalhes completos em `docs/sync-2026-05-22-sqlalchemy-postgres.md`.

### 2026-05-22 — Novas integrações: Mailcow (SMTP direto) e Profiles
- **Mailcow:** envio de email passou a ser **SMTP direto** (`MailcowSMTPClient`,
  STARTTLS:587) em vez do service Docker `mail` — que tinha conflito de
  credenciais e mascarava `535` como ReadTimeout. Suporta imagens inline (CID).
- **Profiles:** `ProfilesClient.get_gender()` resolve M/F para escolher a voz
  do TTS (ElevenLabs). Falha silenciosa → voz default. Ver integrations.md.

### 2026-05-09 — Unificacao: clientes em `app/integrations/`
- **Decisão:** clientes para APIs externas (SMTP, WhatsApp, DeepSeek,
  ElevenLabs, Gemini) movidos de `app/services/clients/` para
  `app/integrations/`.
- **Por quê:** `integrations/` ja e "tudo que sai pra fora deste servico".
  Ter duas pastas (`clients/` + `integrations/`) era redundante.
  Simplificacao: uma unica pasta para toda comunicacao externa.
- **Consequência:** `app/services/clients/` foi removida. Toda nova API
  externa vai direto em `app/integrations/<nome>.py`.

### 2026-05-02 — Bootstrap inicial
- **Decisão:** SQLite como default no template, Postgres opcional via
  `DATABASE_URL`.
- **Por quê:** simplifica o boot do serviço novo (zero infra), e como o
  banco é por-serviço a migração futura é trivial.
- **Consequência:** ao escalar para produção, trocar `DATABASE_URL` para
  uma instância Postgres dedicada **antes** de ter dados que doam.

### 2026-05-02 — Camada de clientes externos em `app/services/clients/`
- **Decisão:** clientes para APIs externas (SMTP mail merge, WhatsApp
  Evolution GO) ficam em `app/services/clients/`, não em `app/integrations/`.
- **Por quê:** `integrations/` lida com infra genérica (httpx, Redis,
  RabbitMQ, webhooks). Já `services/clients/` encapsula a comunicação
  com um serviço externo **específico**, com métodos de alto nível
  (`send_text`, `check_numbers`, `configure_smtp`).
- **Consequência:** toda nova API externa ganha um arquivo em
  `services/clients/<nome>.py` e é registrada em
  `.claude/memory/integrations.md`.
- **Clientes ativos:**
  - `DeepSeekClient` — DeepSeek API (texto, titulos, prompts)
  - `ElevenLabsClient` — ElevenLabs TTS (text-to-speech)
  - `GeminiClient` — Gemini Image Generation + Vision
  - `SMTPClient` — Mail Merge API (`10.10.10.150`)
  - `WhatsAppClient` — Evolution GO v2 (`10.10.10.149`)

### 2026-05-02 — Instância WhatsApp "default" (Supletivo BR)
- **Decisão:** a instância WhatsApp usada para testes é a "default"
  (conectada, logada, número `5511920062177`, Supletivo BR).
- **Por quê:** validar o `WhatsAppClient` fim a fim (health, check,
  send_text, send_media, send_whatsapp_audio, send_sticker).
- **Consequência:** todos os testes de WhatsApp usam essa instância.
  Se trocar de instância, atualizar `whatsapp_instance_name` no `.env`.
