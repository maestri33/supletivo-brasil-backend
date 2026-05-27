# staff

Serviço de **administração (boss da operação)** — cadastro de hubs, definição
de coordenadores e health aggregation da plataforma.

## O que faz

Staff é o serviço administrativo da plataforma. Responsável por:
- Cadastrar e gerenciar polos (hubs)
- Definir e gerenciar coordenadores por polo
- Agregar health de todos os serviços (dashboard operacional)

Acesso restrito a roles `admin` e `staff` com JWT validado via JWKS.

## Stack

Python 3.12 · FastAPI · SQLAlchemy 2.0 async · asyncpg · Alembic · structlog · PyJWT

## Status

**Milestone 1** — spine funcional (config, db, JWT validation). Endpoints de
negócio e modelos de domínio entram nos milestones 4/5.

## Como rodar

```bash
cd staff/
uv sync
uv run uvicorn app.main:app --reload
```

## Variáveis de ambiente

| Variável | Descrição | Exemplo |
|---|---|---|
| `DATABASE_URL` | URL de conexão Postgres | `postgresql+asyncpg://...` |
| `DATABASE_SCHEMA` | Schema do serviço | `staff` |
| `JWT_BASE_URL` | Base URL do serviço jwt | `http://jwt:80` |
| `STAFF_ROLES` | Roles aceitas (JSON) | `["admin","staff"]` |
| `SERVICE_NAME` | Nome do serviço | `staff` |
| `ENVIRONMENT` | Ambiente | `development` / `production` |

## Documentação

| Documento | Local |
|---|---|
| Doc funcional completa | `wiki/staff.md` |
| Regras do Claude Code | `.claude/CLAUDE.md` |
| Convenção geral | `CONVENTION.md` (raiz) |
