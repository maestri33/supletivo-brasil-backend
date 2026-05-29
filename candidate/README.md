# candidate

Funil de cadastro de **candidatos a promotor** (aspirantes). Orquestra as etapas
do cadastro chamando os serviços donos de cada dado (auth, profiles, address,
documents, asaas, roles) e, ao concluir, promove o usuário para `training`.

## Funil (status)
```
captured → personal → education → birth → address → documents → pixkey → selfie → completed
```
Cada `POST` de etapa salva no serviço dono e avança o status; cada `GET` lê o estado.

## Stack
FastAPI · SQLAlchemy 2.0 async + asyncpg · Alembic · Pydantic v2 · httpx · structlog · uv.
Banco: Postgres central, schema **`candidate`**.

## Rodar
```bash
uv sync
cp .env.example .env      # ajuste CANDIDATE_APP_DB_URL e as *_BASE_URL
uv run alembic upgrade head
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Testes / lint
```bash
uv run pytest -q          # sqlite+aiosqlite, integrações stubadas
uv run ruff check . && uv run ruff format --check .
```

## Endpoints (resumo)
- **público:** `POST /api/v1/public/{check,register,login,refresh}`
- **autenticado** (JWT role `lead`): `/api/v1/authenticated/{captured,personal,educational,birth,address,documents,pixkey,selfie}`
- **interno:** `GET /api/v1/demilitarized/candidates[/{external_id}]`
- **saúde:** `/health`, `/ready`, `/status`

Detalhes funcionais: `wiki/candidate.md`. Regras para o Claude Code: `.claude/CLAUDE.md`.

## Pendência
A criação do registro no serviço `training` (passo 6 do `TODO`) entra quando esse
serviço existir; hoje a conclusão promove o papel lead→training via `roles`.
