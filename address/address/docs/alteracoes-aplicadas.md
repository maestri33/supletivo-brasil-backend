# Alterações aplicadas no código LOCAL (coesão com produção)

Data: 2026-05-22 · Companion de `diferencas-local-vs-producao.md`.

## Direção escolhida

> **Migrar o LOCAL para a stack da produção** (SQLAlchemy 2 async + PostgreSQL +
> Alembic, modelo `external_id`/`kind`/`country` ligado a `auth.users`) **e
> preservar todas as features do LOCAL** (entity_addresses, ViaCEP real, webhook,
> upload de comprovante, lat/lng). O conflito do "Address vazio" foi resolvido com
> tabela própria para o fluxo polimórfico.

Resultado: o LOCAL passa a ser um **superset** da produção — mesma stack e mesmo
contrato de `addresses`, com as funcionalidades extras por cima.

## Decisões de arquitetura

1. **Tabela `addresses`** = idêntica à produção + duas colunas nullable `lat`/`lng`
   (feature de geo do LOCAL). Contrato da produção preservado (nenhuma coluna
   existente mudou).
2. **Fluxo polimórfico (`entity_addresses`)** ganhou tabela própria de endereço,
   `entity_address_details` (tudo nullable), evitando o conflito com os NOT NULL +
   FK→`auth.users` da tabela `addresses`. O "dono" continua sendo `(entity_type,
   external_id)` como strings livres.
3. **ViaCEP** (gap na produção) foi implementado em `app/integrations/viacep.py` e
   liga o endpoint `GET /api/v1/addresses/cep/{zipcode}` (antes 501) + o
   preenchimento de endereço das entidades.
4. **Webhook** portado para `app/integrations/webhook.py`; disparado em
   create/update/delete de Address (best-effort).
5. **Validação** unificada nos `app/validators/` da produção (zipcode, kind com
   aliases pt-br, UF, country) — substitui os validators inline do LOCAL.
6. **Exceptions** alinhadas às genéricas da produção (`NotFound`, `Conflict`,
   `ValidationError`, `NotImplementedYet`).

## Mudanças por arquivo

### Reescritos para a stack da produção
- `app/config.py` — Settings minúsculo + `lru_cache`; Postgres/schema; mantém
  `viacep_*`, `webhook_url`, `upload_dir`.
- `app/db.py` — engine async + `async_sessionmaker` + `Base` (schema `addresses`) +
  shadow `auth.users` + `get_session`/`close_db` (era `register_tortoise`).
- `app/main.py` — `lifespan`, logging configurado, CORS por `cors_origins`.
- `app/utils/logging.py` — `configure_logging`/`get_logger`.
- `app/exceptions.py` — exceções genéricas da produção.
- `app/models/address.py` — SQLAlchemy 2 + `lat`/`lng` nullable (era Tortoise).
- `app/schemas/address.py` — usa `validators/`, `external_id/kind/country`,
  `extra="forbid"`, `AddressPatch`, `+ lat/lng`, `+ ViaCepResult`.
- `app/services/address_service.py` — CRUD SQLAlchemy + listagens + trata
  `IntegrityError` da FK + **webhook** + lat/lng.
- `app/api/addresses.py` — injeção de sessão, listagens por dono, `/cep` agora
  **real** (ViaCEP).
- `app/api/health.py` — `/health`, `/ready` (SELECT 1 real), `/status`.
- `app/api/router.py` — `api_router` incluindo health, addresses e entities.

### Novos (features do LOCAL portadas / infra da produção)
- `app/validators/{__init__,zipcode,address_fields}.py`
- `app/integrations/{__init__,viacep,webhook}.py`
- `app/models/entity_address.py` — `EntityAddress` + `EntityAddressDetail` (SQLAlchemy).
- `app/schemas/entity_address.py` — `EntityAddressRead` + `AddressDraftRead`.
- `app/services/entity_address_service.py` — get-or-create, fill-by-CEP, upload, unlink (SQLAlchemy).
- `app/api/entity_addresses.py` — endpoints `/api/v1/entities/...` com sessão.
- `alembic/` + `alembic.ini` + migration `0001` (cria `addresses` com lat/lng +
  `entity_address_details` + `entity_addresses`).
- `Dockerfile`, `Makefile`, `.env.example`, `.dockerignore`, `.gitignore`, `README.md`.
- `pyproject.toml` — deps da produção + `python-multipart` (upload); removidos
  `tortoise-orm`, `aiosqlite`, `fastapi-mcp`; build `hatchling`; ruff/pytest.
- `.env` — Postgres + viacep + webhook + upload_dir.
- `address-service.service` — `ExecStartPre=alembic upgrade head`, porta 8000.

### Correção de robustez (melhoria sobre a produção)
- `alembic/env.py` — cria/commita o schema `addresses` numa **conexão própria
  antes** das migrations. Sem isso, num banco novo o Alembic falha ao criar
  `alembic_version` (que mora em `version_table_schema=addresses`). A produção
  depende do schema já existir; aqui a migração é autossuficiente.

### Removido
- `app/models/entity_address.py` (Tortoise) → reescrito em SQLAlchemy.
- `address_service.egg-info/` (artefato obsoleto; listava layout antigo).
- Dependência `fastapi-mcp` (não estava montada em `main.py` no LOCAL — feature
  inexistente na prática; não há o que portar).

## Renomeações de contrato (para coesão)
- Campo `cep` → `zipcode` (inclusive no endereço das entidades), alinhado à produção.
- `EntityAddress.external_id` continua string (polimórfico); **não** confundir com
  `Address.external_id` (UUID FK→auth.users).

## Teste de ponta a ponta (dados reais, sem mock)

Ambiente: Postgres 16 **real** em Docker isolado (`addr_e2e_pg`, porta 5560), com
schema `auth.users` semeado com UUIDs reais; ViaCEP real (internet); webhook real
(listener local); upload de arquivo real em disco. Nenhum mock.

Setup reproduzível:
```bash
docker run -d --name addr_e2e_pg -e POSTGRES_USER=v7m -e POSTGRES_PASSWORD=v7m \
  -e POSTGRES_DB=v7m -p 5560:5432 postgres:16-alpine
# criar schema auth + auth.users e semear UUIDs (ver auth.users)
export DATABASE_URL='postgresql+asyncpg://v7m:v7m@localhost:5560/v7m'
uv run alembic upgrade head
uv run uvicorn app.main:app --port 8000
```

Resultados (todos ✅):
| # | Caso | Resultado |
|---|------|-----------|
| 1 | POST address válido (external_id real) | 201, zipcode normalizado, UF upper, lat/lng |
| 2 | `kind="casa"` (alias) | normalizado p/ `home` |
| 3 | external_id inexistente (FK real) | 422 `validation_error` |
| 4 | zipcode inválido | 422 |
| 5 | state inválido | 422 |
| 6–10 | GET id / list / by-external-id / current / PATCH | 200, dados corretos |
| 11 | GET /cep/01310100 (ViaCEP real) | 200 → Avenida Paulista/SP |
| 12 | GET /cep/99999998 (inexistente) | 404 |
| 13 | GET /cep/11111111 (dígitos iguais) | 422 |
| 14–15 | DELETE + GET | 204 e depois 404 |
| E1 | get-or-create entity | 200, endereço vazio |
| E2 | fill-by-CEP (ViaCEP real) | 200 → São Paulo persistido |
| E4 | upload de comprovante (arquivo real) | 200, arquivo salvo em disco |
| E5 | unlink | novo vazio; antigo vira `victor_unlinked_1` (histórico) |
| E6 | cep em entidade inexistente | 404 |
| webhook | created×2, updated, deleted | recebidos pelo listener |

## Pendências / notas
- **Convergência inversa**: a produção continua sem entity_addresses, ViaCEP,
  webhook, lat/lng e sem a correção do `env.py`. Se o objetivo for produção ==
  LOCAL, esses itens precisariam ser portados lá também (fora do escopo: aqui só
  o LOCAL foi alterado).
- `uv.lock` não versionado ainda — gerar com `uv lock` antes do build Docker para
  builds reprodutíveis (`--frozen`).
