# coordinator

**Status: implementado (WS-CORE).**

Microsserviço de gestão de coordenadores de polo — administradores locais
de operações acadêmicas. Possui todas as capacidades de um promotor, mais
funções administrativas do polo.

## Função

- Aprovar treinamentos e promover candidatos a promotores (integração com roles)
- Gerenciar documentos e matrículas de alunos
- Aplicar provas e postar resultados
- Postar diplomas e fotos de conclusão (dispara comissão via commissions)

## Stack

FastAPI + SQLAlchemy 2.0 async + asyncpg + Alembic + Pydantic v2 +
httpx.AsyncClient + structlog + pytest-asyncio.

## Como rodar

```bash
uv sync
uv run uvicorn app.main:app --reload --port 8015
```

## Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/api/v1/coordinators` | Criar coordenador |
| GET | `/api/v1/coordinators` | Listar coordenadores |
| GET | `/api/v1/coordinators/{id}` | Detalhe do coordenador |
| PATCH | `/api/v1/coordinators/{id}` | Atualizar status |
| POST | `/api/v1/training-approvals` | Criar aprovação de treinamento |
| GET | `/api/v1/training-approvals` | Listar aprovações |
| PATCH | `/api/v1/training-approvals/{id}` | Aprovar/rejeitar treinamento → dispara promoção |
| POST | `/api/v1/enrollment-fees` | Criar taxa de matrícula |
| GET | `/api/v1/enrollment-fees` | Listar taxas |
| POST | `/api/v1/enrollment-fees/{id}/pay` | Pagar taxa |
| POST | `/api/v1/exams` | Criar prova |
| GET | `/api/v1/exams` | Listar provas |
| POST | `/api/v1/exams/{id}/submit` | Submeter prova |
| POST | `/api/v1/exams/{id}/grade` | Corrigir e postar nota |
| POST | `/api/v1/documents` | Criar documento do aluno |
| GET | `/api/v1/documents` | Listar documentos |
| POST | `/api/v1/documents/{id}/submit` | Enviar documento à instituição |
| POST | `/api/v1/diplomas` | Criar diploma |
| GET | `/api/v1/diplomas` | Listar diplomas |
| POST | `/api/v1/diplomas/{id}/graduate` | Graduar aluno + disparar comissão |

## Integrações

- **commissions**: dispara comissão do coordenador ao graduar aluno (R$ 0,50)
- **roles**: promove candidato → promoter ao aprovar treinamento
- **hub**: referência lógica ao polo do coordenador

## Testes

```bash
uv run pytest tests/ -v
```
