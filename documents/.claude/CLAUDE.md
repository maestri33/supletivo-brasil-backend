# CLAUDE.md — Memória e regras do microsserviço `documents`

> Fonte da verdade para você (Claude Code) sobre o serviço `documents`. Leia inteiro
> antes de agir. Se algo aqui conflita com o pedido atual, **pergunte** — não
> decida sozinho. A convenção geral é `CONVENTION.md` (raiz); este arquivo só
> pode ser **mais restritivo**. Doc funcional completa: `wiki/documents.md`.

---

## 1. Quem é você aqui

- Claude Code **exclusivo deste serviço**. Fala com outros serviços só por HTTP.
- Papel: armazenar e gerenciar **documentos de identificação** dos usuários da
  plataforma (RG, CNH, Carteira de Trabalho, Passaporte, Certidão, Reservista,
  Comprovante de Residência), vinculados a `auth.users`.
- **Não emite nem valida** documentos — só armazena metadados e arquivos.
- Schema `documents`. PK = UUID.

## 2. Regras de ouro (não negociáveis)

1. **Não alucine.** Sem certeza? Consulte o código ou pergunte.
2. **Faça só o que foi pedido.** Sugestões no fim da resposta, não no código.
3. **Stack fixa (§2).** FastAPI + SQLAlchemy 2.0 async + asyncpg + Alembic +
   Pydantic v2 + httpx.AsyncClient + structlog + pydantic-settings.
4. **Cada serviço, seu schema.** Schema `documents`. FK cross-schema para
   `auth.users` via shadow table (`Table` read-only, §4).
5. **Toda mudança de modelo → migração Alembic.**
6. **Dados PII** (RG, CPF, etc.) — logs devem omitir ou mascarar. NUNCA logar
   número de documento completo.

## 3. Stack

| Camada | Tecnologia |
|---|---|
| Runtime | Python 3.12 + `uv` |
| Web | FastAPI + uvicorn |
| ORM | SQLAlchemy 2.0 async (`Mapped`/`mapped_column`, `select()`) |
| Driver | asyncpg (Postgres central, schema `documents`) |
| Migrations | Alembic |
| Validação/Config | Pydantic v2 + pydantic-settings (`.env`) |
| HTTP cliente | httpx.AsyncClient |
| Logs | structlog |
| Testes | pytest + pytest-asyncio |

## 4. Estrutura

```
documents/app/
├── main.py          # FastAPI; lifespan; structlog
├── config.py        # Settings (.env) — DATABASE_URL obrigatório
├── db.py            # async engine, Base, NAMING_CONVENTION, shadow auth_users
├── exceptions.py    # exceções de domínio
├── api/             # rotas (1 arquivo por recurso + router.py)
├── models/          # SQLAlchemy
├── schemas/         # Pydantic v2
├── services/        # lógica de negócio
└── utils/           # helpers (logging, etc.)
```

## 5. O que NÃO fazer

- Não logar PII (número de RG/CNH/CPF completo, endereço).
- Não importar modelo de outro serviço — usar shadow table read-only.
- Não conectar no banco de outro serviço.
- Não versionar uploads (`.gitignore`'d).
- Comentário/doc em **pt-br** e verdadeiro; logs técnicos em inglês.
- Não usar `Base.metadata.create_all()` em produção.

---

**Antes de qualquer tarefa**, leia também `wiki/documents.md` e `CONVENTION.md` (raiz).
