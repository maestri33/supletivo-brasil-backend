# infinitepay — middleware de checkout

Middleware FastAPI sobre a **API de checkout da InfinitePay**: cria links de
pagamento, recebe o webhook server-to-server de confirmação e reenvia eventos
internos via fila de saída com retry. É o **único serviço autorizado** a
integrar com a InfinitePay (CONVENTION §12).

> **Fonte de verdade:** [`wiki/infinitepay.md`](../wiki/infinitepay.md) —
> arquitetura, fluxo de pagamento, modelo de dados, atomicidade e segurança do
> webhook em detalhe. Este README cobre só o necessário para rodar o serviço.
> Doc interativa: `/docs` (Swagger) e `/redoc` no container.

## Stack

| Camada | Ferramenta |
|---|---|
| Runtime | Python 3.12 + `uv` |
| API | FastAPI + uvicorn |
| ORM | SQLAlchemy 2.0 async (`AsyncSession`) + asyncpg |
| Migrações | Alembic |
| Schema Postgres | `infinitepay` (PK UUID, datas `timestamptz`) |
| Validação/Config | Pydantic v2 + pydantic-settings (`.env`) |
| HTTP client | httpx.AsyncClient |
| Logs | structlog |
| Cripto | cryptography (Fernet — cifra o `external_id` do webhook) |

## Como rodar

```bash
make install                  # uv sync
cp .env.example .env          # preencha os segredos (ver abaixo)
uv run alembic upgrade head   # cria schema infinitepay + tabelas
make dev                      # uvicorn em :80 com --reload  (make run = sem reload)
make test                     # uv run pytest (sqlite+aiosqlite)
make lint                     # ruff check app/
```

> O serviço sobe na **porta 80** (ver `Makefile`). A migração cria o schema
> `infinitepay` sozinha (`alembic/env.py`, `CREATE SCHEMA IF NOT EXISTS`).

## Variáveis de ambiente

Copie `.env.example` → `.env`. Resumo (fonte autoritativa: `app/config.py`):

| Var | Default | Descrição |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://…` | Postgres central async — **defina em prod** |
| `DATABASE_SCHEMA` | `infinitepay` | schema do serviço |
| `INFINITEPAY_BASE_URL` | `https://api.checkout.infinitepay.io` | API externa |
| `HTTP_TIMEOUT` | `15` | timeout (s) das chamadas externas |
| `WORKER_POLL_SECONDS` | `5` | intervalo do worker de fila |
| `RUN_INLINE_WORKER` | `true` | roda o worker no lifespan da API |
| `WEBHOOK_ENCRYPTION_KEY` | — | **Fernet** p/ cifrar `external_id` na URL do webhook |
| `INFINITEPAY_HANDLE` … `_PUBLIC_API_URL` | — | defaults da loja p/ `POST /checkout` (handle, price, quantity, description, redirect_url, backend_webhook, public_api_url) |
| `AI_BASE_URL` | `http://ai:8000` | app `ai` central (recibo + triagem de fraude) |
| `AI_FEATURES_ENABLED` | `false` | liga as features de IA (fallback se off/falha) |
| `AI_MODEL` / `AI_PRO_MODEL` | `deepseek-v4-flash` / `-pro` | modelos via app `ai` |

> Gere a Fernet key:
> `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

## Endpoints (resumo)

| Tipo (§5) | Rota | O quê |
|---|---|---|
| desmilitarizado | `POST/GET /api/v1/checkout` | cria / lista / consulta checkouts |
| público externo | `POST /api/v1/webhook?external_id=<cifrado>` | confirmação server-to-server da InfinitePay (confirma out-of-band via `payment_check` antes de marcar pago) |
| desmilitarizado | `GET /health`, `GET /ready` | liveness / readiness |

Catálogo completo, fluxo de pagamento e regras de segurança:
[`wiki/infinitepay.md`](../wiki/infinitepay.md).
