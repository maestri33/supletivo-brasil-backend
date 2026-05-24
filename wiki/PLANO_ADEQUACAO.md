# Plano — Backend supletivo

> Base: `wiki/<app>.md` (14 apps mapeados, 2026-05-23). Convenção: `../CONVENTION.md`.
> **Duas frentes distintas:** A) ADEQUAR os 14 apps existentes · B) CRIAR 8 serviços novos.
> Nota: `wiki/` é documentação (fonte de verdade §15), **não** um microsserviço.
>
> **Atualizado 2026-05-24:** `asaas` e `infinitepay` concluídos até a Fase 5
> (split models + PK UUID + webhook §5 + desempate `order_by` + docs `.claude/`).
> Handoff `infinitepay/MIGRACAO_F3.md` removido (cumprido).

## Princípios
- **Antes de tocar/criar cada serviço:** reler a `../CONVENTION.md` (atualizada) + o `wiki/<app>.md` correspondente — alinhar à convenção *antes* de codar.
- 1 serviço = 1 escopo = 1 PR; ao fim: `ruff` limpo + testes + `wiki/<app>.md` atualizado (§15).
- **Ao concluir cada serviço:** rodar um **agente de conformidade** que compara o código com a `CONVENTION.md` item a item (checklist §15); só fechar quando passar.
- Baseline commit antes de cada fase (working tree tinha ~983 mudanças não commitadas).
- Modelo de referência de estrutura: `lead`, `enrollment`. Fluxo §1: entender → confirmar → resolver.
- **Deploy:** VM no Proxmox rodando Docker (`docker-compose`) inicialmente.

---

## PARTE A — Adequação dos 14 apps existentes

### Fase 1 — Segurança 🔒 (urgente)
- ✅ `otp` (2026-05-23): `database_url` tinha default hardcoded (`v7m:v7m`) em `config.py` → agora campo **obrigatório**, vindo do `.env`; TODO removido; `.env.example` com placeholder; `CLAUDE.md §5` atualizado (serviço vai pra produção online). Sistêmico: `v7m:v7m` em 14 arquivos → demais serviços na **Fase 4** (config).
- ✅ `jwt` (2026-05-23, verificado): `private.pem` **já** está no `.gitignore` e **nunca** foi versionado (`git ls-files`/`git log --all` vazios) → `git rm --cached` desnecessário. Rotação **dispensada** (sem vazamento; invalidaria tokens à toa). `_ensure_keys()` regenera se faltar.
- ⚠️ Webhooks reclassificados: `otp` `/webhook/notify` é **interno** (notify→otp; §5 dispensa auth) e `candidate/routers/public/auth.py` é **superfície pública** (check/register/login), **não** webhook. Verificação de assinatura de **webhook externo** pertence a `asaas`/`infinitepay` (callbacks de pagamento) → **Fase 3/4**.

### Fase 2 — Achatamento estrutural (mecânico)
- ✅ (2026-05-23) 12 aninhados `<app>/<app>` → `<app>/` achatados: address, ai, asaas, auth, candidate, documents, infinitepay, jwt, notify, otp, profiles, roles. (Já corretos: lead, enrollment.) Sem colisão; `TODO`/`media` mantidos no topo (igual ao modelo `enrollment/TODO`). Nenhuma ref hardcoded ao path duplo (imports são `from app.*`). otp validado do novo caminho (ruff + boot). Obs: `candidate` usa `requirements.txt` (sem `pyproject.toml`) → migração de stack na Fase 3.

### Fase 3 — Stack/ORM (reescritas, maior esforço)
- psycopg2 síncrono → asyncpg async: `asaas`, `infinitepay`.
- Tortoise ORM + SQLite → SQLAlchemy async + asyncpg + Postgres: `candidate`, `documents`.
- ✅ `asaas` — **código async feito (2026-05-23)**: spine (db.py async espelhando `address`, alembic/env.py async espelhando `enrollment`, config_store, main lifespan+worker, structlog, pyproject: -psycopg2 +asyncpg +structlog +hatchling +pytest-asyncio, `pytest.ini` removido) + `AsaasClient` httpx→`AsyncClient` + 10 services + 5 routers (config/payment/pixkey/webhook). `database_url` obrigatório (D1, sem default `v7m:v7m`). `ruff` limpo + `import app.main` OK; caminho do dinheiro (`submit_one`/`tick`/`worker_loop`/`reconcile`) revisado. Plano em `asaas/MIGRACAO_F3.md`. Achado: HEAD era sync e o `MIGRACAO_F3` superestimou o trabalho — services/api já tinham sido convertidos junto da spine; sobravam só 4 routers.
  - ✅ **Testes async (2026-05-23):** suíte migrada (conftest `sqlite+aiosqlite` async, `httpx.AsyncClient`/ASGITransport, `fake_asaas` AsyncMock) — **183 passed**, `ruff` limpo. §15 essencialmente fechado.
  - ✅ **Validado contra Postgres real (2026-05-23):** `alembic upgrade head` 0001→0003 OK + smoke de escrita OK. **Fix necessário (migração `0003`):** todas as colunas `DateTime`→`timestamptz` (models `DateTime(timezone=True)`) — bug latente que o sqlite escondia: código usa `datetime.now(UTC)` (aware); psycopg2 tolerava, **asyncpg recusa aware em coluna naive** → quebrava TODA escrita. `183 passed` (sqlite) seguem verdes.
  - ✅ **Pendências asaas resolvidas (2026-05-24):** `alembic/env.py` cria o schema (`CREATE SCHEMA IF NOT EXISTS`); `wiki/asaas.md` reescrita; **PK→UUID + timestamptz** na F4 (migração `0001` squashada, fundiu `charge_support`/`timestamptz`). Remanesce só o TODO de produção (onboarding security key).
- ✅ `infinitepay` — **F3 async (2026-05-24, `cb87af6`):** psycopg2→asyncpg, `httpx.Client`→`AsyncClient`, structlog, config 100% via `.env` (tabela/rotas `config` removidas), IA direta (DeepSeek SDK) removida — recibo/triagem passam pelo app `ai`. **F4 (`827b0dd`):** split `models/`, PK→UUID + timestamptz, webhook §5 (`source_ip`/`user_agent`). Validado: ruff + 20 testes + `alembic upgrade head` contra Postgres real. `wiki/infinitepay.md` reescrita; docs `.claude/` criados.

### Fase 4 — Conformidade transversal
- PK → UUID (§4): ✅ asaas, ✅ infinitepay (2026-05-24). Pendentes: address, documents, enrollment, notify, otp.
- logging cru → structlog (§2): ✅ asaas, ✅ infinitepay. Pendentes: auth, roles.
- `niquests` → `httpx` (§2): auth.
- I/O síncrono → async: ✅ infinitepay, ✅ asaas. Pendentes: ai (OCR), lead (time.sleep).
- Dedup identidade: remover tabela `auth.user_roles` (roles é dono); CPF duplicado (auth delega a profiles); remover `_validate_entry_role`; rever `/atomic` (§6).
- IA central no `ai`: ✅ remover toda IA do `infinitepay` (F3). Pendentes: migração órfã do `notify`; gap `/image/vision` (prompt+language) no `ai`.
- `roles`: lista de papéis → `.env`; regras de transição no DB.

### Fase 5 — Testes + wiki
- Cobertura de comportamento por app; `ruff` limpo; atualizar `wiki/<app>.md`.
- ✅ `asaas` (191 testes, `wiki/asaas.md`, `.claude/`) e ✅ `infinitepay` (20 testes, `wiki/infinitepay.md`, `.claude/`) — 2026-05-24. Demais apps pendentes.

---

## Infra (transversal — habilita a Parte B)
- `docker-compose` (Postgres + Redis) — não existe hoje (só 2 Dockerfiles soltos).
- OTP → Redis (dado efêmero).

---

## PARTE B — Serviços novos (green-field, criar do zero, espelhando `lead`/`enrollment`)

Ordem por dependência:
1. **hub** — polo (endereço + marca + coordenador); base de todos os papéis.
2. **staff** — boss da operação (cadastra hub, define coordenador).
3. **coordinator** — admin do polo (aprova training, taxas, aplica/corrige prova, envia docs).
4. **promoter** — ex-candidato aprovado; landing `/ref=external_id` p/ captar lead.
5. **training** — LMS (matérias, correção por IA via app `ai`); candidate → promoter.
6. **student** — fluxo do aluno (docs, prova, diploma, veterano); enrollment → student. *(o maior)*
7. **fees** — taxas de matrícula via `asaas`.
8. **commissions** — paga promotores/coordenadores; `worker_loop` asyncio espelhando `asaas`, idempotente; job sexta 18h America/Sao_Paulo.

Cada serviço novo segue seu `<app>/TODO` (spec), §11 (notify nos status), §12/§13 (IA via `ai`), §14 (simplicidade).

---

## Execução
Incremental — fase a fase (Parte A) / serviço a serviço (Parte B), com checkpoint. Início sugerido: **Fase 1 — `otp` (segredo)** em sessão nova.
