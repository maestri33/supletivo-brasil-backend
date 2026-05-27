# roles

Motor de regras de transição de papéis (roles) de usuários no pipeline v7m.
Mantém catálogo de regras (`role_rules`) e histórico de atribuições (`user_roles`),
com políticas de `add`/`replace`, pré-requisitos e incompatibilidades. Dono
exclusivo da tabela de roles. Doc completa: `../wiki/roles.md`.

## Rodar

```bash
cd roles/roles             # aninhamento roles/roles/app (desvio §3)
uv sync
cp .env.example .env       # ajuste DATABASE_URL
uv run alembic upgrade head
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Testes / lint

```bash
uv run pytest -q           # testes ausentes (gap de qualidade)
uv run ruff check . && uv run ruff format --check .
```

## Variáveis (`.env`)

| Var | Obrigatória | Descrição |
|-----|:-:|-----------|
| `DATABASE_URL` | ✅ | Postgres async (`postgresql+asyncpg://...`) |
| `DATABASE_SCHEMA` | | schema (default `roles`) |

## Endpoints (todos desmilitarizados)

- **Role:** `GET /api/v1/role`, `GET /{external_id}`, `GET /{external_id}/blocked`, `POST /{external_id}/{role}`, `POST /{external_id}/up/{to_role}`, `DELETE /{external_id}`
- **Regras:** `GET/POST /api/v1/config/roles`, `GET/PATCH/DELETE /{rule_id}`
- **Users:** `GET /api/v1/users`, `DELETE /{external_id}`
- **Saúde:** `/health`, `/ready`, `/status`
