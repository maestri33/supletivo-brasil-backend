# Relatório de Sincronização — service `lead`

**Data:** 2026-05-22
**Fonte de verdade:** `root@10.1.30.20:/opt/v7m/services/lead/` (código externo/produção)
**Destino:** `/home/maestri33/backend/lead/` (cópia local, estava desatualizada)

Após a sincronização, a árvore local ficou **byte-for-byte idêntica** à remota
(`diff -rq` limpo, exceto `.env` local de teste e `.venv`).

---

## 1. Diferença global (a mudança estruturante)

O código local estava numa geração **anterior** do serviço. A diferença dominante
é uma **migração completa de ORM e de banco**:

| Aspecto | Local (antigo) | Remoto (fonte de verdade) |
|---|---|---|
| ORM | **Tortoise ORM** | **SQLAlchemy 2.0 async** (`Mapped`/`mapped_column`) |
| Banco | **SQLite** (`sqlite://db.sqlite3`, schema gerado em runtime) | **PostgreSQL** com schema dedicado `lead` |
| Migrations | nenhuma (`generate_schemas=True`) | **Alembic** (2 revisões: `0001`, `0002`) |
| Sessão | implícita (Tortoise global) | `get_session` (DI por request) + `async_session_maker` |
| `external_id` | `CharField(36)` (string) | `UUID` nativo do Postgres, **FK cross-schema → `auth.users.external_id`** |
| `status` | `CharEnumField` | `Enum` nativo Postgres (`lead.lead_status`) |
| Versão | `0.1.0` | `0.3.0` (app) / `0.2.0` (pyproject) |

Além do ORM, foi adicionado um **segundo meio de pagamento (PIX via Asaas)**
convivendo com o cartão (InfinitePay) já existente, com geração de **QR Code**,
**serving de mídia estática** e novos **templates de mensagem**.

---

## 2. Arquivos REMOVIDOS do local (obsoletos)

| Arquivo | Motivo |
|---|---|
| `app/models.py` | Substituído pelo pacote `app/models/` (SQLAlchemy). Continha models Tortoise. |
| `app/landing.html` | Rota `/` (FileResponse) foi removida do `main.py`. |
| `app/graphify-out/` | Saída gerada de ferramenta de grafo; servida pela rota `/graph`, também removida. Já estava no `.gitignore`. |

## 3. Arquivos NOVOS trazidos do remoto

**Infra / raiz (não existiam no local):**
- `pyproject.toml` — deps novas: `sqlalchemy[asyncio]`, `asyncpg`, `alembic` (saiu `tortoise-orm`).
- `uv.lock`, `Dockerfile` (roda `alembic upgrade head` antes do uvicorn), `alembic.ini`
- `alembic/env.py` + `alembic/versions/0001_*`, `0002_*`
- `.env.example`, `.gitignore`

**App:**
- `app/db.py` — engine async, `Base`, `metadata` com schema, naming convention, stub `auth.users`, `get_session`.
- `app/models/` — pacote: `__init__.py`, `_mixins.py` (TimestampMixin), `lead.py`, `checkout.py`, `message.py`.
- `app/integrations/asaas.py` — cliente PIX (charges) espelhando o `InfinitePayClient`.
- `app/tools/qrcode.py` — salva QR PNG (base64→arquivo), monta data URI e URL absoluta.
- `app/routers/public/docs.py` — router de documentação da API.
- `app/docs/api_guide.md`
- Templates de mensagem PIX: `checkout_lead_pix.md`, `checkout_lead_pix_qr.md`,
  `checkout_promoter_pix.md`, `lead_receipt_pix.md`, `lead_receipt_cc.md`.

## 4. Arquivos ALTERADOS (17)

- **`app/config.py`** — muitos settings novos: `DATABASE_URL`, `DATABASE_SCHEMA`,
  `ASAAS_BASE_URL`, `LEAD_PUBLIC_BASE_URL`, `PIX_DEFAULT_*`, `MEDIA_DIR`,
  `NOTIFY_CALLBACK_URL`, `LEAD_CONTACT_POLL_*`, `CORS_ORIGINS`, `SERVICE_NAME`,
  `APP_VERSION`, `LOG_LEVEL`.
- **`app/main.py`** — removido Tortoise/`load_dotenv`/landing/graph; adicionado
  `engine.dispose()` no shutdown, **CORS**, **mount `/api/v1/public/media`** (StaticFiles),
  router de docs, `/status` enriquecido (versão/uptime/env).
- **`app/dependencies.py`** — JWT agora retorna `UUID`; `_require_status` aceita
  múltiplos status; `require_checkout` aceita `CHECKOUT|COMPLETED` (polling sem 403);
  usa `get_session` + `select`.
- **`app/integrations/notify.py`** — `send_message` ganha `max_retries=1` (POST não idempotente).
- **`app/notify/handlers.py`** — `notify_lead_captured` com polling configurável +
  TTS + `{{first_name}}`; skip de promoter sentinel; `notify_lead_completed` recebe
  `amount_cents` e roteia template PIX vs CC.
- **`app/notify/messages/lead_captured.md`** — copy nova com `{{first_name}}`.
- **`app/routers/authenticated/{captured,checkout,completed,waiting}.py`** —
  SQLAlchemy; `captured` ganha branch **PIX síncrono** (retorna `pix_payload`+`qr_url`)
  vs **cartão assíncrono**; regra de imutabilidade de nome (CPFHub); `checkout`
  retorna bloco `pix`.
- **`app/routers/demilitarized/{leads,checkouts}.py`** — SQLAlchemy; `CheckoutOut`
  ganha campos PIX (`payment_method`, `provider`, `provider_payment_id`,
  `qrcode_*`, `due_date`).
- **`app/routers/demilitarized/webhooks.py`** — SQLAlchemy; **novo webhook
  `POST /api/v1/webhook/asaas-charge`** (onboarding ack, guarda provider, PAID→completed);
  infinitepay protegido contra entrega fora de ordem; dispara `notify_lead_completed`.
- **`app/routers/public/auth.py`** — SQLAlchemy; `promoter_external_id` virou **`ref`**
  na interface pública; tratamento de erro 4xx/502 no `/check`.
- **`app/tools/create_checkout.py`** — refatorado: `create_checkout_for_lead`
  (cartão, BG) + **`create_pix_checkout_for_lead`** (PIX, síncrono) + `PixCheckoutError`;
  mensageria com QR anexado via data URI.
- **`app/tools/messaging.py`** — `notify_and_track` grava `status="pending"` e só
  vira `sent` via webhook callback; grava `failed`/`skipped` em falha (audit trail);
  aceita `media_url`/`title`/`flags`/`event`.
- **`app/tools/webhooks.py`** — skip de promoter sentinel (`00000000-...`) para não
  violar FK em `auth.users`.

---

## 5. Modelo de dados resultante (schema `lead`)

- `lead.leads` — `id`, `external_id (uuid, FK auth.users)`, `status (enum)`,
  `promoter_external_id (uuid)`, timestamps.
- `lead.checkouts` — campos cartão (infinitepay) + campos PIX (asaas:
  `payment_method`, `provider`, `provider_payment_id`, `qrcode_payload`,
  `qrcode_image`, `due_date`), `is_paid`, timestamps.
- `lead.messages` — log de mensagens notify (`direction`, `channel`, `status`,
  `event`, `meta jsonb`).
- FK cross-schema para `auth.users.external_id` em todas as tabelas.

---

## 6. Teste de ponta a ponta (dados reais, sem mock)

Ambiente: Postgres 16 real em container dedicado (`lead-e2e-pg`, porta 5544) com
schemas `auth` (+ stub `auth.users`) e `lead`. App rodando via `uvicorn` real.

| # | Validação | Resultado |
|---|---|---|
| 1 | `import app.main` (build do app + todos routers) | OK — 31 rotas |
| 2 | `alembic upgrade head` no Postgres real (0001+0002) | OK — tabelas, enum, FK, índices criados |
| 3 | `GET /health`, `/ready`, `/status` | OK (`/status` v0.3.0 + uptime) |
| 4 | `GET /api/v1/demilitarized/leads` (+ por id) | OK — serialização UUID/enum/timestamps |
| 5 | `PATCH /demilitarized/leads/{id}` (status) | OK — persistido, `updated_at` auto-bump |
| 6 | `GET /demilitarized/checkouts/{id}` (campos PIX) | OK — todos os campos novos |
| 7 | `POST /webhook/asaas-charge` onboarding ping | OK — 202, sem efeito colateral |
| 8 | `POST /webhook/asaas-charge` guarda checkout ausente | OK — 202 `checkout_missing` |
| 9 | `POST /webhook/asaas-charge` **PAID** | OK — lead→`completed`, checkout `is_paid=true` |
| 10 | Pipeline notify (BG) + audit `lead.messages` | OK — 2 rows `failed` com template PIX correto |

**Cobertura por dados reais:** banco Postgres real, ORM real, HTTP real, migrations
reais. No teste 10, as mensagens ficam `failed` porque os microsserviços externos
(`notify`/`profiles`) **não são alcançáveis** a partir da máquina local (IPs
`10.10.10.x` da rede interna do host remoto) — o que é o comportamento correto e
**não foi mockado**.

### Não testável localmente (requer o service mesh v7m, sem mock)
Fluxos que dependem dos serviços externos (`auth`, `jwt`, `notify`, `profiles`,
`infinitepay`, `asaas`), inalcançáveis fora da rede do host remoto:
- `POST /api/v1/public/{check,register,login,refresh}`
- `POST /api/v1/authenticated/captured` (criação de checkout PIX/cartão)

Esses caminhos foram validados **estaticamente** (import + build do app + assinaturas),
mas a execução real exige rodar dentro da rede onde os serviços respondem
(ex.: no próprio host `10.1.30.20` via docker compose).

---

## 7. Como rodar localmente

```bash
# 1. deps
uv sync
# 2. configurar .env (já criado um de teste apontando para lead-e2e-pg:5544)
# 3. migrations
uv run alembic upgrade head
# 4. servir
uv run uvicorn app.main:app --host 127.0.0.1 --port 8137
```

> O `.env` local criado para o teste usa `DATABASE_URL` do container `lead-e2e-pg`
> e IPs de serviço de exemplo (inalcançáveis). Para uso real, injete as env vars
> do ambiente v7m (em produção isso vem do docker compose). `.env` está no `.gitignore`.

## 8. Backup
A versão local anterior foi preservada em `/tmp/lead-local-backup/` antes da sobrescrita.
