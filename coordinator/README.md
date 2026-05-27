# coordinator

**Status: não criado (Parte B — Sprint futuro).**

Microsserviço de gestão de coordenadores de polo — administradores locais
de operações acadêmicas. Possui todas as capacidades de um promotor, mais
funções administrativas do polo.

## Função

- Aprovar treinamentos e promover candidatos
- Gerenciar documentos e matrículas de alunos
- Aplicar provas e postar resultados
- Postar diplomas e fotos de conclusão

## Requisitos

- `wiki/coordinator.md` — especificação completa
- `TODO` — requisitos do engenheiro

## Stack planejada

FastAPI + SQLAlchemy 2.0 async + asyncpg + Alembic + Pydantic v2 +
httpx.AsyncClient + structlog + pytest-asyncio.

## Como rodar (futuro)

```bash
uv sync
uv run uvicorn app.main:app --reload
```
