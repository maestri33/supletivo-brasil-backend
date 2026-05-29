# CLAUDE.md — Memória e regras do microsserviço `student`

> Fonte da verdade para você (Claude Code) sobre o serviço `student`. Leia inteiro
> antes de agir. Se algo aqui conflita com o pedido atual, **pergunte** — não
> decida sozinho. A convenção geral é `CONVENTION.md` (raiz); este arquivo só
> pode ser **mais restritivo**. Doc funcional completa: `wiki/student.md`.

---

## 1. Quem é você aqui

- Claude Code **exclusivo deste serviço**. Fala com outros serviços só por HTTP.
- Papel: gerenciar o **ciclo de vida do aluno** — desde a promoção do
  enrollment (coordenador define plataforma de estudo) até a formatura
  (veterano). Controla status do funil, documentos, agendamento de provas,
  emissão de certificado e histórico.
- **É caminho de dinheiro?** Não. Mas a transição para veterano dispara
  comissão do coordenador (via `commissions`).
- Schema `student`. PK = UUID.

## 2. Regras de ouro (não negociáveis)

1. **Não alucine.** Sem certeza? Consulte o código ou pergunte.
2. **Faça só o que foi pedido.** Sugestões no fim da resposta, não no código.
3. **Stack fixa (§2).** FastAPI + SQLAlchemy 2.0 async + asyncpg + Alembic +
   Pydantic v2 + httpx.AsyncClient + structlog + pydantic-settings.
4. **Cada serviço, seu schema.** Schema `student`. `external_id` e' referencia
   logica ao `auth.users` (UUID opaco). **Sem FK cross-schema** (§4 do CONVENTION).
5. **Autenticação obrigatória.** Endpoints de negócio exigem JWT + role
   (`coordinator` para promover, `student` para consultar).
6. **Idempotência na promoção.** Promover aluno já existente levanta 409
   (`StudentAlreadyExists`). NUNCA duplique.
7. **Toda mudança de modelo → migração Alembic.**
8. **Toda transição de status → notificação assíncrona** (§11). Templates em
   `<servico>/app/notify/messages/` (a criar nos próximos milestones).
9. **Comentário/doc em pt-br** e verdadeiro; logs técnicos em inglês.

## 3. Stack

| Camada | Tecnologia |
|---|---|
| Runtime | Python 3.12 + `uv` |
| Web | FastAPI + uvicorn |
| ORM | SQLAlchemy 2.0 async (`Mapped`/`mapped_column`, `select()`) |
| Driver | asyncpg (Postgres central, schema `student`) |
| Migrations | Alembic |
| Validação/Config | Pydantic v2 + pydantic-settings (`.env`) |
| HTTP cliente | httpx.AsyncClient (jwt, notify, documents) |
| Auth | PyJWT + JWKS (RS256, via serviço jwt) |
| Logs | structlog |
| Testes | pytest + pytest-asyncio |

## 4. Estrutura

```
student/app/
├── main.py           # FastAPI; lifespan; /health, /ready, /status
├── config.py         # Settings (.env) — STUDENT_APP_DB_URL, JWT_BASE_URL
├── db.py             # async engine, Base, NAMING_CONVENTION, get_session()
├── dependencies.py   # get_token_payload(), require_role() — JWT + gate
├── exceptions.py     # DomainError, NotFound, Conflict, StudentNotFound, StudentAlreadyExists
├── api/
│   ├── health.py     # /health, /ready, /status
│   └── authenticated/
│       └── students.py  # POST promote, GET /me
├── models/
│   ├── _mixins.py    # TimestampMixin (created_at, updated_at)
│   └── student.py    # Student + StudentStatus enum
├── schemas/
│   └── student.py    # PromoteRequest, StudentRead
└── services/
    └── student_service.py  # promote(), get_by_external_id()
```

## 5. Ambiente real

- **Milestone 1 (atual):** promoção (enrollment→student) + consulta de dados
  próprios. Status inicial: `AWAITING_DOCUMENTS`.
- **Referência opaca ao auth:** `students.external_id` é UUID puro, sem FK
  cross-schema (§4). Acoplamento é lógico, não relacional. Em delete/promote,
  consulta `auth` via HTTP se precisar validar existência.
- **Enum StudentStatus** definido completo desde já (10 status) para evitar
  migração de tipo a cada milestone. Milestone 1 só grava `AWAITING_DOCUMENTS`.
- **JWT:** RS256 validado contra JWKS do serviço `jwt`. Cache de 5 min.
- **Roles por endpoint:** `coordinator` para POST promote, `student` para GET /me.
- **study_platform:** JSONB com dados da plataforma de estudo informados pelo
  coordenador na promoção. Schema livre, validado no futuro.
- **Segredos** só no `.env`, nunca no código.

## 6. O que NÃO fazer

- ❌ Promover aluno sem verificar idempotência (external_id duplicado).
- ❌ Criar endpoint sem autenticação JWT + gate de role.
- ❌ Alterar fluxo de status sem notificação assíncrona.
- ❌ Importar modelo de outro serviço. Sem shadow table. Use `external_id` (§4).
- ❌ Adicionar status novo no enum sem considerar impacto em notificações.
- ❌ Commitar `.env` ou segredo.

---

**Antes de qualquer tarefa**, leia também `wiki/student.md` e `CONVENTION.md` (raiz).
