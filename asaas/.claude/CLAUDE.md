# CLAUDE.md — Memória e regras deste microserviço

> Fonte da verdade para você (Claude Code) sobre o serviço `asaas`. Leia inteiro
> antes de agir. Se algo aqui conflita com o pedido atual, **pergunte** — não
> decida sozinho. A convenção geral é `CONVENTION.md` (raiz); este arquivo só
> pode ser **mais restritivo**. Doc funcional completa: `wiki/asaas.md`.
> Catálogo de uso (onboarding, endpoints, curl): `asaas/README.md`.

---

## 1. Quem é você aqui

- Claude Code **exclusivo deste serviço**. Fala com outros serviços só por HTTP.
- Papel: manter o asaas **pequeno, claro e funcional** — é **caminho de
  dinheiro** (payouts PIX), então correção, **idempotência** e atomicidade vêm
  antes de esperteza.
- O serviço é um **middleware PIX sobre a API Asaas v3**, com dois fluxos:
  - **Payouts (saída)** — `kind=pixkey | qrcode` — transferência por chave PIX
    ou pagamento de BR Code.
  - **Charges (entrada)** — `kind=charge` — cobranças PIX via Asaas `/payments`.
- É o **único** app autorizado a integrar com o Asaas (§12).

## 2. Regras de ouro (não negociáveis)

1. **Não alucine.** Sem certeza? Consulte o código (`app/config.py` p/ envs;
   `app/config_store.py` p/ config operacional) ou pergunte.
2. **Faça só o que foi pedido.** Sugestões no fim da resposta, não no código.
3. **Antes de codar, leia.** `.claude/memory/*.md` + os arquivos de `app/`.
4. **Stack fixa (§2).** FastAPI + SQLAlchemy 2.0 async + asyncpg + Alembic +
   Pydantic v2 + httpx.AsyncClient + structlog + pydantic-settings.
5. **Porta 80** (ver `Makefile`). Não mude sem confirmar.
6. **Cada serviço, seu banco.** Schema `asaas`. Sem FK cross-schema aqui:
   `external_id` é **fornecido pelo cliente** (string), não é FK do `auth`.
7. **Config é híbrida.** Config operacional (API key Asaas, URLs internas,
   wallet, token de segurança) vive na tabela `asaas.config` via
   `config_store`; o `.env` só faz **bootstrap** (`_seed_from_env` popula
   quando a tabela está vazia; depois o **DB vence**, operador faz override via
   `POST /api/v1/config/*`). Não é `.env` puro como o infinitepay.
8. **Money path é idempotente.** Nunca quebre as invariantes de payout em
   `.claude/memory/architecture.md` (commit do `asaas_id` antes do efeito
   externo → não duplica após timeout, BLOQUEIO §15).

## 3. Stack

| Camada | Tecnologia |
|---|---|
| Runtime | Python 3.12 + `uv` |
| Web | FastAPI + uvicorn (porta 80) |
| ORM | SQLAlchemy 2.0 async (`Mapped`/`mapped_column`, `select()`) |
| Driver | asyncpg (Postgres central, schema `asaas`) |
| Migrations | Alembic (`uv run alembic upgrade head`) |
| Validação/Config | Pydantic v2 + pydantic-settings (`.env` p/ bootstrap) |
| HTTP cliente | httpx.AsyncClient (`AsaasClient`) |
| Logs | structlog |
| Testes | pytest + pytest-asyncio (`asyncio_mode="auto"`), sqlite+aiosqlite |

## 4. Estrutura — onde cada coisa mora

```
asaas/
├── .claude/                 # você e sua memória (CLAUDE.md + memory/)
├── app/
│   ├── main.py              # FastAPI; lifespan (worker payment + seed_from_env)
│   ├── config.py            # Settings (.env) — bootstrap
│   ├── config_store.py      # config operacional na tabela asaas.config
│   ├── db.py                # async engine, Base, NAMING_CONVENTION, utcnow
│   ├── api/                 # charge, payment, pixkey, config, webhook + router
│   ├── models/              # 1 arquivo/entidade: config_kv, customer, payment,
│   │                        #   pix_key, url_verify_nonce, webhook_event
│   ├── schemas/             # Pydantic v2
│   ├── services/            # charge, payment, pixkey, customer, notifications,
│   │                        #   security_validator, config_* (url/key/internal/status)
│   ├── integrations/        # asaas_client.py (httpx.AsyncClient)
│   └── utils/               # brcode.py (BR Code), net.py (origem), logging.py
├── alembic/                 # env.py async + versions/ (revision 0001)
├── tests/
├── Dockerfile · Makefile · pyproject.toml · .env.example
└── README.md                # onboarding + endpoints (catálogo de uso)
```

**Regra das pastas** (§3): rota → `api/<recurso>.py` (+ `router.py`); model →
`models/<entidade>.py` (+ `__init__.py`); schema → `schemas/`; negócio →
`services/<recurso>.py`; cliente externo → `integrations/`. Não cabe? Pergunte.

## 5. Ambiente real

- **Hospedagem:** Proxmox + Docker, produção online.
- **Tipos de endpoint (§5):** `charge`/`payment`/`pixkey`/`config` são
  **desmilitarizados** (consumidos por outros apps). `webhook.py` é **público
  externo** (server-to-server do Asaas) — validado pelo header
  `asaas-access-token` (`services/security_validator.py`, o "Mecanismo de
  Segurança" do Asaas) e grava origem (`source_ip`/`user_agent` via
  `utils/net.py`).
- **Segredos** só no `.env`/DB de config, nunca no código nem no `.env.example`.

## 6. Comandos

```bash
make install                                   # uv sync
make dev / make run                             # uvicorn :80 (--reload / prod)
make test                                       # uv run pytest -q  (190 testes)
make lint / make fmt                            # ruff check / format
uv run alembic revision --autogenerate -m "…"  # gera migração
uv run alembic upgrade head                     # aplica (cria o schema asaas)
```

## 7. Gerenciamento de memória

Leia antes de implementar; atualize ao terminar:
- `.claude/memory/architecture.md` — decisões com data (F3/F4, idempotência, worker).
- `.claude/memory/conventions.md` — UUID, ordenação, timestamptz, config, erros.
- `.claude/memory/integrations.md` — Asaas, webhook, notificações internas.

## 8. Como pedir ajuda

Pare e **pergunte** quando a spec é ambígua, falta info de conexão, ou há 2+
caminhos com trade-off real. Perguntas curtas, sem "menu" desnecessário.

## 9. O que NÃO fazer

- Não duplicar payout: o `asaas_id` é commitado **antes** de confirmar o efeito
  externo; respeite a idempotência (BLOQUEIO §15).
- Não tratar config como `.env` puro — config operacional é DB (`config_store`).
- Não integrar com Asaas fora de `integrations/asaas_client.py` (§12).
- Não conectar no banco de outro serviço.
- Não usar `Base.metadata.create_all()` em produção — mudança de modelo = migração.
- Não ordenar query paginada/FIFO só por `created_at` — desempate por `id`
  (ver `conventions.md`).
- Comentário/doc em **pt-br** e verdadeiro; logs técnicos em inglês. Sem segredo
  em log.

---

**Antes de qualquer tarefa**, leia também `.claude/memory/*.md` e `wiki/asaas.md`.
