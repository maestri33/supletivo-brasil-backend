# Convenção de Código — Backend (Microsserviços)

> **Fonte de verdade da padronização.** O Claude lê este arquivo em toda sessão e
> **aplica o Checklist de Revisão (§10) a cada alteração**, sem precisar ser pedido.
> Particularidades de cada serviço ficam no `CLAUDE.md` da pasta do serviço.
> Em conflito, o `CLAUDE.md` do serviço só pode ser **mais restritivo** que este — nunca afrouxar.

---

## 1. Contexto

- O backend é um conjunto de **microsserviços** independentes.
- **Deploy:** uma **VM no Proxmox rodando Docker** (via `docker-compose`) — inicialmente; 1 container Docker por serviço.
- Regra de ouro: **1 serviço = 1 diretório na raiz = 1 container Docker = 1 schema Postgres = 1 responsabilidade**.
- Stack predominante: **Python / FastAPI** (núcleo da convenção).
- **Apps-modelo de referência: `lead` e `enrollment`** (estrutura correta `<servico>/app`, sem aninhamento). Na dúvida, espelhe a estrutura e o estilo deles.
- **Encontre os TODOS**, sempre que encontrar um TODO, é sua obrigacao, 1 Entender ele, 2 confirmar com usuário  mais informaocoes, para realmente ficarem alinhados, 3 resolver e apagar ele...

---

## 2. Stack Canônica (FastAPI) — *"stack correta"*

Toda dependência deve sair desta lista. **Lib fora do padrão exige justificativa registrada no `CLAUDE.md` do serviço.**

| Camada | Ferramenta | Versão mínima |
|---|---|---|
| Runtime | Python | 3.12 |
| API | FastAPI | 0.115 |
| Server | uvicorn[standard] | 0.32 |
| ORM | SQLAlchemy[asyncio] | 2.0 |
| Driver PG | asyncpg | 0.30 |
| Migrações | Alembic | 1.14 |
| Validação | Pydantic | 2.8 |
| Config | pydantic-settings | 2.5 |
| HTTP client | httpx | 0.27 |
| Logs | structlog | 24.4 |
| Build | hatchling (`packages = ["app"]`) | — |
| Lint/format | ruff (`line-length = 100`, `target-version = py312`) | — |
| Testes | pytest + pytest-asyncio (`asyncio_mode = "auto"`) | — |
| Cache/efêmero | Redis (ex.: OTP, locks) | 7 |
| Orquestração | docker-compose (Postgres + Redis + serviços) | — |

**Proibido:** `requests` (use `httpx`) · `print()`/`logging` cru (use `structlog`) · `os.environ` espalhado (use `pydantic-settings`) · Pydantic v1 · SQLAlchemy estilo síncrono 1.x · Flask em serviço novo.

---

## 3. Estrutura de Diretórios — *"design de diretórios / locais corretos"*

```
<servico>/
├── app/
│   ├── __init__.py
│   ├── main.py          # cria o FastAPI, registra routers/middlewares, lifespan
│   ├── config.py        # Settings (pydantic-settings) via get_settings() cacheado
│   ├── db.py            # engine async, Base, metadata c/ schema, get_session()
│   ├── exceptions.py    # exceções de domínio
│   ├── api/             # 1 arquivo por recurso + router.py (agrega) + health.py
│   ├── models/          # SQLAlchemy — 1 arquivo por entidade
│   ├── schemas/         # Pydantic — 1 arquivo por entidade
│   ├── services/        # lógica de negócio — 1 *_service.py por entidade
│   ├── integrations/    # clients de serviços externos (httpx)
│   ├── utils/           # helpers (logging, etc.)
│   └── validators/      # validações de domínio (opcional)
├── alembic/             # migrações  +  alembic.ini
├── tests/
├── pyproject.toml
├── README.md            # o que faz, como rodar, variáveis de ambiente
├── CLAUDE.md            # particularidades do serviço
└── .env                 # NÃO versionar
```

**Regras:**
- Cada tipo de arquivo no seu diretório. Model em `models/`, schema em `schemas/`, regra de negócio em `services/`, rota em `api/`.
- `api/` (pasta), **nunca** `routers/`. `schemas/` e `models/` como **pastas**, nunca `schemas.py`/`models.py`.
- Sem aninhamento de nome (`servico/servico/app` → o pacote é `<servico>/app`).
- Endpoint **fino**: valida entrada, chama `service`, devolve `schema`. Sem lógica de negócio na rota.
- Entenda o que o engenheiro quer, nao saia pressupondo o alucinando, pois acabará tendo que refazer tudo caso nao fique como ele espera, e ele já tem tudo em mente !

---

## 4. Postgres — *"relacionado com postgres / há relacionamento"*

- **Async sempre:** `create_async_engine` + `async_sessionmaker` + `AsyncSession` + `asyncpg`. Nada de engine síncrono.
- **Schema próprio por serviço:** `metadata = MetaData(schema=settings.database_schema)`. O nome do schema é o domínio (`addresses`, `auth`, ...).
- **NAMING_CONVENTION** padronizada para constraints (copiar de `address/app/db.py`).
- **PK = UUID** (`postgresql.UUID`). Referência cross-service usa `external_id`.
- **Relacionamento entre serviços = shadow table read-only.** Nunca importe model de outro serviço. Declare uma `Table` mínima do schema alheio só com a PK necessária:
  ```python
  # Shadow auth.users — necessário pro SQLAlchemy resolver a FK cross-schema.
  auth_users = Table("users", metadata,
      Column("external_id", PG_UUID(as_uuid=True), primary_key=True),
      schema="auth")
  ```
- **Toda mudança de modelo → migração Alembic.** Proibido `Base.metadata.create_all()` em produção.

---
## 5. Lógica das API´s — *"Temos 3 tipos"*

- Os endpoints sao divididos em 3 tipos:
- Desmilitarizados, estes nao necessitam de nem um tipo de autenticacao ou seguranca, pois só será executado dentro da nossa plataforma por outros apps.
- Autenticados, este o nome já diz, requer jwt, role tem que conferir, status deve bater(quando aplicável)...
- Públicas estas o nome já diz, é pública, devemos ter cuidado com elas, salvar o máximo de informacoes possivel, como ip de origem e o que pudermos, estao inclusas nelas o webhooks externos, que quando possível devemos desenvolver algum tipo de verificacao... estes nunca devem ir direto para nosso código, quando for o caso, devemos ter um app específico para o servico, e dali enviar webhooks internos na area desmilitarizada.

---
---


## 6. Fronteiras do Serviço — *"cada app restrito à sua função"*

- Comunicação entre serviços **só** por HTTP (`httpx`) ou eventos. **Nunca** importando código de outro serviço.
- Nenhum serviço acessa o schema/banco de outro (exceto shadow table read-only para FK).
- Sem lógica de domínio alheio (ex.: `address` não calcula comissão; `lead` não emite cobrança).
- Cada serviço é dono **exclusivo** do seu schema e das suas migrações.

---

## 7. Idioma — *"código em inglês / comentários verdadeiros em pt-br"*

- **Identificadores em inglês:** variáveis, funções, classes, módulos, tabelas, colunas, rotas.
- **Docstrings e comentários em pt-br** — e **verdadeiros**: devem descrever o que o código faz *hoje*. Comentário desatualizado/falso é defeito: corrija ou apague.
- Comente o **porquê**, não o óbvio. Sem comentário decorativo nem código comentado.
- Mensagens de erro de domínio voltadas ao cliente: pt-br. Logs técnicos (`structlog`): inglês.

---

## 8. Ferramentas Bem Exploradas — *"ferramentas bem exploradas"*

- **FastAPI:** `Depends` para injeção (sessão, settings, auth); routers modulares; `response_model` e `status_code` em toda rota; `lifespan` (**não** `@app.on_event`, depreciado); `BackgroundTasks` quando couber.
- **Pydantic v2:** `model_config`, `field_validator`/`model_validator` (não a API v1).
- **SQLAlchemy 2.0:** `Mapped`/`mapped_column`, `select()`, sessão async. Sem `Query` legado.
- **structlog** para todo log; **httpx.AsyncClient** para toda chamada externa; **pydantic-settings** para toda config.

---

## 9. Anti-ruído — *"não há ruídos"*

**Não devem existir no código-fonte** (e devem estar no `.gitignore`):
`__pycache__/` · `.venv/` · `.ruff_cache/` · `.pytest_cache/` · `*.pyc` · `*.egg-info/` · `uploads/` e dados locais · backups · arquivos órfãos (ex.: `graphify-out/`) · `config.py` **e** `config/` duplicados.

- Sem código morto, sem trecho comentado, sem `TODO` sem dono.
- `ruff check` e `ruff format` **limpos** antes de concluir qualquer alteração.

---

## 10. Não-duplicação — *"código não duplicado"*

- Lógica repetida vira função em `utils/` (ou `services/`). Proibido copiar-colar entre módulos.
- Padrão repetido entre **vários** serviços: avaliar lib compartilhada — mas só com necessidade real (sem over-engineering).
- Antes de criar, **procure** se já existe util/service que resolve.

---

## 11. Notify — *"Sistema de notificacao"*

- Principalmente os apps de Roles (Lead, Candidate e etc) ao mudar o Stauts devem emitir notificacoes, para isso ja possuimos um sistema... todo app que emite notificacao, deve possuir um diretório destinado para isso, e lá o conteúdo das notificacoes no modelo .md, para quem deve ser enviada, se tts, gerado por ia, geracao de imagem e etc... tudo já implementando em notify.
- Ao terminar o app se pergunte, quantos envolvidos em cada status tempos aqui, informa-lo da mudanca será benéfico ou estratégico ? Crie notificacao (devem sempre ser chamadas de forma assincrona)...
- Ao terminar o app também se pergunte, porque alguém pode ficar parado neste status, será que alguma notificacao pode motiva-lo a avancar... ai crie notificacoes para determinados roles/status que estao a x tempo parados.

---

## 12. Integracoes — *"Toda integracao externa tem que ficar dentro deste diret´rio"*

- Tem integracao com outro app da própria plataforma ? crie um client com nome da plataforma aqui... exemplo, notify.py, só desenvolva funcoes que for usar...
- Integracao com servico externo ? Primeiro, VEJA SE NAO TEMOS UM APP EXCLUSIVO PRA ISSO... se nao... CRIE A INTEGRACAO... é PROIBIDO dois apps integrar com mesmo servico... se um integrar (como IA), outros devem replicar lógica dele, para garantir que se quebrar um token ou mudar uma lógica de api externa sabemos onde atacar...
- Toda variável que configura esta integracao deve estar em .env
- Garanta que o fluxo nao quebre caso a integracao falhar, ESTUDE O CÓDIGO, PREVEJA POSSIVEIS ERROS E ALTERNATIVAS PARA SOLUCOES


## 13. Do uso de IA— *"somos muito a favor da integracao com IA"*

- Privilegie integracoes com IA, ao terminar um app se pergunte, onde posso por IA pra colaborar, resolver, melhorar, resolver algo neste app... Integre sem medo.
- Garanta que o fluxo de nao quebre caso algo inesperado aconteca

---
## 14. Menos é mais — *"simplicidade é tudo"*

- Evite coisas complexas, menos é mais, solucoes simples, logica reduzida devem ser privilegiadas

---
---

## 15. Checklist de Revisão — *o Claude aplica a cada alteração*

A cada mudança que eu revisar ou produzir, verifico e reporto:


- [ ] **TODOS** - encontrou todos os TODOS que foram colocados naquele app ?
- [ ] **TirarDúvidas** - Fez perguntas ao solicitante para evitar alucinacoes e entender exatamente o que o usuário espera ?
- [ ] **Stack** — usa só a stack canônica (§2)? Nenhuma lib proibida/sem justificativa?
- [ ] **Postgres** — async (`asyncpg`/`AsyncSession`)? Schema próprio? Migração Alembic criada quando o modelo mudou?
- [ ] **Relacionamento** — FK cross-schema via shadow table, sem importar model alheio (§4)?
- [ ] **Diretórios** — cada arquivo no lugar certo? `api/`, `models/`, `schemas/`, `services/` (pastas)?
- [ ] **Fronteira** — alteração dentro da responsabilidade do serviço, sem invadir domínio alheio (§5)?
- [ ] **Idioma** — identificadores em inglês; docstrings/comentários em pt-br e **verdadeiros** (§6)?
- [ ] **Ruído** — nada de `__pycache__`/órfãos/código morto/duplicação de config (§8)?
- [ ] **Duplicação** — não repete lógica existente; reusa util/service (§9)?
- [ ] **Ferramentas** — usa DI, Pydantic v2, SQLAlchemy 2.0, structlog, httpx corretamente (§7)?
- [ ] **Documentação** — README/docstrings/comentários condizem com o código (§11)?
- [ ] **Testes & lint** — há teste para o comportamento novo? `ruff` limpo?
- [ ] **Wiki** - Funciona ? Aprovado ? Apto a producao, ai tu vai e cria um único arquivo .md em wiki, este deve ser fonte de verdade !

Para cada item: ✅ ok · ⚠️ ajustar (com o porquê) · ❌ bloqueia.
