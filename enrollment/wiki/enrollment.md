# enrollment — Serviço de matrícula

Fonte da verdade funcional do serviço `enrollment`. Atualizada em 2026-05-27.

## O que faz

Quando um **lead paga** (evento `lead.completed` vindo do serviço `lead`), o
`enrollment` orquestra a coleta de dados de matrícula até o aluno ser liberado
pelo coordenador do polo e virar **student**. É o estágio entre "lead pagou"
e "aluno na plataforma".

Funil em 5 etapas (matriculando) + 1 etapa (coordenador):

```
lead.completed (webhook)
        │
        ▼
   STARTED ──▶ PROFILE ──▶ ADDRESS ──▶ DOCUMENTS (RG) ──▶ EDUCATION ──▶ SELFIE
                                                                          │
                                                                          ▼
                                                              AWAITING_RELEASE
                                                                          │
                                                          coordenador POST release
                                                                          │
                                                                          ▼
                                                                     COMPLETED
```

Cada etapa de matriculando é um POST autenticado em `/api/v1/authenticated/<phase>`
que valida o status anterior, chama o serviço dono do dado (delegação por HTTP,
CONVENTION §6), avança o status, faz commit e dispara notificação async.
**Dados educacionais** são a única exceção: persistidos no schema próprio
`enrollment.educational_data` (PRD §4).

## Quem chama / quem chamamos

### Recebe HTTP (de outros apps)

| Endpoint | Quem chama | Tipo |
|----------|-----------|------|
| `POST /api/v1/webhook/new/{external_id}` | `lead` ao atingir status `completed` | Desmilitarizado (webhook interno) |
| `GET /api/v1/enrollments/{external_id}` | `coordinator`, `staff`, dashboards internos | Desmilitarizado (audit) |
| `GET /api/v1/events` + `GET /api/v1/events/{id}` | auditoria interna | Desmilitarizado |
| `POST /api/v1/authenticated/profile` | matriculando (JWT role `enrollment`) | Autenticado |
| `POST /api/v1/authenticated/address` (+ `/cep/{cep}`) | matriculando | Autenticado |
| `PUT /api/v1/authenticated/documents/rg` | matriculando | Autenticado |
| `POST /api/v1/authenticated/documents/images/{slot}` | matriculando (`rg_foto_frente\|verso`) | Autenticado |
| `POST /api/v1/authenticated/documents/submit` | matriculando | Autenticado |
| `POST /api/v1/authenticated/education` | matriculando | Autenticado |
| `POST /api/v1/authenticated/selfie` | matriculando | Autenticado |
| `POST /api/v1/authenticated/enrollments/{ext_id}/release` | coordenador (JWT role `coordinator`) | Autenticado |

### Chama HTTP (de outros apps)

| Serviço | Para quê | Bloqueante? |
|---------|----------|-------------|
| `roles` | Promove `lead→enrollment` no webhook + `enrollment→student` no release | **Sim** (CONVENTION §7 nota — promoção de papel é intencionalmente bloqueante) |
| `profiles` | PATCH dos dados pessoais (etapa profile) | Sim (falha → 4xx propaga) |
| `address` | Cria endereço + vincula CEP (etapa address); consulta CEP | Sim |
| `documents` | PUT do RG + upload das fotos (RG + selfie) | Sim |
| `ai` | Validação heurística da selfie via `/image/vision` | **Não** (best-effort — selfie passa se `ai` cair, CONVENTION §13) |
| `notify` | Aviso ao matriculando a cada avanço de status + aviso ao coordenador quando completa | **Não** (async via `BackgroundTasks`, falha não bloqueia) |
| `jwt` | Validação RS256+JWKS (cache 5min) das chamadas autenticadas | Sim |

### NÃO chama (TODO `§1 não tocar`)

- `asaas`, `infinitepay`: pagamento já aconteceu no `lead`.
- `auth`: não criamos/alteramos usuário (já existe quando o webhook chega).
- `mail`: notificações passam por `notify` (canal pode ser email, mas a decisão é do notify).

## Schema

```
enrollment.enrollments
  id                       UUID PK
  external_id              UUID UNIQUE     ─ referência lógica a auth.users (sem FK §4)
  status                   String(24)      ─ started|profile|address|documents|education|selfie|awaiting_release|completed
  promoter_external_id     UUID NULL       ─ promotor que indicou o lead
  hub_external_id          UUID NULL       ─ hub do promotor (preencher quando hub service existir)
  created_at, updated_at   timestamptz

enrollment.educational_data            ─ 1:1 com enrollments via FK CASCADE
  id                       UUID PK
  enrollment_id            UUID UNIQUE FK → enrollments.id
  last_year_studied        Integer NOT NULL  ─ "último ano estudado" (TODO §1)
  last_year_date           Date NOT NULL     ─ "quando foi"
  last_school              String(255)       ─ "em que escola foi"
  created_at               timestamptz

enrollment.enrollment_events           ─ log auditivo (legado + libertação)
  id                       BIGINT PK autoincrement
  external_id              UUID
  event                    String(64)        ─ ex: "lead.completed", "enrollment.completed"
  promoter_external_id     UUID NULL
  payload                  JSONB             ─ dados da plataforma no release (platform_id, classe, notas, coordenador)
  received_at              timestamptz
  processed_at             timestamptz NULL
```

## Máquina de estados

| De | Para | Disparo |
|----|------|---------|
| (none) | `started` | webhook `lead.completed` (cria Enrollment + promove role `lead→enrollment`) |
| `started` | `profile` | `POST /authenticated/profile` |
| `profile` | `address` | `POST /authenticated/address` |
| `address` | `documents` | `POST /authenticated/documents/submit` (após PUT dados + 2 imagens) |
| `documents` | `education` | `POST /authenticated/education` |
| `education` | `selfie` | `POST /authenticated/selfie` (transição interna; passa direto pra próxima) |
| `selfie` | `awaiting_release` | mesmo POST `/authenticated/selfie` (PRD §5.9) |
| `awaiting_release` | `completed` | `POST /authenticated/enrollments/{ext_id}/release` (coordenador promove `enrollment→student`) |

Progressão é **unidirecional e sequencial**. POST fora de ordem retorna 403
com a mensagem "Status 'X' — requer 'Y'".

## Idempotência

- **Webhook** (`lead.completed`): dedup por `(external_id, event)` na tabela `enrollment_events`. Reenviar = `already_exists: true`, mesmo `enrollment_id`. Promoção de role é checada (`get_roles` antes do `up/`) para não levantar 422 quando já está em `enrollment`.
- **Endpoints do funil**: cada um avança exatamente 1 status. Reenviar no mesmo status: `profiles/address/documents` chamam o serviço dono que é responsável por idempotência (PATCH é naturalmente idempotente; `address.create_address` cria nova linha — TODO de dedup futuro). `education` substitui em memória se já existir. **Não retrocede.**
- **Release**: gate `awaiting_release`, fora disso retorna 409 com code `INVALID_STATUS`.

## Notificações disparadas

`app/notify/messages/*.md` documenta o conteúdo.

| Evento | Destinatário | Quando |
|--------|--------------|--------|
| `enrollment_advance` (1 template, conteúdo por status) | matriculando | A cada `POST /profile`, `/address`, `/documents/submit`, `/education`, `/selfie`, `/release` |
| `coordinator_awaiting_release` | coordenador do hub (best-effort enquanto `hub` service não existe — enviado ao `hub_external_id` se conhecido) | Quando selfie aceita → `awaiting_release` |

Todas são **async via BackgroundTasks** (CONVENTION §13) — falha não bloqueia.

## Decisões de design

1. **Role `enrollment` durante o funil.** O matriculando NÃO continua como `lead` durante a matrícula (diferente do `candidate`, que fica `lead` o funil inteiro). Promovido no webhook, despromovido no release. Isolamento de scope JWT.
2. **`external_id` na URL do `/release`** (estilo PRD §5.10), e não do JWT — porque o coordenador opera em nome de OUTRO usuário. As demais etapas pegam do JWT (estilo candidate).
3. **`educational_data` local**, não em `profiles`. Por quê? Dado de domínio específico de matrícula que `profiles` (serviço genérico de "dados pessoais") não modela. PRD §4.
4. **RG obrigatório** (não CNH). TODO original: "sim obrigatório RG". O slot CNH do `documents` é ignorado nesta etapa.
5. **Selfie best-effort no `ai`.** Falha do `ai` (timeout/down) NÃO bloqueia — aceita a selfie e segue. CONVENTION §13. Imagem que `ai/vision` descreve sem termos humanos (sem "pessoa", "rosto", "olhos"...) é rejeitada com 422.
6. **Promoção de role no webhook é bloqueante.** Se `roles` cai, o webhook retorna 502 e o `lead` retenta. Sem role correta, o matriculando não autentica no funil — então não tem como ser best-effort. CONVENTION §7 nota.

## Como rodar

```bash
# Local com Postgres compartilhado de dev
TEST_DATABASE_URL=postgresql+asyncpg://supletivo:supletivo_dev@localhost:5433/supletivo \
  uv run pytest

# Container
docker compose -f docker-compose.dev.yml up -d --build enrollment
curl http://localhost:8009/health
```

## Pendências conhecidas

1. **Resolução do coordenador** depende do serviço `hub` (não existe ainda). Hoje a notificação `coordinator_awaiting_release` envia ao `hub_external_id` do agregado se conhecido, senão só loga. Quando `hub` existir: `promoter → hub → coordinator`.
2. **`address.create_address` não é idempotente.** Reenviar a etapa cria uma nova linha em `address` — o `address` precisa lidar com isso (TODO no app `address`, não aqui).
3. **CORS_ORIGINS=*** em dev/staging. Legado herdado; tem que apertar em prod via env.
4. **Tabela `educational_data` não tem `updated_at`.** Decisão intencional (matriculando só envia uma vez), mas se virar mutável, precisa de migração.
5. **Pre-existente, corrigido nesta sessão:** `alembic/env.py` tinha `settings.DATABASE_URL` (maiúsculo) que quebrava o `alembic upgrade head` no boot do container.

---

**Última atualização:** 2026-05-27. **Status:** funcional, smoke + 23 testes E2E verdes, aprovado para teste em dev. Quando virar produção, atualizar este arquivo.
