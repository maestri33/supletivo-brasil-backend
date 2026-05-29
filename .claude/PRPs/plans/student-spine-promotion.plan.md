# Plan: student — Milestone 1 (Spine + Promoção)

## Summary
Cria o esqueleto do microsserviço `student` (stack canônica) e o primeiro fluxo de negócio: o **coordenador promove** um usuário de matrícula para aluno (`enrollment → student`), inserindo os dados da plataforma de estudo, criando o registro do aluno no status inicial e expondo o **GET dos dados** do aluno. Tudo dentro de `student/` apenas.

## User Story
Como **coordenador do polo**, quero promover um candidato matriculado a aluno informando os dados da plataforma de estudo, para que o aluno entre no funil e possa acompanhar e avançar seus status; e como **aluno**, quero consultar meus dados a qualquer momento.

## Problem → Solution
Hoje `student/` só tem o arquivo `TODO` (spec). → Serviço FastAPI funcional com schema Postgres próprio (`student`), model `Student` (PK UUID), endpoint autenticado de promoção (role `coordinator`) e GET de dados do aluno (role `student`), migração Alembic, testes e lint verdes.

## Metadata
- **Complexity**: Medium (3–10 arquivos novos, padrões existentes)
- **Source PRD**: `.claude/prds/student.prd.md`
- **PRD Phase**: Milestone 1 — Spine + promoção
- **Estimated Files**: ~18 arquivos (todos CREATE, dentro de `student/`)

---

## UX Design

Internal/backend service — sem UI. Touchpoints são endpoints HTTP.

### Interaction Changes
| Touchpoint | Before | After | Notes |
|---|---|---|---|
| `POST /api/v1/authenticated/students` (promover) | inexistente | coordenador (JWT role `coordinator`) cria o aluno a partir de `external_id` + dados da plataforma | idempotente por `external_id` |
| `GET /api/v1/authenticated/students/me` | inexistente | aluno (JWT role `student`) lê os próprios dados | usa `external_id` do token |
| `GET /health` `/ready` `/status` | inexistente | liveness/uptime | sem prefixo, igual `lead` |

---

## Mandatory Reading

| Priority | File | Lines | Why |
|---|---|---|---|
| P0 | `asaas/app/db.py` | 1-53 | Padrão canônico de `db.py`: Base, NAMING_CONVENTION, `utcnow`, `get_session`, `close_db` |
| P0 | `enrollment/app/db.py` | 33-39 | **Shadow table** `auth.users` para FK cross-schema (§4) |
| P0 | `asaas/app/config.py` | 1-25, 95-99 | `Settings` pydantic-settings, `database_url` obrigatório (sem default), `get_settings()` cacheado |
| P0 | `asaas/alembic/env.py` | 1-74 | `env.py` async + `CREATE SCHEMA IF NOT EXISTS` + `include_object` (só o schema próprio) |
| P0 | `lead/app/dependencies.py` | 1-92 | Validação JWT/JWKS + cache + checagem de role + gate por status |
| P0 | `enrollment/app/models/enrollment_event.py` | 1-56 | Model com `PG_UUID(as_uuid=True)` + `ForeignKey("auth.users.external_id")` |
| P1 | `lead/app/models/_mixins.py` | 1-21 | `TimestampMixin` (`timestamptz`, `server_default=func.now()`, `onupdate`) |
| P1 | `lead/app/main.py` | 1-44, 86-108 | `lifespan`, registro de routers, health endpoints |
| P1 | `asaas/pyproject.toml` | all | `pyproject.toml` canônico (deps, ruff, pytest asyncio) |
| P2 | `asaas/.claude/CLAUDE.md` | §4, §5 | Regras de pastas e tipos de endpoint do modelo de referência |

## External Documentation
No external research needed — feature uses established internal patterns (FastAPI + SQLAlchemy 2.0 async + asyncpg + Alembic + Pydantic v2 + PyJWT, todos já em uso no repo).

---

## Patterns to Mirror

### NAMING_CONVENTION  (db.py / metadata + schema)
// SOURCE: asaas/app/db.py:18-39
```python
NAMING_CONVENTION = {
    "ix": "%(column_0_label)s_idx",
    "uq": "%(table_name)s_%(column_0_name)s_key",
    "ck": "%(table_name)s_%(constraint_name)s_check",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "pk": "%(table_name)s_pkey",
}
metadata = MetaData(naming_convention=NAMING_CONVENTION, schema=settings.database_schema)

class Base(DeclarativeBase):
    metadata = metadata

def utcnow() -> datetime:
    return datetime.now(UTC)

engine = create_async_engine(settings.database_url, pool_pre_ping=True)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
```

### SHADOW_TABLE  (FK cross-schema sem importar model alheio, §4)
// SOURCE: enrollment/app/db.py:33-39
```python
# Shadow auth.users — necessário pro SQLAlchemy resolver FK cross-schema.
auth_users = Table(
    "users",
    metadata,
    Column("external_id", PG_UUID(as_uuid=True), primary_key=True),
    schema="auth",
)
```

### CONFIG  (pydantic-settings, database_url obrigatório)
// SOURCE: asaas/app/config.py:14-25, 95-99
```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8",
        case_sensitive=False, extra="ignore")
    database_url: str = Field(validation_alias="STUDENT_APP_DB_URL")
    database_schema: str = "student"

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

### MODEL  (PK UUID + FK cross-schema + timestamps)
// SOURCE: enrollment/app/models/enrollment_event.py:18-47 + lead/app/models/_mixins.py:9-20
```python
class Student(Base, TimestampMixin):
    __tablename__ = "students"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    external_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("auth.users.external_id", ondelete="RESTRICT", onupdate="CASCADE",
                   name="students_external_id_fkey"),
        unique=True, index=True, nullable=False,
    )
    status: Mapped[StudentStatus] = mapped_column(
        SAEnum(StudentStatus, name="student_status", native_enum=False, length=40),
        default=StudentStatus.AWAITING_DOCUMENTS, nullable=False, index=True,
    )
    study_platform: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
```

### AUTH/ROLE GATE  (JWT/JWKS + role)
// SOURCE: lead/app/dependencies.py:21-92  (mesma lógica; troca a role exigida)
```python
async def get_current_external_id(credentials=Depends(HTTPBearer())) -> UUID: ...
# payload validado com options={"require": ["exp", "roles", "external_id"]}

def require_role(role: str):
    async def _dep(... payload ...) -> UUID:
        if role not in payload.get("roles", []):
            raise HTTPException(403, f"Requires '{role}' role")
        return UUID(payload["external_id"])
    return Depends(_dep)
```

### ALEMBIC ENV  (async + cria schema)
// SOURCE: asaas/alembic/env.py:56-67
```python
async with connectable.connect() as conn:
    await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"'))
    await conn.commit()
async with connectable.connect() as connection:
    await connection.run_sync(do_run_migrations)
```

### MAIN/LIFESPAN
// SOURCE: lead/app/main.py:32-44, 89-107
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("service.startup", service=settings.service_name)
    yield
    await close_db()

app = FastAPI(title=settings.service_name, version=settings.app_version, lifespan=lifespan)
app.include_router(students_router)

@app.get("/health")
async def health(): return {"status": "ok", "service": settings.service_name}
```

### PYPROJECT
// SOURCE: asaas/pyproject.toml (copiar; trocar name → "student-app", description; adicionar `pyjwt>=2.9`)

### TEST_STRUCTURE
// SOURCE: asaas/pyproject.toml `[tool.pytest.ini_options] asyncio_mode="auto"` + dev dep `aiosqlite`
// Mirror: conftest com engine `sqlite+aiosqlite`, `httpx.AsyncClient`/`ASGITransport`, override de `get_session` e da dependency de auth.

---

## Files to Change
| File | Action | Justification |
|---|---|---|
| `student/pyproject.toml` | CREATE | Stack canônica (copiar asaas + pyjwt) |
| `student/.env.example` | CREATE | `STUDENT_APP_DB_URL` placeholder, `JWT_BASE_URL`, urls de integração (placeholder) |
| `student/Makefile` | CREATE | install/dev/test/lint/migrate (espelha asaas) |
| `student/Dockerfile` | CREATE | espelha asaas |
| `student/app/__init__.py` | CREATE | pacote |
| `student/app/config.py` | CREATE | Settings pydantic-settings |
| `student/app/db.py` | CREATE | engine async, Base, NAMING_CONVENTION, `utcnow`, shadow `auth.users`, `get_session`, `close_db` |
| `student/app/exceptions.py` | CREATE | exceções de domínio (`StudentAlreadyExists`, `StudentNotFound`) |
| `student/app/dependencies.py` | CREATE | JWT/JWKS + `require_role("coordinator"|"student")` |
| `student/app/main.py` | CREATE | FastAPI, lifespan, routers, health |
| `student/app/models/__init__.py` | CREATE | exporta `Student`, `StudentStatus` |
| `student/app/models/_mixins.py` | CREATE | `TimestampMixin` |
| `student/app/models/student.py` | CREATE | model `Student` + enum `StudentStatus` |
| `student/app/schemas/__init__.py` | CREATE | exporta schemas |
| `student/app/schemas/student.py` | CREATE | `PromoteRequest`, `StudentRead` |
| `student/app/services/__init__.py` | CREATE | pacote |
| `student/app/services/student_service.py` | CREATE | `promote()`, `get_by_external_id()` |
| `student/app/api/__init__.py` | CREATE | pacote |
| `student/app/api/authenticated/__init__.py` | CREATE | agrega routers autenticados |
| `student/app/api/authenticated/students.py` | CREATE | `POST /students` (coordenador), `GET /students/me` (aluno) |
| `student/app/api/public/__init__.py` + `health.py` | CREATE | health (ou no main, igual lead) |
| `student/alembic.ini` | CREATE | espelha asaas |
| `student/alembic/env.py` | CREATE | async + cria schema |
| `student/alembic/script.py.mako` | CREATE | copiar de asaas |
| `student/alembic/versions/2026-05-25_initial_student_schema.py` | CREATE | tabela `students` |
| `student/tests/conftest.py` | CREATE | fixtures sqlite async + client + auth override |
| `student/tests/test_promotion.py` | CREATE | testes do fluxo de promoção + GET |
| `student/.claude/` | CREATE (M6) | adiado p/ Milestone 6 |
| `student/TODO` | KEEP | spec; só apagar quando todos os milestones cumpridos (§9) |

## NOT Building (fora do Milestone 1)
- Upload/validação de documentos e worker_loop de IA → **Milestone 2**.
- Prova (agendamento/correção) → **Milestone 3**.
- Diploma, role veterano, comissão → **Milestone 4**.
- Notify async e GET de pendência/PDF → **Milestone 5**.
- `wiki/student.md`, `.claude/` e fechamento §15 → **Milestone 6**.
- Clients `integrations/` (documents/ai/notify/commissions) — só criados quando o milestone que os usa chegar.
- Escopo por polo/hub na autorização (open question) — qualquer coordenador autenticado pode promover por ora.

---

## Step-by-Step Tasks

### Task 1: Scaffolding do pacote + pyproject + tooling
- **ACTION**: Criar `student/pyproject.toml`, `.env.example`, `Makefile`, `Dockerfile`, `app/__init__.py`.
- **IMPLEMENT**: Copiar `asaas/pyproject.toml`; trocar `name="student-app"`, `description`; **adicionar** `"pyjwt>=2.9"` em `dependencies` (necessário p/ validar JWT, igual `lead`). Manter `[tool.ruff]` line-length=100/py312 e `[tool.pytest.ini_options] asyncio_mode="auto"`.
- **MIRROR**: PYPROJECT.
- **IMPORTS**: n/a.
- **GOTCHA**: `lead` usa `fastapi_structured_logging`; **não** seguir isso — a convenção §2 manda `structlog`. Espelhe `asaas` (structlog).
- **VALIDATE**: `cd student && uv sync` resolve sem erro.

### Task 2: `config.py`
- **ACTION**: Criar `student/app/config.py`.
- **IMPLEMENT**: `Settings` com `database_url: str = Field(validation_alias="STUDENT_APP_DB_URL")` (sem default — D1), `database_schema: str = "student"`, `service_name: str = "student"`, `app_version: str = "0.1.0"`, `jwt_base_url: str` (p/ JWKS), `cors_origins: list[str] = []`. `get_settings()` com `@lru_cache`.
- **MIRROR**: CONFIG.
- **GOTCHA**: `database_url` **obrigatório sem default** (D1 do PLANO — proibido `v7m:v7m` hardcoded). Nada de `os.environ` fora deste módulo (§2).
- **VALIDATE**: `python -c "from app.config import get_settings"` com `.env` de teste.

### Task 3: `db.py` com shadow table
- **ACTION**: Criar `student/app/db.py`.
- **IMPLEMENT**: Copiar asaas `db.py` (Base, NAMING_CONVENTION, `utcnow`, engine, `get_session`, `close_db`) **e** adicionar a shadow `auth_users` do enrollment.
- **MIRROR**: NAMING_CONVENTION + SHADOW_TABLE.
- **IMPORTS**: `from sqlalchemy import Column, MetaData, Table`, `from sqlalchemy.dialects.postgresql import UUID as PG_UUID`.
- **GOTCHA**: schema do shadow é `"auth"`, não `student`. O `include_object` do alembic (Task 8) filtra tabelas de outro schema → a shadow não vira migração.
- **VALIDATE**: import sem erro; `Base.metadata.tables` contém `student.students` e `auth.users`.

### Task 4: `models/` — `Student` + `StudentStatus`
- **ACTION**: Criar `models/__init__.py`, `models/_mixins.py`, `models/student.py`.
- **IMPLEMENT**: `_mixins.TimestampMixin` (copiar do lead). `StudentStatus(str, Enum)` com o funil completo (proposto): `AWAITING_DOCUMENTS`, `DOCUMENTS_UNDER_REVIEW`, `EXAM_RELEASED`, `EXAM_SCHEDULED`, `EXAM_FAILED`, `AWAITING_DOCUMENTATION_DISPATCH`, `PENDING`, `AWAITING_DIPLOMA_ISSUANCE`, `AWAITING_PICKUP`, `VETERAN`. `Student` conforme snippet MODEL (PK `id` UUID default `uuid4`, `external_id` FK→`auth.users.external_id` unique, `status` default `AWAITING_DOCUMENTS`, `study_platform` JSONB, timestamps via mixin). `models/__init__.py` exporta `Student, StudentStatus` (alembic importa `app.models`).
- **MIRROR**: MODEL.
- **IMPORTS**: `from enum import Enum`; `from uuid import UUID, uuid4`; `from typing import Any`; `from sqlalchemy import Enum as SAEnum, ForeignKey`; `from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID`; `from sqlalchemy.orm import Mapped, mapped_column`.
- **GOTCHA**: usar `native_enum=False` no `SAEnum` p/ o status funcionar em sqlite (testes) e postgres sem criar tipo enum nativo — coluna vira VARCHAR. Definir o enum inteiro agora evita migração de tipo a cada milestone; M1 só grava `AWAITING_DOCUMENTS`.
- **VALIDATE**: `from app.models import Student, StudentStatus` ok.

### Task 5: `dependencies.py` — auth + role gate
- **ACTION**: Criar `student/app/dependencies.py`.
- **IMPLEMENT**: Copiar `get_jwks()` + a validação JWT do lead (`dependencies.py:21-66`), mas **generalizar a role**: `get_token_payload()` retorna o payload validado; `require_role(role: str)` retorna `Depends` que checa `role in payload["roles"]` e devolve `UUID(payload["external_id"])`. Usar `settings.jwt_base_url`.
- **MIRROR**: AUTH/ROLE GATE.
- **IMPORTS**: `import time, jwt, httpx`; `from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials`.
- **GOTCHA**: `options={"require": ["exp", "roles", "external_id"]}` e `algorithms=["RS256"]` — igual lead. JWKS cache 5 min (cache global de módulo). Não importar model de outro serviço.
- **VALIDATE**: nos testes, sobrescrever essa dependency (não bater no jwt real).

### Task 6: `schemas/` — Promote + Read
- **ACTION**: Criar `schemas/__init__.py`, `schemas/student.py`.
- **IMPLEMENT**: `PromoteRequest`: `external_id: UUID`, `study_platform: dict[str, Any]` (dados da plataforma — formato livre por ora, ver Open Question). `StudentRead`: `id, external_id, status, study_platform, created_at, updated_at` com `model_config = ConfigDict(from_attributes=True)`.
- **MIRROR**: Pydantic v2 (`field_validator`/`ConfigDict`, §7).
- **GOTCHA**: Pydantic v2 — `ConfigDict(from_attributes=True)`, nunca `class Config` v1.
- **VALIDATE**: `StudentRead.model_validate(student_obj)` ok.

### Task 7: `services/student_service.py`
- **ACTION**: Criar `services/__init__.py`, `services/student_service.py`.
- **IMPLEMENT**: `async def promote(session, *, external_id, study_platform) -> Student`: checa se já existe (`select(Student).where(external_id==...)`) → se sim, `raise StudentAlreadyExists` (idempotência: 409); cria `Student(status=AWAITING_DOCUMENTS)`, `add/flush/refresh`. `async def get_by_external_id(session, external_id) -> Student`: `scalar`; se None → `raise StudentNotFound`.
- **MIRROR**: SERVICE (negócio fora da rota, §3).
- **IMPORTS**: `from sqlalchemy import select`; models; exceptions.
- **GOTCHA**: rota fina — toda regra aqui. Não commitar na service; deixar o `get_session` controlar transação (commit na rota ou via session context). Seguir o que asaas faz (services usam a session passada).
- **VALIDATE**: teste unitário com sqlite.

### Task 8: Alembic (env async + migração inicial)
- **ACTION**: Criar `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`, `alembic/versions/2026-05-25_initial_student_schema.py`.
- **IMPLEMENT**: Copiar `asaas/alembic/env.py` e `script.py.mako`; `alembic.ini` apontando `script_location = alembic`. Migração inicial: `CREATE TABLE student.students` (colunas do model, FK p/ `auth.users.external_id`, índice em `external_id` unique e `status`). `include_object` garante que a shadow `auth.users` não entra.
- **MIRROR**: ALEMBIC ENV.
- **IMPORTS**: no env, `import app.models  # noqa: F401`.
- **GOTCHA**: `version_table_schema=SCHEMA` + `CREATE SCHEMA IF NOT EXISTS` antes do upgrade (banco novo). Usar `DateTime(timezone=True)` (timestamptz) nas colunas — asyncpg recusa datetime aware em coluna naive (bug que mordeu o asaas, F3).
- **VALIDATE**: `uv run alembic upgrade head` contra Postgres real cria `student.students`.

### Task 9: `api/authenticated/students.py` + router + `main.py`
- **ACTION**: Criar `api/__init__.py`, `api/authenticated/__init__.py`, `api/authenticated/students.py`, `api/public/health.py` (ou health no main), `app/main.py`, `app/exceptions.py`.
- **IMPLEMENT**:
  - `exceptions.py`: `StudentError`, `StudentAlreadyExists`, `StudentNotFound`.
  - `students.py`: `router = APIRouter(prefix="/api/v1/authenticated/students", tags=["students"])`.
    - `POST ""` → `Depends(require_role("coordinator"))` (ignora o external_id do coordenador), body `PromoteRequest`, chama `student_service.promote(...)`, commit, `status_code=201`, retorna `StudentRead`. Mapear `StudentAlreadyExists`→409.
    - `GET "/me"` → `external_id = require_role("student")`, chama `get_by_external_id`, `StudentNotFound`→404, retorna `StudentRead`.
  - `main.py`: structlog setup, `lifespan` (startup log + `close_db` no shutdown), CORS, `include_router`, health `/health`/`/ready`/`/status`.
- **MIRROR**: MAIN/LIFESPAN + endpoint fino (§3) + tipos de endpoint (§5: ambos `authenticated`).
- **IMPORTS**: `from app.dependencies import require_role`; `from app.db import get_session, close_db`.
- **GOTCHA**: `response_model=StudentRead` e `status_code` explícitos em toda rota (§7). Endpoint fino: zero regra de negócio na rota.
- **VALIDATE**: `python -c "import app.main"` sem erro; OpenAPI lista as rotas.

### Task 10: Testes
- **ACTION**: Criar `tests/conftest.py`, `tests/test_promotion.py`.
- **IMPLEMENT**: conftest: engine `sqlite+aiosqlite:///:memory:`, cria tabelas via `Base.metadata.create_all` (drop da shadow `auth.users`? — sqlite não tem schema; ver gotcha), `AsyncClient(transport=ASGITransport(app))`, override de `get_session` e de `require_role` (fixture que injeta external_id/role fake). Testes: (a) coordenador promove → 201 + status `AWAITING_DOCUMENTS`; (b) promover duas vezes o mesmo `external_id` → 409; (c) aluno faz `GET /me` → 200 com seus dados; (d) `GET /me` sem registro → 404; (e) role errada → 403.
- **MIRROR**: TEST_STRUCTURE.
- **GOTCHA**: sqlite não suporta schema Postgres nem FK cross-schema. Espelhar o conftest do `asaas`/`enrollment` (como eles neutralizam schema/shadow em sqlite — ler `asaas/tests/conftest.py` na hora de implementar). Provável: `metadata.schema=None` em teste ou usar `aiosqlite` com `ATTACH`. **Confirmar lendo o conftest de asaas/enrollment.**
- **VALIDATE**: `uv run pytest -q` verde.

---

## Testing Strategy

### Unit / Integration Tests
| Test | Input | Expected Output | Edge Case? |
|---|---|---|---|
| promote_ok | coordenador + external_id novo | 201, status=AWAITING_DOCUMENTS | não |
| promote_idempotent | external_id já promovido | 409 StudentAlreadyExists | sim |
| get_me_ok | aluno com registro | 200 StudentRead | não |
| get_me_missing | aluno sem registro | 404 StudentNotFound | sim |
| role_forbidden | token sem role exigida | 403 | sim |
| token_invalid | JWT expirado/forjado | 401 | sim |

### Edge Cases Checklist
- [x] Promoção duplicada (idempotência → 409)
- [x] Token inválido/expirado (401)
- [x] Role insuficiente (403)
- [x] Aluno inexistente no GET (404)
- [ ] external_id inexistente em `auth.users` (FK RESTRICT) — falha no Postgres real, fora do escopo do sqlite de teste

---

## Validation Commands

### Static Analysis / Lint
```bash
cd /home/maestri33/backend/student && uv run ruff check . && uv run ruff format --check .
```
EXPECT: limpo.

### Unit Tests
```bash
cd /home/maestri33/backend/student && uv run pytest -q
```
EXPECT: todos passam.

### Database Validation
```bash
cd /home/maestri33/backend/student && uv run alembic upgrade head
```
EXPECT: cria schema `student` + tabela `students` no Postgres central.

### Import smoke
```bash
cd /home/maestri33/backend/student && uv run python -c "import app.main"
```
EXPECT: sem erro.

### Manual Validation
- [ ] `uvicorn app.main:app` sobe; `/health` responde `{"status":"ok"}`.
- [ ] `POST /api/v1/authenticated/students` com JWT de coordenador cria aluno.
- [ ] `GET /api/v1/authenticated/students/me` com JWT de aluno retorna o registro.

---

## Acceptance Criteria
- [ ] Serviço sobe; health ok.
- [ ] Coordenador promove (enrollment→student), registro nasce em `AWAITING_DOCUMENTS`.
- [ ] GET de dados do aluno funciona.
- [ ] Promoção idempotente (409 em duplicata).
- [ ] `ruff` limpo + `pytest` verde + `alembic upgrade head` ok.
- [ ] Nenhum diretório fora de `student/` tocado.

## Completion Checklist
- [ ] Código segue padrões de asaas (stack) e lead/enrollment (estrutura).
- [ ] PK UUID + FK cross-schema via shadow table (§4); sem importar model alheio.
- [ ] structlog (não `print`/logging cru); httpx p/ qualquer chamada externa.
- [ ] `database_url` obrigatório via `.env` (sem default).
- [ ] Endpoints finos; `response_model`+`status_code` em todas as rotas; 3 tipos §5 respeitados.
- [ ] Sem ruído (`__pycache__`/órfãos) no commit; `.gitignore` cobre.
- [ ] Self-contained — sem necessidade de busca extra durante a implementação (exceto ler `asaas/tests/conftest.py` p/ o padrão de sqlite, já sinalizado).

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Padrão de teste sqlite vs schema/FK cross-schema | Alta | Médio | Ler `asaas/tests/conftest.py`/`enrollment` antes da Task 10; provavelmente neutralizam schema em sqlite |
| Formato de `study_platform` indefinido | Média | Baixo | JSONB livre no M1; fechar contrato depois (Open Question) |
| Role exata no JWT (`coordinator`/`student`) | Média | Médio | Confirmar nomes das roles com `auth`/`roles` antes de fechar; gate centralizado em `require_role` facilita ajuste |
| Outro agente da fleet editar `student/` em paralelo | Média | Médio | `git status` antes de começar; escopo restrito a `student/` |

## Notes
- **Decisões herdadas do PRD:** dependências como contratos (M2+); documentos no `documents`; prova no `student`; validação IA via worker (M2).
- **Open Questions que tocam o M1:** (1) nomes finais das roles no JWT; (2) formato de `study_platform`. Nenhuma bloqueia o M1 — ambas têm default seguro (gate centralizado + JSONB).
- **Logging:** seguir `asaas` (structlog puro), **não** o `fastapi_structured_logging` do lead — alinhado à §2.
- **§9/TODO:** `student/TODO` (spec) só é apagado quando todos os milestones forem cumpridos; até lá permanece como requisito.

---
*Plano gerado de `.claude/prds/student.prd.md` → Milestone 1. Próximo: `/prp-implement`.*
