# Plan: documents — Milestone 1 (Base canônica + provisionamento)

**Source PRD**: `.claude/prds/documents-service.prd.md`
**Selected Milestone**: 1 — Base canônica + provisionamento
**Complexity**: Large (reescrita de stack do serviço inteiro; é o alicerce dos milestones 2–5)

## Summary
Reescrever o `documents` na stack canônica (Python 3.12, FastAPI, SQLAlchemy 2.0 async + asyncpg, Postgres schema `documents`, Alembic, Pydantic v2, structlog), substituindo Tortoise+SQLite. Entregar o **schema completo** (Document + sub-documentos, PK UUID, nomes em inglês) e um **endpoint de provisionamento desmilitarizado** que, dado um `external_id`, cria o Document e todos os sub-documentos vazios numa única operação. CRUD textual, imagens e eventos notify ficam para os milestones 2–4.

## Patterns to Mirror
| Category | Source | Pattern |
|---|---|---|
| db/engine | `lead/app/db.py:16-67` | `NAMING_CONVENTION` + `MetaData(naming_convention, schema=settings.DATABASE_SCHEMA)`; `Base(DeclarativeBase)`; shadow `auth_users` Table p/ FK cross-schema; `create_async_engine`+`async_sessionmaker(expire_on_commit=False)`; `get_session()` |
| config | `lead/app/config.py:12-81` + `profiles` CLAUDE §2 | `Settings(BaseSettings)` com `SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")`; `DATABASE_URL` **obrigatório sem default**; `DATABASE_SCHEMA="documents"` |
| models | `lead/app/models/lead.py:21-61` + `_mixins.py` | `Mapped[...]`/`mapped_column`; `TimestampMixin`; `PG_UUID(as_uuid=True)`; FK→`auth.users.external_id` nomeada; `Enum(..., schema=, create_type=True, values_callable=...)` |
| PK UUID | CONVENTION §4 + auditoria `wiki/documents.md` desvio #5 | PK = `PG_UUID` com `default=uuid4` (diverge do serial de lead/profiles — aqui seguimos a CONVENTION explícita) |
| endpoint demilitarized | `lead/app/api/demilitarized/leads.py:13-52` | `APIRouter(prefix="/api/v1/demilitarized")`; schemas `APIModel` inline; `Depends(get_session)`; `select()`; `HTTPException` 404; mapper `_to_out` |
| schemas base | `lead/app/schemas/__init__.py` | `APIModel(BaseModel)` com `model_config=ConfigDict(...)`; re-export central; imports `from app.schemas import APIModel` |
| main/lifespan | `lead/app/main.py:32-107` | `lifespan` asynccontextmanager (`engine.dispose()` no shutdown); CORS; health/ready/status na raiz; `include_router` |
| exceptions | `profiles` CLAUDE §3 (`DomainError→Conflict/NotFound/ValidationError`) | hierarquia `DomainError` + handler em `main.py` mapeando p/ HTTP |
| alembic async | `lead/alembic/env.py:1-64` | env async; `include_object` filtra outros schemas; `include_schemas=True`; `version_table_schema=SCHEMA`; importa `app.models` |
| logging | `documents/app/utils/logging.py` (atual) + CONVENTION §2 | `structlog` via `get_logger(__name__)` |
| tests | `profiles/tests/test_health.py:1-45` | pytest-asyncio (`asyncio_mode=auto`); fixture `client: AsyncClient`; conftest com Postgres real/test db |

## Domínio (modelagem alvo — schema `documents`)
- **Document** (tabela `documents`): `id` UUID PK; `external_id` UUID unique/index, FK→`auth.users.external_id`; `proof_of_residence_photo`, `photo` (colunas de imagem simples); `created_at`/`updated_at`; relacionamentos 1:1 com os sub-documentos abaixo.
- **Sub-documentos 1:1** (cada um: `id` UUID PK, `document_id` UUID FK→`documents.id`, campos + fotos), nomes de arquivo/tabela em **inglês**:
  - `RG` (`rg`): numero, orgao_emissor, data_emissao, foto_frente, foto_verso
  - `DriverLicense` (`driver_licenses`, CNH): numero, categoria, data_nascimento, validade, registro_nacional, foto_frente, foto_verso
  - `WorkCard` (`work_cards`, CTPS): numero, serie, uf, data_emissao, foto_frente, foto_verso
  - `Passport` (`passports`): numero, validade, data_emissao, foto_frente, foto_verso
  - `Certificate` (`certificates`, certidão **única por Document**): tipo (Enum: birth/marriage/death), numero, cartorio, livro, folha, termo, data_emissao, foto
  - `MilitaryService` (`military_services`, reservista — **criado só para homens**): numero, serie, categoria, ra, foto

> Nota: nomes de domínio em inglês conforme §7. A rota atual `/api/v1/documentos` (PT) passa a `/api/v1/documents`.

## Files to Change
| File | Action | Why |
|---|---|---|
| `documents/pyproject.toml` | UPDATE | py3.12; stack canônica (sqlalchemy[asyncio], asyncpg, alembic, pydantic, pydantic-settings, httpx, structlog, python-multipart); remover tortoise/aiosqlite; hatchling `packages=["app"]`; config ruff (line-length 100, py312) |
| `documents/.env.example` | CREATE | documentar todas as env vars (sem segredo) |
| `documents/.env` | UPDATE | `DATABASE_URL` Postgres; `DATABASE_SCHEMA=documents`; remover SQLite |
| `documents/app/config.py` | UPDATE | `Settings` pydantic-settings v2; `DATABASE_URL` obrigatório; `MEDIA_DIR`, `MAX_UPLOAD_MB`, `NOTIFY_BASE_URL`, `PROFILES_BASE_URL`, `HTTP_TIMEOUT` |
| `documents/app/db.py` | UPDATE | engine async + Base + metadata(schema) + NAMING_CONVENTION + shadow `auth_users` + `get_session` |
| `documents/app/models/_mixins.py` | CREATE | `TimestampMixin` (espelha lead) |
| `documents/app/models/document.py` | UPDATE | SQLAlchemy 2.0, UUID PK, FK external_id, colunas de imagem simples, relationships |
| `documents/app/models/rg.py` | UPDATE | SQLAlchemy 2.0, UUID PK, FK document_id |
| `documents/app/models/driver_license.py` | CREATE | renomeia `cnh.py` p/ inglês |
| `documents/app/models/work_card.py` | CREATE | renomeia `carteira_trabalho.py` |
| `documents/app/models/passport.py` | CREATE | renomeia `passaporte.py` |
| `documents/app/models/certificate.py` | CREATE | certidão como tabela própria (era inline) |
| `documents/app/models/military_service.py` | CREATE | reservista como tabela própria (era inline) |
| `documents/app/models/cnh.py`, `carteira_trabalho.py`, `passaporte.py` | DELETE | nomes em PT substituídos |
| `documents/app/models/__init__.py` | UPDATE | registrar todos os models p/ o Alembic |
| `documents/app/schemas/__init__.py` | UPDATE | `APIModel` base (Pydantic v2) |
| `documents/app/schemas/document.py` | UPDATE | `ProvisionRequest`/`DocumentOut` (provisionamento + leitura) |
| `documents/app/exceptions.py` | UPDATE | `DomainError`→NotFound/Conflict/ValidationError |
| `documents/app/services/document_service.py` | UPDATE | `provision(external_id, sex)`: cria Document + todos sub-docs; militar só p/ homem; `get_document` |
| `documents/app/api/documents.py` | UPDATE | endpoint `POST /api/v1/demilitarized/documents` (provision) + `GET /{external_id}`; rota em inglês |
| `documents/app/api/health.py` | UPDATE | /health, /ready (checa DB) |
| `documents/app/api/router.py` | UPDATE | agrega routers |
| `documents/app/main.py` | UPDATE | FastAPI + lifespan + structlog + CORS + handler DomainError + health/ready/status |
| `documents/app/utils/logging.py` | UPDATE | structlog `get_logger` (manter) |
| `documents/alembic.ini` | CREATE | config Alembic |
| `documents/alembic/env.py` | CREATE | env async (espelha lead) |
| `documents/alembic/script.py.mako` | CREATE | template |
| `documents/alembic/versions/0001_initial.py` | CREATE | schema `documents` + todas as tabelas (autogenerate + ajuste do `CREATE SCHEMA`) |
| `documents/Makefile` | CREATE | dev/test/migrate/lint (espelha profiles) |
| `documents/README.md` | CREATE | o que faz, como rodar, env vars |
| `documents/.claude/CLAUDE.md` | CREATE | particularidades do serviço |
| `documents/tests/conftest.py` | CREATE | fixtures (app + AsyncClient + Postgres de teste) |
| `documents/tests/test_health.py` | CREATE | /health, /ready |
| `documents/tests/test_provision.py` | CREATE | provisiona → Document + sub-docs criados; militar condicional; idempotência |

## Tasks
### Task 1: pyproject + config + .env
- **Action**: trocar deps p/ stack canônica (py3.12), reescrever `Settings` (DATABASE_URL obrigatório, schema `documents`), criar `.env.example`.
- **Mirror**: `lead/app/config.py`, `profiles` CLAUDE §2.
- **Validate**: `cd documents && uv sync && python -c "from app.config import settings; print(settings.DATABASE_SCHEMA)"`

### Task 2: db.py + _mixins
- **Action**: engine async, Base, metadata(schema), NAMING_CONVENTION, shadow `auth_users`, `get_session`; `TimestampMixin`.
- **Mirror**: `lead/app/db.py:16-67`, `lead/app/models/_mixins.py`.
- **Validate**: `python -c "import app.db"`

### Task 3: models (todos, inglês, UUID PK)
- **Action**: Document + RG/DriverLicense/WorkCard/Passport/Certificate/MilitaryService; deletar arquivos PT; registrar em `models/__init__.py`.
- **Mirror**: `lead/app/models/lead.py`.
- **Validate**: `python -c "import app.models; from app.db import Base; print(sorted(Base.metadata.tables))"`

### Task 4: exceptions + schemas
- **Action**: `DomainError` hierarchy; `APIModel` base; `ProvisionRequest` (external_id, sex), `DocumentOut` (com sub-docs).
- **Mirror**: `profiles` exceptions; `lead/app/schemas/__init__.py`.
- **Validate**: `python -c "import app.schemas, app.exceptions"`

### Task 5: service (provision)
- **Action**: `provision(session, external_id, sex)` cria Document + todos sub-docs vazios; cria `MilitaryService` só quando `sex` masculino; idempotente (não duplica se já existe). `get_document`.
- **Mirror**: service async com `select()`/commit (estilo `lead` endpoints).
- **Validate**: coberto pelo Task 8 (test_provision).

### Task 6: api + main
- **Action**: `POST /api/v1/demilitarized/documents` (body `ProvisionRequest`) + `GET /api/v1/demilitarized/documents/{external_id}`; health/ready; `main.py` com lifespan/structlog/CORS/handler DomainError.
- **Mirror**: `lead/app/api/demilitarized/leads.py`, `lead/app/main.py`.
- **Validate**: `python -c "from app.main import app; print([r.path for r in app.routes])"`

### Task 7: alembic
- **Action**: `alembic.ini`, `env.py` async, `script.py.mako`; gerar `0001_initial` (criar schema `documents` + tabelas); `alembic upgrade head`.
- **Mirror**: `lead/alembic/env.py`.
- **Validate**: `make migrate` (ou `uv run alembic upgrade head`) contra Postgres.

### Task 8: tests + Makefile + docs
- **Action**: conftest (app+AsyncClient+test DB), test_health, test_provision (Document+sub-docs, militar condicional, idempotência); Makefile; README; CLAUDE.md.
- **Mirror**: `profiles/tests/test_health.py` + conftest de `notify`/`profiles`.
- **Validate**: `make test` verde, `ruff check app tests` limpo.

## Validation
```bash
cd /home/maestri33/backend/documents
uv sync
ruff check app tests && ruff format --check app tests
uv run alembic upgrade head          # cria schema documents + tabelas
uv run pytest -q                     # health + provision
python -c "from app.main import app; print([r.path for r in app.routes])"
```

## Risks
| Risk | Likelihood | Mitigation |
|---|---|---|
| PK UUID diverge do serial usado em lead/profiles | Média | Seguir CONVENTION §4 (regra explícita) + auditoria; documentar a divergência no CLAUDE.md |
| Rota PT→EN (`/documentos`→`/documents`) quebra chamadores atuais | Média | Confirmar com o dono; serviço é desmilitarizado/interno, poucos consumidores; anunciar a mudança |
| Fonte do `sex` p/ regra militar indefinida (Open Question do PRD) | Alta | MVP: recebe `sex` no payload de provisionamento; se ausente/desconhecido, **não** cria MilitaryService |
| FK cross-schema exige `auth.users` existente no Postgres de teste | Média | Shadow table + conftest cria o schema `auth` mínimo, ou usa `external_id` sem FK em teste isolado |
| Dados do SQLite atual (Open Question) | Baixa | Tratar como greenfield salvo confirmação; `media/` antigo migrado/limpo num passo à parte |

## Acceptance
- [ ] Serviço sobe na stack canônica; `alembic upgrade head` cria schema `documents` + todas as tabelas
- [ ] `POST /api/v1/demilitarized/documents` provisiona Document + todos os sub-documentos (militar só p/ homem); idempotente
- [ ] `GET /.../documents/{external_id}` retorna o Document com sub-docs
- [ ] PK UUID; nomes em inglês; Pydantic v2; structlog
- [ ] `pytest` verde, `ruff` limpo
- [ ] Patterns espelhados de `lead`/`profiles`, não reinventados

---
*Aguardando confirmação antes de escrever código. Open Questions do PRD (sex source, acesso à mídia, shadow table, migração de dados) podem ajustar Tasks 5/7.*
