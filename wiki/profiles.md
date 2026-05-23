# profiles

## Função
Gerencia perfis de usuário (dados pessoais, nascimento e escolaridade), vinculados 1-para-1 a `auth.users` via `external_id`. Enriquecimento automático via CPFHub.io na criação.

## Status
- **Endpoints:** completos (CRUD + busca CPF + first-name).
- **Migrações:** 2 revisões aplicadas (0001 schema inicial, 0002 índices de busca). Sem pendências de migração.
- **Testes:** existem (`tests/test_profiles.py`, `test_health.py`, `test_*_validation.py`, `tests/integrations/test_cpfhub.py`); cobertura não auditada.

## Estrutura
**Aninhada (desvio da convenção):** `profiles/profiles/app/` em vez do canônico `profiles/app/`. O diretório raiz `profiles/` contém apenas um subdiretório `profiles/` com o pacote real.

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

## Pendências
**TODO no código:**
- Nenhum `TODO`/`FIXME`/`HACK` encontrado nos arquivos `app/`.

**Desvios da CONVENTION:**
1. **Aninhamento incorreto:** pacote em `profiles/profiles/app/` em vez de `profiles/app/` — viola a regra "sem aninhamento de nome".
2. **Validação de CPF duplicada com auth:** `app/validators/cpf.py` valida CPF localmente; o serviço `auth` provavelmente faz a mesma validação — risco de divergência de regras.
3. **`import re` dentro de função** (`list_profiles`): deve ser movido para o topo do arquivo.
4. **`updated_at` sem trigger no banco:** definido com `onupdate=func.now()` no ORM mas sem `trigger` ou `DEFAULT` equivalente na migração — atualizações diretas no Postgres não atualizam o campo.
5. **Sem `README.md` no serviço** — exigido pela convenção (`§3`).
6. **Sem `CLAUDE.md`** — exigido pela convenção para particularidades do serviço.
