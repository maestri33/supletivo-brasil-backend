# Diferenças globais — código LOCAL vs. PRODUÇÃO

- **LOCAL** (`este, mais desenvolvido`): `/home/maestri33/backend/address/address/`
- **PRODUÇÃO / DESTINO** (`adaptado p/ acelerar o deploy`): `root@10.1.30.20:/opt/v7m/services/addresses/`
- Cópia da produção usada na comparação (read-only, sem binários): `/tmp/addresses_remote/`
- Data da comparação: 2026-05-22

> **Resumo de uma linha:** não é o mesmo código com pequenas divergências — são **duas arquiteturas diferentes** do mesmo serviço. O LOCAL é mais rico em funcionalidades; a PRODUÇÃO é mais "production-grade" em stack e integração.

---

## 1. Diferença estrutural (a mais importante)

| Aspecto | LOCAL | PRODUÇÃO |
|---|---|---|
| ORM | **Tortoise ORM** | **SQLAlchemy 2.0 (async)** |
| Banco | **SQLite** (`sqlite:///root/address.db`) | **PostgreSQL** (`postgresql+asyncpg://…`) |
| Criação de schema | `generate_schemas=True` (auto, em runtime) | **Alembic** (migrations versionadas) |
| Schema do banco | nenhum (SQLite) | `addresses` (Postgres), + FK cross-schema p/ `auth.users` |
| Sessão | implícita (Tortoise global) | `AsyncSession` injetada via `Depends(get_session)` |
| Python | `>=3.11` | `>=3.12` |
| Lifecycle | `register_tortoise` no import | `lifespan` (startup/shutdown + `close_db`) |

Consequência: **toda a camada de dados é incompatível** entre os dois. Migrar de um para o outro é reescrever models, services e db.

---

## 2. Modelo de dados (`addresses`) — incompatível

| Campo | LOCAL (Tortoise) | PRODUÇÃO (SQLAlchemy) |
|---|---|---|
| `id` | int PK | int PK |
| `external_id` | ❌ não existe | ✅ **UUID, NOT NULL, FK → `auth.users.external_id`** (RESTRICT/CASCADE) |
| `kind` | ❌ não existe | ✅ `varchar(20)` NOT NULL (`home`/`billing`/`shipping`) |
| `zipcode` / `cep` | `cep varchar(8)` **nullable** | `zipcode varchar(8)` **NOT NULL** |
| `street` | nullable | **NOT NULL** |
| `number` | nullable | nullable |
| `complement` | nullable | nullable |
| `neighborhood` | nullable | nullable |
| `city` | nullable | **NOT NULL** |
| `state` | nullable | **NOT NULL** |
| `country` | ❌ não existe | ✅ `varchar(2)` NOT NULL default `BR` |
| `lat` / `lng` | ✅ `varchar(30)` nullable | ❌ não existe |
| `created_at`/`updated_at` | ✅ | ✅ |

- **LOCAL**: endereço "genérico/avulso", quase tudo nullable, com geo (`lat`/`lng`).
- **PRODUÇÃO**: endereço **pertence a um usuário** (`external_id`) e é **tipado** (`kind`), com NOT NULLs e default de país. Sem geo.

---

## 3. Funcionalidades exclusivas de cada lado

### Só no LOCAL (o "mais desenvolvido")
- **Módulo `entity_addresses`** inteiro (`api/`, `models/`, `schemas/`, `services/`):
  - vínculo **polimórfico** `(entity_type, external_id)` único — `user`, `hub`, `atendimento`, `parceiro`…
  - `GET .../entities/{type}/{id}` = **get-or-create** com endereço vazio
  - `POST .../cep?cep=` = consulta ViaCEP e **preenche** o endereço
  - `POST .../proof` = **upload de comprovante** (multipart, grava em `UPLOAD_DIR`)
  - `POST .../unlink` = desvincula e cria novo (preserva histórico renomeando)
- **ViaCEP de fato implementado** (`lookup_cep` chama `viacep.com.br/ws/...`)
- **Webhook**: toda criação/alteração/deleção de Address dispara `POST` p/ `WEBHOOK_URL`
- **Validação de CEP utilitária** com endpoint `GET /cep/{cep}` retornando `CepInfo {cep, formatted, valid}`
- Dependências: `fastapi-mcp`, `python-multipart`, `aiosqlite`
- `API.md` (doc dos endpoints) e `address-service.service` (unit systemd)

### Só na PRODUÇÃO (o "production-grade")
- **`app/validators/`**: `zipcode.py` (valida/normaliza CEP, rejeita "todos dígitos iguais") e `address_fields.py` (`validate_kind` com **aliases** pt-br, `validate_state` UF, `validate_country` ISO-3166).
- **`app/integrations/`** (placeholder p/ 3rd-party).
- **Alembic** (`alembic/`, `alembic.ini`, migration inicial criando schema + tabela + 4 índices).
- **Endpoints de listagem/consulta por dono**:
  - `GET /api/v1/addresses?external_id=&kind=&limit=&offset=` (lista + filtros + paginação)
  - `GET .../by-external-id/{eid}` (todos do usuário)
  - `GET .../by-external-id/{eid}/{kind}/current` (mais recente do tipo)
- **Health mais completo**: `/health`, `/ready` (faz `SELECT 1` real), `/status` (versão + uptime).
- **Infra de deploy**: `Dockerfile` (uv, multistage, healthcheck, `alembic upgrade head` no boot), `Makefile`, `.env.example`, `.dockerignore`, `README.md`.
- **Config tipada e estruturada** (`get_settings()` com `lru_cache`, `cors_origins`, `viacep_*`).
- ViaCEP **declarado como gap** (`/cep/{zipcode}` → 501 `NotImplementedYet`).

---

## 4. Diferenças por arquivo (compartilhados)

| Arquivo | Diferença principal |
|---|---|
| `app/config.py` | LOCAL: chaves MAIÚSCULAS, SQLite, `PORT=80`, `WEBHOOK_URL`, `UPLOAD_DIR`. PROD: minúsculas, `lru_cache`, Postgres, `database_schema`, `cors_origins`, `viacep_*`. |
| `app/main.py` | LOCAL: `init_orm` + CORS `*` fixo. PROD: `lifespan`, logging configurado, `cors_origins.split(",")`, `version`. |
| `app/db.py` | LOCAL: `register_tortoise`. PROD: engine async + `async_sessionmaker` + `Base` (schema `addresses`) + shadow `auth.users` + `get_session`/`close_db`. |
| `app/exceptions.py` | LOCAL: erros específicos (`AddressNotFoundError`, `InvalidCepError`, `InvalidStateError`, `InvalidNumberError`, `EntityAddressNotFoundError`). PROD: genéricos (`NotFound`, `Conflict`, `ValidationError`, `NotImplementedYet`). Base `DomainError` levemente diferente. |
| `app/api/router.py` | LOCAL: `router` + inclui `entity_addresses`. PROD: `api_router`, sem entities. |
| `app/api/addresses.py` | LOCAL: CRUD + `/cep/{cep}` (valida formato), `HTTPException` manual. PROD: CRUD + listagens por `external_id`/`kind`, injeção de sessão, `/cep` = 501. |
| `app/api/health.py` | LOCAL: `/health` e `/ready` estáticos. PROD: `/health`, `/ready` (SELECT 1), `/status`. |
| `app/schemas/address.py` | LOCAL: validators inline na classe, campos nullable, `lat/lng`, `CepInfo`. PROD: usa `app.validators.*`, `external_id/kind/country`, `extra="forbid"`, `AddressPatch`. |
| `app/services/address_service.py` | LOCAL: Tortoise + webhook + ViaCEP real. PROD: SQLAlchemy, trata `IntegrityError` da FK, listagens, sem webhook/ViaCEP. |
| `app/utils/logging.py` | LOCAL: `setup_logging()` (lê settings, JSON em prod). PROD: `configure_logging(level)` + `get_logger(name)`. |
| `pyproject.toml` | LOCAL: hatch ausente, `tortoise-orm`, `aiosqlite`, `fastapi-mcp`, `python-multipart`. PROD: `hatchling`, `sqlalchemy`, `asyncpg`, `alembic`, `ruff`, `pytest` config. |

---

## 5. Conflitos de reconciliação (exigem decisão)

1. **`entity_addresses` × modelo da PRODUÇÃO.** O get-or-create cria `Address` **vazio** (`Address.create()` sem campos). Na produção, `addresses.addresses` tem `external_id` NOT NULL (FK p/ `auth.users`), `street/city/state` NOT NULL — **endereço vazio é proibido**. Além disso, o `external_id` polimórfico do LOCAL é uma **string** (`"victor"`, `"user"`), não um UUID de `auth.users`. São conceitos diferentes de "dono".
2. **`lat`/`lng`** existem só no LOCAL; **`kind`/`country`** só na PRODUÇÃO. Unir os dois muda o contrato da tabela.
3. **ViaCEP**: implementado no LOCAL, declarado como gap (501) na PRODUÇÃO.
4. **Webhook / upload de proof**: existem só no LOCAL; não há equivalente na PRODUÇÃO.

> Estes 4 pontos definem o "como" da coesão e são decididos antes da reescrita — ver `alteracoes-aplicadas.md` (a ser gerado) para a direção escolhida e o que foi efetivamente alterado.
