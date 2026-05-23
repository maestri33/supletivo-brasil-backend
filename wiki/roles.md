# roles

## Função

Motor de regras de transição de papéis (roles) de usuários no pipeline v7m.
Mantém o catálogo de regras (`role_rules`) e o histórico de atribuições (`user_roles`), aplicando políticas de `add`/`replace`, pré-requisitos e incompatibilidades.

---

## Status

**Parcial.**

- Endpoints de leitura, atribuição, promoção e CRUD de regras implementados e funcionais.
- 1 migração Alembic presente (rev `0001`, 2026-05-15) cobrindo as duas tabelas.
- **Sem testes** — diretório `tests/` inexistente; pytest está no `dev` group mas nunca executado.
- `structlog` ausente (usa `logging` cru — violação da stack canônica).
- `httpx` declarado nas dependências da convenção mas não instalado nem usado (sem integrações implementadas).
- SEEDS de regras hardcoded em `main.py` (pendência registrada no TODO).

---

## Estrutura

**Aninhada — desvio da convenção.**

```
roles/          ← raiz do serviço (esperado: pacote aqui)
└── roles/      ← aninhamento indevido (roles/roles/app em vez de roles/app)
    ├── app/
    │   ├── main.py · config.py · db.py · exceptions.py
    │   ├── api/        role.py · role_rules.py · users.py · router.py
    │   ├── models/     role_rule.py · user_role.py
    │   ├── schemas/    role_rule.py · user_role.py · __init__.py (CustomModel)
    │   └── services/   role_service.py
    ├── alembic/
    ├── pyproject.toml
    ├── TODO
    └── data/roles.db*   ← arquivos SQLite órfãos (não usados; Postgres é o banco real)
```

`pyproject.toml` aponta `packages = ["app"]` (correto internamente), mas o diretório raiz duplicado (`roles/roles/`) viola `§3` da convenção.

---

## Endpoints

Todos os endpoints são **desmilitarizados** (sem autenticação JWT — chamados internamente pela plataforma).

### `api/role.py` — prefixo `/api/v1/role`

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/v1/role` | Lista todos os usuários com roles ativas |
| GET | `/api/v1/role/{external_id}` | Retorna roles ativas de um usuário |
| GET | `/api/v1/role/{external_id}/blocked` | Verifica se o usuário está em role bloqueante |
| POST | `/api/v1/role/{external_id}/{role}` | Atribui role direta (modo `add`) a um usuário |
| POST | `/api/v1/role/{external_id}/up/{to_role}` | Promove usuário para nova role (modo `replace`, revoga a anterior) |
| DELETE | `/api/v1/role/{external_id}` | Remove todas as atribuições de um usuário |

### `api/role_rules.py` — prefixo `/api/v1/config/roles`

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/v1/config/roles` | Lista todas as regras de transição |
| GET | `/api/v1/config/roles/{rule_id}` | Detalhe de uma regra |
| POST | `/api/v1/config/roles` | Cria nova regra de transição |
| PATCH | `/api/v1/config/roles/{rule_id}` | Atualiza regra existente |
| DELETE | `/api/v1/config/roles/{rule_id}` | Remove regra |

### `api/users.py` — prefixo `/api/v1/users`

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/v1/users` | Lista usuários com roles ativas (duplica `GET /api/v1/role`) |
| DELETE | `/api/v1/users/{external_id}` | Remove todas as atribuições de um usuário (duplica `DELETE /api/v1/role/{external_id}`) |

### `main.py` — sem prefixo

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/` | Dashboard: contagem de regras, usuários e distribuição de roles |
| GET | `/health` | Health check simples |
| GET | `/ready` | Readiness check |
| GET | `/status` | Status com uptime em segundos |

---

## Dados

**Schema Postgres:** `roles`

### Tabela `roles.role_rules`

| Coluna | Tipo | Restrições | Descrição |
|--------|------|-----------|-----------|
| `id` | UUID | PK, `gen_random_uuid()` | Identificador da regra |
| `from_role` | VARCHAR(64) | nullable | Role de origem (`null` = atribuição direta) |
| `to_role` | VARCHAR(64) | NOT NULL | Role de destino |
| `mode` | VARCHAR(16) | NOT NULL | `add` (acumula) ou `replace` (revoga origem) |
| `requires_role` | VARCHAR(64) | nullable | Pré-requisito: role que o usuário deve ter |
| `forbids_role` | VARCHAR(64) | nullable | Incompatibilidade: role que bloqueia a transição |
| `blocking` | BOOLEAN | NOT NULL, default `false` | Se `true`, usuário nessa role é considerado "bloqueado" |

**Catálogo seed (hardcoded em `main.py`):**

| from_role | to_role | mode | requires_role |
|-----------|---------|------|---------------|
| null | lead | add | — |
| lead | enrollment | replace | — |
| enrollment | student | replace | — |
| null | veteran | add | student |
| null | candidate | add | — |
| candidate | promoter | replace | — |
| null | coordinator | add | promoter |

### Tabela `roles.user_roles`

| Coluna | Tipo | Restrições | Descrição |
|--------|------|-----------|-----------|
| `id` | UUID | PK, `gen_random_uuid()` | Identificador do registro |
| `external_id` | UUID | NOT NULL, FK → `auth.users.external_id`, INDEX | Referência cross-schema ao usuário |
| `role` | VARCHAR(64) | NOT NULL | Nome da role atribuída |
| `assigned_at` | TIMESTAMPTZ | NOT NULL, default `now()` | Data/hora de atribuição |
| `revoked_at` | TIMESTAMPTZ | nullable | Preenchido na promoção; `null` = role ativa |

**Soft-delete por `revoked_at`** — histórico preservado, roles ativas filtradas por `revoked_at IS NULL`.

**Shadow table** (`db.py`): `auth.users` declarada localmente com apenas `external_id` (PK) para resolver a FK cross-schema sem importar modelos do serviço `auth`.

**Dados locais indevidos:** `data/roles.db`, `roles.db-shm`, `roles.db-wal` — arquivos SQLite presentes no repositório, não usados pelo serviço (banco real é Postgres).

---

## Integrações

**Internas:** nenhuma — o serviço não chama outros microsserviços via `httpx`.

**Externas:** nenhuma.

**Ausências notáveis:**
- Nenhuma integração com o serviço `notify` (§11 da convenção exige notificações em mudanças de status/role).
- `httpx` não está instalado (não está em `pyproject.toml` como dependência direta).

---

## Pendências

### TODO do serviço (`TODO`)
> "Se houver como mudarmos as funções fixas para .env ao invés de DB eu fico grato"

Refere-se ao array `SEEDS` em `main.py` — as 7 regras de transição estão hardcoded e inseridas via seed no startup. A sugestão é movê-las para variável de ambiente (ou arquivo de configuração), eliminando a dependência de lógica de negócio no código-fonte.

### TODOs no código
Nenhum comentário `# TODO` encontrado no código-fonte.

### Desvios da convenção (`CONVENTION.md`)

| # | Desvio | Severidade |
|---|--------|-----------|
| 1 | **Aninhamento indevido** — pacote em `roles/roles/app` em vez de `roles/app` (§3) | Alta |
| 2 | **`logging` cru** em vez de `structlog` (`main.py` linha 4 e 20) — lib proibida (§2) | Alta |
| 3 | **Sem testes** — diretório `tests/` inexistente (§15 checklist) | Alta |
| 4 | **Duplicação de endpoints** — `GET /api/v1/users` e `DELETE /api/v1/users/{id}` repetem exatamente `role.py` (§10) | Média |
| 5 | **`structlog` ausente** do `pyproject.toml` — não está nem como dependência declarada | Alta |
| 6 | **Sem notificações** — mudanças de role não emitem eventos para `notify` (§11) | Média |
| 7 | **Arquivos SQLite** (`data/roles.db*`) presentes — dados locais indevidos no repositório (§9) | Baixa |
| 8 | **SEEDS hardcoded** em `main.py` — lógica de negócio/configuração misturada com bootstrap (TODO aberto) | Média |
| 9 | **`httpx` não declarado** em `pyproject.toml` — ausente como dependência mesmo sendo stack canônica | Baixa |
