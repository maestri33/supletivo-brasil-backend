# hub

Serviço de **polos (hubs)** — unidades físicas da operação educacional.

## O que faz

Gerencia o cadastro e consulta de polos. Cada polo conecta uma localidade
física a um endereço, coordenador, promotores e alunos. É a entidade raiz
da operação presencial.

## Stack

Python 3.12 · FastAPI · SQLAlchemy 2.0 async · asyncpg · Alembic · structlog

## Como rodar

```bash
cd hub/
make install    # uv sync
make dev        # uvicorn com reload (porta 80)
```

## Variáveis de ambiente

| Variável | Descrição | Exemplo |
|---|---|---|
| `DATABASE_URL` | URL de conexão Postgres | `postgresql+asyncpg://...` |
| `DATABASE_SCHEMA` | Schema do serviço | `hub` |
| `ENV` | Ambiente | `dev` / `staging` / `prod` |
| `LOG_LEVEL` | Nível de log | `INFO` |

## Documentação

| Documento | Local |
|---|---|
| Doc funcional completa | `wiki/hub.md` |
| Regras do Claude Code | `.claude/CLAUDE.md` |
| Convenção geral | `CONVENTION.md` (raiz) |
