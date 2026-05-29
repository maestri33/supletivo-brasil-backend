# CLAUDE.md — Memória e regras do microsserviço `hub`

> Fonte da verdade para você (Claude Code) sobre o serviço `hub`. Leia inteiro
> antes de agir. Se algo aqui conflita com o pedido atual, **pergunte** — não
> decida sozinho. A convenção geral é `CONVENTION.md` (raiz); este arquivo só
> pode ser **mais restritivo**. Doc funcional completa: `wiki/hub.md`.

---

## 1. Quem é você aqui

- Claude Code **exclusivo deste serviço**. Fala com outros serviços só por HTTP.
- Papel: gerenciar **polos (hubs)** — unidades físicas da operação educacional.
  Cada polo tem nome, marca (estacio, wyden), endereço e coordenador. É a
  entidade raiz que conecta promotores, alunos e coordenadores a uma localidade.
- **É caminho de dinheiro?** Não. Hub é registro administrativo, sem transações
  financeiras.
- Schema `hub`. PK = UUID.

## 2. Regras de ouro (não negociáveis)

1. **Não alucine.** Sem certeza? Consulte o código ou pergunte.
2. **Faça só o que foi pedido.** Sugestões no fim da resposta, não no código.
3. **Stack fixa (§2).** FastAPI + SQLAlchemy 2.0 async + asyncpg + Alembic +
   Pydantic v2 + httpx.AsyncClient + structlog + pydantic-settings.
4. **Cada serviço, seu schema.** Schema `hub`. FK cross-schema são UUID puro,
   nullable, sem shadow table — hub é registro fino (§4).
5. **Marcas válidas:** `estacio`, `wyden` — enum fixo, validar no schema Pydantic
   (próximo milestone).
6. **Toda mudança de modelo → migração Alembic.**
7. **Comentário/doc em pt-br** e verdadeiro; logs técnicos em inglês.

## 3. Stack

| Camada | Tecnologia |
|---|---|
| Runtime | Python 3.12 + `uv` |
| Web | FastAPI + uvicorn |
| ORM | SQLAlchemy 2.0 async (`Mapped`/`mapped_column`, `select()`) |
| Driver | asyncpg (Postgres central, schema `hub`) |
| Migrations | Alembic |
| Validação/Config | Pydantic v2 + pydantic-settings (`.env`) |
| HTTP cliente | httpx.AsyncClient |
| Logs | structlog + fastapi-structured-logging |
| Testes | pytest + pytest-asyncio |

## 4. Estrutura

```
hub/app/
├── main.py           # FastAPI; lifespan; /health, /ready, /status
├── config.py         # Settings (.env) com lru_cache
├── db.py             # async engine, Base, NAMING_CONVENTION, get_session()
├── exceptions.py     # DomainError, NotFound
├── seed.py           # seed de dados iniciais de polos
├── api/
│   ├── health.py     # /health, /ready, /status
│   └── hubs.py       # GET /api/v1/hubs/{external_id} (desmilitarizado)
├── models/
│   └── hub.py        # model Hub
└── schemas/
    └── hub.py        # HubRead
```

## 5. Ambiente real

- **Milestone 1 (atual):** spine funcional — health/ready/status + leitura de polo
  por external_id. CRUD completo (POST/PATCH/DELETE) entra nos próximos milestones.
- **Endpoints desmilitarizados (§5):** leitura de hubs é uso interno entre
  serviços — sem autenticação. Escrita futura será autenticada (staff).
- **FK cross-schema:** `address_external_id` e `coordinator_external_id` são
  UUID puro, nullable, **sem shadow table**. Hub não precisa de FK real — é
  referência lógica.
- **Access logging:** healthcheck (`/health`, `/ready`, `/status`) não gera log
  de acesso — configurado via `fastapi-structured-logging`.
- **Segredos** só no `.env`, nunca no código.

## 6. O que NÃO fazer

- ❌ Criar FK real cross-schema para address ou coordinator — manter UUID puro.
- ❌ Adicionar marca nova sem validar no schema Pydantic.
- ❌ Importar modelo de outro serviço.
- ❌ Criar endpoint público (externo) — hub é interno à plataforma.
- ❌ Commitar `.env` ou segredo.

---

**Antes de qualquer tarefa**, leia também `wiki/hub.md` e `CONVENTION.md` (raiz).
