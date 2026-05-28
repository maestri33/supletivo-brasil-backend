# student

## Função

Gerencia o **ciclo de vida do aluno** — da promoção pós-matrícula até a
certificação final. Controla o funil completo: envio de documentos, agendamento
de provas, correção, emissão de certificado/histórico e transição para veterano.

---

## Status

**Milestone 1 — promoção funcional.** Coordenador promove matriculado a aluno
(POST) e aluno consulta seus dados (GET /me). Status inicial: `AWAITING_DOCUMENTS`.

Próximos milestones implementam o funil completo conforme `TODO`.

---

## Estrutura

```
student/
├── app/
│   ├── main.py           # FastAPI, lifespan, /health, /ready, /status
│   ├── config.py         # Settings (pydantic-settings) — STUDENT_APP_DB_URL
│   ├── db.py             # engine async, Base, NAMING_CONVENTION, get_session()
│   ├── dependencies.py   # validação JWT RS256 + gate por role
│   ├── exceptions.py     # DomainError, StudentNotFound, StudentAlreadyExists
│   ├── api/
│   │   ├── health.py
│   │   └── authenticated/
│   │       └── students.py   # POST promote, GET /me
│   ├── models/
│   │   ├── _mixins.py        # TimestampMixin
│   │   └── student.py        # Student + StudentStatus enum
│   ├── schemas/
│   │   └── student.py        # PromoteRequest, StudentRead
│   └── services/
│       └── student_service.py  # promote(), get_by_external_id()
├── alembic/
├── tests/
├── pyproject.toml
├── Makefile
└── Dockerfile
```

---

## Modelo de dados

### Tabela `student.students`

| Coluna | Tipo | Constraints | Descrição |
|---|---|---|---|
| `id` | UUID | PK, default uuid4 | ID interno |
| `external_id` | UUID | UNIQUE, FK→auth.users.external_id (RESTRICT) | ID do usuário no auth |
| `status` | StudentStatus | NOT NULL, indexed | Status atual do funil |
| `study_platform` | JSONB | NOT NULL, default {} | Dados da plataforma de estudo |
| `created_at` | timestamptz | server_default now() | Criação |
| `updated_at` | timestamptz | server_default now(), onupdate | Última atualização |

### StudentStatus (enum completo)

| Status | Descrição |
|---|---|
| `awaiting_documents` | Aguardando envio de documentos (inicial) |
| `documents_under_review` | Documentos em análise pela IA |
| `exam_released` | Prova liberada para agendamento |
| `exam_scheduled` | Prova agendada |
| `exam_failed` | Reprovado — reagendar |
| `awaiting_documentation_dispatch` | Aguardando envio de documentação |
| `pending` | Pendência (ex.: comissão do coordenador) |
| `awaiting_diploma_issuance` | Aguardando emissão do certificado |
| `awaiting_pickup` | Aguardando retirada do certificado |
| `veteran` | Formado (veterano) — dispara comissão |

---

## Endpoints

### Health/Status (disponíveis)

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/health` | Healthcheck simples |
| GET | `/ready` | Readiness |
| GET | `/status` | Versão, ambiente, uptime |

### Negócio (disponíveis — Milestone 1)

| Método | Rota | Tipo | Role | Descrição |
|--------|------|------|------|-----------|
| POST | `/api/v1/authenticated/students` | Autenticado | `coordinator` | Promover matriculado a aluno |
| GET | `/api/v1/authenticated/students/me` | Autenticado | `student` | Aluno consulta seus dados |

### Planejados (próximos milestones)

| Método | Rota | Tipo | Descrição |
|--------|------|------|-----------|
| POST | `/api/v1/authenticated/students/documents` | Autenticado (`student`) | Upload de documento (RG, certificado, etc.) |
| GET | `/api/v1/authenticated/students/documents` | Autenticado (`student`) | Listar documentos |
| POST | `/api/v1/authenticated/students/exams/schedule` | Autenticado (`student`) | Agendar prova |
| PATCH | `/api/v1/authenticated/students/{id}/exam-result` | Autenticado (`coordinator`) | Registrar resultado da prova |
| GET | `/api/v1/authenticated/students/{id}` | Autenticado (`coordinator`) | Coordenador consulta aluno |

---

## Notas técnicas

- **FK cross-schema real:** `students.external_id` → `auth.users.external_id`.
  É a única FK cross-schema real do projeto (RESTRICT on delete, CASCADE on update).
- **Idempotência:** promover aluno já existente levanta `StudentAlreadyExists` (409).
- **study_platform:** JSONB livre — dados da plataforma de estudos (URL, login, etc.)
  informados pelo coordenador na promoção.
- **Enum completo:** os 10 status do `StudentStatus` são definidos desde o
  Milestone 1 para evitar migração de tipo a cada milestone.
- **Schema:** `student` (próprio, conforme CONVENTION §4).
- **Engine:** async (`create_async_engine` + `asyncpg`).
- **JWT:** RS256 via JWKS do serviço `jwt`, cache 5 min.

---

## Dependências

- **auth** — FK real para `auth.users.external_id`
- **jwt** — validação de token (JWKS)
- **enrollment** — origem da promoção (coordenador promove enrollment→student)
- **documents** — upload e validação de documentos (RG, certificado, histórico)
- **notify** — notificações de mudança de status
- **commissions** — comissão do coordenador ao virar veterano
- **ai** — validação assíncrona de documentos (OCR, verificação)

---

## Variáveis de ambiente

| Variável | Descrição | Exemplo |
|---|---|---|
| `STUDENT_APP_DB_URL` | URL de conexão Postgres | `postgresql+asyncpg://...` |
| `DATABASE_SCHEMA` | Schema do serviço | `student` |
| `JWT_BASE_URL` | Base URL do serviço jwt | `http://jwt:80` |
| `CORS_ORIGINS` | Origens CORS (JSON) | `["*"]` |
| `SERVICE_NAME` | Nome do serviço | `student` |
