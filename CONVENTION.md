# Convenção de Código — Backend (Microsserviços)

> **Fonte de verdade da padronização.** O Claude lê este arquivo em toda sessão e
> **aplica o Checklist de Revisão (§21) a cada alteração**, sem precisar ser pedido.
> Particularidades de cada serviço ficam no `CLAUDE.md` da pasta do serviço.
> Em conflito, o `CLAUDE.md` do serviço só pode ser **mais restritivo** que este — nunca afrouxar.

---

## 1. Contexto

- O backend é um conjunto de **microsserviços** independentes.
- **Deploy:** uma **VM no Proxmox rodando Docker** (via `docker-compose`) — 1 container por serviço.
- **Regra de ouro:** `1 serviço = 1 diretório na raiz = 1 container Docker = 1 schema Postgres = 1 responsabilidade`.
- Stack predominante: **Python / FastAPI**.
- **App-modelo de referência: `lead`** (estrutura `<servico>/app`, sem aninhamento). Na dúvida, espelhe a estrutura e o estilo dele.
- Antes de codar, **entenda o que o engenheiro quer**. Pergunte, não pressuponha. Ele já tem tudo em mente — alucinação custa retrabalho.

---

## 2. Stack Canônica (FastAPI)

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
| Cache/efêmero | Redis (ex.: OTP, locks, rate-limit) | 7 |
| Orquestração | docker-compose | — |

**Proibido:** `requests` (use `httpx`) · `print()`/`logging` cru (use `structlog`) · `os.environ` espalhado (use `pydantic-settings`) · Pydantic v1 · SQLAlchemy estilo síncrono 1.x · Flask em serviço novo · `Base.metadata.create_all()` em produção.

**Porta padrão:** 8000 (HTTP) por container.

---

## 3. Estrutura de Diretórios

```
<servico>/
├── app/
│   ├── __init__.py
│   ├── main.py          # cria o FastAPI, registra routers/middlewares, lifespan
│   ├── config.py        # Settings (pydantic-settings) via get_settings() cacheado
│   ├── db.py            # engine async, Base, metadata c/ schema, get_session()
│   ├── dependencies.py  # Depends() reutilizáveis (sessão, auth, gates de role/status)
│   ├── exceptions.py    # exceções de domínio
│   ├── api/             # rotas — public/ · authenticated/ · demilitarized/ · health.py · router.py
│   ├── models/          # SQLAlchemy — 1 arquivo por entidade
│   ├── schemas/         # Pydantic — 1 arquivo por entidade
│   ├── services/        # lógica de negócio — 1 *_service.py por entidade
│   ├── integrations/    # clients HTTP de outros serviços (httpx)
│   ├── notify/          # quando o serviço emite notificações — messages/*.md
│   ├── utils/           # helpers (logging, etc.)
│   └── validators/      # validações de domínio (opcional)
├── alembic/             # migrações  +  alembic.ini
├── tests/
├── pyproject.toml
├── README.md            # o que faz, como rodar, variáveis de ambiente
├── CLAUDE.md            # particularidades do serviço (mais restritivo que este)
├── wiki/<servico>.md    # fonte de verdade funcional (criado só após aprovação)
└── .env                 # NÃO versionar — `.env.example` espelha sem segredos
```

**Regras:**
- Cada tipo de arquivo no seu diretório. Model em `models/`, schema em `schemas/`, regra de negócio em `services/`, rota em `api/`.
- `api/` (pasta), **nunca** `routers/`. `schemas/` e `models/` como **pastas**, nunca `schemas.py`/`models.py`.
- Sem aninhamento de nome (`servico/servico/app` → o pacote é `<servico>/app`).
- **Endpoint fino:** valida entrada → chama `service` → devolve `schema`. Sem lógica de negócio na rota.
- Identificador novo → inglês. Comentário/docstring → pt-br verdadeiro (§15).
- **Spec/TODO do dono pode estar em pt-br** — é explicação para você entender o pedido. O código continua em inglês.

---

## 4. Postgres e Relacionamentos

- **Async sempre:** `create_async_engine` + `async_sessionmaker` + `AsyncSession` + `asyncpg`. Nada de engine síncrono.
- **Schema próprio por serviço:** `metadata = MetaData(schema=settings.database_schema)`. Nome do schema = domínio (`addresses`, `auth`, …).
- **NAMING_CONVENTION** padronizada para constraints (copiar de `address/app/db.py`).
- **PK = UUID** (`postgresql.UUID`).
- **Relacionamento entre serviços = `external_id`, NÃO FK cross-schema.**
  - `external_id` é UUID **opaco**, referência lógica ao serviço dono (ex.: `auth.users.external_id`).
  - **Sem shadow table.** Sem FK declarada cruzando schemas. Sem `Table(... schema="auth")` em outro serviço.
  - Validação de existência (quando precisar) é via chamada HTTP ao serviço dono — não via DB.
- **Toda mudança de modelo → migração Alembic.** Proibido `Base.metadata.create_all()` em produção.

---

## 5. APIs — Três tipos de endpoint

Todo endpoint pertence a **um e apenas um** dos três tipos. Pasta espelha isso: `api/public/`, `api/authenticated/`, `api/demilitarized/`.

### 5.1 Desmilitarizado (`api/demilitarized/`)
- Consumido **apenas dentro da plataforma**, por outros apps.
- **Sem autenticação.** Sem rate-limit. Sem JWT.
- Não exposto ao mundo. Firewall + rede interna do Proxmox garantem o isolamento.
- Ex.: webhook interno entre apps, listagem de dados para outro serviço.

### 5.2 Autenticado (`api/authenticated/`)
- Requer **JWT válido** (RS256 via app `jwt`, JWKS cacheado 5 min).
- Requer **role compatível** (gate em `dependencies.py`).
- Requer **status compatível** (quando aplicável — ex.: candidato só avança se status anterior bate).

### 5.3 Público (`api/public/`)
- Exposto ao mundo. Cuidado redobrado.
- **Logar IP de origem, user-agent e todo metadado de contexto.**
- Rate-limit obrigatório (Redis).
- **Webhooks externos NUNCA chegam direto no código de negócio.** Quando o webhook vem de um terceiro (gateway, IA externa, etc.), ele entra no **app dedicado àquele serviço** (ex.: app `asaas` recebe webhook do Asaas), e dali é repassado via webhook **interno** (desmilitarizado) para o app que precisa do evento.

---

## 6. Fronteiras do Serviço — Cada um no seu domínio

- Comunicação entre serviços **só** por HTTP (`httpx`). **Nunca** importando código de outro serviço.
- Nenhum serviço acessa o schema/banco de outro. Sem shadow table. Sem JOIN cross-schema.
- **Sem lógica de domínio alheio.** Exemplos:
  - `auth` **não** tem tabela de roles — roles vivem em `roles` (§8).
  - `address` **não** calcula comissão.
  - `lead` **não** emite cobrança — chama `fees`/`asaas`.
  - `candidate` **não** valida pix — chama `asaas`.
  - `student` **não** corrige prova — orquestra `training` + `ai`.
  - `fees` **não** libera acesso — só guarda status, quem libera é o serviço dono do recurso.
- Cada serviço é dono **exclusivo** do seu schema, das suas migrações e do seu domínio.

---

## 7. Integrações Internas Obrigatórias

Existem serviços **internos compartilhados** que centralizam responsabilidades transversais. **É PROIBIDO** qualquer outro app falar com a API externa correspondente diretamente — sempre via app interno.

| Responsabilidade | App interno | Quem pode falar com a API externa |
|---|---|---|
| Pagamentos / PIX / cobrança | **`asaas`** (app **interno**) | Só `asaas` fala com a API do Asaas. Outros apps consomem o app interno `asaas` via HTTP. |
| IA (LLM, visão, correção, validação) | **`ai`** (app **interno**) | Só `ai` fala com qualquer provedor de IA (DeepSeek, OpenAI, etc.). Outros apps consomem `ai` via HTTP. |
| Notificações (WhatsApp/SMS/email/TTS) | **`notify`** | Só `notify`. Outros apps disparam via HTTP + `notify/messages/*.md` no app emissor. |
| JWT / JWKS | **`jwt`** | Só `jwt` assina e expõe JWKS. Outros apps validam consultando JWKS. |
| Roles / transições de papel | **`roles`** | Só `roles` lê/escreve a tabela de roles (§8). |
| OTP | **`otp`** | Só `otp` gera/valida códigos. |
| Identidade / cadastro de user | **`auth`** | Só `auth` cria/atualiza usuário (CPF, phone, email). |
| Polos | **`hub`** | Só `hub` cadastra/altera polos. |
| Documentos / fotos de docs | **`documents`** | Só `documents` armazena arquivos de identidade. |
| Endereços | **`address`** | Só `address` resolve CEP e guarda endereços. |
| Perfis | **`profiles`** | Só `profiles` mantém dados pessoais (nome, etc.). |

**Regras de integração:**
- Cliente HTTP do app interno mora em `<servico>/app/integrations/<app_interno>.py`. Só implementa o que esse serviço **realmente usa**.
- Toda config de integração (URL base, timeout, token) em `.env`. Nunca hardcoded.
- **Fluxo nunca quebra por falha de integração** — degrade gracioso + log estruturado. Exceção: ações intencionalmente bloqueantes (ex.: promoção de papel na criação de promoter), documentadas no `CLAUDE.md` do serviço.
- **Idempotência** obrigatória em qualquer integração que move dinheiro (§12).

**Por que centralizar:** se um token quebra ou a API externa muda, sabemos exatamente onde atacar. Duplicar integração = duplicar fragilidade.

---

## 8. Sistema de Roles — `.env`, não DB

- **Lista de roles válidas** vive em `.env` do app `roles`, NÃO em tabela do banco.
- **Transições válidas** (ex.: `lead → candidate → training → promoter`) também em `.env`.
- Tabela em `roles` armazena apenas: **quem (external_id) tem qual role agora + histórico de transições**.
- **Nenhum outro app** mantém tabela de roles. `auth` **não** tem `user_roles`. Quem precisa saber o role do user chama `roles` via HTTP.
- Toda transição de role passa por `roles` (chamada HTTP), é atômica e auditável (quem mudou, de qual → qual, quando, por quê).
- Um usuário pode acumular roles (ex.: `coordinator` continua sendo `promoter`; `veteran` continua sendo `student`).

---

## 9. Provisionamento Automático no Cadastro

Quando `auth` cria um usuário (`POST /register`), ele dispara provisionamento **best-effort** dos registros relacionados, com campos `null`:

- `profiles` → registro de perfil vazio (preenchido depois no funil)
- `documents` → registro `document` com todos os sub-documentos (`rg`, `cnh`, `certidao`, `reservista`, etc.) criados com campos `null`. `certidao` é única por document mas pode ser nascimento/casamento/etc. `reservista` existe para todo user homem; mulher fica null permanentemente.
- `notify` → registro de contato (phone + canais preferidos)
- `address` → registro de endereço vazio
- `roles` → role inicial (ex.: `lead`)

**"Best-effort"** porque transação distribuída entre microsserviços via HTTP não é atômica de verdade. Cada chamada loga falha mas não bloqueia o cadastro. Reconciliação posterior, quando aplicável, fica no app dono.

---

## 10. Unicidade Absoluta de Identidade

`auth` garante: **NUNCA** dois usuários com `cpf`, `phone` ou `email` iguais — nem **falsos**.

- Unique constraint no DB para `cpf`, `phone`, `email`.
- Validação ativa de formato: CPF com algoritmo de dígito verificador; phone com regex E.164 BR; email com regex padrão.
- Validação ativa de **veracidade** (quando aplicável): consulta via app `ai` ou app dedicado para flag de CPF fake/clonado. Falha de validação não bloqueia cadastro, mas marca registro com flag para revisão.

---

## 11. Não-duplicação de Dados Derivados

Se um dado pode ser **derivado** de outro, **não duplique a lógica** — chame o serviço dono.

- CPF puxa nome → consulta o serviço dono dessa lookup, não reimplementa em cada app.
- CEP puxa endereço → chama `address` (que internamente integra com ViaCEP/etc.).
- Foto de selfie → valida via `ai`, não duplicar OCR/face em cada app.
- Saldo de comissão → consulta `commissions`, não recalcular.

---

## 12. Caminho do Dinheiro — Idempotência

Quando o fluxo move dinheiro (cobrança, payout, comissão):

1. **Persistir a intenção** no banco local **antes** de chamar o app `asaas`.
2. **ID determinístico** para o pagamento (ex.: `fee-<fee_id>-<kind>`, `commission-<commission_id>`). Re-submit → mesma chave → `asaas` responde `already_exists` em vez de duplicar.
3. **Status interno guiado por webhook** do app `asaas` (que por sua vez recebe do Asaas externo).
4. **Webhook nunca cria pagamento, só atualiza status** de pagamento já existente. Se chega webhook de algo desconhecido, log + descarte controlado.
5. **Fuso horário explícito:** `America/Sao_Paulo` para qualquer agendamento/janela (ex.: processamento semanal de comissões sexta 18h). Nunca confiar em hora local do container.

---

## 13. Notificações

- Apps de **role com funil** (Lead, Candidate, Training, Enrollment, Student, Coordinator) emitem notificação em **toda mudança de status**.
- Notificação é **sempre async** (FastAPI `BackgroundTasks`). Nunca bloqueia a resposta HTTP.
- Falha de notificação **nunca quebra o fluxo** — try/except + log, segue o jogo.
- Cada serviço emissor tem `app/notify/messages/<evento>.md` com o conteúdo da mensagem (texto + metadados de canal/voz/imagem).
- Disparo via cliente HTTP em `app/integrations/notify.py`.
- Ao fechar o app, pergunte:
  - **Quantos envolvidos** existem em cada status? Vale informar mudança a algum deles?
  - **Algum status pode estagnar** o usuário? Vale criar notificação de retomada (ex.: "candidato 7 dias parado em `documents`")?

---

## 14. Uso de IA

- **Privilegie integração com IA.** Ao fechar um app, pergunte: onde IA pode colaborar, validar, melhorar?
- **Toda IA passa pelo app interno `ai`** (§7). Proibido cliente DeepSeek/OpenAI/Anthropic/etc. em qualquer outro app.
- Fluxo **degrada se IA falhar** — nunca bloqueia caminho crítico, só não enriquece.
- Exemplos esperados:
  - `candidate`: validar selfie como assinatura
  - `documents`: extrair dados de RG/CNH/comprovante e validar consistência
  - `training`: corrigir resposta vs gabarito, dar nota 0–10 + justificativa
  - `auth`: flagar CPF/email suspeitos
  - `commissions`: detectar anomalia em volume de leads

---

## 15. Idioma

- **Identificadores em inglês:** variáveis, funções, classes, módulos, tabelas, colunas, rotas.
- **Docstrings e comentários em pt-br** — e **verdadeiros**: descrevem o que o código faz **hoje**. Comentário desatualizado/falso é defeito → corrija ou apague.
- Comente o **porquê**, não o óbvio. Sem comentário decorativo. Sem código comentado.
- **Mensagens de erro de domínio** voltadas ao cliente: pt-br.
- **Logs técnicos** (`structlog`): inglês, estruturado, sem PII (CPF, RG, telefone completo, endereço completo).
- **Spec/TODO em pt-br é explicação para entender o pedido** — o código fica em inglês independentemente. Ex.: TODO diz "documento RG"; no código fica `rg_document`, não `documento_rg`.

---

## 16. Ferramentas Bem Exploradas

- **FastAPI:** `Depends` para injeção (sessão, settings, auth); routers modulares; `response_model` e `status_code` em toda rota; `lifespan` (**não** `@app.on_event`); `BackgroundTasks` quando couber.
- **Pydantic v2:** `model_config`, `field_validator`/`model_validator` (não a API v1).
- **SQLAlchemy 2.0:** `Mapped`/`mapped_column`, `select()`, sessão async. Sem `Query` legado.
- **structlog** para todo log.
- **httpx.AsyncClient** para toda chamada externa.
- **pydantic-settings** para toda config.

---

## 17. Anti-ruído

**Não devem existir no código-fonte** (e devem estar no `.gitignore`):
`__pycache__/` · `.venv/` · `.ruff_cache/` · `.pytest_cache/` · `*.pyc` · `*.egg-info/` · `uploads/` e dados locais · backups · arquivos órfãos · `config.py` **e** `config/` duplicados.

- Sem código morto.
- Sem trecho comentado.
- **Sem `TODO` órfão** — todo TODO tem dono e prazo, ou vira spec, ou apaga.
- `ruff check` e `ruff format` **limpos** antes de concluir qualquer alteração.

---

## 18. Não-duplicação de Código

- Lógica repetida vira função em `utils/` (ou `services/`). Proibido copiar-colar entre módulos do mesmo serviço.
- Padrão repetido entre **vários** serviços: avaliar lib compartilhada — só com necessidade real (sem over-engineering).
- Antes de criar, **procure** se já existe util/service que resolve.

---

## 19. Wiki — Fonte de Verdade Funcional

- **Nada de encher código de `.md`.**
- Após o app **funcionar + ser aprovado + estar apto a produção**, criar **um único** arquivo `wiki/<servico>.md` no app. Esse arquivo:
  - Explica o que o app faz (visão funcional)
  - Lista integrações (quem ele chama, quem chama ele)
  - Mostra funil de status (se houver)
  - É a **fonte de verdade** consultada por humanos e pelo Claude antes de qualquer mudança
- Antes da Wiki existir: o TODO original do dono fica como spec viva. Quando a Wiki nasce, o TODO sai.

---

## 20. Menos é mais

- Soluções simples > soluções espertas.
- Lógica reduzida > abstração prematura.
- Se em dúvida entre 2 caminhos: o mais curto, o mais óbvio, o mais fácil de apagar.

---

## 21. Checklist de Revisão — *o Claude aplica a cada alteração*

A cada mudança que eu revisar ou produzir, verifico e reporto. Para cada item: ✅ ok · ⚠️ ajustar (com o porquê) · ❌ bloqueia.

- [ ] **TODOs** — encontrei todos os TODOs do app? Entendi cada um? Confirmei com o usuário antes de resolver? Apaguei após resolver?
- [ ] **Dúvidas** — perguntei ao solicitante antes de pressupor? (Alucinar = retrabalho)
- [ ] **Stack** — só stack canônica (§2)? Lib fora do padrão tem justificativa no `CLAUDE.md`?
- [ ] **Postgres** — async (`asyncpg`/`AsyncSession`)? Schema próprio? PK = UUID? Migração Alembic quando modelo mudou?
- [ ] **Relacionamento** — `external_id` (não FK cross-schema, não shadow table)? Validação por HTTP, não JOIN (§4)?
- [ ] **Diretórios** — cada arquivo no lugar certo? `api/` divide `public/`, `authenticated/`, `demilitarized/` (§3, §5)?
- [ ] **Fronteira** — alteração dentro da responsabilidade do serviço? Sem invadir domínio alheio (§6)?
- [ ] **Integrações internas** — Asaas só via app interno `asaas`, IA só via app interno `ai`, notify só via `notify`, roles só via `roles`, etc. (§7)?
- [ ] **Roles** — nenhuma tabela de roles fora do app `roles`? Lista/transições em `.env` (§8)?
- [ ] **Provisionamento** — `auth` criou Profile + Documents + Notify + Address + Role inicial best-effort (§9)?
- [ ] **Unicidade** — `auth` garante CPF/phone/email únicos e validados (§10)?
- [ ] **Não-duplicação derivada** — CPF puxa nome via serviço, CEP via `address`, etc. (§11)?
- [ ] **Dinheiro** — intenção persistida antes da chamada? ID determinístico? Webhook só atualiza, não cria? Fuso `America/Sao_Paulo` explícito (§12)?
- [ ] **Endpoints** — tipo correto (público/autenticado/desmilitarizado)? Público tem log de IP + rate-limit? Autenticado tem gate de role/status (§5)?
- [ ] **Notify** — toda mudança de status emite notificação assíncrona? Mensagens em `notify/messages/*.md`? Falha não quebra fluxo (§13)?
- [ ] **IA** — onde IA pode colaborar neste app? Integração via app interno `ai`? Degrada se falhar (§14)?
- [ ] **Idioma** — identificadores em inglês; docstrings/comentários em pt-br **verdadeiros**; sem PII em log (§15)?
- [ ] **Ferramentas** — DI, Pydantic v2, SQLAlchemy 2.0, structlog, httpx corretamente (§16)?
- [ ] **Ruído** — sem `__pycache__`/órfãos/código morto/config duplicado/TODO órfão (§17)?
- [ ] **Duplicação** — não repete lógica existente; reusa util/service (§18)?
- [ ] **Testes & lint** — há teste para o comportamento novo? `ruff check` e `ruff format` limpos?
- [ ] **Wiki** — app funciona + aprovado + apto a produção → criei `wiki/<servico>.md` único como fonte de verdade (§19)?
- [ ] **Simplicidade** — escolhi o caminho mais curto e fácil de apagar (§20)?
