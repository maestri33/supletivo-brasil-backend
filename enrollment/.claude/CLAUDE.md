# CLAUDE.md — Memória e regras do microsserviço `enrollment`

> Fonte da verdade para você (Claude Code) sobre o serviço `enrollment`. Leia inteiro
> antes de agir. Se algo aqui conflita com o pedido atual, **pergunte** — não
> decida sozinho. A convenção geral é `CONVENTION.md` (raiz); este arquivo só
> pode ser **mais restritivo**. Doc funcional completa: `wiki/enrollment.md`.

---

## 1. Quem é você aqui

- Claude Code **exclusivo deste serviço**. Fala com outros serviços só por HTTP.
- Papel: **receptor de webhook** do serviço `lead`. Quando um Lead atinge o status
  `COMPLETED`, o `lead` envia um POST para este serviço, que persiste o evento de
  forma **auditável e idempotente**. É a porta de entrada do candidato no pipeline
  de matrícula.
- **Modelo de referência** de estrutura (junto com `lead`) — serve como exemplo
  para novos serviços (§3 da convenção).
- Schema `enrollment`. PK = UUID.

## 2. Regras de ouro (não negociáveis)

1. **Não alucine.** Sem certeza? Consulte o código ou pergunte.
2. **Faça só o que foi pedido.** Sugestões no fim da resposta, não no código.
3. **Stack fixa (§2).** FastAPI + SQLAlchemy 2.0 async + asyncpg + Alembic +
   Pydantic v2 + httpx.AsyncClient + structlog + pydantic-settings.
4. **Idempotência obrigatória** no recebimento de webhook — `lead_id` + `status`
   devem ser únicos; reenvio não pode criar duplicata.
5. **Cada serviço, seu schema.** Schema `enrollment`. FK cross-schema via shadow
   table (`Table` read-only, §4).
6. **Toda mudança de modelo → migração Alembic.**

## 3. Stack

| Camada | Tecnologia |
|---|---|
| Runtime | Python 3.12 + `uv` |
| Web | FastAPI + uvicorn |
| ORM | SQLAlchemy 2.0 async (`Mapped`/`mapped_column`, `select()`) |
| Driver | asyncpg (Postgres central, schema `enrollment`) |
| Migrations | Alembic |
| Validação/Config | Pydantic v2 + pydantic-settings (`.env`) |
| HTTP cliente | httpx.AsyncClient |
| Logs | structlog |
| Testes | pytest + pytest-asyncio |

## 4. Estrutura

```
enrollment/app/
├── main.py          # FastAPI; lifespan; structlog
├── config.py        # Settings (.env)
├── db.py            # async engine, Base, NAMING_CONVENTION
├── exceptions.py
├── api/             # rotas (webhook receptor + router.py)
├── models/          # SQLAlchemy
├── schemas/         # Pydantic v2
└── services/        # lógica de negócio
```

## 5. Ambiente real

- **Tipos de endpoint (§5):** o webhook receptor do `lead` é **desmilitarizado**
  (comunicação interna entre apps). Qualquer endpoint público futuro deve ser
  tratado com cuidado redobrado.
- **Segredos** só no `.env`, nunca no código.

## 6. O que NÃO fazer

- Não duplicar lead sem verificação de idempotência.
- Não importar modelo de outro serviço — usar shadow table read-only.
- Não logar PII.
- Comentário/doc em **pt-br** e verdadeiro; logs técnicos em inglês.
- Não usar `Base.metadata.create_all()` em produção.

---

**Antes de qualquer tarefa**, leia também `wiki/enrollment.md` e `CONVENTION.md` (raiz).
