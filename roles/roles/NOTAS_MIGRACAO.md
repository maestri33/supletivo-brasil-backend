# Sincronização do serviço `roles` com a fonte de verdade

**Fonte de verdade:** `root@10.1.30.20:/opt/v7m/services/roles/`
**Código local:** `/home/maestri33/backend/roles/roles/`
**Data:** 2026-05-22

O código local estava **desatualizado**. Esta nota documenta as diferenças encontradas,
as alterações aplicadas para deixar o local coeso com o remoto, e o resultado do teste
end-to-end com Postgres real (sem mock).

---

## 1. Diferença global / arquitetural

O remoto sofreu uma **migração completa de ORM e de banco**:

| Aspecto              | Local (antigo)                          | Remoto (fonte de verdade)                              |
|----------------------|------------------------------------------|--------------------------------------------------------|
| ORM                  | TortoiseORM 1.1.7                        | SQLAlchemy 2 (async)                                    |
| Banco                | SQLite (`aiosqlite`)                     | PostgreSQL (`asyncpg`)                                  |
| Schema do banco      | sem schema (SQLite)                      | schema `roles` no Postgres central `v7m`               |
| Migrations           | `generate_schemas=True` (auto)          | Alembic (`alembic upgrade head`)                       |
| `external_id`        | `CharField(max_length=36)` (string)     | `UUID` com FK cross-schema → `auth.users.external_id`  |
| Sessão de banco      | escopo de módulo (Tortoise)             | `AsyncSession` injetada via `Depends(get_session)`     |
| Seed de regras       | inexistente                             | seed automático no `lifespan` (7 regras)               |
| Porta                | 80                                       | 8000                                                   |
| Empacotamento        | sem build-system                        | `hatchling` + Dockerfile + healthcheck                 |
| Versão               | 0.1.0                                    | 0.2.0                                                  |

Resumo: deixou de ser um microserviço SQLite isolado e passou a ser um serviço do
**pipeline v7m**, compartilhando o Postgres central e referenciando `auth.users` por
foreign key entre schemas.

---

## 2. Arquivos novos (só existiam no remoto)

- `Dockerfile` — imagem `python:3.12-slim` + `uv`, usuário não-root, `HEALTHCHECK` em
  `/health`, e `CMD` que roda `alembic upgrade head` antes do `uvicorn`.
- `alembic.ini` — config do Alembic (`file_template` com data, logging).
- `alembic/env.py` — env assíncrono; cria a version table no schema `roles`
  (`version_table_schema`), filtra objetos por schema via `include_object`.
- `alembic/script.py.mako` — template padrão de migration.
- `alembic/versions/2026-05-15_initial_roles_schema.py` — migration `0001`:
  cria `roles.role_rules` e `roles.user_roles` (com FK → `auth.users.external_id`,
  `ondelete=RESTRICT`, `onupdate=CASCADE`) e índice em `external_id`.

## 3. Arquivos alterados (atualizados para a versão remota)

- `app/config.py` — `SettingsConfigDict` lendo `.env`; `DATABASE_URL` agora Postgres;
  novo `DATABASE_SCHEMA="roles"`; `PORT` 80 → 8000.
- `app/db.py` — reescrito de TortoiseORM para SQLAlchemy 2: `Base`/`metadata` com
  `naming_convention` e schema; tabela espelho `auth.users` para resolver a FK
  cross-schema; `engine` async + `async_session_maker`; dependency `get_session()`.
- `app/main.py` — `lifespan` agora roda seed (`_seed_if_empty`, 7 regras) e dá
  `engine.dispose()` no shutdown; `/` reescrito com `select`/`func.count`; removido o
  bloco `database` do payload de `/`; novos endpoints `/ready` e `/status`.
- `app/models/role_rule.py` — `Model` Tortoise → `Base` SQLAlchemy 2 (`mapped_column`,
  `PG_UUID`, `default=uuid.uuid4`).
- `app/models/user_role.py` — idem; `external_id` virou `UUID` com `ForeignKey`
  `auth.users.external_id`; `assigned_at` com `server_default=func.now()`.
- `app/services/role_service.py` — toda a lógica reescrita para SQLAlchemy async;
  todas as funções agora recebem `session: AsyncSession` e `external_id: UUID`;
  usa `select`/`delete`/`scalar`/`scalars`/`commit` no lugar das queries Tortoise.
- `app/api/config.py` — endpoints recebem `session = Depends(get_session)` e repassam
  ao service; `rule_id` repassado como `UUID` (sem `str(...)`).
- `app/api/role.py` — `external_id` agora `UUID` nos path params; `Depends(get_session)`;
  respostas convertem UUID para `str`.
- `app/api/users.py` — idem (`UUID` + `Depends(get_session)`).
- `pyproject.toml` — versão 0.2.0; build-system `hatchling`; troca de deps
  (remove `tortoise-orm`/`aiosqlite`, adiciona `sqlalchemy[asyncio]`/`asyncpg`/`alembic`);
  grupo `dev` (pytest, ruff) e config de `ruff`/`pytest`.

## 4. Arquivos idênticos (sem alteração)

`app/__init__.py`, `app/api/__init__.py`, `app/api/router.py`, `app/exceptions.py`,
`app/models/__init__.py`, `app/schemas/__init__.py`, `app/schemas/role_rule.py`,
`app/schemas/user_role.py`, `app/services/__init__.py`, `.gitignore`.

## 5. Arquivos só locais (preservados — não existem no remoto)

- `.env` — config local (estava com SQLite/porta 80; **atualizado** para Postgres/8000
  para ficar coeso com o novo código).
- `roles.service` — unit systemd local.
- `uv.lock` — lockfile (estava com deps Tortoise; **regenerado** para as novas deps).
- `data/roles.db*` — banco SQLite antigo, agora obsoleto (mantido, não removido).

---

## 6. Teste end-to-end (sem mock, dados reais)

**Ambiente:** container Postgres 16 dedicado e isolado (`roles-e2e-pg`, `localhost:5547`,
base `v7m`), criado só para o teste — a infra compartilhada (`asaas-e2e-pg`) **não** foi
tocada. Pré-requisitos reais criados: schema `auth` + `auth.users` (3 UUIDs reais) e
schema `roles`. Migration aplicada com `alembic upgrade head` (revisão `0001`). Serviço
subido com `uvicorn` real e exercitado via HTTP real (`curl`).

**Resultado: 26/26 verificações OK.**

Cobertura:
- Ciclo de vida U1: `lead` → (promoção) `enrollment` → (promoção) `student` + `veteran`
  (add). Persistência confirmada no banco: `lead` e `enrollment` ficam com `revoked_at`
  preenchido; `student` e `veteran` ativas (replace revoga, add acumula).
- Ciclo de vida U2: `candidate` → (promoção) `promoter` + `coordinator` (requires promoter).
- Erros de domínio reais: atribuir role de promoção direto (422 `INVALID_ROLE_ASSIGNMENT`),
  `requires_role` ausente (422), role duplicada (422), promoção sem `from_role` (422),
  regra inexistente (404 `ROLE_NOT_FOUND`).
- **FK cross-schema validada:** atribuir role a um `external_id` ausente em `auth.users`
  é rejeitado pelo banco (`ForeignKeyViolationError` em `user_roles_external_id_fkey`).
- CRUD de regras: create (201) → get (200) → patch (200) → delete (204) → get (404).
- Listagem (`/role`, `/users`), remoção de usuário (deleta 3 linhas, inclui revogadas) e
  `health`/`ready`/`status` (200).
- Seed automático do `lifespan` confirmado: 7 regras (4 add, 3 replace).

### Observação (comportamento idêntico à fonte de verdade)
Atribuir a um `external_id` inexistente em `auth.users` retorna **HTTP 500** (a
`IntegrityError` da FK não é capturada). Isso é **fiel ao código remoto** (a fonte de
verdade também não trata esse caso) — não é regressão. Melhoria futura possível: capturar
`IntegrityError` e responder 404/422.

### Reproduzir o teste
```bash
cd /home/maestri33/backend/roles/roles
docker run -d --name roles-e2e-pg -e POSTGRES_USER=v7m -e POSTGRES_PASSWORD=v7m \
  -e POSTGRES_DB=v7m -p 5547:5432 postgres:16-alpine
# criar schemas auth/roles + auth.users (UUIDs reais), depois:
DATABASE_URL="postgresql+asyncpg://v7m:v7m@localhost:5547/v7m" uv run alembic upgrade head
DATABASE_URL="postgresql+asyncpg://v7m:v7m@localhost:5547/v7m" \
  uv run uvicorn app.main:app --host 127.0.0.1 --port 8099
```
