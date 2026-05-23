# Plano — Backend supletivo

> Base: `wiki/<app>.md` (14 apps mapeados, 2026-05-23). Convenção: `../CONVENTION.md`.
> **Duas frentes distintas:** A) ADEQUAR os 14 apps existentes · B) CRIAR 8 serviços novos.
> Nota: `wiki/` é documentação (fonte de verdade §15), **não** um microsserviço.

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

### Fase 4 — Conformidade transversal
- PK → UUID (§4): address, documents, enrollment, infinitepay, notify, otp.
- logging cru → structlog (§2): asaas, auth, infinitepay, roles.
- `niquests` → `httpx` (§2): auth.
- I/O síncrono → async: ai (OCR), infinitepay (httpx.Client), lead (time.sleep), asaas.
- Dedup identidade: remover tabela `auth.user_roles` (roles é dono); CPF duplicado (auth delega a profiles); remover `_validate_entry_role`; rever `/atomic` (§6).
- IA central no `ai`: finalizar migração órfã do `notify`; remover toda IA do `infinitepay`; gap `/image/vision` (prompt+language) no `ai`.
- `roles`: lista de papéis → `.env`; regras de transição no DB.

### Fase 5 — Testes + wiki
- Cobertura de comportamento por app; `ruff` limpo; atualizar `wiki/<app>.md`.

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
