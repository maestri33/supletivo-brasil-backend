# CLAUDE.md — hub (polo)

Particularidades do serviço `hub` que complementam CONVENTION.md da raiz.

## Model

- **PK = UUID (PG_UUID nativo).** Nada de string/varchar. Isso força Postgres real nos testes — sem SQLite.
- **Sem FK cross-schema.** `address_external_id` e `coordinator_external_id` são UUID puro, nullable. Sem shadow table — o hub é registro fino.
- **Marcas válidas:** `estacio`, `wyden`. Enum fixo no schema Pydantic (`field_validator`). Para adicionar marca, editar `VALID_BRANDS` em `app/schemas/hub.py`.

## API

- **Desmilitarizado:** `GET /api/v1/hubs` e `GET /api/v1/hubs/{external_id}` — uso interno entre serviços.
- **Autenticado (staff JWT):** `POST/PATCH /api/v1/hubs`, `PUT /api/v1/hubs/{id}/coordinator` — dependency `get_current_external_id` exige JWT com role `staff`/`admin`.

## Seed

- `app/seed.py` define o polo default com UUID determinístico `00000000-0000-0000-0000-000000000001`.
- A migração `0001` chama `seed.default_hub_insert_sql("hub")` no upgrade.

## Testes

- **Postgres real obrigatório.** Ou `testcontainers[postgres]` + docker, ou `TEST_DATABASE_URL`. Sem mock/SQLite.
- Fixtures em `tests/conftest.py`: engine de sessão, session_factory, client ASGI autenticado (bypass JWT via monkeypatch).
- Monkeypatch de `get_current_external_id` retorna UUID fixo — não depende de JWKS real.

## Config

- `DATABASE_URL` obrigatório (sem default). `DATABASE_SCHEMA` default `hub`.
- `ENV` aceita `dev`/`staging`/`prod`. `SERVICE_NAME` default `hub`.
- `.env.example` já cobre todas as vars necessárias.
