# CLAUDE.md — Memória e regras deste microserviço

> Este arquivo é a **fonte da verdade** para você (Claude Code) sobre este
> microserviço. Leia ele inteiro antes de fazer qualquer coisa. Se algo aqui
> conflita com o que o usuário pediu agora, **pergunte** — não decida sozinho.

---

## 1. Quem é você aqui

- Você é o Claude Code **exclusivo deste serviço**. Você não conhece outros
  serviços do ecossistema; quando precisar falar com outro serviço, faz isso
  via HTTP, fila ou webhook (ver `app/integrations/`).
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
4. **Stack fixa.** Não troque FastAPI por Flask, SQLAlchemy por outro ORM,
   uv por poetry. Se o usuário pedir, confirme antes.
5. **Porta 8000.** Esse serviço expõe a porta **8000** (HTTP), publicada no
   host em `:8157` via Docker Compose. (Era 80; mudou no sync de 2026-05-22.)
6. **Postgres central, schema próprio.** Este serviço usa o **Postgres central
   `v7m`** no schema **`notify`** — não tem banco próprio. Há FK cross-schema
   para `auth.users`. Não leia/escreva tabelas de schema de outro serviço por
   SQL (exceto a FK `auth.users`); para o resto, chama a API do serviço.

## 3. Stack

| Camada            | Tecnologia                              |
| ----------------- | --------------------------------------- |
| Runtime           | Python 3.12 + `uv`                      |
| Web framework     | FastAPI                                 |
| Servidor ASGI     | Uvicorn (porta 8000)                    |
| ORM               | SQLAlchemy 2 (async)                     |
| Migrations        | Alembic                                 |
| Banco             | Postgres central v7m (schema `notify`)  |
| Validação         | Pydantic v2                             |
| Config            | pydantic-settings + `.env`              |
| HTTP cliente      | httpx (async)                           |
| Cache / pub-sub   | redis.asyncio                           |
| Mensageria        | aio-pika (RabbitMQ)                     |
| Testes            | pytest + pytest-asyncio + httpx client  |
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
│   ├── db.py                 # SQLAlchemy async (Base, engine, get_session)
│   ├── exceptions.py         # DomainError, NotFound, Conflict, IntegrationError
│   ├── api/                  # routers HTTP
│   │   ├── router.py         # agrega todos os routers
│   │   ├── health.py         # /health, /ready
│   │   ├── contacts.py       # CRUD + /check
│   │   ├── messages.py       # POST /send + list
│   │   ├── logs.py           # listagem de logs
│   │   └── templates.py      # get/update email template
│   ├── models/               # modelos SQLAlchemy (Contact, Message, Log, Template)
│   ├── schemas/              # Pydantic schemas (request/response)
│   ├── services/             # regras de negócio (contact, message, log, template, metrics)
│   ├── integrations/         # clientes externos
│   │   ├── http_client.py    # httpx shared com retry
│   │   ├── smtp.py           # SMTPClient — envio SMTP direto + helpers admin Mailcow
│   │   ├── whatsapp.py       # WhatsAppClient — Evolution GO v2 (+resolve_br_number)
│   │   ├── ai.py             # AIClient — texto/imagem/TTS/JSON (service ai)
│   │   ├── profiles.py       # ProfilesClient — gênero p/ voz TTS
│   │   ├── deepseek.py       # DeepSeekClient — edição de template via IA
│   │   ├── elevenlabs.py     # ElevenLabsClient — TTS
│   │   └── gemini.py         # GeminiClient — imagem + visao
│   └── utils/
│       └── logging.py        # structlog
├── tests/                    # pytest
├── scripts/
│   ├── dev.sh                # roda uvicorn em dev
│   └── new_service.sh        # clona este template p/ um novo serviço
├── pyproject.toml
├── .env.example
├── Makefile
└── README.md
```

**Regra das pastas:**
- Endpoint HTTP novo → `app/api/<feature>.py`, registrar em `app/api/router.py`
- Modelo de banco novo → `app/models/<entidade>.py`, importar em
  `app/models/__init__.py` para o Alembic enxergar (autogenerate)
- Schema Pydantic → `app/schemas/<feature>.py`
- Lógica de negócio (mais de 5 linhas) → `app/services/<feature>_service.py`
- Chamada pra outro serviço → `app/integrations/<servico>_client.py`
- Consumir mensagem de fila → `app/workers/<topico>_consumer.py`

Se uma coisa nova não cabe em nenhuma dessas pastas, **pergunte** antes
de criar pasta nova.

## 5. Ambiente real

- **Hospedagem:** Proxmox (LXC ou VM) — este serviço é **dev mas roda em
  ambiente real**. Não é localhost de brincadeira.
- **Rede:** está numa **DMZ**. Não há firewall protegendo este serviço de
  outros serviços internos. Por enquanto, **segurança não é prioridade** —
  pode pular auth, CORS aberto, sem rate-limit. O usuário vai pedir essas
  camadas depois, num passe explícito de "agora trava isso".
- **Modelo do Claude Code:** DeepSeek v4 Pro (configurado em `settings.json`
  via `ANTHROPIC_BASE_URL` apontando pra um proxy compatível, ex.:
  claude-code-router ou litellm).

## 6. Comandos que você usa direto

```bash
# bootstrap (uma vez)
uv sync

# rodar local
make dev                  # = uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# testes (precisa de Postgres real — testcontainers OU TEST_DATABASE_URL)
make test                 # = uv run pytest -q

# migrations (Alembic)
make migrate                       # = uv run alembic upgrade head
make migrate-new msg='descricao'   # gera revision (autogenerate)
```

## 7. Gerenciamento de memória

- **`.claude/memory/architecture.md`** — sempre que tomar uma decisão
  arquitetural (escolheu RabbitMQ vs NATS, quebrou um modelo em dois,
  mudou estratégia de cache), registre aqui em uma seção datada.
- **`.claude/memory/conventions.md`** — convenções deste serviço
  específico (nomes, padrões de erro, formato de log). Atualize quando
  for combinado algo novo.
- **`.claude/memory/integrations.md`** — para cada serviço externo com
  que este serviço fala: URL base, endpoints usados, formato esperado,
  retry policy. Atualize **toda vez** que adicionar uma chamada nova.
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

- Não criar segundo banco/conexão neste serviço (uma engine, o Postgres `v7m`).
- Não ler/escrever tabelas de schema de outro serviço por SQL (exceto a FK
  `auth.users`). Para dados de outro serviço, chama a API dele.
- Não adicionar dependência sem registrar em `pyproject.toml` via
  `uv add`.
- Não escrever migration manual — usa `alembic revision --autogenerate`
  (`make migrate-new`).
- Não logar segredo (token, senha, payload sensível).
- Não escrever README/comentário em inglês — este projeto é em **PT-BR**.

---

**Antes de começar qualquer tarefa**, leia também:
- `.claude/memory/architecture.md`
- `.claude/memory/conventions.md`
- `.claude/memory/integrations.md`
