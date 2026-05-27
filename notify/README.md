# notify

Microsserviço de notificações multicanal (WhatsApp + e-mail). Recebe pedidos de
envio de outros serviços, processa em background (Redis + RabbitMQ), persiste
logs de auditoria e gerencia contatos, templates HTML e arquivos de mídia. Doc
completa: `../wiki/notify.md`.

## Rodar

```bash
cd notify/notify           # aninhamento notify/notify/app (desvio §3)
uv sync
cp .env.example .env       # ajuste DATABASE_URL, REDIS_URL, RABBITMQ_URL
uv run alembic upgrade head
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Testes / lint

```bash
uv run pytest -q           # health, contacts, logs, templates, metrics
uv run ruff check . && uv run ruff format --check .
```

## Variáveis (`.env`)

| Var | Obrigatória | Descrição |
|-----|:-:|-----------|
| `DATABASE_URL` | ✅ | Postgres async (`postgresql+asyncpg://...`) |
| `REDIS_URL` | ✅ | Redis para cache/pub-sub |
| `RABBITMQ_URL` | | RabbitMQ para mensageria |
| `SMTP_*` | | Config SMTP para e-mail |
| `AI_BASE_URL` | | URL do serviço `ai` (templates IA) |

## Endpoints (todos desmilitarizados)

- **Messages:** `POST /api/v1/messages/send`, `GET /`, `GET /{id}`, `POST /test-email`
- **Contacts:** `POST/GET /api/v1/contacts`, `GET/CHECK/DELETE /{external_id}`
- **Templates:** `POST/GET /api/v1/templates`, `GET/PUT/DELETE /{slug}`
- **Logs:** `GET /api/v1/logs`, `GET /by-external-id/{id}`, `GET /metrics`
- **WhatsApp:** `GET /api/v1/whatsapp/profile/{id}`, `GET /profiles`
- **Saúde:** `/health`, `/ready`, `/status`
