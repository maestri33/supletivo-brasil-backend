# auth

## Função

Fonte de verdade de identidade da plataforma: registra usuários (CPF + phone), valida unicidade, emite OTP e coordena provisionamento de perfil, role, contato e JWT. Não guarda senha — autenticação é delegada a OTP e JWT externos.

---

## Status

**Parcial.**

- Endpoints de `register`, `check`, `recover` e `login` implementados e funcionais.
- Migrações Alembic existem (7 arquivos) e cobrem o schema atual (`users`, `user_roles`, `refresh_tokens` — embora `refresh_tokens` apareça em migração mas **não** no model Python atual).
- Testes presentes para `recover` (9 casos) e `test_role_logic` (14 casos); **ausentes** para `register`, `login`, `check`, `atomic` e `log`.
- `schemas/` e `services/` **não existem** — validação inline nas rotas e lógica de negócio misturada em `api/*.py`.
- TODO do serviço: provisionamento automático na criação cobre Profile, Contato, **Documentos** e **Endereço** (get-or-create, best-effort §12). Email deferido — unicidade fica a jusante.

---

## Estrutura

**Achatada — conforme convenção** (`auth/app/`; flatten do aninhamento `auth/auth/app/` feito em 2026-05-23, ver `PLANO_ADEQUACAO`).

```
auth/          ← raiz do repositório = pasta do serviço
├── app/
│   ├── main.py · config.py · db.py · exceptions.py
│   ├── api/        atomic.py · check.py · deps.py · log.py · login.py · recover.py · register.py · router.py
│   ├── models/     user.py  (User + UserRole)
│   ├── integrations/  jwt.py · notify.py · otp.py · profiles.py · roles.py
│   ├── utils/      logging.py · validation.py
│   └── config/     systemd/auth.service  ← pasta colide com config.py (ver §Pendências)
├── alembic/ + alembic.ini
├── tests/
├── pyproject.toml
└── TODO
```

Ausentes conforme convenção: `schemas/`, `services/`.

---

## Endpoints

### `api/check.py` — prefixo `/api/v1/check`

| Método | Rota | Descrição | Tipo |
|--------|------|-----------|------|
| POST | `/api/v1/check` | Verifica CPF, phone ou external_id; dispara OTP em background se encontrado; rate-limit via Redis | Público |

### `api/login.py` — prefixo `/api/v1/login`

| Método | Rota | Descrição | Tipo |
|--------|------|-----------|------|
| POST | `/api/v1/login` | Valida role, verifica OTP, emite JWT (access + refresh) | Público |

### `api/recover.py` — prefixo `/api/v1/recover`

| Método | Rota | Descrição | Tipo |
|--------|------|-----------|------|
| POST | `/api/v1/recover` | Recupera `external_id` por CPF ou phone e dispara OTP; rate-limit via Redis | Público |

### `api/register.py` — prefixo `/api/v1/register`

| Método | Rota | Descrição | Tipo |
|--------|------|-----------|------|
| POST | `/api/v1/register` | Valida CPF e phone (unicidade + formato), cria `User`, provisiona roles/perfil/contato/OTP em background | Público |

### `api/atomic.py` — prefixo `/api/v1/atomic`

| Método | Rota | Descrição | Tipo |
|--------|------|-----------|------|
| POST | `/api/v1/atomic` | Gera token de limpeza total do ecossistema (TTL 60s, requer Redis) | Desmilitarizado |
| DELETE | `/api/v1/atomic/{atomic_id}` | Confirma token e apaga dados de auth + profiles + roles + notify + lead | Desmilitarizado |

### `api/log.py` — prefixo `/api/v1/log`

| Método | Rota | Descrição | Tipo |
|--------|------|-----------|------|
| GET | `/api/v1/log` | Consulta logs de chamadas armazenados no Redis (filtros: direction, service, method, status) | Desmilitarizado |
| DELETE | `/api/v1/log` | Limpa todos os logs do Redis | Desmilitarizado |

### `main.py` — raiz

| Método | Rota | Descrição | Tipo |
|--------|------|-----------|------|
| GET | `/health` | Liveness check | Desmilitarizado |
| GET | `/ready` | Readiness check | Desmilitarizado |

---

## Dados

**Schema Postgres:** `auth`

### `users`
| Coluna | Tipo | Restrições |
|--------|------|-----------|
| `id` | UUID | PK |
| `external_id` | UUID | UNIQUE NOT NULL — referência cross-service |
| `created_at` | TIMESTAMPTZ | default now() |

### `user_roles`
| Coluna | Tipo | Restrições |
|--------|------|-----------|
| `id` | UUID | PK |
| `user_id` | UUID | FK → `users.external_id` ON DELETE CASCADE |
| `role` | VARCHAR | NOT NULL |
| `assigned_at` | TIMESTAMPTZ | default now() |
| `revoked_at` | TIMESTAMPTZ | nullable |

### `refresh_tokens` (migração existe, model Python ausente)
Criada em migração `2026-05-01_add_refresh_tokens_table.py`; sem representação ORM no código atual — inconsistência.

**Sem shadow tables** declaradas neste serviço (auth é o origem, outros serviços usam shadow de `auth.users`).

---

## Integrações

### Internas

> Clients legados (profiles, notify, roles, otp, jwt) usam `niquests` (desvio de §2, migração pendente). Clients novos (documents, address) já usam `httpx`.

| Client | Arquivo | Operações | Lib |
|--------|---------|-----------|-----|
| `ProfilesClient` | `integrations/profiles.py` | `check_cpf`, `create`, `get_one`, `patch_field` | niquests |
| `NotifyClient` | `integrations/notify.py` | `check_contact`, `get_contact`, `create_contact` | niquests |
| `RolesClient` | `integrations/roles.py` | `get_roles`, `is_blocked`, `assign`, `promote`, `get_rule` | niquests |
| `OTPClient` | `integrations/otp.py` | `create`, `check` | niquests |
| `JWTClient` | `integrations/jwt.py` | `issue`, `refresh`, `get_jwks` | niquests |
| `DocumentsClient` | `integrations/documents.py` | `ensure` (GET get-or-create) | httpx |
| `AddressClient` | `integrations/address.py` | `ensure` (GET get-or-create polimórfico) | httpx |

### Externas
Nenhuma integração com APIs externas de terceiros — todos os clientes apontam para serviços internos da plataforma.

### Redis
Usado para rate-limit de OTP (`otp:ratelimit:{external_id}`) e armazenamento de logs de acesso (`logs:all`). Opcional — degradação silenciosa se ausente.

---

## Pendências

### TODO do serviço (`auth/TODO`)
> Ao ser criado, o usuário deve provisionar automaticamente:
> - Profile + tabelas auxiliares
> - Documentos + auxiliares
> - Contato (notify)
> - Endereço
> (todos com null inicialmente)
>
> JAMAIS pode haver dois usuários com CPF, PHONE ou EMAIL iguais ou falsos.

O provisionamento em `register._provision()` cobre `roles`, `profiles`, `notify.create_contact`, **`documents.ensure`** (get-or-create) e **`address.ensure`** (get-or-create polimórfico na tabela `entity_addresses`) — todos best-effort (§12: falha de um passo é logada e não impede os demais). **Email permanece deferido:** não é coletado no `register`; a unicidade fica a cargo dos serviços a jusante quando o email for preenchido. Endereço usa o contrato polimórfico (`GET /api/v1/entities/{entity_type}/{external_id}`) até `address` expor o `POST /webhook/external_id/` tipado.

### Desvios da CONVENTION

| Gravidade | Desvio |
|-----------|--------|
| ❌ | **`niquests`** usado em todos os clients e em `atomic.py`/`register.py` — lib proibida; a convenção exige `httpx` (CONVENTION §2) |
| ❌ | **`import logging`** (stdlib) em `integrations/*.py` — proibido; usar `structlog` (CONVENTION §2) |
| ❌ | **`fastapi_structured_logging`** em `main.py` — lib fora da stack canônica; a convenção exige `structlog` diretamente |
| ⚠️ | **`schemas/` ausente** — schemas Pydantic inline nas rotas (`LoginRequest`, `RegisterRequest`, etc.) em vez de pasta dedicada (CONVENTION §3) |
| ⚠️ | **`services/` ausente** — lógica de negócio (validação, provisionamento) acoplada nos arquivos de `api/` (CONVENTION §3) |
| ⚠️ | **`refresh_tokens`** existe na migração mas não tem model ORM — inconsistência entre schema e código |
| ⚠️ | **`init_db()`** em `db.py` usa `Base.metadata.create_all` — proibido em produção (CONVENTION §4) |
| ⚠️ | Testes cobrem apenas `recover` e lógica de roles; `register`, `login`, `check`, `atomic` e `log` sem cobertura |
| ⚠️ | Config duplicada: `app/config.py` e pasta `app/config/` (contém `systemd/auth.service`) — risco de confusão, pasta deveria ser renomeada |
