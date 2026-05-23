# Sync 2026-05-22 — alinhamento com a fonte da verdade

> **Fonte da verdade:** `root@10.1.30.20:/opt/v7m/services/notify/`
> (parte do monorepo git `/opt/v7m`, stack rodando em Docker Compose).
> **Alvo:** este repositório local, que estava desatualizado.
>
> Este documento registra (1) as diferenças globais entre os dois códigos e
> (2) as alterações aplicadas localmente para deixá-los coesos.

---

## 1. Resumo executivo

O código externo sofreu uma **reescrita da camada de persistência** e ganhou
**novas features**. As duas mudanças estruturais mais importantes:

1. **ORM/Migrations:** `Tortoise ORM + Aerich + SQLite` → **`SQLAlchemy 2
   (async) + Alembic + Postgres central`**.
2. **Topologia de banco:** de "um SQLite por serviço" para **um Postgres
   central `v7m` com um schema por serviço** (`notify`) e **FK cross-schema
   para `auth.users`** (todo contacto pertence a um usuário do serviço auth).

Tudo passou a rodar em Docker Compose, com hostnames de serviço internos
(`postgres`, `ai`, `whats-api`, `mail`, `profiles`, `notify`) na **porta 8000**
(o `notify` é publicado no host em `:8157`).

> ⚠️ Isso **contraria** duas "regras de ouro" do `CLAUDE.md` atual
> (porta 80; cada serviço com seu próprio banco). Ver seção 6.

---

## 2. Diferenças globais (externo = correto)

### 2.1 Persistência (`app/db.py`, `pyproject.toml`)
- **Antes:** `TORTOISE_ORM` dict, `Tortoise.init`, `generate_schemas` em dev,
  SQLite default (`sqlite://data/app.db`).
- **Agora:** `DeclarativeBase` (`Base`), `MetaData(schema="notify")` com
  `NAMING_CONVENTION`, `create_async_engine` (asyncpg, `pool_pre_ping`),
  `async_session_maker`, dependency `get_session()`. `init_db()` virou **no-op**
  (schema é gerenciado pelo Alembic). Tabela sombra `auth.users` declarada para
  o SQLAlchemy resolver a FK cross-schema.
- **Deps:** removidos `tortoise-orm`, `aerich`; adicionados
  `sqlalchemy[asyncio]>=2.0`, `alembic>=1.14`, `asyncpg>=0.30`.

### 2.2 Migrations
- **Antes:** Aerich em `migrations/models/…`.
- **Agora:** **Alembic** em `alembic/` + `alembic.ini`:
  - `0001` initial schema (contacts/messages/logs no schema `notify`, FK
    `contacts.external_id → auth.users`, `messages.contact_id`, `logs.message_id`).
  - `0002` tabela `templates` + seed `default` + coluna `logs.external_id`
    (FK `auth.users`).
  - `0003` seed de templates por contexto (`welcome`, `checkout`, `receipt`,
    `parabens`), idempotente (`ON CONFLICT DO NOTHING`).

### 2.3 Config (`app/config.py`)
- `port` 80 → **8000**.
- `database_url` SQLite → `postgresql+asyncpg://v7m:v7m@postgres:5432/v7m`;
  novo `database_schema="notify"`.
- Novos blocos: **Mailcow** (`mailcow_smtp_*`, `mailcow_from_*`,
  `mailcow_api_*`), **Profiles** (`profiles_base_url`, `profiles_timeout_s`),
  **WhatsApp retries** (`whatsapp_max_retries=3`, `whatsapp_retry_backoff_base_s=1.0`),
  **vozes por gênero** (`elevenlabs_voice_male/female`).
- Hostnames migraram de `*.local` para nomes de serviço Docker (`ai:8000`,
  `whats-api:8080`, `mail:8000`, `profiles:8000`, `notify:8000`).
- SMTP API (`smtp_api_base_url`) marcado **DEPRECATED** (substituído por Mailcow).

### 2.4 Entrypoint (`app/main.py`)
- Removido o endpoint `/` "dashboard" (que pingava todas as integrações via Tortoise).
- Novos `/health`, `/ready` (SELECT 1 via SQLAlchemy) e `/status` (uptime +
  `metrics_service.status_snapshot`).
- `lifespan` chama `template_service.bootstrap_from_disk_if_needed()`;
  não chama mais `init_db()` (Alembic cuida do schema).
- Versão 0.4.0 → **0.5.0**.

### 2.5 Modelos (`app/models/`) — todos reescritos em SQLAlchemy 2
- **Contact:** `external_id` UUID **FK `auth.users` (RESTRICT)**, único; `phone`,
  `email` únicos; timestamps; relação `messages`.
- **Message:** **status por canal** — `whatsapp_status` **e** `email_status`
  (antes era status único) + `email_subject`, `tts_audio_url`, `type`,
  `content_text`. Constantes `STATUS_PENDING/SENT/FAILED/SKIPPED`.
- **Log:** `message_id` (FK), `external_id` (FK auth.users), `action`,
  `details` **JSONB**.
- **Template (novo):** `slug` único, `name`, `html`, `version`, `is_active`,
  timestamps. `DEFAULT_SLUG="default"`.

### 2.6 Integrações novas
- **`app/integrations/mailcow.py` (`MailcowSMTPClient`)** — envio SMTP direto
  STARTTLS:587 (via `smtplib` em thread), suporte a **imagens inline CID** e
  charset utf-8 explícito; API admin REST para app-passwords/mailboxes.
  Substitui o service Docker `mail` (que tinha conflito de credenciais e
  mascarava `535` como ReadTimeout).
- **`app/integrations/profiles.py` (`ProfilesClient`)** — `get_gender(external_id)`
  → `M`/`F`/`None` para escolher a voz do TTS. Nunca propaga erro (fallback
  para voz default).

### 2.7 Serviços
- **`message_service.py` (reescrito, +620/-182):** pipeline em background —
  download de `.md`, detecção de mídia (base64/URL), IA de texto/imagem,
  WhatsApp com `resolve_br_number` (variantes do 9º dígito) + **retry
  exponencial** (1s/3s/9s…), email via Mailcow com CID inline, **TTS por
  gênero** (profiles → voz) com fallback para texto, callback de **webhook**,
  `whatsapp_status`/`email_status` independentes. Novo `send_test_email`
  (deliverability, não cria Contact/Message).
- **`template_service.py` (reescrito):** DB-backed multi-slug (CRUD), edição
  via IA (DeepSeek), `get_active_or_default` com fallback, bootstrap do disco
  (`data/email_template.html`).
- **`metrics_service.py` (novo):** agregações Postgres-side para `/status` e
  `/api/v1/logs/metrics`.

### 2.8 API (`app/api/`)
- **contacts:** `external_id` agora é **UUID**; `GET /check`, CRUD, `PATCH
  /{id}/email`, `DELETE`.
- **messages:** `POST /send` (cria pending + processa em background),
  `POST /test-email`, `GET`, `GET /{id}`.
- **templates:** CRUD por slug (`GET/POST/GET{slug}/PUT{slug}/DELETE{slug}`) +
  `GET /email/legacy` (compat).
- **logs:** `GET`, `GET /by-external-id/{uuid}`, `GET /metrics`.
- **whatsapp/instructions:** mantidos, adaptados ao novo client/DB.

### 2.9 Cliente WhatsApp (`app/integrations/whatsapp.py`, +97/-1)
- Novo `resolve_br_number` (resolve com/sem 9º dígito via `check_numbers`,
  cache em memória TTL 1h) — evita silent-fail de entrega da Evolution 2.3.7.

### 2.10 Testes (`tests/`)
- **`conftest.py` (reescrito):** usa **Postgres real** (testcontainers **ou**
  `TEST_DATABASE_URL`); **não** usa mais SQLite (PG_UUID/JSONB/schema não são
  portáveis). Cria schemas `auth`+`notify`, popula `auth.users`, seed
  `default`, limpa entre testes. Isola **apenas IO externo** (WhatsApp/DNS/
  SMTP/Mailcow/DeepSeek).
- Novos: `test_templates.py`, `test_status_metrics.py`,
  `test_logs_by_external_id.py`, `test_test_email.py`.

### 2.11 Infra
- **`Dockerfile` (novo):** base `python:3.12-slim` + `uv`; `CMD` roda
  `alembic upgrade head && uvicorn … --port 8000`.
- **`Makefile`:** alvos `migrate`/`migrate-new` (Alembic), porta 8000.
- **`pyproject.toml`:** build hatchling, `version=0.5.0`, deps SQLAlchemy/
  Alembic, sem mypy.

---

## 3. Alterações aplicadas neste repositório local

| Item | Ação |
| --- | --- |
| `app/**` | Substituído integralmente pela fonte da verdade (idêntico) |
| `tests/**` | Substituído integralmente (idêntico) |
| `alembic/` + `alembic.ini` | Copiados da fonte |
| `Dockerfile`, `Makefile`, `README.md`, `.env.example` | Copiados da fonte |
| `migrations/` (Aerich) | **Aposentada** (movida para backup, fora do projeto) |
| Dependências | `uv add sqlalchemy[asyncio] alembic asyncpg`; `uv remove tortoise-orm aerich` + `--dev mypy`; `uv sync` |

**Backup do estado anterior:** `/tmp/notify-local-backup.0dObf8/local-src-before-sync.tgz`
(inclui `migrations-aerich-removed/`).

---

## 4. Testes executados (sem mock de banco, dados reais)

1. **Suíte pytest contra Postgres real** (container efêmero `postgres:16-alpine`,
   `TEST_DATABASE_URL`): **40 passed**. O banco é real; só o IO de rede externo
   é isolado (design da própria suíte da fonte da verdade).
2. **Migrations Alembic reais** (`alembic upgrade head`): `0001→0002→0003` OK;
   4 tabelas + `alembic_version` criadas no schema `notify`, 5 templates seedados.
3. **Boot real do app + HTTP real** contra o Postgres real:
   - `/health`, `/ready`, `/status` (métricas reais) OK.
   - `GET /api/v1/templates` → 5 seeds; `POST` cria (id 6); `PUT` sobe versão →
     persistência confirmada via SQL direto.
   - `GET /api/v1/contacts`, `/logs`, `/logs/metrics` OK.
4. **Paridade com produção** (`http://10.1.30.20:8157`, somente leitura):
   mesma versão (0.5.0), mesmos slugs de template e mesmo formato de métricas.

> Fluxos de **envio real** (WhatsApp/Email/TTS) dependem dos microserviços
> `whats-api`/`mail`/`ai`/`profiles`, acessíveis apenas dentro da rede Compose
> do host remoto. Não foram disparados a partir desta máquina para **não
> enviar mensagens reais a destinatários reais**. Esses caminhos são cobertos
> pela suíte (banco real, IO externo isolado) e pelo serviço já em produção.

---

## 5. Pendência: `pyproject.toml` e `.env`

Ambos estão **deny-listed** para edição nas permissões locais
(`.claude/settings.json`).

- **`pyproject.toml`:** as **dependências** foram sincronizadas via `uv`
  (funcionalmente equivalentes). Resíduo estrutural ainda divergente da fonte:
  falta `[build-system]` (hatchling), `version` ainda `0.4.0`, seção
  `[tool.aerich]` obsoleta e `[tool.ruff.lint]` extra. Para espelhar 100%,
  liberar `Edit(./pyproject.toml)` ou colar o `pyproject.toml` da fonte.
- **`.env`:** não alterado. Para rodar/testar localmente foram usadas variáveis
  de ambiente (`DATABASE_URL`, `DATABASE_SCHEMA`, `TEST_DATABASE_URL`). O
  `.env.example` (atualizado) lista todas as chaves novas (Mailcow, Profiles,
  schema, etc.).

---

## 6. `CLAUDE.md` ficou desatualizado (recomendação)

A arquitetura real (fonte da verdade) contraria o `CLAUDE.md` atual:

- **Porta:** doc diz "somente porta 80"; real é **8000** (publicada em 8157).
- **Banco:** doc diz "cada serviço, seu banco / nunca conecte no banco de
  outro serviço"; real é **Postgres central compartilhado** com schema por
  serviço **e FK cross-schema para `auth.users`**.
- **Migrations:** doc cita Aerich; real é **Alembic**.

`CLAUDE.md` também está deny-listed. Recomendo atualizá-lo (ou liberar a
edição) para refletir SQLAlchemy/Alembic/Postgres central, porta 8000 e o
acoplamento com o schema `auth`.
