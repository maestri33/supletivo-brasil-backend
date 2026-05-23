# CLAUDE.md — Memória e regras deste microserviço

> Este arquivo é a **fonte da verdade** para você (Claude Code) sobre este
> microserviço. Leia ele inteiro antes de fazer qualquer coisa. Se algo aqui
> conflita com o que o usuário pediu agora, **pergunte** — não decida sozinho.

---

## 1. Quem é você aqui

- Você é o Claude Code **exclusivo deste serviço**. Você não conhece outros
  serviços do ecossistema; quando precisar falar com outro serviço, faz isso
  via HTTP (ver `app/integrations/`).
- Seu papel: **manter este serviço pequeno, claro e funcional.** Nada de
  abstração prematura, nada de framework dentro de framework.
- Sua missão recorrente: implementar features, corrigir bugs, escrever testes
  e documentar — sempre dentro da estrutura definida abaixo.

## 2. Regras de ouro (não negociáveis)

1. **Não alucine.** Se você não tem certeza de uma assinatura de função, de
   uma versão de pacote ou do nome de uma env var, **consulte o Context7
   MCP** ou pergunte ao usuário. Nunca invente import path, nunca invente
   método de biblioteca.
2. **Faça apenas o que foi pedido.** Não acrescente features "que ficariam
   legais". Se achar que falta algo, comente no fim da resposta com a
   sugestão — não implemente.
3. **Antes de codar, leia.** Sempre leia os arquivos relevantes desta pasta
   (`.claude/memory/*.md`, `app/`) antes de propor mudança. Atualize a
   memória quando aprender algo novo (seção 7).
4. **Stack fixa.** Não troque FastAPI por Flask, SQLAlchemy por Tortoise,
   Postgres por SQLite, uv por poetry. Se o usuário pedir, confirme antes.
   (A stack migrou de Tortoise/SQLite/Aerich → SQLAlchemy 2/Postgres/Alembic
   em 2026-05-15; ver `MIGRACAO.md`.)
5. **Porta 8000.** Esse serviço expõe **somente** a porta 8000 (HTTP). Não mude.
6. **Cada serviço, seu banco.** Não conecte este serviço no banco de outro
   serviço. Se precisa de dado de outro serviço, chama a API dele.
7. **Configuração no .env.** Toda config do OTP vai no `.env`, não no banco.
   Pra alterar, edita `.env` e restart o serviço.

## 3. Stack

| Camada            | Tecnologia                              |
| ----------------- | --------------------------------------- |
| Runtime           | Python 3.12 + `uv`                      |
| Web framework     | FastAPI                                 |
| Servidor ASGI     | Uvicorn (porta 8000)                    |
| ORM               | SQLAlchemy 2 (async, `Mapped`/`mapped_column`) |
| Migrations        | Alembic (`alembic upgrade head`)        |
| Banco             | PostgreSQL central (asyncpg), schema `otp`; FK p/ `auth.users` |
| Validação         | Pydantic v2                             |
| Config            | pydantic-settings + `.env`              |
| HTTP cliente      | httpx (async)                           |
| Testes            | pytest + pytest-asyncio (suíte legada em skip — ver `MIGRACAO.md`) |
| Logs              | structlog (JSON em prod)                |

## 4. Estrutura do projeto — onde cada coisa mora

```
.
├── .claude/                  # você (Claude Code) e sua memória
│   ├── CLAUDE.md             # este arquivo — sempre leia primeiro
│   ├── settings.json         # modelo + permissões
│   └── memory/               # contexto persistente do serviço
│       ├── architecture.md   # decisões arquiteturais
│       ├── conventions.md    # como escrevemos código aqui
│       └── integrations.md   # como falamos com outros serviços
├── .mcp.json                 # MCPs habilitados (Context7)
├── app/
│   ├── main.py               # entrypoint FastAPI, lifespan, porta 8000
│   ├── config.py             # Settings (lê .env)
│   ├── db.py                 # Base/engine/async_session_maker (SQLAlchemy)
│   ├── api/                  # routers HTTP — UM arquivo por feature
│   │   ├── deps.py           # Depends() reutilizáveis (http_client)
│   │   ├── router.py         # agrega todos os routers
│   │   ├── health.py         # /health, /ready
│   │   ├── otp.py            # /api/v1/otp, /check, /logs
│   │   ├── webhook.py        # /webhook/notify/{message_id}
│   │   └── status.py         # /status (JSON com dados reais + métricas)
│   ├── models/               # modelos SQLAlchemy (1 arquivo por entidade)
│   ├── schemas/              # Pydantic schemas (request/response)
│   ├── services/             # regras de negócio (chamadas pelo router)
│   │   ├── otp.py            # geração, validação, listagem
│   │   ├── otp.md            # template da mensagem
│   │   ├── rate_limit.py     # rate limit por external_id
│   │   ├── cleanup.py        # purga de logs antigos (task de fundo)
│   │   ├── queue.py          # fila de retry do notify (task de fundo)
│   │   └── notify.py         # envio de mensagens via notify
│   ├── integrations/         # chamadas HTTP pra outros serviços
│   │   ├── http_client.py    # httpx client + retry
│   │   └── notify_client.py  # wrapper HTTP do notify
│   └── utils/                # logging, helpers genéricos
├── alembic/                  # migrations (env.py + versions/)
├── alembic.ini
├── tests/                    # pytest (suíte legada em skip)
├── scripts/
│   ├── dev.sh                # roda uvicorn em dev
│   └── otp.service           # systemd unit file
├── Dockerfile
├── pyproject.toml
├── .env.example
├── Makefile
└── README.md
```

**Regra das pastas:**
- Endpoint HTTP novo → `app/api/<feature>.py`, registrar em `app/api/router.py`
- Modelo de banco novo → `app/models/<entidade>.py`, importar em
  `app/models/__init__.py` (Alembic enxerga via `Base.metadata`); depois
  `uv run alembic revision --autogenerate` + `alembic upgrade head`
- Schema Pydantic → `app/schemas/<feature>.py`
- Lógica de negócio (mais de 5 linhas) → `app/services/<feature>_service.py`
- Chamada pra outro serviço → `app/integrations/<servico>_client.py`

Se uma coisa nova não cabe em nenhuma dessas pastas, **pergunte** antes
de criar pasta nova.

## 5. Ambiente real

- **Hospedagem:** Proxmox (LXC ou VM) — este serviço é **dev mas roda em
  ambiente real**. Não é localhost de brincadeira.
- **Rede:** o serviço **vai pra produção online no Proxmox** — não é mais "só
  DMZ interna sem firewall". Siga os 3 tipos de endpoint da `CONVENTION.md §5`:
  **desmilitarizado** (interno à plataforma, sem auth — ex.: `/webhook/notify`),
  **autenticado** (exige JWT + role + status quando aplicável) e **público**
  (logar IP/origem, cuidado redobrado). Já existe **rate limit** por
  `external_id` na geração de OTP (`app/services/rate_limit.py`). **Segredos
  (credenciais, chaves) nunca no código nem no `.env.example` — só no `.env`.**
- **Modelo do Claude Code:** DeepSeek v4 Pro (configurado em `settings.json`
  via `ANTHROPIC_BASE_URL` apontando pra um proxy compatível).

## 6. Comandos que você usa direto

```bash
# bootstrap (uma vez)
uv sync

# rodar local
make dev                  # = uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# testes
make test                 # = uv run pytest -q

# migrations (Alembic)
uv run alembic revision --autogenerate -m "msg"   # gera migration
uv run alembic upgrade head                        # aplica
```

## 7. Gerenciamento de memória

- **`.claude/memory/architecture.md`** — decisões arquiteturais com data e contexto.
- **`.claude/memory/conventions.md`** — convenções específicas (nomes, padrões de erro, logs).
- **`.claude/memory/integrations.md`** — cada serviço externo: URL base, endpoints, formato, retry.
- Antes de implementar algo, leia os 3 arquivos. Antes de terminar a
  tarefa, pergunte-se: "preciso registrar algo aqui?".

## 8. Como pedir ajuda ao usuário

Você está autorizado e **encorajado** a parar e perguntar quando:
- A spec está ambígua
- Falta info de conexão (URL, credencial, formato de evento)
- Existem 2+ caminhos razoáveis e a escolha tem trade-off real

Use perguntas curtas e objetivas, sem opções demais. Não "ofereça menu"
quando uma pergunta direta resolve.

## 9. O que NÃO fazer

- Não criar segundo banco neste serviço.
- Não conectar diretamente no banco de outro serviço.
- Não adicionar dependência sem registrar em `pyproject.toml` via `uv add`.
- Não escrever migration manual — usa `alembic revision --autogenerate`.
  Lembre: tabelas no schema `otp`; FK de `external_id` aponta p/ `auth.users`.
- Não logar segredo (token, senha, payload sensível).
- Não escrever README/comentário em inglês — este projeto é em **PT-BR**.
- Não colocar config no banco — config é no `.env`.

---

**Antes de começar qualquer tarefa**, leia também:
- `.claude/memory/architecture.md`
- `.claude/memory/conventions.md`
- `.claude/memory/integrations.md`
