# CLAUDE.md — Memória e regras deste microserviço

> Este arquivo é a **fonte da verdade** para você (Claude Code) sobre o serviço
> `infinitepay`. Leia ele inteiro antes de fazer qualquer coisa. Se algo aqui
> conflita com o que o usuário pediu agora, **pergunte** — não decida sozinho.
> A convenção geral está em `CONVENTION.md` (raiz). Este arquivo só pode ser
> **mais restritivo** que ela, nunca afrouxar. A doc funcional completa (fonte
> de verdade do comportamento) é `wiki/infinitepay.md`.

---

## 1. Quem é você aqui

- Você é o Claude Code **exclusivo deste serviço**. Não conhece o código dos
  outros serviços; quando precisa de outro serviço, fala por HTTP (ver
  `app/integrations/`).
- Papel: manter o infinitepay **pequeno, claro e funcional** — é caminho de
  dinheiro, então correção e atomicidade vêm antes de esperteza.
- O serviço é um **middleware de checkout da InfinitePay**: cria links de
  pagamento, recebe o webhook de confirmação e reenvia eventos internos via
  fila de saída com retry. É o **único** app autorizado a integrar com a
  InfinitePay (§12).

## 2. Regras de ouro (não negociáveis)

1. **Não alucine.** Sem certeza de assinatura, versão de pacote ou nome de env
   var? Consulte o código (`app/config.py` é a fonte das envs) ou pergunte.
   Nunca invente import path nem método de biblioteca.
2. **Faça só o que foi pedido.** Sugestões extras vão no fim da resposta, não
   no código.
3. **Antes de codar, leia.** `.claude/memory/*.md` + os arquivos de `app/`
   relevantes. Atualize a memória quando aprender algo novo (seção 7).
4. **Stack fixa (§2 da CONVENTION).** FastAPI + SQLAlchemy 2.0 async + asyncpg +
   Alembic + Pydantic v2 + httpx.AsyncClient + structlog + pydantic-settings.
   Nada de `requests`, `print`/`logging` cru, engine síncrono, Pydantic v1.
5. **Porta 80.** O serviço expõe a porta **80** (ver `Makefile`). Não mude sem
   confirmar.
6. **Cada serviço, seu banco.** Schema `infinitepay`. Não conecte em banco de
   outro serviço; referência a outros serviços via `external_id` UUID opaco
   (§4 da CONVENTION).
7. **Config no `.env`.** Não existe tabela `config` nem rotas `/config` (foram
   removidas na Fase 3). Toda config vem de `app/config.py::get_settings()`.
8. **Caminho do dinheiro é atômico.** Nunca quebre as invariantes da seção
   "Atomicidade" em `.claude/memory/architecture.md`.

## 3. Stack

| Camada | Tecnologia |
|---|---|
| Runtime | Python 3.12 + `uv` |
| Web | FastAPI + uvicorn (porta 80) |
| ORM | SQLAlchemy 2.0 async (`Mapped`/`mapped_column`, `select()`) |
| Driver | asyncpg (Postgres central, schema `infinitepay`) |
| Migrations | Alembic (`uv run alembic upgrade head`) |
| Validação | Pydantic v2 |
| Config | pydantic-settings + `.env` |
| HTTP cliente | httpx.AsyncClient |
| Cripto | cryptography (Fernet) — cifra `external_id` no webhook |
| Logs | structlog (logger `"infinitepay"`) |
| Testes | pytest + pytest-asyncio (`asyncio_mode="auto"`), sqlite+aiosqlite |

## 4. Estrutura — onde cada coisa mora

```
infinitepay/
├── .claude/                 # você (Claude Code) e sua memória
│   ├── CLAUDE.md            # este arquivo — leia primeiro
│   └── memory/              # contexto persistente do serviço
│       ├── architecture.md  # decisões arquiteturais (com data)
│       ├── conventions.md   # como escrevemos código aqui
│       └── integrations.md  # como falamos com outros serviços
├── app/
│   ├── main.py              # FastAPI; lifespan (worker async + close_db); structlog
│   ├── config.py            # Settings (pydantic-settings); get_settings() cacheado
│   ├── db.py                # async engine, Base, NAMING_CONVENTION, get_session,
│   │                        #   close_db, utcnow
│   ├── exceptions.py        # DomainError + subclasses
│   ├── api/                 # checkout.py, webhooks.py, health.py + router.py
│   ├── models/              # 1 arquivo por entidade: checkout, webhook_log, outbound_job
│   ├── schemas/             # Pydantic v2 (checkout, webhook, health, error)
│   ├── services/            # checkout_service + receipt + monitor (estes usam app `ai`)
│   ├── integrations/        # infinitepay_client.py + ai.py (httpx.AsyncClient)
│   ├── workers/             # outbound_queue.py (fila com retry + claim atômico)
│   └── utils/               # validators.py, crypto.py (Fernet), logging.py, net.py
├── alembic/                 # env.py async + versions/ (revision 0001)
├── tests/                   # async (pytest-asyncio, httpx ASGITransport)
├── Dockerfile · Makefile · pyproject.toml · .env.example
└── README.md                # como rodar + env vars (enxuto; wiki é a fonte)
```

**Regra das pastas** (§3 CONVENTION):
- Rota nova → `app/api/<recurso>.py`, registrar em `app/api/router.py`.
- Model novo → `app/models/<entidade>.py`, importar em `app/models/__init__.py`
  (Alembic enxerga via `Base.metadata`); depois `alembic revision --autogenerate`.
- Schema Pydantic → `app/schemas/<recurso>.py`.
- Regra de negócio → `app/services/<recurso>_service.py`.
- Chamada a outro serviço → `app/integrations/<servico>.py`.
- Não cabe em nenhuma? **Pergunte** antes de criar pasta nova.

## 5. Ambiente real

- **Hospedagem:** VM/LXC no Proxmox + Docker. Não é localhost de brincadeira —
  vai pra produção online.
- **Tipos de endpoint (§5):** `checkout` e `health` são **desmilitarizados**
  (consumidos por outros apps da plataforma). `webhooks.py` é **público
  externo** (server-to-server da InfinitePay). Em rota pública: logue origem
  (`source_ip`/`user_agent` via `app/utils/net.py`) e nunca confie só no
  payload — a confirmação é **out-of-band** via `payment_check`.
- **Segredos** (Fernet key, credenciais) só no `.env`, nunca no código nem no
  `.env.example`. Nunca logue payload sensível.

## 6. Comandos

```bash
make install                                  # uv sync
make dev                                       # uvicorn :80 --reload
make run                                        # uvicorn :80 (sem reload)
make test                                       # uv run pytest -q
make lint / make fmt                            # ruff check / format app/
uv run alembic revision --autogenerate -m "…"  # gera migração
uv run alembic upgrade head                     # aplica (cria o schema infinitepay)
```

## 7. Gerenciamento de memória

- **`.claude/memory/architecture.md`** — decisões arquiteturais com data e
  contexto (Fases 3/4, atomicidade, worker).
- **`.claude/memory/conventions.md`** — convenções específicas (UUID, ordenação,
  timestamptz, erros, logs).
- **`.claude/memory/integrations.md`** — cada serviço externo: URL base,
  endpoints, formato, fallback.
- Leia os 3 antes de implementar. Ao terminar, pergunte-se: "preciso registrar
  algo aqui?".

## 8. Como pedir ajuda

Pare e **pergunte** quando: a spec está ambígua, falta info de conexão
(URL/credencial/formato de evento), ou há 2+ caminhos com trade-off real.
Perguntas curtas e objetivas — sem "menu" quando uma pergunta direta resolve.

## 9. O que NÃO fazer

- Não recriar a tabela `config` nem rotas `/config` (config é `.env`).
- Não integrar a IA direto (DeepSeek/SDK `openai`): recibo e triagem de fraude
  passam **sempre** pelo app `ai` via `app/integrations/ai.py` (§12).
- Não conectar no banco de outro serviço.
- Não usar `Base.metadata.create_all()` em produção — toda mudança de modelo é
  migração Alembic.
- Não ordenar query paginada só por `created_at` (não é único) — use desempate
  por `id` (ver `conventions.md`).
- Não escrever README/comentário em inglês — docstrings/comentários em **pt-br**
  e verdadeiros. Logs técnicos (structlog) em inglês.
- Não logar segredo nem payload sensível.

---

**Antes de qualquer tarefa**, leia também:
- `.claude/memory/architecture.md`
- `.claude/memory/conventions.md`
- `.claude/memory/integrations.md`
- `wiki/infinitepay.md` (comportamento — fonte de verdade)
