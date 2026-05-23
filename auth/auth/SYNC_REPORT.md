# Relatório de Sincronização — Auth Service

**Data:** 2026-05-22
**Fonte da verdade:** código externo em `root@10.1.30.20:/opt/v7m/services/auth/`
**Destino:** código local `/home/maestri33/backend/auth/auth/`
**Método:** cópia do externo via `scp` para `/tmp/auth-prod` (sem `rsync` — ausente no host remoto), seguida de `diff` recursivo e aplicação dos arquivos.

Após o sync, `diff -r` (excluindo `.env` e caches) entre local e externo retorna **EXIT 0 — coesão total**.

---

## 1. Visão geral das diferenças

| Categoria | Qtd | Arquivos |
|---|---|---|
| Modificados | 9 | `app/config.py`, `app/db.py`, `app/main.py`, `app/api/router.py`, `app/api/check.py`, `app/api/register.py`, `alembic/env.py`, `pyproject.toml`, `uv.lock` |
| Novos (só no externo) | 3 | `app/api/recover.py`, `tests/test_recover.py`, `Dockerfile` |
| Idênticos (sem ação) | — | integrações, models, `login.py`, `atomic.py`, `log.py`, `deps.py`, `exceptions.py`, utils, todas as migrações, `conftest.py`, `test_role_logic.py`, `Makefile`, `alembic.ini`, `.gitignore` |
| Local-only (preservado) | 1 | `.env` (não existe no externo — prod injeta env de outra forma) |

---

## 2. Detalhe das alterações aplicadas

### Modificados

1. **`app/config.py`** — `APP_VERSION` `"0.2.0"` → `"0.3.0"`.

2. **`app/db.py`** — `metadata = MetaData(..., schema=settings.DB_SCHEMA)` → `schema=settings.DB_SCHEMA or None`.
   Permite schema vazio (ex.: SQLite, que não tem schemas) virar `None` em vez de string vazia.

3. **`app/main.py`** — duas mudanças no `lifespan`:
   - Removido `from app.db import init_db` e a chamada `await init_db()`. O serviço **não cria mais tabelas no boot** — passa a depender exclusivamente do Alembic (o `Dockerfile` roda `alembic upgrade head` antes de subir).
   - Inicialização do Redis agora protegida por `if settings.REDIS_URL:` (com `else: app.state.redis = None`), permitindo rodar sem Redis configurado.

4. **`app/api/router.py`** — registra o novo router: `from app.api.recover import router as recover_router` + `api_router.include_router(recover_router, prefix="/api/v1")`.

5. **`app/api/check.py`** — função `_try_acquire_otp_slot` renomeada para `try_acquire_otp_slot` (tornada pública, pois `recover.py` a importa). 4 ocorrências atualizadas.

6. **`app/api/register.py`** — `await db.flush()` → `await db.commit()` ao criar o usuário.
   **Motivo (comentário do próprio código):** commitar antes de retornar evita race com serviços a jusante (ex.: *lead*) que tentam inserir FK→`auth.users` antes do commit do dependency-cleanup do FastAPI.

7. **`alembic/env.py`** — suporte explícito a schema:
   - `SCHEMA = settings.DB_SCHEMA or "auth"`
   - `include_schemas=True` e `version_table_schema=SCHEMA` nas configs *offline* e *online*.
   Garante que a tabela `alembic_version` e a introspecção fiquem no schema correto (`auth`).

8. **`pyproject.toml`** — adicionada dependência `aiosqlite>=0.20.0` (suporta o fallback SQLite do `DATABASE_URL` default).

9. **`uv.lock`** — ressincronizado: `+ aiosqlite 0.22.1`, bumps transitivos `idna 3.13→3.15`, `niquests 3.18.7→3.18.8`.

### Novos

10. **`app/api/recover.py`** — endpoint `POST /api/v1/recover`. Recuperação de `external_id` por `cpf` **ou** `phone` (nunca `external_id`), dispara OTP no canal conhecido. Semântica explícita de *recovery* com `otp_sent`/`otp_wait`, compartilhando rate-limit e lookups com `check.py`.

11. **`tests/test_recover.py`** — 9 testes do endpoint `/recover` (validação, not-found, happy-path, rate-limit). Usa `monkeypatch` nos lookups e um `FakeRedis` — não depende de DB nem de serviços externos.

12. **`Dockerfile`** — build multi-stage com `uv` (python:3.12-slim), usuário não-root, `HEALTHCHECK` em `/health`, e CMD `alembic upgrade head && uvicorn app.main:app ... --proxy-headers`.

### Ajuste local (fora do código, em `.env`)

- **`.env`** — `APP_VERSION` `0.2.0` → `0.3.0`, para o serviço local reportar a mesma versão da fonte da verdade (o `.env` sobrescreve o default do `config.py`). O `.env` não existe no externo e foi preservado quanto ao resto (URLs de serviços, credenciais).

---

## 3. Pendências pré-existentes (presentes em AMBOS os lados — fora do escopo do sync)

Não foram alteradas porque já são **idênticas** entre local e externo (não são defasagem; são dívida técnica da própria fonte da verdade):

- **`tests/test_role_logic.py` + `tests/conftest.py` — testes órfãos.** Importam `app.models.identity.Identity` (não existe mais; hoje é `app.models.user.User`) e exercitam endpoints de gestão de roles (`/api/v1/config/roles`, `/api/v1/role/{id}/up/{role}`) que pertencem ao **Roles Service**, não a este Auth Service. Resultado: **2 falhas + 15 erros** no `pytest`.
- **Tabelas sem ORM.** As migrações criam `role_rules` e `refresh_tokens` no schema `auth`, mas o ORM atual (`app/models/user.py`) só define `User` e `UserRole`. Resquício da época em que este código incluía role-management.

> Recomendação (não aplicada): remover/atualizar `test_role_logic.py` e `conftest.py`, e decidir o destino de `role_rules`/`refresh_tokens`. Como mexeria na fonte da verdade, ficou de fora deste sync.

---

## 4. Teste ponta a ponta (infra real, sem mock)

Ambiente montado localmente: **Postgres 16** + **Redis 7** em Docker (batendo com o `.env`: `localhost:5432`, `localhost:6379`), `uv sync`, migração e app reais.

| Verificação | Resultado |
|---|---|
| `alembic upgrade head` (Postgres real) | ✅ 7 migrações → head `c832fc1a6459`; tabelas em `auth.*` |
| Boot do app (sem `init_db`, confiando no Alembic) | ✅ startup limpo |
| `GET /health` | ✅ 200 `{"status":"ok","version":"0.3.0"}` |
| `GET /ready` | ✅ 200 |
| Rotas registradas (OpenAPI) | ✅ inclui `POST /api/v1/recover` (prova do sync do router) |
| `POST /recover` `{}` / cpf inválido / phone inválido | ✅ 422 `MISSING_FIELD` / `CPF_INVALID` / `PHONE_INVALID` |
| `POST /check` `{}` | ✅ 422 `MISSING_FIELD` |
| `POST /atomic` (Redis real) | ✅ 201 com token |
| `GET /log` (Redis real) | ✅ 200, entradas persistidas pelo middleware |
| `pytest tests/test_recover.py` | ✅ 9/9 |

### O que NÃO pôde ser testado aqui (e por quê)

Os fluxos completos `register` / `login` / `check`(encontrado) / `recover`(encontrado) dependem dos 6 serviços downstream (`profiles`, `otp`, `jwt`, `roles`, `notify`, `lead` em `10.10.10.x`). **Esses serviços estão inacessíveis a partir desta máquina** (`10.1.20.30`): há rota via `10.1.20.1`, mas as portas estão filtradas/fora (TCP recusado). Eles só respondem de dentro da rede de produção — o próprio host `10.1.30.20`, onde o auth roda de fato.

- A fiação foi **verificada como correta**: `POST /recover` com CPF válido chamou o caminho certo (`GET http://10.10.10.173/api/v1/profiles/cpf/...`) e retornou `niquests.exceptions.ConnectTimeout` real — comportamento esperado dado o downstream indisponível, **não** regressão do sync.
- **Observação de robustez (pré-existente):** em erro de *conexão* (não de status HTTP) o downstream não é capturado por `lookup_*` (que só tratam erros de status via `*Error`), então a request resulta em **HTTP 500** (`ConnectTimeout` não tratado). Esse comportamento é idêntico na fonte da verdade.

### Como reproduzir o ambiente e2e

```bash
docker run -d --name auth-e2e-pg -e POSTGRES_USER=auth -e POSTGRES_PASSWORD=auth_local -e POSTGRES_DB=auth -p 5432:5432 postgres:16-alpine
docker run -d --name auth-e2e-redis -p 6379:6379 redis:7-alpine
docker exec auth-e2e-pg psql -U auth -d auth -c 'CREATE EXTENSION IF NOT EXISTS "uuid-ossp"; CREATE SCHEMA IF NOT EXISTS auth;'
uv sync --extra dev
uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
# teardown: docker rm -f auth-e2e-pg auth-e2e-redis
```
