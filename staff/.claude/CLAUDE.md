# CLAUDE.md — Memória e regras do microsserviço `staff`

> Fonte da verdade para você (Claude Code) sobre o serviço `staff`. Leia inteiro
> antes de agir. Se algo aqui conflita com o pedido atual, **pergunte** — não
> decida sozinho. A convenção geral é `CONVENTION.md` (raiz); este arquivo só
> pode ser **mais restritivo**. Doc funcional completa: `wiki/staff.md`.

---

## 1. Quem é você aqui

- Claude Code **exclusivo deste serviço**. Fala com outros serviços só por HTTP.
- Papel: **boss da operação** — cadastro de hubs, definição de coordenadores,
  health aggregation de todos os serviços. É o serviço de administração da
  plataforma. Staff é quem gerencia a estrutura (polos, coordenadores) e
  supervisiona a saúde do sistema.
- **É caminho de dinheiro?** Não diretamente. Mas gerencia entidades que
  impactam comissões (coordenadores, hubs).
- Schema `staff`. PK = UUID.
- **Milestone 1 (atual):** spine — config, db, dependencies (JWT/JWKS com gate
  admin/staff). Modelos de domínio e endpoints entram nos milestones 4/5.

## 2. Regras de ouro (não negociáveis)

1. **Não alucine.** Sem certeza? Consulte o código ou pergunte.
2. **Faça só o que foi pedido.** Sugestões no fim da resposta, não no código.
3. **Stack fixa (§2).** FastAPI + SQLAlchemy 2.0 async + asyncpg + Alembic +
   Pydantic v2 + httpx.AsyncClient + structlog + pydantic-settings.
4. **Cada serviço, seu schema.** Schema `staff`.
5. **Autenticação obrigatória.** Todo endpoint (exceto health) exige JWT válido
   com role `admin` ou `staff`. JWKS cacheado por 5 min.
6. **JWT via serviço `jwt`.** NUNCA valide token localmente sem consultar JWKS.
7. **Toda mudança de modelo → migração Alembic.**
8. **Comentário/doc em pt-br** e verdadeiro; logs técnicos em inglês.

## 3. Stack

| Camada | Tecnologia |
|---|---|
| Runtime | Python 3.12 + `uv` |
| Web | FastAPI + uvicorn |
| ORM | SQLAlchemy 2.0 async (`Mapped`/`mapped_column`, `select()`) |
| Driver | asyncpg (Postgres central, schema `staff`) |
| Migrations | Alembic |
| Validação/Config | Pydantic v2 + pydantic-settings (`.env`) |
| HTTP cliente | httpx.AsyncClient (jwt, outros serviços) |
| Auth | PyJWT + JWKS (RS256, via serviço jwt) |
| Logs | structlog + fastapi-structured-logging |
| Testes | pytest + pytest-asyncio |

## 4. Estrutura

```
staff/app/
├── config.py         # Settings (.env) — SERVICE_NAME, DATABASE_URL, JWT_BASE_URL, STAFF_ROLES
├── db.py             # async engine, Base, NAMING_CONVENTION, get_session()
├── dependencies.py   # get_jwks(), get_current_external_id() — JWT RS256 + gate admin/staff
├── exceptions.py     # DomainError, NotFound, Conflict, ValidationError
├── api/              # rotas (a implementar nos milestones 4/5)
├── models/           # SQLAlchemy (a implementar nos milestones 4/5)
├── schemas/          # Pydantic v2 (a implementar nos milestones 4/5)
└── services/         # lógica de negócio (a implementar nos milestones 4/5)
```

## 5. Ambiente real

- **Milestone 1 (atual):** spine apenas — sem endpoints de negócio, sem modelos
  de domínio. O que existe: config, db engine, validação JWT com gate por role.
- **Roles aceitas:** `admin`, `staff` (configurável via `STAFF_ROLES` no `.env`).
- **JWKS:** cache de 5 minutos (`_jwks_cache` global). Requer `JWT_BASE_URL`
  apontando para o serviço `jwt`.
- **Endpoints planejados:** cadastro de hubs (POST), definição de coordenador
  (PATCH), health aggregation de todos os serviços (GET).
- **Sem shadow tables** no milestone 1 — modelos de domínio entram nos
  milestones 4/5.
- **Segredos** só no `.env`, nunca no código.

## 6. O que NÃO fazer

- ❌ Criar endpoint sem autenticação JWT + gate de role.
- ❌ Validar JWT sem consultar JWKS do serviço `jwt`.
- ❌ Importar modelo de outro serviço.
- ❌ Dar role de staff para usuário externo sem aprovação.
- ❌ Commitar `.env` ou segredo.

---

**Antes de qualquer tarefa**, leia também `wiki/staff.md` e `CONVENTION.md` (raiz).
