# Roles — Adequação à Convenção + Regras no `.env`

> Serviço: `roles/` · Schema: `roles` · Convenção: `CONVENTION.md`
> Status desta SPEC: **DRAFT** — requisitos consolidados do PRD anterior + código existente + TODO. Aguardando review humano antes de implementação.

---

## 1. Contexto de Negócio

O serviço `roles` é o **motor de transição de papéis** do pipeline v7m. Ele gerencia o catálogo de regras de transição entre roles (candidate→promoter, lead→enrollment→student, student→veteran, etc) e mantém a associação de roles ativas para cada usuário (`external_id`).

Todo o ecossistema de autenticação e fluxos depende deste serviço:
- **`auth`** — consome `GET /api/v1/config/roles` (register.py) e `GET /api/v1/config/roles/{id}` (integrations/roles.py) para validar regras; usa `POST /api/v1/role/{ext_id}/{role}` para atribuir papéis em `atomic.py`.
- **`candidate`** — consome `GET /api/v1/role/{ext_id}` para ler papéis e `POST /api/v1/role/{ext_id}/up/{role}` para promover.

**Problema atual:** As 7 regras de transição estão **hardcoded** em `main.py` (array `SEEDS`, linhas 40-48), o serviço usa `logging` cru em vez de `structlog`, expõe endpoints duplicados (`users.py` replica `role.py`) e **não tem testes**. O custo: regra de negócio enterrada no código (não versionável por config), inconsistência com os demais serviços já adequados, e ausência de rede de segurança.

**Meta:** Adequar `roles` à `CONVENTION.md`, tornar as regras de transição configuráveis via `.env` (conforme pedido explícito no `roles/TODO`: *"Se houver como mudarmos as funcoes fixas para .env ao inves de DB eu fico grato"*), e cobrir com testes.

## 2. Atores

| Ator | Tipo | Ação |
|------|------|------|
| **`auth` (register)** | Serviço interno | Consulta `GET /api/v1/config/roles` para obter regras válidas ao registrar usuários |
| **`auth` (integrations/roles)** | Serviço interno | Consulta `GET /api/v1/config/roles/{id}` para obter regra específica via `get_rule` |
| **`auth` (atomic)** | Serviço interno | Atribui roles via `POST /api/v1/role/{ext_id}/{role}` e `POST /api/v1/role/{ext_id}/up/{role}` |
| **`candidate`** | Serviço interno | Consulta `GET /api/v1/role/{ext_id}` para ler papéis; promove via `POST .../up/promoter` |
| **`enrollment`** | Serviço interno | Promove `lead`→`student` via `POST /api/v1/role/{ext_id}/up/student` (planejado) |
| **Victor (operador/dev)** | Humano | Mantém o catálogo de regras de transição (atualmente editando código; futuro: `.env`) |

**Nota:** Todos os endpoints são **desmilitarizados** (internos, sem JWT). Nenhum endpoint é exposto a usuários finais.

## 3. Estados / Máquina de Estados

### Modos de Regra (RoleRule.mode — StrEnum)

```
add     → a role é ADICIONADA às roles ativas do usuário (não remove nenhuma)
replace → a role SUBSTITUI a from_role (revoga from_role, adiciona to_role)
```

| Modo | Comportamento | Exemplo |
|------|---------------|---------|
| `add` | Cria novo `UserRole` ativo sem revogar nenhum existente | `None→candidate`, `None→lead` |
| `replace` | Revoga `from_role` (seta `revoked_at`) e cria `to_role` | `lead→enrollment`, `candidate→promoter` |

### Pipeline de Transição (regras atuais — hardcoded em `SEEDS`)

```
None ──add──► candidate ──replace──► promoter
None ──add──► lead ──replace──► enrollment ──replace──► student
None ──add──► veteran  (requires_role: student)
None ──add──► coordinator (requires_role: promoter)
```

### Estado dos UserRole

```
ATIVO (revoked_at = NULL) ──[promote/replace]──► REVOGADO (revoked_at = timestamp) + NOVO ATIVO criado
ATIVO (revoked_at = NULL) ──[delete_user]──► HARD DELETE (todos os registros do external_id)
```

**Invariante:** Um usuário pode ter múltiplas roles ativas simultaneamente (ex: `student` + `veteran`). A revogação só acontece em transições `replace`.

## 4. Entidades & Campos

### Schema `roles`

#### `role_rules` — Catálogo de regras de transição

| Coluna | Tipo | Nullable | Default | Descrição |
|--------|------|----------|---------|-----------|
| `id` | `UUID` PK | NOT NULL | `uuid4()` | PK do agregado |
| `from_role` | `String(64)` | NULL | — | Role de origem (NULL = atribuição direta, sem pré-requisito de role ativa) |
| `to_role` | `String(64)` | NOT NULL | — | Role de destino |
| `mode` | `String(16)` | NOT NULL | — | `add` (soma) ou `replace` (substitui from_role) |
| `requires_role` | `String(64)` | NULL | — | Role que o usuário **deve ter ativa** para receber `to_role` (ex: `student` para `veteran`) |
| `forbids_role` | `String(64)` | NULL | — | Role que o usuário **não pode ter ativa** para receber `to_role` |
| `blocking` | `Boolean` | NOT NULL | `False` | Se `True`, ter esta role ativa bloqueia o usuário (checked por `is_blocked`) |

#### `user_roles` — Papéis ativos/revogados por usuário

| Coluna | Tipo | Nullable | Default | FK / Índice | Descrição |
|--------|------|----------|---------|-------------|-----------|
| `id` | `UUID` PK | NOT NULL | `uuid4()` | — | PK do registro |
| `external_id` | `UUID` | NOT NULL | — | FK → `auth.users.external_id` (RESTRICT/CASCADE), INDEX | UUID do usuário |
| `role` | `String(64)` | NOT NULL | — | — | Nome da role (ex: `candidate`, `promoter`) |
| `assigned_at` | `DateTime(tz)` | NOT NULL | `now()` | — | Timestamp de atribuição |
| `revoked_at` | `DateTime(tz)` | NULL | — | — | NULL = ativo; preenchido = revogado |

**Shadow table:** `auth.users` é declarada como shadow table em `db.py` para resolver FK cross-schema no SQLAlchemy.

## 5. Endpoints

### 5.1. GET `/` — Dashboard do serviço

| Campo | Valor |
|-------|-------|
| **Tipo** | Desmilitarizado |
| **Response** | Stats agregados: total de regras (add/replace/blocking), total de usuários com roles ativas, distribuição das top 10 roles, uptime |

### 5.2. GET `/health`, `/ready`, `/status` — Healthchecks

| Campo | Valor |
|-------|-------|
| **Tipo** | Desmilitarizado |
| **Response** | `{"status": "ok", "service": "roles"}` + uptime (no `/status`) |

### 5.3. CRUD de Regras — `/api/v1/config/roles`

| Método | Rota | Descrição | Status Pós-adequação |
|--------|------|-----------|---------------------|
| `GET` | `/api/v1/config/roles` | Lista todas as regras | **PERMANECE** (servido do `.env`) |
| `GET` | `/api/v1/config/roles/{rule_id}` | Obtém regra por ID | **PERMANECE** (servido do `.env`) |
| `POST` | `/api/v1/config/roles` | Cria regra | **REMOVE** (regras vêm do `.env`) |
| `PATCH` | `/api/v1/config/roles/{rule_id}` | Atualiza regra | **REMOVE** |
| `DELETE` | `/api/v1/config/roles/{rule_id}` | Deleta regra | **REMOVE** |

**Justificativa da remoção:** Com regras no `.env`, não faz sentido manter endpoints de escrita. A alteração de regras passa a ser deploy/config. Os endpoints GET permanecem para preservar contratos consumidos por `auth`.

### 5.4. Gestão de Roles por Usuário — `/api/v1/role`

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/api/v1/role` | Lista todos os usuários com roles ativas |
| `GET` | `/api/v1/role/{external_id}` | Roles ativas de um usuário |
| `GET` | `/api/v1/role/{external_id}/blocked` | Se o usuário está bloqueado (role com `blocking=True`) |
| `POST` | `/api/v1/role/{external_id}/{role}` | Atribui role (mode `add`) |
| `POST` | `/api/v1/role/{external_id}/up/{to_role}` | Promove role (mode `replace`) |
| `DELETE` | `/api/v1/role/{external_id}` | Hard-delete de todos os UserRole do usuário |

**Todos desmilitarizados (internos).**

### 5.5. Endpoints Duplicados — `/api/v1/users` (REMOVER)

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/api/v1/users` | **Duplicata** de `GET /api/v1/role` |
| `DELETE` | `/api/v1/users/{external_id}` | **Duplicata** de `DELETE /api/v1/role/{external_id}` |

**Ação:** Remover `users.py` do `router.py`. Endpoint canônico: `/api/v1/role`.

## 6. Integrações Externas

| Serviço | Tipo | Propósito | Direção |
|---------|------|-----------|---------|
| `auth` (DB) | FK cross-schema (`auth.users.external_id`) | Garantir integridade referencial — `UserRole.external_id` deve existir em `auth.users` | Roles→Auth (DB-level) |
| `auth` (HTTP) | Consumidor | `auth` chama endpoints de roles para register, atomic, integrations | Auth→Roles (HTTP) |
| `candidate` (HTTP) | Consumidor | `candidate` chama endpoints para ler roles e promover | Candidate→Roles (HTTP) |
| `enrollment` (HTTP, planejado) | Consumidor | `enrollment` chamará para promover `lead`→`student` | Enrollment→Roles (HTTP) |

**Nota:** `roles` **não faz** chamadas HTTP a outros serviços (não tem `httpx`). A dependência é via FK no banco e via HTTP inbound. Integração com `notify` está fora de escopo.

## 7. Eventos Disparados / Consumidos

### Consumidos

Nenhum. O serviço `roles` não consome eventos/webhooks. É puramente request/response.

### Disparados

Nenhum atualmente. O PRD original mencionava notificações `notify` como futuro, mas está **fora de escopo** deste PRD de adequação.

**Débito registrado:** Disparar eventos de mudança de role (ex: `role.assigned`, `role.promoted`) para consumo por `notify` ou outros serviços. Registrar no `wiki/roles.md`.

## 8. Regras de Negócio Invariantes

1. **`mode` é `add` ou `replace`** — Validação no endpoint POST (atual) e no parser do `.env` (futuro). Qualquer outro valor é rejeitado.

2. **Atribuição direta proibida para roles de promoção** — Se uma regra existe com `mode=replace` para um `to_role`, o endpoint `POST /role/{ext_id}/{role}` deve rejeitar com `INVALID_ROLE_ASSIGNMENT`, orientando a usar `/role/{ext_id}/up/{role}`.

3. **`requires_role` é verificado na atribuição** — Se a regra tem `requires_role`, o usuário **deve ter essa role ativa** no momento da atribuição/promoção. Ex: `veteran` exige `student` ativo.

4. **`forbids_role` é verificado** — Se a regra tem `forbids_role`, o usuário **não pode ter essa role ativa**. Ex: roles mutuamente exclusivas.

5. **`replace` revoga a role de origem** — Ao promover `from_role→to_role`, o `UserRole` da `from_role` recebe `revoked_at = now()` e um novo `UserRole` para `to_role` é criado na mesma transição.

6. **Usuário não pode ter role duplicada** — Tentativa de atribuir role já ativa retorna `INVALID_ROLE_ASSIGNMENT`.

7. **FK real para `auth.users`** — `external_id` em `user_roles` referencia `auth.users.external_id` com RESTRICT. Tentativa de atribuir role a `external_id` inexistente gera `IntegrityError` traduzido para `USER_NOT_FOUND`.

8. **`blocking` marca usuário como bloqueado** — `is_blocked()` verifica se qualquer role ativa do usuário pertence a uma regra com `blocking=True`. Usado por outros serviços (ex: `candidate`) para impedir ações.

9. **Regras no `.env` como fonte de verdade** — As 7 regras de transição devem ser configuráveis via variável de ambiente (ex: `ROLE_RULES=[{...}]`), parseadas por `pydantic-settings` no startup. Zero hardcode em `main.py`.

10. **Seed idempotente** — O `_seed_if_empty` atual verifica se já existem regras antes de inserir. Na versão `.env`, a seed deve ser substituída pela leitura do `.env` e upsert das regras (ou eliminação completa do seed se as regras viverem apenas em memória).

## 9. Critérios de Aceite

1. [ ] `SEEDS` array removido de `main.py` — zero regras hardcoded.
2. [ ] Regras de transição lidas do `.env` via `pydantic-settings` (ex: `ROLE_RULES=[{"from_role":null,"to_role":"lead","mode":"add"}, ...]`).
3. [ ] `GET /api/v1/config/roles` retorna as regras derivadas do `.env` (preserva contrato de `auth/register.py`).
4. [ ] `GET /api/v1/config/roles/{id}` continua funcionando (preserva contrato de `auth/integrations/roles.py`).
5. [ ] Endpoints de escrita de regras (`POST/PATCH/DELETE /api/v1/config/roles`) removidos.
6. [ ] `users.py` removido; `router.py` não inclui mais `users_router`.
7. [ ] `logging` cru substituído por `structlog` — `import logging` e `getLogger` ausentes de `app/`.
8. [ ] `structlog` adicionado ao `pyproject.toml`.
9. [ ] Suíte `pytest` cobrindo: atribuição (`assign_role`), promoção (`promote`), bloqueio (`is_blocked`), listagem, delete, tentativa de role duplicada, tentativa sem `requires_role`.
10. [ ] `ruff check` + `ruff format` limpos.
11. [ ] Contratos consumidos por `auth` e `candidate` preservados (GET de regras e de papéis seguem respondendo com mesma estrutura).
12. [ ] `.env` com JSON malformado no `ROLE_RULES` gera erro claro no startup (validação via `pydantic-settings`), não crash silencioso.

## 10. Riscos / Open Questions

### Riscos

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| Remover escrita de `/config/roles` quebra `auth` | Alta | Alto | Manter contratos **GET** (`/config/roles`, `/config/roles/{id}`); ajustes de escrita pertencem a PR coordenado no `auth` |
| Remover `/users` quebra `auth/atomic.py` | Alta | Alto | `atomic.py` deve apontar para `/role` no PR do `auth`; documentar no PRD |
| Perda da edição de regras em runtime | Média | Médio | Era o pedido explícito do TODO (`.env` como fonte); mudança de regra passa a ser deploy/config |
| `.env` com JSON malformado derruba o boot | Média | Médio | Validar/parsear via `pydantic-settings` com erro claro no startup; testar cenário em testes |
| Testes exigem Postgres (FK cross-schema) | Baixa | Baixo | Espelhar conftest async sqlite (`aiosqlite`) usado por asaas/infinitepay; shadow table funciona em sqlite |
| `requires_role`/`forbids_role`/`blocking` ausentes nos seeds atuais | Baixa | Baixo | Todos existem no schema; incluir exemplos no `.env` template para cobrir os 3 campos |

### Open Questions

- [ ] **Formato das regras no `.env`**: uma var com JSON (`ROLE_RULES=[{...}]`) vs múltiplas vars? Validar legibilidade vs parsing. Pydantic-settings suporta JSON em vars de ambiente nativamente.
- [ ] **Lista de papéis válidos**: também vai pro `.env` (ex: `VALID_ROLES=lead,candidate,promoter,...`) ou deriva das próprias regras?
- [ ] **Seed no DB vs memória**: as regras do `.env` devem ser **persistidas** no DB (upsert no startup, como o `_seed_if_empty` atual) ou servidas **direto da memória** sem tocar no DB? A segunda opção elimina a tabela `role_rules` como fonte, mas exige refatorar `role_service.py` que hoje lê do DB.
- [ ] **`blocking` e `forbids_role`** continuam expressos no `.env`? Hoje só `requires_role` aparece nos seeds; `forbids_role` e `blocking` existem no schema mas nenhum seed os usa. Incluir exemplos no template.
- [ ] **Compatibilidade com `auth`**: confirmar que `GET /config/roles/{id}` (com `{id}` sendo UUID da regra no DB) basta para `auth/integrations/roles.py:get_rule`. Se as regras saírem do DB, o `{id}` muda de significado — pode exigir ajuste no `auth`.
- [ ] **`data/*.db` locais**: limpar arquivos sqlite de desenvolvimento que estão como clutter local (não versionados, mas poluem o workspace).

---

*Status: DRAFT — requisitos consolidados do PRD anterior (76 linhas) + inspeção de código fonte (22 arquivos em `roles/app/`) + TODO. Aguardando review humano antes de implementação.*
