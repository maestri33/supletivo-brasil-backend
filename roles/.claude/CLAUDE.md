# CLAUDE.md — Memória e regras do microsserviço `roles`

> Fonte da verdade para você (Claude Code) sobre o serviço `roles`. Leia inteiro
> antes de agir. Se algo aqui conflita com o pedido atual, **pergunte** — não
> decida sozinho. A convenção geral é `CONVENTION.md` (raiz); este arquivo só
> pode ser **mais restritivo**. Doc funcional completa: `wiki/roles.md`.

---

## 1. Quem é você aqui

- Claude Code **exclusivo deste serviço**. Fala com outros serviços só por HTTP.
- Papel: **motor de regras de transição de papéis (roles)** de usuários no
  pipeline v7m. Define quais papéis um usuário pode ter, quais transições são
  permitidas, e em quais condições. É o **dono exclusivo** da tabela de roles —
  `auth` não deve manter tabela de roles própria.
- **Não é caminho de dinheiro**, mas é dependência crítica: erros de role podem
  expor endpoints indevidamente ou bloquear usuários legítimos.
- Schema `roles`. PK = UUID.

## 2. Regras de ouro (não negociáveis)

1. **Não alucine.** Sem certeza? Consulte o código ou pergunte.
2. **Faça só o que foi pedido.** Sugestões no fim da resposta, não no código.
3. **Stack fixa (§2).** FastAPI + SQLAlchemy 2.0 async + asyncpg + Alembic +
   Pydantic v2 + httpx.AsyncClient + structlog + pydantic-settings.
4. **Dono exclusivo de roles.** `auth` não deve ter tabela `user_roles` —
   deduplicar e consolidar aqui.
5. **Transições de role** devem ser atômicas e auditáveis. Sempre logue quem
   mudou, de qual role para qual, e por quê.
6. **Cada serviço, seu schema.** Schema `roles`. FK cross-schema via shadow
   table (`Table` read-only, §4).
7. **Toda mudança de modelo → migração Alembic.**

## 3. Stack

| Camada | Tecnologia |
|---|---|
| Runtime | Python 3.12 + `uv` |
| Web | FastAPI + uvicorn |
| ORM | SQLAlchemy 2.0 async (`Mapped`/`mapped_column`, `select()`) |
| Driver | asyncpg (Postgres central, schema `roles`) |
| Migrations | Alembic |
| Validação/Config | Pydantic v2 + pydantic-settings (`.env`) |
| HTTP cliente | httpx.AsyncClient |
| Logs | structlog |
| Testes | pytest + pytest-asyncio |

## 4. Estrutura

```
roles/app/
├── main.py          # FastAPI; lifespan; structlog
├── config.py        # Settings (.env) — DATABASE_URL obrigatório
├── db.py            # async engine, Base, NAMING_CONVENTION
├── exceptions.py
├── api/             # rotas (assign, revoke, list, transitions)
├── models/          # SQLAlchemy
├── schemas/         # Pydantic v2
└── services/        # lógica de transição, validação de permissões
```

## 5. Ambiente real

- **Tipos de endpoint (§5):** endpoints de gerenciamento de roles são
  **desmilitarizados** (consumidos internamente). Qualquer endpoint de consulta
  pública deve ser avaliado caso a caso.
- **Lista de papéis:** candidato, lead, promoter, student, coordinator, staff, admin.
  Regras de transição devem ser configuráveis (idealmente no DB, não hardcoded).

## 6. O que NÃO fazer

- ❌ Permitir transição de role sem validação de regra de negócio.
- ❌ Duplicar tabela de roles no `auth` — consolidar aqui.
- ❌ Importar modelo de outro serviço — usar shadow table read-only.
- ❌ Expor lista completa de roles/users em endpoint público.
- Comentário/doc em **pt-br** e verdadeiro; logs técnicos em inglês.
- Não usar `Base.metadata.create_all()` em produção.

---

**Antes de qualquer tarefa**, leia também `wiki/roles.md` e `CONVENTION.md` (raiz).
