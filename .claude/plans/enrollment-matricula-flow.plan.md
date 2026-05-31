# Plan: Enrollment — Abertura da matrícula (milestone 1)

**Source PRD**: `.claude/prds/enrollment-matricula-flow.prd.md`
**Selected Milestone**: 1 — Abertura da matrícula
**Complexity**: Small–Medium

## Summary
Criar o **agregado de matrícula** (`enrollment.enrollments`, PK UUID §4) que hoje
não existe: o serviço só loga `enrollment_events`. Ao receber o webhook
`lead.completed`, além de persistir o evento, o serviço passa a **get-or-create**
um registro `Enrollment` idempotente por `external_id`, vinculado ao matriculando e
ao `promoter_external_id` que veio no payload, com status inicial `started`. Um GET
de leitura torna o agregado observável/testável. As transições por etapa
(perfil/endereço/RG/educação/selfie/liberação) são milestones 2–5.

## Decisão de design (registrar)
- O PRD pede "espelhar candidate", mas o `candidate` usa **ref lógico sem FK**. O
  `enrollment` já é dono de uma tabela com **FK real → `auth.users` + shadow table +
  conftest com Postgres real** (`make_auth_user`). Para **consistência dentro do
  serviço** e reuso da infra de teste, o novo agregado mantém **FK real + PG_UUID**
  (não o `UUIDStr`/sqlite do candidate). Espelha-se do candidate o *conceito*
  (orquestrador, `Status` StrEnum + `STATUS_ORDER`, `get_or_create`/`advance`), não o
  mecanismo de persistência.
- Corrige a dívida §4 do serviço: o agregado novo nasce com **PK UUID** (o
  `enrollment_events` legado em BIGINT fica como está — fora do escopo do milestone).

## Patterns to Mirror
| Category | Source | Pattern |
|---|---|---|
| Status machine | `candidate/app/models/candidate.py:23-48` | `StrEnum` + `STATUS_ORDER` tuple |
| Service get-or-create | `candidate/app/services/candidate.py:17-41` | `get` / `get_or_create` (idempotente por external_id) / `advance` |
| Webhook idempotente + FK 409 | `enrollment/app/api/webhooks.py:44-96` | dedup por chave + `IntegrityError`→`Conflict` |
| Model/FK/index | `enrollment/app/models/enrollment_event.py:18-52` | `PG_UUID`, FK `auth.users.external_id`, `index=True`, `server_default=func.now()` |
| Migration | `enrollment/alembic/versions/2026-05-15_initial_enrollment_schema.py` | `op.create_table` no schema `enrollment`, índices nomeados |
| Tests (PG real) | `enrollment/tests/conftest.py:69-155` + `tests/test_webhooks.py` | testcontainers/`TEST_DATABASE_URL`, `make_auth_user`, `client` ASGI |
| Exceptions | `enrollment/app/exceptions.py` | `Conflict` / `NotFound` |

## Files to Change
| File | Action | Why |
|---|---|---|
| `enrollment/app/models/enrollment.py` | CREATE | Model `Enrollment` + `EnrollmentStatus` + `STATUS_ORDER` |
| `enrollment/app/models/__init__.py` | UPDATE | Reexportar `Enrollment`, `EnrollmentStatus`, `STATUS_ORDER` (popular metadata p/ alembic) |
| `enrollment/app/services/__init__.py` | CREATE | Pasta `services/` (exigida §3, hoje ausente) |
| `enrollment/app/services/enrollment.py` | CREATE | `get` / `get_or_create` do agregado (idempotente por `external_id`) |
| `enrollment/app/schemas/enrollment.py` | CREATE | `EnrollmentRead` (saída do GET) |
| `enrollment/app/schemas/__init__.py` | UPDATE | Reexportar `EnrollmentRead` |
| `enrollment/app/api/webhooks.py` | UPDATE | No `receive()`, criar o agregado (get_or_create) na mesma transação do evento |
| `enrollment/app/api/enrollments.py` | CREATE | `GET /api/v1/enrollments/{external_id}` (desmilitarizado, audit) |
| `enrollment/app/main.py` | UPDATE | `include_router` do novo `enrollments_router` |
| `enrollment/alembic/versions/0002_*.py` | CREATE | Migração `enrollment.enrollments` (PK UUID, FK, índices) |
| `enrollment/tests/conftest.py` | UPDATE | `_clean_between_tests`: TRUNCATE `enrollment.enrollments` também |
| `enrollment/tests/test_enrollment_aggregate.py` | CREATE | Criação na webhook, idempotência, GET, 409 external_id desconhecido |

## Tasks
### Task 1: Model `Enrollment` + status machine
- **Action**: `EnrollmentStatus(StrEnum)` = `started, profile, address, documents, education, selfie, awaiting_release, completed` + `STATUS_ORDER`. Model `Enrollment`: `id` PG_UUID PK `default=uuid4`; `external_id` PG_UUID FK→`auth.users.external_id` (RESTRICT/CASCADE) `unique index`; `status` String(24) default `started` index; `promoter_external_id` PG_UUID nullable index; `hub_external_id` PG_UUID nullable index (resolvido quando `hub` existir); `created_at`/`updated_at` `timestamptz` `server_default now()`.
- **Mirror**: `candidate/app/models/candidate.py` (enum/order) + `enrollment/app/models/enrollment_event.py` (FK/index/PG_UUID).
- **Validate**: `uv run python -c "import app.models"` sem erro; `ruff check`.

### Task 2: Service do agregado
- **Action**: `services/enrollment.py` com `get(session, external_id)` e `get_or_create(session, external_id, promoter_external_id) -> tuple[Enrollment, bool]` (status inicial `started`, idempotente). `advance()` fica para milestones 2–5.
- **Mirror**: `candidate/app/services/candidate.py:11-41`.
- **Validate**: coberto pelos testes da Task 5.

### Task 3: Webhook cria o agregado
- **Action**: em `webhooks.py::receive()`, após montar/checar o evento, chamar `enrollment_svc.get_or_create(...)` na **mesma sessão** antes do `commit` (um único `commit`; o `except IntegrityError` já cobre external_id ausente para ambos). Resposta inclui `enrollment_id` e `status`. Chamar get_or_create mesmo quando o evento já existe (garante agregado para eventos logados antes deste milestone).
- **Mirror**: fluxo idempotente atual `webhooks.py:44-96`.
- **Validate**: testes Task 5.

### Task 4: Leitura + migração
- **Action**: `schemas/enrollment.py::EnrollmentRead` (`from_attributes`); `api/enrollments.py` com `GET /api/v1/enrollments/{external_id}` (404 `NotFound` se ausente); registrar router no `main.py`. Migração `0002` criando `enrollment.enrollments` espelhando o estilo da `0001` (índices nomeados, schema `enrollment`).
- **Mirror**: `webhooks.py` GET 404 + migração `0001`.
- **Validate**: `uv run alembic upgrade head` contra Postgres real (0001→0002).

### Task 5: Testes
- **Action**: `test_enrollment_aggregate.py`: (a) `POST /webhook/new/{external_id}` cria agregado `status=started` com `promoter_external_id`; (b) reenviar webhook não duplica (idempotente); (c) `GET /enrollments/{external_id}` retorna; 404 quando ausente; (d) `external_id` fora de `auth.users` → 409, nenhum agregado criado. Atualizar `conftest` para truncar `enrollments`.
- **Mirror**: `enrollment/tests/test_webhooks.py` + `make_auth_user`.
- **Validate**: `uv run pytest -q`.

## Validation
```bash
cd enrollment
uv run ruff check . && uv run ruff format --check .
uv run pytest -q                         # precisa de Postgres: testcontainers OU TEST_DATABASE_URL
uv run alembic upgrade head              # 0001 -> 0002 contra Postgres real
```

## Risks
| Risk | Likelihood | Mitigation |
|---|---|---|
| Testes pulam sem Docker/Postgres (conftest faz SKIP) | Média | Rodar com `testcontainers[postgres]` + docker OU `TEST_DATABASE_URL` apontando p/ PG real |
| Nome/ordem do enum de status diverge do que o dono espera | Média | Nomes propostos seguem o TODO (perfil→endereço→RG→educação→selfie→aguardando→concluído); confirmar antes de codar |
| `enrollment_events` legado em BIGINT vs agregado em UUID (inconsistência) | Baixa | Documentado; legado fora do escopo, não é bloqueador |
| `database_url` ainda tem default `v7m:v7m` (dívida Fase 1) | Baixa | Fora do milestone 1; tratar em milestone de config/segurança |

## Acceptance
- [ ] Webhook `lead.completed` cria `Enrollment` (`status=started`) ligado a external_id + promoter, idempotente
- [ ] `GET /enrollments/{external_id}` expõe o agregado (404 quando ausente)
- [ ] Migração `0002` aplica contra Postgres real
- [ ] `ruff` limpo + suíte verde
- [ ] Padrões espelhados (candidate/enrollment), sem reinventar; sem TODO órfão
