# Relatório de Sincronização — profiles

**Data:** 2026-05-22
**Fonte da verdade:** `root@10.1.30.20:/opt/v7m/services/profiles/` (remoto)
**Alvo:** `/home/maestri33/backend/profiles/profiles/` (local)

O código local estava desatualizado. Este relatório documenta (1) as diferenças
globais entre os dois códigos, (2) as alterações aplicadas no local para ficar
coeso com o remoto e (3) os testes de ponta a ponta executados com dados reais.

---

## 1. Resumo executivo

A diferença global é uma **migração completa de ORM e de stack de persistência**,
mais uma **nova integração externa**:

| Tema | Local (antes) | Remoto (fonte da verdade) |
|------|---------------|----------------------------|
| ORM | Tortoise ORM | **SQLAlchemy 2 (async)** |
| Banco | SQLite (`data/profiles.db`) | **PostgreSQL central (asyncpg)** |
| Migrations | Aerich (`migrations/`) | **Alembic (`alembic/`)** |
| `external_id` | `CharField(36)` (string livre) | **`UUID` com FK p/ `auth.users`** |
| Identidade por CPF | — | **Integração CPFHub.io** (best-effort) |
| Listagem | retorna tudo | **paginação + filtros (`q`, `cpf`)** |
| Criação | SELECT prévio + create | **INSERT confiando em constraints (409/422)** |
| Deploy | systemd (`profiles.service`, porta 80) | **Dockerfile** (uvicorn :8000 + `alembic upgrade`) |
| Versão | 0.2.0 | **0.3.0** |

Após a sincronização, o diretório local ficou **byte-a-byte idêntico ao remoto**,
exceto pelos arquivos locais de ambiente intencionalmente preservados
(`.env`, `data/`, `profiles.service`).

---

## 2. Inventário de mudanças

### 2.1 Arquivos MODIFICADOS (local atualizado a partir do remoto)

| Arquivo | O que mudou |
|---------|-------------|
| `pyproject.toml` | Remove `tortoise-orm`, `aerich`, `redis`, `aio-pika`, `mypy`; adiciona `sqlalchemy[asyncio]`, `asyncpg>=0.30`, `alembic`. Adiciona build-system hatchling. Remove `[tool.aerich]`. Versão 0.2.0 → 0.3.0. |
| `app/config.py` | `port` 80 → 8000; `database_url` sqlite → `postgresql+asyncpg://…`; novo `database_schema="profiles"`; novos `cpfhub_api_key/base_url/timeout_seconds`. |
| `app/db.py` | Reescrito: de `TORTOISE_ORM`/`Tortoise.init` para `Base` declarativa, `metadata` com schema, `engine`, `async_session_maker`, `get_session()`, `close_db()`. Inclui tabela-sombra `auth.users` para a FK cross-schema. |
| `app/main.py` | Troca `register_tortoise` por `lifespan` (asynccontextmanager) + `close_db()`. Usa `settings.version`. |
| `app/models/profile.py` | Tortoise → SQLAlchemy 2 (`Mapped`/`mapped_column`). `external_id` vira `UUID` com FK `auth.users.external_id` (RESTRICT/CASCADE). Relacionamentos `birth_info`/`educational`. Remove listas `*_CHOICES` (mantém as constantes de valor). |
| `app/models/birth_info.py` | Tortoise → SQLAlchemy 2; `profile_id` FK p/ `profiles.profiles.id` (CASCADE). |
| `app/models/educational.py` | Tortoise → SQLAlchemy 2; idem FK. Remove listas `*_CHOICES`. |
| `app/schemas/profile.py` | `external_id`: `str` → `UUID` em `ProfileCreate`, `ProfileRead`, `ProfileListItem`, `CPFCheckResponse`. |
| `app/api/health.py` | Reescrito p/ SQLAlchemy. Rotas: `/health` (leve), `/ready` (faz `SELECT 1` real), `/status` (uptime/versão). Remove o `/` que checava integrações via HTTP. |
| `app/api/profiles.py` | Todos os endpoints recebem `session: AsyncSession = Depends(get_session)`. `external_id` tipado como `UUID`. `list_all` ganha `limit/offset/q/cpf`. |
| `app/services/profile_service.py` | Reescrito p/ SQLAlchemy. Criação atômica sem SELECT prévio (confia em constraints; `IntegrityError` → 409/422 via `_classify_integrity_error`). Enriquecimento pós-save via CPFHub (`_enrich_from_cpfhub`, best-effort). `list_profiles` com paginação/filtros. |

### 2.2 Arquivos/diretórios ADICIONADOS (novos, vindos do remoto)

- `app/integrations/__init__.py`
- `app/integrations/cpfhub.py` — cliente HTTP async da CPFHub.io: retry com backoff em `429/5xx`, parsing seguro, **nunca levanta** (best-effort → `None`), não loga PII.
- `alembic.ini`
- `alembic/env.py` — async, schema `profiles`, `include_object` ignora outros schemas (ex.: `auth`).
- `alembic/script.py.mako`
- `alembic/versions/2026-05-15_initial_profiles_schema.py` (rev `0001`) — cria `profiles.profiles`, `profiles.birth_info`, `profiles.educational` + FK p/ `auth.users`.
- `alembic/versions/2026-05-15_0002_indexes_search.py` (rev `0002`) — índice `lower(name)` e `created_at`.
- `alembic/versions/.gitkeep`
- `tests/integrations/__init__.py`
- `tests/integrations/test_cpfhub.py` — 17 testes unitários do cliente (usam `httpx.MockTransport`).
- `Dockerfile` — `python:3.12-slim` + uv; CMD roda `alembic upgrade head` e sobe uvicorn :8000.
- `.env.example` — modelo de configuração do novo stack.

### 2.3 Diretórios REMOVIDos (para coerência com o remoto)

- `migrations/` (placeholder do Aerich, só tinha `.gitkeep`) — substituído por `alembic/`.

### 2.4 Arquivos LOCAIS preservados (não existem/não se aplicam no remoto)

- `.env` — **atualizado** para o novo stack (ver §4). Era SQLite/porta 80; agora aponta para Postgres.
- `data/profiles.db` (+ `-shm`/`-wal`) — banco SQLite antigo, **obsoleto** no novo stack. Mantido em disco (não apaguei dados), mas não é mais usado.
- `profiles.service` — unit systemd de deploy local. **Mantido**, porém defasado (ver §5).

---

## 3. Inconsistências encontradas NA fonte da verdade (remoto)

Pontos que já estão quebrados/defasados **no próprio remoto** — não foram
introduzidos por esta sincronização. Como a regra é "remoto é a fonte da verdade",
**não os corrigi** (corrigir divergiria do remoto). Ficam registrados como pendências:

1. **`tests/conftest.py` quebra a suíte inteira.** Ainda faz `from tortoise import Tortoise`
   e inicializa `sqlite://:memory:`. Como `tortoise` foi removido do `pyproject`, o
   `pytest` **nem coleta** os testes (`ModuleNotFoundError: tortoise`). Ou seja,
   `make test` está quebrado também no remoto.
2. **`tests/test_profiles.py` incompatível com o novo contrato.** Usa `external_id`
   como `"t1"`, `"ghost"`, etc. — não são UUID e não existem em `auth.users`.
   Contra o app SQLAlchemy resultariam em `422` (UUID) / violação de FK.
3. **`tests/test_health.py`** depende da mesma fixture `client`/`db` (Tortoise).
4. **`Makefile` defasado:** `make migrate` chama `aerich`; `make lint` chama `mypy`
   (ambos removidos do `pyproject`); `dev/run` usam porta 80 (config agora é 8000).
5. **Lint (ruff) pré-existente** (arquivos idênticos ao remoto):
   - `app/services/profile_service.py`: `F401` `sqlalchemy.or_` importado e não usado.
   - `app/validators/profile_fields.py`: `F601` chave de dict `"a positivo"` repetida.

> Recomendação: atualizar `conftest.py` para SQLAlchemy + Postgres de teste (com
> seed em `auth.users`), corrigir os `external_id` dos testes para UUID e ajustar
> `Makefile`. Posso aplicar isso se você autorizar divergir do remoto nesses arquivos.

---

## 4. Alterações de configuração local (`.env`)

Necessárias para o app rodar no novo stack (o `.env` antigo apontava p/ SQLite,
incompatível com o `db.py` atual). Novo conteúdo aponta para um Postgres local
dedicado de teste:

```
DATABASE_URL=postgresql+asyncpg://v7m:v7m@127.0.0.1:5548/v7m
DATABASE_SCHEMA=profiles
PORT=8000
CPFHUB_API_KEY=        # vazio = enriquecimento desabilitado (best-effort)
```

> A chave real da CPFHub e a `DATABASE_URL` de produção ficam no `.env` do remoto
> (não lido — segredos de produção). Para validar o enriquecimento real é preciso
> configurar `CPFHUB_API_KEY`.

---

## 5. Pendência de deploy (`profiles.service`)

A unit systemd local está defasada para o novo stack:
- `--port 80` (novo padrão é 8000) e sem `--proxy-headers`;
- **não roda `alembic upgrade head`** antes de subir (o Dockerfile do remoto roda);
- `WorkingDirectory=/root/profiles` e `.venv` — confira se batem com este host.

O remoto deploya via **Dockerfile** (que já executa as migrations no boot). Se o
deploy local continuar por systemd, recomendo adicionar um `ExecStartPre` com
`alembic upgrade head` e trocar a porta.

---

## 6. Testes de ponta a ponta (reais, sem mock)

Ambiente real montado para o teste:
- Postgres real: container `profiles-e2e-pg` (`postgres:16-alpine`) em `127.0.0.1:5548`.
- Schemas reais: `auth.users` (alvo da FK, semeado com UUIDs) + `profiles` (criado por **Alembic real**: `alembic upgrade head` → revisões 0001 e 0002).
- App real: `uvicorn app.main:app` apontando para esse Postgres.
- Requisições HTTP reais via `httpx`; inspeção do banco via `asyncpg`.

### Resultados

| Suíte | Resultado |
|-------|-----------|
| E2E HTTP + Postgres (`/tmp/e2e_profiles.py`) | **57/57 PASS** |
| Unit CPFHub (`tests/integrations/test_cpfhub.py`, `--noconftest`) | **17/17 PASS** |
| CPFHub rede real (401 → `None`, best-effort) | **PASS** |
| `/health`, `/ready` (SELECT 1 real), `/status` | **OK** (service `profiles-service`, v0.3.0) |

Cobertura do e2e (dados reais, UUIDs existentes em `auth.users`, CPFs com dígito válido):
- **Create:** mínimo (201); CPF duplicado (409); `external_id` duplicado (409);
  CPF inválido/igual (422); campos extras (422); **FK cross-schema inexistente (422,
  com mensagem citando `auth.users`)**; sem chave CPFHub o `name` continua `null`.
- **CPF lookup:** cadastrado (found/valid), válido não cadastrado, inválido.
- **List:** formato `{external_id,cpf,name}`; filtro `q` (prefix de nome); filtro
  `cpf` (prefix); `limit`/`offset`; `limit>100` capado.
- **Get:** existente (com `created_at/updated_at`), inexistente (404), não-UUID (422).
- **First-name:** primeiro nome normalizado.
- **Patch:** nome normaliza; gender m→M (inválido 422); blood_type O+ (inválido 422);
  civil_status Married→married (inválido 422); state sp→SP (inválido 422); birth_date
  válido / menor de idade (422) / futuro (422); CPF imutável (422); campo desconhecido
  (422); inexistente (404); educational level cria registro.
- **Delete + cascade:** 204; get depois 404; **`birth_info` e `educational` removidos
  em cascata (verificado direto no Postgres)**; delete inexistente 404.
- **Recreate:** recriar com o mesmo `external_id` após delete → 201.

### Como reproduzir / derrubar o ambiente

```bash
cd /home/maestri33/backend/profiles/profiles
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port <porta>
uv run python /tmp/e2e_profiles.py          # e2e
uv run pytest tests/integrations/test_cpfhub.py --noconftest -q

# limpeza
docker rm -f profiles-e2e-pg
# backup do código local pré-sync: /tmp/profiles_local_backup_*.tar.gz
```
