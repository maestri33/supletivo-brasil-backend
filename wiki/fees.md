# fees

## Função

Serviço FastAPI das **taxas de matrícula**. O **coordenador do polo** registra,
por aluno, uma taxa composta de **dois payouts PIX por QR Code** (BR Code):
um **à vista** e um **agendado**. Os pagamentos são executados pelo serviço
`asaas` (dono exclusivo da integração Asaas/PIX, §12) — o fees nunca fala com a
API Asaas direto. O status da taxa é **derivado** dos dois pagamentos e, quando
a parte à vista é paga, o acesso à plataforma fica **liberável**.

> **Escopo (§6):** o fees só guarda o status da taxa e emite notificações. Ele
> **não** libera acesso por conta própria nem chama `student`/`auth`/`enrollment`
> — quem precisa liberar acesso consulta o status do fees (`FIRST_PAID`/
> `FULLY_PAID`). `student_external_id` é opaco (UUID fornecido por quem chama),
> sem FK cross-schema, mesmo princípio do `asaas`.

## Status

**Funcional (green-field, criado 2026-05-24).** Stack canônica async.

- Stack: FastAPI + SQLAlchemy 2.0 **`AsyncSession`** + **asyncpg** + **Alembic** +
  **Pydantic v2** + **`httpx.AsyncClient`** + **structlog** (`fastapi-structured-logging`) +
  pydantic-settings.
- Verificação: `ruff check`/`format` limpos · `pytest` **13 passed**
  (sqlite+aiosqlite, asaas/notify stubbados) · `alembic upgrade head` validado via
  geração de SQL offline (DDL do schema `fees` + 2 tabelas + índices).
- `database_url` é **obrigatório** (sem default com credenciais — regra de
  segurança da Fase 1).

## Estrutura

`fees/app/` — achatado conforme §3 (pacote `app`).

```
fees/
├── app/
│   ├── main.py              # FastAPI; lifespan; health/ready/status; handler DomainError
│   ├── config.py            # Settings (.env); database_url obrigatório
│   ├── db.py                # async engine, Base, NAMING_CONVENTION, utcnow, get_session
│   ├── exceptions.py        # DomainError + NotFound/Conflict/ValidationError
│   ├── dependencies.py      # JWT (gate de coordenador via JWKS) + get_asaas_client
│   ├── api/
│   │   ├── authenticated/fees.py     # CRUD de taxas (role coordenador)
│   │   └── demilitarized/webhooks.py # callback de status do asaas
│   ├── models/              # fee, fee_payment (+ _mixins)
│   ├── schemas/             # Pydantic v2 (create/read/webhook)
│   ├── services/fee_service.py  # criação, derivação de status, aplicação de webhook
│   ├── integrations/        # asaas.py, notify.py (BaseClient + request_with_retry)
│   └── notify/              # handlers.py + messages/*.md (§11)
├── alembic/                 # env.py async + versions/ (revision 0001 cria o schema)
├── tests/                   # async (sqlite), asaas/notify stubbados
├── Dockerfile · Makefile · pyproject.toml · .env.example · README.md
└── .claude/                 # CLAUDE.md + memory/
```

## Endpoints

### `api/authenticated/fees.py` — `/api/v1/authenticated/fees` — tag `fees` (autenticados)

Exigem JWT RS256 válido com a role de coordenador (`COORDINATOR_ROLE`, default
`coordinator`); o JWKS vem do serviço `jwt`.

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/` | Cria a taxa: 2 payouts PIX (à vista + agendado). Dispara ambos no asaas. 409 se já há taxa ativa pro aluno |
| GET | `/` | Lista taxas (filtro `status`, paginado) |
| GET | `/student/{student_external_id}` | Última taxa de um aluno |
| GET | `/{fee_id}` | Taxa por id (com os dois pagamentos) |

### `api/demilitarized/webhooks.py` — `/api/v1/webhook` — tag `webhooks` (desmilitarizado, §5)

Consumido só pelo serviço `asaas` (out-webhook interno); sem auth (§5).

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/asaas-payout` | Recebe `{payment_id, kind, external_id, status}`; correlaciona por `payment_id`, atualiza a parcela, re-deriva a taxa e notifica. Aceita o ping `ASAAS_APP_ONBOARDING`. Idempotente; `payment_id` desconhecido → 202 ignorado |

### Saúde — `/health` `/ready` `/status` (convenção v7m)

## Dados

**Schema Postgres:** `fees`. **PK = UUID** (`postgresql.UUID(as_uuid=False)`,
gerada na app via `uuid4`). Datas/hora em **`timestamptz`** (UTC).

| Tabela | PK | Campos-chave | Unique/Index |
|--------|----|--------------|--------------|
| `fee` | `id` (UUID) | `student_external_id`, `coordinator_external_id`, `status`, `description` | idx: student_external_id, coordinator_external_id, status |
| `fee_payment` | `id` (UUID) | `fee_id`, `kind` (upfront\|scheduled), `payment_id`, `qrcode_payload`, `amount`, `scheduled_date`, `status`, `asaas_id`, `last_error` | UNIQUE: payment_id; idx: fee_id, status |

Referências por **valor**, sem FK: `fee_payment.fee_id` → `fee.id`;
`fee.student_external_id`/`coordinator_external_id` são UUIDs opacos. `payment_id`
é determinístico (`fee-<fee_id>-<kind>`) — é a Idempotency-Key enviada ao asaas e
a chave de correlação do webhook.

### Máquina de estado da taxa (`fee.status`)

```
PENDING ─┬─ (parte à vista PAID) ──► FIRST_PAID ── (parte agendada PAID) ──► FULLY_PAID
         └─ (parte à vista FAILED/CANCELLED) ──► FAILED
```

- `FIRST_PAID` (e `FULLY_PAID`) = **acesso liberável**. A falha da parte agendada
  **não** rebaixa uma taxa já paga na 1ª parte (gera alerta ao coordenador).
- `fee_payment.status` espelha o status de payout do asaas
  (`SCHEDULED/QUEUED/SUBMITTING/SUBMITTED/PAID/AWAITING_BALANCE/FAILED/CANCELLED/NEEDS_RECONCILE`);
  `SUBMIT_ERROR` é marcador local de falha de rede ao chamar o asaas na criação.

### Idempotência (caminho do dinheiro)

A intenção (linhas no DB) é **commitada antes** de chamar o asaas. O `payment_id`
é determinístico, então um re-submit recebe `payment_id_already_exists` do asaas e
**nunca duplica** o pagamento. O webhook é idempotente (re-entregar o mesmo status
não re-notifica nem re-transiciona).

## Integrações (§12)

| Serviço | Client | Uso |
|---------|--------|-----|
| **asaas** | `integrations/asaas.py` (`httpx.AsyncClient`) | `POST /api/v1/payment/qrcode` (à vista), `POST /api/v1/payment/qrcode/scheduled` (agendado), `GET /api/v1/payment/{payment_id}` |
| **notify** | `integrations/notify.py` | `POST /api/v1/messages/send` — notificações de status (§11), sempre async (BackgroundTasks) |
| **jwt** | `dependencies.py` (JWKS) | `GET /.well-known/jwks.json` para validar o token do coordenador |

Falha de notificação é logada e **não** propaga (§12). O asaas deve apontar a
`internal_url_payout`/`internal_url_scheduling` para `/api/v1/webhook/asaas-payout`
do fees (config operacional do asaas, não-código).

## Notificações (§11)

A cada transição, BackgroundTask assíncrona:
- `FIRST_PAID` → aluno: acesso liberado (TTS).
- `FULLY_PAID` → aluno: taxa quitada.
- parcela `FAILED/CANCELLED` → coordenador: pagamento falhou, agir.

> Pendência conhecida (§11): lembrete por inatividade (aluno parado em `PENDING`)
> exigiria um worker agendado — fora do escopo desta primeira versão.

## Tipos de endpoint (§5)

`authenticated/fees` são **autenticados** (JWT + role coordenador).
`demilitarized/webhooks` é **desmilitarizado** (só o app `asaas` chama, §5).

## Dependências do ecossistema (a confirmar quando os serviços existirem)

- **role `coordinator`**: nome em `.env` (`COORDINATOR_ROLE`) — alinhar com o
  serviço `roles` quando ele formalizar os papéis.
- **`student`/`hub`/`coordinator`** ainda não existem (só `TODO`); o fees é
  self-contained e não depende deles em runtime (external_id opaco).
