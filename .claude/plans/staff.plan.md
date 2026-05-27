# Plan: Staff — Milestone 1 (Scaffolding + Auth)

**Source PRD**: `.claude/prds/staff.prd.md`
**Selected Milestone**: #1 Scaffolding + Auth — *serviço sobe com `/health` próprio; operação autentica via JWT + role admin/staff*
**Complexity**: Medium (novo serviço, mas espelha `lead`/`profiles` quase 1:1)

## Summary
Criar o esqueleto do serviço `staff` conforme CONVENTION.md (§3), espelhando o app-modelo `lead`: app FastAPI com lifespan, logging estruturado, CORS, health/ready/status próprios, camada de banco async (schema `staff`) e o gate de autenticação JWT+role (admin/staff). Sem modelos de domínio ainda — hub/coordenador entram nos milestones 4/5. Entrega verificável: serviço sobe, `/health` responde, e um endpoint autenticado de prova (`/api/v1/authenticated/me`) rejeita sem token/role e aceita com role válida.

## Patterns to Mirror
| Category | Source | Pattern |
|---|---|---|
| App/entrypoint | `lead/app/main.py:1-107` | FastAPI + `lifespan` + `fastapi_structured_logging` + CORS + AccessLog + health/ready/status na raiz |
| Config | `lead/app/config.py:1-82` | `pydantic-settings` `BaseSettings`, `model_config` env_file, instância `settings` |
| DB | `lead/app/db.py:1-68` | `create_async_engine` + `async_sessionmaker` + `Base`/`metadata(schema=...)` + `NAMING_CONVENTION` + `get_session()` |
| Auth | `lead/app/dependencies.py:17-66` | JWKS cache 5min + `jwt.decode` RS256 (`require exp/roles/external_id`) + check de role |
| Health schema | `lead/app/api/public/health.py:1-5` | `HealthOut(BaseModel)` |
| Tests | `profiles/tests/conftest.py` + `profiles/tests/test_health.py` | `ASGITransport`+`AsyncClient` fixture; testes de `/health`,`/ready`,`/status` |
| pyproject | `lead/pyproject.toml:1-43` | hatchling `packages=["app"]`, stack canônica, ruff `line-length=100`/`py312`, pytest `asyncio_mode=auto` |
| Alembic | `lead/alembic/` + `lead/alembic.ini` | env async (skeleton, sem versions ainda) |

## Files to Change
| File | Action | Why |
|---|---|---|
| `staff/app/__init__.py` | CREATE | pacote |
| `staff/app/main.py` | CREATE | FastAPI app, lifespan, logging, CORS, AccessLog, health/ready/status, registra router autenticado |
| `staff/app/config.py` | CREATE | `Settings` (SERVICE_NAME=staff, DATABASE_URL, DATABASE_SCHEMA=staff, JWT_BASE_URL, STAFF_ROLES, CORS, HTTP_TIMEOUT) |
| `staff/app/db.py` | CREATE | engine async + `Base`/`metadata(schema="staff")` + `get_session()` (sem shadow tables ainda) |
| `staff/app/dependencies.py` | CREATE | `get_jwks`, `get_current_external_id` exigindo role ∈ STAFF_ROLES (admin/staff) |
| `staff/app/exceptions.py` | CREATE | exceções de domínio (mínimo; base p/ milestones seguintes) |
| `staff/app/api/__init__.py` | CREATE | pacote |
| `staff/app/api/health.py` | CREATE | `HealthOut` schema (status/service) |
| `staff/app/api/authenticated/__init__.py` | CREATE | agrega routers autenticados |
| `staff/app/api/authenticated/me.py` | CREATE | `GET /api/v1/authenticated/me` — endpoint de prova do gate JWT+role |
| `staff/pyproject.toml` | CREATE | build/deps/ruff/pytest (stack canônica) |
| `staff/alembic.ini` | CREATE | config alembic |
| `staff/alembic/env.py` | CREATE | env async (mirror lead), `versions/` vazio |
| `staff/alembic/script.py.mako` | CREATE | template migração |
| `staff/alembic/versions/.gitkeep` | CREATE | manter pasta |
| `staff/tests/__init__.py` | CREATE | pacote |
| `staff/tests/conftest.py` | CREATE | fixture `client` (ASGITransport) |
| `staff/tests/test_health.py` | CREATE | testa `/health`,`/ready`,`/status` |
| `staff/tests/test_auth.py` | CREATE | gate: sem token → 403; token inválido → 401 |
| `staff/.env.example` | CREATE | vars: DATABASE_URL, DATABASE_SCHEMA, JWT_BASE_URL, STAFF_ROLES, CORS, LOG_LEVEL |
| `staff/.gitignore` | CREATE | `.venv`,`__pycache__`,`.env`,`.ruff_cache`,`.pytest_cache` (§9) |
| `staff/Dockerfile` | CREATE | imagem do serviço (mirror lead) |
| `staff/CLAUDE.md` | CREATE | particularidades: staff dono de hub/coordenador; role admin/staff; fronteira c/ hub-coordinator paralelos |
| `staff/README.md` | CREATE | o que faz, como rodar, env vars (enxuto) |

## Tasks
### Task 1: pyproject + config + .env.example
- **Action**: criar `pyproject.toml` (copiar stack de `lead`, name=`staff`), `config.py` com `Settings` enxuto (identidade, DATABASE_URL, DATABASE_SCHEMA="staff", JWT_BASE_URL, `STAFF_ROLES: list[str] = ["admin","staff"]`, CORS, HTTP_TIMEOUT) e `.env.example`.
- **Mirror**: `lead/pyproject.toml`, `lead/app/config.py`.
- **Validate**: `cd staff && uv sync` instala sem erro.

### Task 2: camada de banco (db.py)
- **Action**: engine async, `metadata(naming_convention, schema="staff")`, `Base`, `async_session_maker`, `get_session()`. Sem shadow tables (entram no milestone que criar FK→auth.users).
- **Mirror**: `lead/app/db.py:1-68` (sem o bloco shadow).
- **Validate**: `python -c "from app.db import engine, get_session"` importa.

### Task 3: auth dependency (dependencies.py)
- **Action**: `get_jwks()` (cache 5min via JWT_BASE_URL `/.well-known/jwks.json`), `get_current_external_id()` decodifica RS256 exigindo `exp/roles/external_id` e checa interseção `roles ∩ STAFF_ROLES` (senão 403). Reaproveitável por todos os endpoints de gestão futuros.
- **Mirror**: `lead/app/dependencies.py:17-66` (troca `"lead" not in roles` por checagem contra `settings.STAFF_ROLES`).
- **Validate**: import ok; coberto pelo `test_auth.py`.

### Task 4: app FastAPI + health + endpoint de prova
- **Action**: `main.py` (lifespan, `setup_logging`, CORS, AccessLog excluindo health, `/health`,`/ready`,`/status`; `/ready` faz `SELECT 1` async tolerante a falha). `api/health.py` (`HealthOut`). `api/authenticated/me.py` (`GET /api/v1/authenticated/me` → `{external_id}` via `Depends(get_current_external_id)`), agregado em `api/authenticated/__init__.py` e incluído no app.
- **Mirror**: `lead/app/main.py:32-107`, `profiles` `/ready` com check de DB.
- **Validate**: `uvicorn app.main:app` sobe; `curl /health`→200; `curl /api/v1/authenticated/me` sem token→403.

### Task 5: alembic skeleton
- **Action**: `alembic.ini`, `alembic/env.py` async (offline+online), `script.py.mako`, `versions/.gitkeep`. Sem migração (não há modelo no milestone 1).
- **Mirror**: `lead/alembic/env.py`, `lead/alembic.ini`.
- **Validate**: `cd staff && alembic check` (ou `alembic history`) roda sem erro de config.

### Task 6: testes (health + auth gate)
- **Action**: `conftest.py` (fixture `client` ASGITransport), `test_health.py` (status 200 + payload), `test_auth.py` (sem token→403; token inválido→401).
- **Mirror**: `profiles/tests/conftest.py`, `profiles/tests/test_health.py`.
- **Validate**: `cd staff && pytest` verde.

### Task 7: Dockerfile + .gitignore + CLAUDE.md + README
- **Action**: `Dockerfile` (mirror lead), `.gitignore` (§9), `CLAUDE.md` (particularidades + nota da fronteira hub/coordinator paralelos), `README.md` enxuto.
- **Mirror**: `lead/Dockerfile`, `lead/.gitignore`.
- **Validate**: `ruff check staff && ruff format --check staff` limpos.

## Validation
```bash
cd staff
uv sync
ruff check . && ruff format --check .
pytest
# manual smoke:
# uvicorn app.main:app --port 8000
# curl :8000/health        -> {"status":"ok","service":"staff"}
# curl :8000/status        -> inclui version/uptime
# curl :8000/api/v1/authenticated/me  -> 403 (sem token)
```

## Risks
| Risk | Likelihood | Mitigation |
|---|---|---|
| `/ready` quebra se DB indisponível no boot | Média | check `SELECT 1` em try/except, retorna status degradado em vez de 500 |
| Divergência de versão da stack vs. demais serviços | Baixa | copiar versões exatas do `lead/pyproject.toml` |
| Alembic env async mal configurado (sem models ainda) | Baixa | skeleton sem `target_metadata` de tabela; validar só config |
| Testar token JWT válido exige JWKS real | Média | milestone 1 testa só rejeição (403/401); caminho feliz coberto quando houver fixture de JWT |

## Acceptance
- [ ] `staff/` segue a estrutura §3 (app/api/models?/schemas?/services?/, tests, pyproject, alembic) — models/schemas/services entram nos próximos milestones
- [ ] `uvicorn app.main:app` sobe e `/health`,`/ready`,`/status` respondem
- [ ] `GET /api/v1/authenticated/me` rejeita sem token (403) e com token inválido (401)
- [ ] `pytest` verde; `ruff check`/`ruff format` limpos
- [ ] Padrões espelhados de `lead`/`profiles`, não reinventados
- [ ] Stack 100% canônica (§2); nada de lib proibida
```
