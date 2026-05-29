# student

Serviço de **gestão de alunos** — ciclo de vida do aluno desde a matrícula
até a certificação.

## O que faz

Gerencia o funil do aluno após a matrícula:
- Promoção do enrollment para student (coordenador)
- Status do funil: documentos, provas, certificação, formatura
- Consulta de dados próprios pelo aluno

## Stack

Python 3.12 · FastAPI · SQLAlchemy 2.0 async · asyncpg · Alembic · structlog · PyJWT

## Status

**Milestone 1** — promoção (enrollment→student) + consulta de dados próprios
funcionais. Próximos milestones: upload de documentos, agendamento de provas,
emissão de certificado.

## Como rodar

```bash
cd student/
make install    # uv sync
make dev        # uvicorn com reload (porta 80)
```

## Variáveis de ambiente

| Variável | Descrição | Exemplo |
|---|---|---|
| `STUDENT_APP_DB_URL` | URL de conexão Postgres | `postgresql+asyncpg://...` |
| `DATABASE_SCHEMA` | Schema do serviço | `student` |
| `JWT_BASE_URL` | Base URL do serviço jwt | `http://jwt:80` |
| `CORS_ORIGINS` | Origens CORS (JSON) | `["*"]` |

## Documentação

| Documento | Local |
|---|---|
| Doc funcional completa | `wiki/student.md` |
| Regras do Claude Code | `.claude/CLAUDE.md` |
| Convenção geral | `CONVENTION.md` (raiz) |
