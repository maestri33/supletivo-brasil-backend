# notify

Servico de notificacao multicanal do ecossistema v7m. Roda em LXC/VM no
Proxmox, schema `notify` no Postgres central `v7m`.

Stack: **Python 3.12 + FastAPI + SQLAlchemy 2 async + Alembic + uv +
structlog**, porta 8000 interna (mapeada para `8157` no host via
`docker-compose.yml`).

Dispara mensagens via:

- **E-mail** — Mail Merge API (`app/integrations/smtp.py`) → service `mail`
  (Mailcow self-hosted em `mail.v7m.org`, SPF+DKIM+DMARC validados).
- **WhatsApp** — Evolution GO v2 (`app/integrations/whatsapp.py`) →
  service `whats-api` (Baileys, instancia `default`).
- **AI** — `app/integrations/ai.py` agrega text/image/tts → service `ai`
  (DeepSeek v4 Pro, Gemini imagem, ElevenLabs TTS).

> **Filosofia.** Cada microservico e' **generico, reutilizavel, simples
> e completo**. Schema proprio, comunicacao com outros services
> exclusivamente via HTTP/fila/webhook (nunca via SQL cross-schema —
> excecao: FK para `auth.users.external_id`).

---

## Endpoints

### Saude

| Path | Resposta |
|---|---|
| `GET /health` | `{"status":"ok","service":"notify"}` — liveness |
| `GET /ready` | mesmo + `db` — readiness (testa DB) |
| `GET /status` | mesmo + `uptime_seconds` + `metrics` (24h snapshot) |

### Contactos

| Verbo | Path | Descricao |
|---|---|---|
| `GET` | `/api/v1/contacts/check?phone=...&email=...` | consulta existencia local + valida no WhatsApp/MX |
| `POST` | `/api/v1/contacts` | cria contacto (`external_id` UUID + phone/email) |
| `GET` | `/api/v1/contacts` | lista paginavel |
| `GET` | `/api/v1/contacts/{external_id}` | busca por external_id |
| `PATCH` | `/api/v1/contacts/{external_id}/email` | adiciona/atualiza email |
| `DELETE` | `/api/v1/contacts/{external_id}` | remove |

### Mensagens

| Verbo | Path | Descricao |
|---|---|---|
| `POST` | `/api/v1/messages/send` | envia mensagem multicanal (WhatsApp + Email). Aceita `template_slug` opcional. |
| `POST` | `/api/v1/messages/test-email` | diagnostico de deliverability — nao cria Contact/Message |
| `GET` | `/api/v1/messages?contact_id=&limit=&offset=` | lista mensagens |
| `GET` | `/api/v1/messages/{id}` | busca mensagem |

### Templates (multi-slug, DB-backed)

| Verbo | Path | Descricao |
|---|---|---|
| `GET` | `/api/v1/templates?only_active=&limit=` | lista templates (sem o HTML) |
| `POST` | `/api/v1/templates` | cria por `html` direto OU `instruction` (IA edita a partir do `default`) |
| `GET` | `/api/v1/templates/{slug}` | busca; fallback automatico para `default` se slug nao existir |
| `PUT` | `/api/v1/templates/{slug}` | atualiza HTML/name/is_active OU usa `instruction` (IA) |
| `DELETE` | `/api/v1/templates/{slug}` | remove (bloqueado para `default` — use `is_active=false`) |

Seeds aplicados pela migration `0003`: `welcome`, `checkout`, `receipt`,
`parabens` (variantes do `default` com paletas distintas).

### Logs e metricas

| Verbo | Path | Descricao |
|---|---|---|
| `GET` | `/api/v1/logs?message_id=&limit=` | lista geral |
| `GET` | `/api/v1/logs/by-external-id/{eid}` | timeline por usuario (cobre logs antigos via JOIN com `message_id`) |
| `GET` | `/api/v1/logs/metrics?window_hours=24` | snapshot completo de mensagens + erros |

---

## Como rodar

### Via docker compose (recomendado — runtime real)

```bash
# Do monorepo:
cd /Users/maestri33/Documents/Workspace/v7m
docker compose up -d --build notify

# Migrations rodam automaticamente no entrypoint (alembic upgrade head)
curl http://localhost:8157/status
```

### Local (dev sem container)

```bash
cp .env.example .env          # ajustar DATABASE_URL para localhost
uv sync
make migrate                  # alembic upgrade head
make dev                      # uvicorn --reload :8000
```

---

## Comandos

```bash
make install                  # uv sync
make dev                      # uvicorn --reload :8000
make run                      # uvicorn workers=2 (sem reload)
make test                     # pytest (ver "Testes" abaixo)
make lint                     # ruff check
make fmt                      # ruff format + fix
make migrate                  # alembic upgrade head
make migrate-new msg='descr'  # alembic revision --autogenerate -m 'descr'
make clean                    # remove caches
```

---

## Testes

Suite SQLAlchemy 2 + Postgres real. Tres fontes em fallback graceful no
[`tests/conftest.py`](tests/conftest.py):

1. **`testcontainers[postgres]`** (recomendado — zero config quando
   docker disponivel)
2. **Env var `TEST_DATABASE_URL`** — CI ou DB dedicado
3. Nenhuma → `pytest.skip` com instrucoes claras

```bash
# Opcao 1: instala testcontainers (uma vez)
uv add --dev testcontainers[postgres] asgi-lifespan
make test

# Opcao 2: aponta para um Postgres ja em pe
docker exec v7m-postgres psql -U v7m -d postgres -c "CREATE DATABASE v7m_test;"
TEST_DATABASE_URL='postgresql+asyncpg://v7m:v7m@localhost:5432/v7m_test' \
  uv run pytest -q
```

40 testes cobrem CRUD de contactos, templates multi-slug,
`/messages/test-email`, timeline por usuario, /status com metricas, e os
endpoints de saude. WhatsApp/DNS/SMTP/DeepSeek sao mockados via
fixture autouse `_isolate_external_io`.

---

## Banco

**Postgres central `v7m`, schema `notify`.** Migrations em `alembic/`:

| Rev | Descricao |
|---|---|
| 0001 | tabelas iniciais (`contacts`, `messages`, `logs`) + FK cross-schema para `auth.users.external_id` |
| 0002 | tabela `templates` (multi-slug) + coluna `logs.external_id` (FK auth.users) |
| 0003 | seeds dos templates de contexto (`welcome`, `checkout`, `receipt`, `parabens`) |

> **Cross-schema FK permitida apenas para `auth.users.external_id`** —
> nenhum outro schema e' acessado diretamente. Dados de outros services
> sao buscados via API.

---

## Configuracao (env vars)

| Variavel | Descricao | Default |
|---|---|---|
| `SERVICE_NAME` | nome | `notify` |
| `ENV` | `dev`/`staging`/`prod` | `dev` |
| `LOG_LEVEL` | nivel structlog | `INFO` |
| `PORT` | porta uvicorn interna | `8000` |
| `DATABASE_URL` | conexao Postgres | `postgresql+asyncpg://v7m:v7m@postgres:5432/v7m` |
| `DATABASE_SCHEMA` | schema do servico | `notify` |
| `PUBLIC_BASE_URL` | URL publica (`/media`) | `http://notify:8000` |
| `DMZ_BASE_URL` | URL interna (DMZ — Evolution baixa midia) | `http://notify:8000` |
| `SMTP_API_BASE_URL` | endpoint do service `mail` | `http://mail:8000` |
| `SMTP_HOST`/`PORT`/`USER`/`PASS` | credenciais SMTP (mail merge configura no startup) | — |
| `WHATSAPP_API_BASE_URL` | Evolution GO | `http://whats-api:8080` |
| `WHATSAPP_GLOBAL_API_KEY` | chave global Evolution | — |
| `WHATSAPP_INSTANCE_NAME` | instancia (chip) | `default` |
| `AI_BASE_URL` | service `ai` (text/image/tts) | `http://ai:8000` |
| `DEEPSEEK_API_KEY` | (legacy — usado para edicao de template via IA) | — |
| `ELEVENLABS_API_KEY` | (legacy) | — |
| `GEMINI_API_KEY` | (legacy) | — |

Ver [`.env.example`](.env.example) para a lista completa.

---

## Integracoes ativas

| Modulo | Para que |
|---|---|
| `app/integrations/http_client.py` | httpx async compartilhado com retry |
| `app/integrations/smtp.py` | service `mail` (mail merge CSV + Jinja2) |
| `app/integrations/whatsapp.py` | Evolution GO v2 (texto/midia/audio/sticker) |
| `app/integrations/ai.py` | service `ai` (texto/imagem/tts) |
| `app/integrations/deepseek.py` | DeepSeek direto (edicao de template via IA) |
| `app/integrations/elevenlabs.py` | TTS (legacy, prefira `ai.py`) |
| `app/integrations/gemini.py` | imagem (legacy, prefira `ai.py`) |

Detalhes de cada integracao (endpoints, auth, retry) estao em
[`.claude/memory/integrations.md`](.claude/memory/integrations.md).

---

## Contexto operacional

- Roda em LXC ou VM no Proxmox.
- Esta em **zona desmilitarizada** — sem firewall entre services internos.
- Ambiente e' **dev**, mas **infra e real**: portas, hosts, banco, chip
  WhatsApp.
- **Seguranca nao e prioridade hoje** — sem auth, CORS aberto, sem
  rate-limit. Sera coberto em passe explicito de "agora trava isso".
