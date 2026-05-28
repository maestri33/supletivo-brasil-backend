# address

Microsserviço de endereços da plataforma. Armazena endereços tipados vinculados a
`auth.users` (tabela `addresses`) e um vínculo polimórfico genérico para qualquer
entidade (tabela `entity_addresses`). Integra ViaCEP para lookup de CEP. Doc
completa: `../wiki/address.md`.

## Rodar

```bash
uv sync
cp .env.example .env      # ajuste DATABASE_URL
uv run alembic upgrade head
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Testes / lint

```bash
uv run pytest -q           # testes ainda ausentes (COD-25)
uv run ruff check . && uv run ruff format --check .
```

## Variáveis (`.env`)

| Var | Obrigatória | Descrição |
|-----|:-:|-----------|
| `DATABASE_URL` | ✅ | Postgres async (`postgresql+asyncpg://...`) |
| `DATABASE_SCHEMA` | | schema (default `addresses`) |

## Endpoints (todos desmilitarizados)

- **Address:** `POST/GET /api/v1/addresses`, `GET /by-external-id/{id}`, `GET /{id}`, `PATCH /{id}`, `DELETE /{id}`, `GET /cep/{zipcode}`
- **Entity:** `GET /api/v1/entities/{type}/{id}`, `POST .../cep`, `POST .../proof`, `POST .../unlink`
- **Saúde:** `/health`, `/ready`, `/status`
