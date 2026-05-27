# profiles

## Função
Gerencia perfis de usuário (dados pessoais, nascimento e escolaridade), vinculados 1-para-1 a `auth.users` via `external_id`. Enriquecimento automático via CPFHub.io na criação.

## Status
- **Endpoints:** completos (CRUD + busca CPF + first-name).
- **Migrações:** 3 revisões (0001 schema inicial, 0002 índices de busca, 0003 trigger `updated_at`). Sem pendências de migração.
- **Testes:** existem (`tests/test_profiles.py`, `test_health.py`, `test_*_validation.py`, `tests/integrations/test_cpfhub.py`); cobertura não auditada.

## Estrutura
**Conforme a convenção:** pacote em `profiles/app/` (achatado na Fase 2; o antigo aninhamento `profiles/profiles/app/` não existe mais). Possui `README.md` e `.claude/` (CLAUDE.md + memory) próprios.

## Endpoints
**Arquivo:** `app/api/profiles.py` — todos internos/desmilitarizados (sem autenticação explícita no router).

| Método | Rota | Descrição |
|---|---|---|
| POST | `/api/v1/profiles` | Cria perfil; dispara enriquecimento CPFHub pós-save. |
| GET | `/api/v1/profiles` | Lista com paginação (`limit`/`offset`) e filtros prefix (`q`, `cpf`). |
| GET | `/api/v1/profiles/{external_id}` | Retorna perfil completo com birth_info e educational. |
| GET | `/api/v1/profiles/cpf/{cpf}` | Verifica existência e validade de CPF. |
| GET | `/api/v1/profiles/first-name/{external_id}` | Retorna primeiro nome e nome completo. |
| PATCH | `/api/v1/profiles/{external_id}` | Atualização parcial (profile + birth_info + educational). |
| DELETE | `/api/v1/profiles/{external_id}` | Remove perfil (cascade apaga birth_info e educational). |

**Arquivo:** `app/api/health.py` — público.

| Método | Rota | Descrição |
|---|---|---|
| GET | `/health` | Healthcheck. |

## Dados
**Schema Postgres:** `profiles`

| Tabela | PK | FKs e Uniques | Campos-chave |
|---|---|---|---|
| `profiles.profiles` | `id` (serial) | `external_id` UNIQUE → `auth.users.external_id` (RESTRICT); `cpf` UNIQUE | `cpf` String(11), `name`, `gender`, `civil_status`, `description`, `created_at`, `updated_at` |
| `profiles.birth_info` | `id` (serial) | `profile_id` UNIQUE → `profiles.profiles.id` (CASCADE) | `state` String(2), `city`, `birth_date` |
| `profiles.educational` | `id` (serial) | `profile_id` UNIQUE → `profiles.profiles.id` (CASCADE) | `level`, `elementary_completed`, `elementary_year`, `high_school_completed` |

**Shadow table:** `auth.users` (coluna `external_id` apenas) — declarada em `db.py` para o SQLAlchemy resolver a FK cross-schema.

**Índices extras (0002):** `profiles_name_lower_idx` (btree em `lower(name)`), `profiles_created_at_idx`.

## Integrações
- **CPFHub.io** (externa, `app/integrations/cpfhub.py`): lookup de identidade por CPF via `GET /cpf/{cpf}` com header `x-api-key`. Retry automático em status transientes (429/5xx), 3 tentativas, backoff 0.2s/0.8s. Desabilitada quando `cpfhub_api_key` está vazio. Retorna `CPFHubIdentity` (name, gender, birth_date) — best-effort, falhas silenciosas.
- Sem integrações internas httpx com outros microsserviços.

## Conformidade (§15 — adequado em 2026-05-24)
**TODO no código:** nenhum `TODO`/`FIXME`/`HACK` em `app/` (e não há arquivo
`TODO`-spec — a spec é esta wiki). §15.1 ✅.

**Desvios resolvidos:**
1. ✅ **Aninhamento** — pacote achatado para `profiles/app/` (Fase 2).
2. ✅ **Segurança** — `database_url` deixou de ter default hardcoded
   (`v7m:v7m`); agora **obrigatório** via `.env` (espelha a Fase 1 do `otp`);
   `.env.example` com placeholder.
3. ✅ **`import re`** movido para o topo de `profile_service.py` (e `or_` sem
   uso removido).
4. ✅ **`updated_at`** — trigger `profiles.set_updated_at()` + `BEFORE UPDATE`
   em `profiles.profiles` (migração `0003`); cobre UPDATE por SQL direto.
5. ✅ **`README.md`** criado (§3).
6. ✅ **`.claude/`** criado (CLAUDE.md + memory/{architecture,conventions,integrations}).
7. ✅ **`alembic/env.py`** passou a criar o schema (`CREATE SCHEMA IF NOT EXISTS`).
8. ✅ **Makefile** corrigido — alvos do template Tortoise (`aerich`, `mypy`)
   trocados por `alembic`/`ruff`.

**Decisão registrada (não é desvio):**
- **CPF "duplicado" com `auth`:** profiles é o **dono** da identidade/CPF;
  `auth` delega a profiles (PLANO Fase 4). O `validators/cpf.py` **fica** aqui.
