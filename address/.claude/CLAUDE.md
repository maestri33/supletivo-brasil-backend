# CLAUDE.md — Memória e regras do microsserviço `address`

> Fonte da verdade para você (Claude Code) sobre o serviço `address`. Leia inteiro
> antes de agir. Se algo aqui conflita com o pedido atual, **pergunte** — não
> decida sozinho. A convenção geral é `CONVENTION.md` (raiz); este arquivo só
> pode ser **mais restritivo**. Doc funcional completa: `wiki/address.md`.

---

## 1. Quem é você aqui

- Claude Code **exclusivo deste serviço**. Fala com outros serviços só por HTTP.
- Papel: manter o address **pequeno, claro e funcional** — gerencia endereços
  vinculados a `auth.users` (tabela `addresses`) e vínculo polimórfico genérico
  (tabela `entity_addresses`).
- Não é **caminho de dinheiro** (diferente do asaas/infinitepay), mas é
  dependência de `auth` e `candidate`.
- A PK de todas as tabelas é **UUID** (CONVENTION §4), gerada na aplicação via
  `uuid4`.

## 2. Regras de ouro (não negociáveis)

1. **Não alucine.** Sem certeza? Consulte o código ou pergunte.
2. **Faça só o que foi pedido.** Sugestões no fim da resposta, não no código.
3. **Stack fixa (§2).** FastAPI + SQLAlchemy 2.0 async + asyncpg + Alembic +
   Pydantic v2 + httpx.AsyncClient + structlog + pydantic-settings.
4. **Porta 8000** (ver `Makefile`). Não mude sem confirmar.
5. **Cada serviço, seu schema.** Schema `addresses`. FK cross-schema para
   `auth.users` é declarada no model e resolvida via shadow table `auth_users`
   em `db.py` (§4 — `Table` read-only, nunca import de model alheio).
6. **Testes ausentes.** Este serviço ainda não tem suíte de testes. Toda
   alteração de modelo ou serviço deve incluir testes. Ver `pyproject.toml`
   (pytest-asyncio, asyncio_mode=auto).
7. **Config é `.env` puro** (pydantic-settings). Sem config_store como o asaas.

## 3. Stack

| Camada | Tecnologia |
|---|---|
| Runtime | Python 3.12 + `uv` |
| Web | FastAPI + uvicorn (porta 8000) |
| ORM | SQLAlchemy 2.0 async (`Mapped`/`mapped_column`, `select()`) |
| Driver | asyncpg (Postgres central, schema `addresses`) |
| Migrations | Alembic (`uv run alembic upgrade head`) |
| Validação/Config | Pydantic v2 + pydantic-settings (`.env`) |
| HTTP cliente | httpx.AsyncClient (ViaCEP + webhook) |
| Logs | structlog |
| Testes | pytest + pytest-asyncio (`asyncio_mode="auto"`) |

## 4. Estrutura — onde cada coisa mora

```
address/
├── app/
│   ├── main.py              # FastAPI; lifespan; structlog
│   ├── config.py            # Settings (.env)
│   ├── db.py                # async engine, Base, NAMING_CONVENTION, shadow auth_users
│   ├── api/                 # addresses.py, entity_addresses.py, health.py + router.py
│   ├── models/              # address.py, entity_address.py
│   ├── schemas/             # address.py, entity_address.py (Pydantic v2)
│   ├── services/            # address_service.py, entity_address_service.py
│   ├── integrations/        # viacep.py, webhook.py (httpx.AsyncClient)
│   ├── validators/          # address_fields.py, zipcode.py
│   └── utils/               # logging.py (structlog)
├── alembic/                 # env.py async + versions/ (0001 + 0002 UUID)
├── Dockerfile · Makefile · pyproject.toml · .env.example
└── TODO                     # removido na Fase 4 — itens implementados
```

**Regra das pastas** (§3): rota → `api/<recurso>.py` (+ `router.py`); model →
`models/<entidade>.py`; schema → `schemas/`; negócio → `services/<recurso>.py`;
cliente externo → `integrations/`. Não cabe? Pergunte.

## 5. Ambiente real

- **Hospedagem:** Proxmox + Docker, produção.
- **Tipos de endpoint (§5):** todos os endpoints de `addresses`/`entities` são
  **desmilitarizados** (consumidos por outros apps). `health`/`ready`/`status`
  são de infraestrutura.
- **Segredos** só no `.env`, nunca no código nem no `.env.example`.
- **uploads/** é `.gitignore`'d — não versiona PDFs de comprovante.

## 6. Comandos

```bash
make install                                   # uv sync
make dev / make run                            # uvicorn :8000 (--reload / prod)
make test                                      # uv run pytest -q
make lint / make fmt                           # ruff check / format
uv run alembic revision --autogenerate -m "…"  # gera migração
uv run alembic upgrade head                    # aplica (cria o schema addresses)
```

## 7. Migrações

- **0001**: Schema inicial (PK integer, 3 tabelas).
- **0002**: Transição PK int→UUID (drop + recreate greenfield — sem dados de
  produção a preservar). Estratégia: `_drop_all()` → `_create_all(as_uuid=True)`.
- PK UUID é gerada na aplicação (`default=uuid4` nos models), sem
  `server_default` na coluna.
- O `env.py` cria o schema `addresses` automaticamente no `run_migrations_online`
  (`CREATE SCHEMA IF NOT EXISTS`), então o `upgrade` funciona em DB novo.

## 8. Como pedir ajuda

Pare e **pergunte** quando a spec é ambígua, falta info de conexão, ou há 2+
caminhos com trade-off real. Perguntas curtas, sem "menu" desnecessário.

## 9. O que NÃO fazer

- Não usar `Base.metadata.create_all()` em produção — mudança de modelo = migração.
- Não importar modelo de outro serviço — usar shadow table `Table` read-only.
- Não logar PII (CEP completo, endereço com número, comprovante).
- Não conectar no banco de outro serviço.
- Não versionar arquivos em `uploads/`.
- Comentário/doc em **pt-br** e verdadeiro; logs técnicos em inglês. Sem segredo
  em log.
- Não criar FK cross-schema sem shadow table declarada em `db.py`.

---

**Antes de qualquer tarefa**, leia também `wiki/address.md` e `CONVENTION.md` (raiz).
