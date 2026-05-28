# Plan: training — Milestone 1 (Autoria de matérias)

**Source PRD**: `.claude/prds/training.prd.md`
**Selected Milestone**: M1 — Autoria de matérias
**Complexity**: Medium

## Summary
Criar o serviço novo `training` do zero, espelhando a estrutura convention-compliant do `candidate` (que é o template mais atual: `services/`, `schemas/`, `exceptions.py`, `api/{router,errors}`, `tests/`). O escopo do M1 é só **autoria de matéria**: endpoints desmilitarizados para criar/listar/buscar matéria (texto + 1 questão + 1 resposta esperada; vídeo/foto nulos na criação) e **upload + armazenamento de vídeo/foto no próprio `training`** (volume local), sem nenhuma lógica de trainee/correção/promoção (esses são M2–M5).

## Decisões já resolvidas (não reabrir no M1)
- **Mídia armazenada no próprio `training`** (resposta do dono) → volume local `MEDIA_DIR`, padrão `lead.MEDIA_DIR = /app/media`.
- **Endpoints de autoria são desmilitarizados** (§5) — sem auth, uso interno (painel/admin da plataforma).
- **Papel intermediário já se chama `training`** e o `candidate` já promove para ele ao concluir o funil (`candidate/app/services/selfie.py:104`). **Fora do escopo do M1.**
- PK = UUID (§4). `lead` usa `BigInteger` — é desvio; aqui seguimos a convenção (UUID), como manda §4.

## Patterns to Mirror
| Category | Source | Pattern |
|---|---|---|
| Wiring/app | `candidate/app/main.py` | `lifespan` (não `on_event`), `get_settings()` cacheado, handler global de `DomainError`→JSONResponse, `/health` `/ready` `/status`, `configure_logging`/`get_logger` |
| Config | `candidate/app/config.py` | pydantic-settings com `get_settings()` cacheado e env prefix (`CANDIDATE_APP_*` → `TRAINING_APP_*`) |
| DB | `lead/app/db.py` + `candidate/app/db.py` | `MetaData(naming_convention=…, schema=settings.DATABASE_SCHEMA)`, `Base`, shadow `auth.users`, engine async + `async_sessionmaker`, `get_session()`, `close_db()` |
| Mixins | `lead/app/models/_mixins.py` | `TimestampMixin` (`created_at`/`updated_at` server_default `now()`) |
| Model | `lead/app/models/lead.py` | `Mapped`/`mapped_column`, comments pt-br; **PK UUID** (não BigInteger) |
| Exceptions | `candidate/app/exceptions.py` | `DomainError` base + `NotFound`/`Conflict`/`ValidationError`/`IntegrationError`; services nunca importam HTTPException |
| Demilitarized API | `candidate/app/api/demilitarized/candidates.py` | `APIRouter(prefix="/api/v1/demilitarized", tags=["demilitarized"])`, `Depends(get_session)`, chama `services/`, devolve `schemas/` |
| Upload | `candidate/app/api/authenticated/selfie.py` + `services/selfie.py` | `UploadFile = File(...)`, `content = await file.read()`, service persiste o binário (aqui: local, não via `documents`) |
| Router agg | `candidate/app/api/router.py` | `api_router.include_router(...)` por router |
| Tests | `candidate/tests/conftest.py` | sqlite+aiosqlite via env **antes** de importar `app.*`, `DATABASE_SCHEMA=""`, drop/create por teste, `ASGITransport` client, factory fixtures |

## Modelo de dados (schema Postgres `training`)
Tabela `materials` (identificadores em inglês — §7; "matéria" → `Material`):
| Coluna | Tipo | Notas |
|---|---|---|
| `id` | UUID PK | `gen_random_uuid()` |
| `title` | VARCHAR | nome da matéria |
| `text_content` | TEXT | o "1 texto" |
| `question` | TEXT | a "1 questão" |
| `expected_answer` | TEXT | a "1 resposta esperada" |
| `video_path` | VARCHAR NULL | nulo na criação; preenchido no upload |
| `photo_path` | VARCHAR NULL | nulo na criação; preenchido no upload |
| `created_at`/`updated_at` | TIMESTAMPTZ | `TimestampMixin` |

Sem shadow table no M1 (matéria não referencia usuário). A shadow `auth.users` entra no db.py mesmo assim (preparada para M2+), mas sem FK ainda.

## Files to Change
| File | Action | Why |
|---|---|---|
| `training/pyproject.toml` | CREATE | stack canônica (§2) + `python-multipart` (UploadFile) |
| `training/.env.example` | CREATE | `TRAINING_APP_DB_URL`, `DATABASE_SCHEMA=training`, `MEDIA_DIR`, etc. |
| `training/.gitignore` | CREATE | espelha `lead/.gitignore` (§9 anti-ruído) |
| `training/Dockerfile` | CREATE | espelha `lead/Dockerfile` |
| `training/README.md` | CREATE | o que faz / como rodar / env (§3) |
| `training/CLAUDE.md` | CREATE | particularidades do serviço (§1) |
| `training/app/__init__.py` | CREATE | pacote |
| `training/app/main.py` | CREATE | mirror `candidate/app/main.py` |
| `training/app/config.py` | CREATE | mirror `candidate/app/config.py` (+ `MEDIA_DIR`, `MAX_UPLOAD_MB`, formatos aceitos) |
| `training/app/db.py` | CREATE | mirror `candidate/app/db.py` (schema `training`) |
| `training/app/exceptions.py` | CREATE | mirror `candidate/app/exceptions.py` |
| `training/app/utils/__init__.py` + `utils/logging.py` | CREATE | mirror `candidate/app/utils/logging.py` |
| `training/app/models/__init__.py` | CREATE | popula metadata (importa `Material`) |
| `training/app/models/_mixins.py` | CREATE | mirror `lead/app/models/_mixins.py` |
| `training/app/models/material.py` | CREATE | model `Material` (UUID PK) |
| `training/app/schemas/__init__.py` | CREATE | base schema (mirror candidate) |
| `training/app/schemas/material.py` | CREATE | `MaterialCreate`, `MaterialUpdate`, `MaterialOut`, `MaterialListResponse` (Pydantic v2) |
| `training/app/services/__init__.py` | CREATE | pacote |
| `training/app/services/material.py` | CREATE | regra de negócio: create/get/list/update matéria |
| `training/app/services/media.py` | CREATE | helper de storage local (salva/valida/resolve path em `MEDIA_DIR`) |
| `training/app/api/__init__.py` | CREATE | pacote |
| `training/app/api/router.py` | CREATE | agrega routers |
| `training/app/api/errors.py` | CREATE | mirror `candidate/app/api/errors.py` (uso futuro em M2) |
| `training/app/api/demilitarized/__init__.py` | CREATE | pacote |
| `training/app/api/demilitarized/materials.py` | CREATE | endpoints de autoria + upload/download de mídia |
| `training/alembic.ini` + `alembic/env.py` + `alembic/script.py.mako` | CREATE | mirror `lead/alembic*` |
| `training/alembic/versions/<date>_initial_training_schema.py` | CREATE | 1ª migração: schema `training` + tabela `materials` |
| `training/tests/conftest.py` | CREATE | mirror `candidate/tests/conftest.py` (sem mocks de integração ainda) |
| `training/tests/test_health.py` | CREATE | health/ready/status |
| `training/tests/test_materials.py` | CREATE | CRUD + upload/download (sucesso + 404 + validações) |
| `training/TODO` | KEEP | só apagar quando o serviço estiver pronto+aprovado e nascer `wiki/training.md` (§15) |

## Tasks
### Task 1: Esqueleto do serviço (estrutura + infra)
- **Action**: criar `pyproject.toml` (stack §2 + `python-multipart`), `.env.example`, `.gitignore`, `Dockerfile`, `app/__init__.py`, `config.py`, `db.py` (schema `training`), `exceptions.py`, `utils/logging.py`, `main.py` com `/health|/ready|/status`.
- **Mirror**: `candidate/app/{main,config,db,exceptions}.py`, `lead/{Dockerfile,.gitignore,alembic.ini}`.
- **Validate**: `cd training && ruff check . && python -c "import app.main"` (importável).

### Task 2: Modelo + migração inicial
- **Action**: `models/_mixins.py`, `models/material.py` (UUID PK, campos acima), `models/__init__.py`; configurar `alembic/env.py` apontando para `Base.metadata`; gerar `versions/<date>_initial_training_schema.py` criando schema `training` + tabela `materials`.
- **Mirror**: `lead/app/models/lead.py` (mas PK UUID), `lead/alembic/env.py` e `lead/alembic/versions/2026-05-15_initial_lead_schema.py`.
- **Validate**: `cd training && alembic upgrade head` num Postgres dev (e `alembic downgrade base` volta limpo).

### Task 3: Schemas + service de matéria
- **Action**: `schemas/material.py` (Create/Update/Out/ListResponse, Pydantic v2 `model_config`); `services/material.py` (create/get/list/update via `select()` async).
- **Mirror**: `candidate/app/schemas/candidate.py`, `candidate/app/services/candidate.py`.
- **Validate**: coberto pelos testes da Task 5.

### Task 4: Storage de mídia + endpoints desmilitarizados
- **Action**: `services/media.py` (salva binário em `MEDIA_DIR/{material_id}/{video|photo}.<ext>`, valida tamanho/mime, resolve caminho); `api/demilitarized/materials.py`:
  - `POST /api/v1/demilitarized/materials` (cria; vídeo/foto null) → 201
  - `GET /api/v1/demilitarized/materials` (lista) · `GET /…/{id}` (busca; 404 via `NotFound`)
  - `PUT /…/{id}` (atualiza campos de texto)
  - `POST /…/{id}/video` e `POST /…/{id}/photo` (`UploadFile`, grava e seta o path)
  - `GET /…/{id}/video` e `GET /…/{id}/photo` (devolve o arquivo via `FileResponse`; 404 se ausente)
  - registrar em `api/router.py`.
- **Mirror**: `candidate/app/api/demilitarized/candidates.py` (CRUD) + `candidate/app/api/authenticated/selfie.py` (upload `UploadFile`), mas storage local (não via `documents`).
- **Validate**: `cd training && ruff check .` + testes da Task 5.

### Task 5: Testes
- **Action**: `tests/conftest.py` (sqlite+aiosqlite, schema "", drop/create por teste, `ASGITransport`, factory `make_material`, `MEDIA_DIR` em tmpdir); `test_health.py`; `test_materials.py` (criar matéria, listar, buscar, 404, upload vídeo+foto, download, rejeição de mime/tamanho inválido).
- **Mirror**: `candidate/tests/conftest.py` + `candidate/tests/test_demilitarized.py`.
- **Validate**: `cd training && pytest -q`.

## Validation
```bash
cd /home/maestri33/backend/training
ruff check .
ruff format --check .
pytest -q
# Migração (Postgres dev): sobe e desce limpo
alembic upgrade head && alembic downgrade base && alembic upgrade head
```

## Risks
| Risk | Likelihood | Mitigation |
|---|---|---|
| `UploadFile` sem `python-multipart` → erro em runtime | Média | incluir `python-multipart` no `pyproject.toml` (Task 1) e cobrir upload em teste |
| Servir mídia local sem controle de acesso (alerta de `documents.md`) | Baixa | conteúdo de curso não é sensível como RG; servir via endpoint `GET` (`FileResponse`), não `StaticFiles` aberto |
| Crescimento ilimitado de `MEDIA_DIR` | Média | `MAX_UPLOAD_MB` + whitelist de mime no `media.py`; volume dedicado |
| Migração cross-schema/`gen_random_uuid()` exigir extensão | Baixa | usar `server_default=text("gen_random_uuid()")` (nativo PG13+) como no `roles` |
| `config.py` do candidate ter env prefix/campos que eu não li por inteiro | Baixa | abrir `candidate/app/config.py` e `utils/logging.py` na hora de criar e copiar fielmente |

## Acceptance
- [ ] Estrutura `training/app/...` espelha `candidate` (sem aninhamento `training/training`, §3)
- [ ] Só stack canônica (§2) + `python-multipart` justificado no `CLAUDE.md`
- [ ] PK UUID, schema próprio `training`, migração Alembic criada (§4)
- [ ] Endpoints de autoria desmilitarizados; upload/download de vídeo/foto funcionando
- [ ] `ruff check`/`ruff format` limpos; `pytest` verde
- [ ] `training/TODO` mantido (sai só com o serviço pronto + `wiki/training.md`)
- [ ] Sem lógica de trainee/correção/promoção/notify (fica para M2–M5)
```
