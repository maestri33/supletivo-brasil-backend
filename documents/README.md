# documents

Serviço de documentos (PDFs, comprovantes e outros arquivos) vinculados a
`auth.users` e entidades polimórficas. Armazena metadados no banco e arquivos
binários em disco (`DOCUMENTS_STORAGE_DIR`). Suporta upload, download, listagem e
exclusão. Doc completa: `../wiki/documents.md`.

## Rodar

```bash
uv sync
cp .env.example .env      # ajuste DATABASE_URL
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
| `DOCUMENTS_STORAGE_DIR` | | Diretório de arquivos (default `./storage`) |
| `MAX_FILE_SIZE_MB` | | Limite de upload (default `50`) |

## Endpoints (todos desmilitarizados)

- **Documents:** `POST/GET /api/v1/documents`, `GET/DELETE /{id}`, `GET /{id}/file`
- **Entidades:** `GET /api/v1/entities/{type}/{id}/documents`, `POST .../upload`, `GET .../file`
- **Saúde:** `/health`, `/ready`, `/status`
