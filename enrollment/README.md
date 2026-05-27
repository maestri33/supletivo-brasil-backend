# enrollment

Serviço de matrícula — gerencia o fluxo de inscrição de candidatos aprovados no
treinamento. Orquestra a transição `training → student`, cria o registro de
matrícula, gerencia turmas e coordena com `fees` a cobrança da taxa. Doc
completa: `../wiki/enrollment.md`.

## Rodar

```bash
uv sync
cp .env.example .env      # ajuste DATABASE_URL e *_BASE_URL
uv run alembic upgrade head
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Testes / lint

```bash
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
```

## Variáveis (`.env`)

| Var | Obrigatória | Descrição |
|-----|:-:|-----------|
| `DATABASE_URL` | ✅ | Postgres async (`postgresql+asyncpg://...`) |
| `FEES_BASE_URL` | | URL do serviço `fees` |
| `ROLES_BASE_URL` | | URL do serviço `roles` |
| `NOTIFY_BASE_URL` | | URL do serviço `notify` |

## Endpoints

- **Autenticado:** `POST /api/v1/authenticated/enrollments`, `GET /{id}`, `GET /student/{external_id}`
- **Coordenador:** `PATCH /api/v1/authenticated/enrollments/{id}/status`
- **Desmilitarizado:** `GET /api/v1/demilitarized/enrollments/{external_id}`
- **Saúde:** `/health`, `/ready`, `/status`
