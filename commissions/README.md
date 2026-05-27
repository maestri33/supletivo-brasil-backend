# commissions

**Status: não criado (Parte B — Sprint futuro).**

Microsserviço de cálculo e pagamento de comissões para promotores e
coordenadores. Processa pagamentos semanais via PIX (integração Asaas).

## Função

- Comissão por lead concluído (promotor)
- Comissão por graduação de aluno (coordenador)
- Processamento semanal com bônus por meta
- Pagamento PIX via Asaas

## Requisitos

- `wiki/commissions.md` — especificação completa
- `TODO` — requisitos do engenheiro

## Stack planejada

FastAPI + SQLAlchemy 2.0 async + asyncpg + Alembic + Pydantic v2 +
httpx.AsyncClient + structlog + pytest-asyncio.

## Como rodar (futuro)

```bash
uv sync
uv run uvicorn app.main:app --reload
```
