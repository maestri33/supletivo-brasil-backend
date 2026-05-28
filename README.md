# Backend — Plataforma Supletivo

> Microsserviços Python/FastAPI para gestão de cursos supletivos — matrícula, pagamentos, notas e certificação.

---

## Arquitetura

22 microsserviços independentes — **1 serviço = 1 diretório = 1 container = 1 schema Postgres = 1 responsabilidade**.

| Camada | Serviços |
|---|---|
| Identidade & Acesso | `auth`, `jwt`, `otp`, `roles`, `profiles` |
| Domínio (core) | `candidate`, `enrollment`, `student`, `training`, `lead`, `promoter`, `hub`, `coordinator`, `staff` |
| Financeiro | `asaas`, `infinitepay`, `fees`, `commissions` |
| Infra & Utilidades | `address`, `ai`, `documents`, `notify` |

---

## Stack

| Camada | Tecnologia |
|---|---|
| Runtime | Python 3.12 |
| Web | FastAPI + uvicorn |
| ORM | SQLAlchemy 2.0 async + asyncpg |
| Migrações | Alembic |
| Validação | Pydantic v2 + pydantic-settings |
| HTTP | httpx.AsyncClient |
| Logs | structlog |
| Cache | Redis |
| Orquestração | Docker + docker-compose |

---

## Começo Rápido

### Pré-requisitos

- Python 3.12 + `uv`
- Docker + docker-compose (para Postgres/Redis)
- `make`

### Subir ambiente de desenvolvimento

```bash
# Infra compartilhada (Postgres + Redis)
docker compose up -d postgres redis

# Subir um serviço individual
cd <servico>/
make install    # uv sync
make dev        # uvicorn com reload
```

---

## Documentação

| Documento | Propósito |
|---|---|
| `CONVENTION.md` | Padrão de código obrigatório para todos os serviços |
| `CONTRIBUTING.md` | Guia de contribuição, commits e branches |
| `.github/PULL_REQUEST_TEMPLATE.md` | Template de PR com checklist de conformidade |
| `wiki/<servico>.md` | Documentação funcional de cada serviço (fonte de verdade §15) |
| `wiki/RUNBOOK.md` | Guia operacional — subir, derrubar, backup, restore, on-call |
| `wiki/PLANO_ADEQUACAO.md` | Plano de adequação dos 14 apps existentes + 8 novos |

### CLAUDE.md

Cada serviço tem seu `CLAUDE.md` em `<servico>/.claude/CLAUDE.md` com regras e particularidades. **Leia antes de mexer no serviço.**

---

## Links

- Repo: `git@github.com:...` (definir)
- Convenção: [`CONVENTION.md`](CONVENTION.md)
- Contribuição: [`CONTRIBUTING.md`](CONTRIBUTING.md)
