# promoter

## Função
Representa o **promotor** — o ex-candidato que passou pelo `training` e foi
aprovado na entrevista com o **coordenador do polo**. O promotor divulga um
**link de captação** (`<landing>/ref=<external_id>`) e acompanha seus **leads** e
**comissões**. É um serviço **enxuto e agregador**: não tem funil, não duplica os
domínios de `lead`, `commissions` ou `roles` — só persiste sua identidade, valida
o `ref` e expõe visões read-only (CONVENTION §6).

## Status
**Funcional (2026-05-25)** — green-field na stack canônica (SQLAlchemy 2.0 async +
asyncpg + Postgres schema `promoter` + Alembic). Espelha o app-modelo `candidate`.
ruff limpo, 16 testes passando, boot ok. `alembic upgrade head` requer Postgres
(migração `0001` cria o schema + tabela `promoters`).

**Pendências conhecidas (sem TODO órfão):**
- O serviço **`commissions` ainda não existe** (só spec/TODO). `GET /me/commissions`
  **degrada** para `available=false` + lista vazia (§12); não inventamos o contrato
  dele (§2). Quando existir, o client em `integrations/commissions.py` passa a
  responder sem mudança de chamada.
- O `lead` ainda não filtra leads por promoter no endpoint desmilitarizado; o
  promoter passa o filtro por query **e** aplica filtro defensivo client-side por
  `promoter_external_id`.

## Stack
Python 3.12 + uv · FastAPI · SQLAlchemy 2.0 async (`Mapped`/`mapped_column`) · asyncpg
· Alembic · Pydantic v2 + pydantic-settings · httpx.AsyncClient · structlog · pyjwt.

## Estrutura
`promoter/app/`: `main.py`, `config.py`, `db.py`, `exceptions.py`, `dependencies.py`,
`utils/logging.py`, `models/` (Promoter + PromoterStatus), `schemas/`, `services/`
(promoter, auth, leads, commissions, notifications), `integrations/` (auth, jwt,
roles, profiles, notify, lead, commissions), `api/{public,authenticated,demilitarized}/`
+ `api/router.py`. `alembic/` (env async + revisão `0001`), `tests/`, `pyproject.toml`,
`README.md`, `.claude/`.

## Modelo (schema `promoter`)
`promoters`: `id` (UUID, PK), `external_id` (UUID, único — é também o `ref`),
`status` (`active`/`suspended`), `hub_external_id` (UUID, nullable), `created_at`,
`updated_at`. Sem FK cross-schema: `external_id` é referência lógica ao `auth.users`.

## Endpoints

### `api/public/auth.py` — público (exposto)
| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/api/v1/public/check` | Verifica CPF/phone/external_id e dispara OTP (auth) |
| POST | `/api/v1/public/login` | Valida OTP (role `promoter`) e retorna JWT + status |
| POST | `/api/v1/public/refresh` | Renova tokens (jwt) |

> Sem `/register`: o promotor **não se auto-registra** — é criado pelo coordinator.

### `api/authenticated/me.py` — autenticado (JWT role `promoter`, promoter `active`)
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/v1/authenticated/me` | Dados do promoter + `ref_url` |
| GET | `/api/v1/authenticated/me/leads` | Leads atribuídos (agrega do `lead`, read-only) |
| GET | `/api/v1/authenticated/me/commissions` | Comissões (agrega do `commissions`; degrada) |

### `api/demilitarized/promoters.py` — interno (sem auth, §5)
| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/api/v1/demilitarized/promoters` | **Coordinator** cria o promoter (promove papel candidate→promoter, idempotente) |
| GET | `/api/v1/demilitarized/promoters` | Lista/filtra por hub/status |
| GET | `/api/v1/demilitarized/promoters/{external_id}` | Busca por external_id |
| GET | `/api/v1/demilitarized/validate-ref/{ref}` | **Lead** valida o `ref` da captação (valid só se `active`) |

## Fluxo de captação (fronteira §6)
A landing chama o **`lead` direto** com `ref=<external_id>`. O `lead` resolve o ref
chamando `GET /validate-ref/{ref}` do promoter; se válido, grava `promoter_external_id`
no lead. O promoter **não capta** — só valida e, depois, **agrega** os leads do
promotor em `/me/leads`.

## Criação do promoter
1. `coordinator` aprova a entrevista → `POST /demilitarized/promoters {external_id, hub_external_id?}`.
2. `get_or_create` (idempotente por `external_id`); se novo, **promove** `candidate→promoter`
   no `roles` (bloqueante: se `roles` falhar, não commita; coordinator repete).
3. commit → notifica (BackgroundTasks) o promotor (boas-vindas + link) e o hub.

## Notificações (§11)
Ao virar promotor: mensagem de boas-vindas com o link de captação ao próprio, e
aviso de "novo promotor" ao hub. Assíncronas (BackgroundTasks) e tolerantes a falha.

## Integrações (§12)
`auth` (check/login) · `jwt` (refresh/JWKS) · `roles` (promote) · `lead` (lista leads)
· `commissions` (lista comissões — degrada) · `notify` (mensagens) · `profiles`
(reservado). Toda config em `.env` (`*_BASE_URL`, `LANDING_BASE_URL`, `HUB_DEFAULT`).

## Rodar
```bash
cd promoter && uv sync
cp .env.example .env   # ajuste PROMOTER_APP_DB_URL
uv run alembic upgrade head
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
uv run pytest -q && uv run ruff check . && uv run ruff format .
```
