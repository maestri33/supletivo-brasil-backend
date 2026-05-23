# addresses

Microsserviço de endereços ligado a `auth.users` (FK cross-schema), com suporte a
endereços de usuário (home/billing/shipping) **e** a um vínculo polimórfico de
entidades (user/hub/atendimento/parceiro…).

Stack: FastAPI + SQLAlchemy 2 (async) + PostgreSQL + Alembic.

## Modelo (schema `addresses`)

```
addresses(
  id           int PK,
  external_id  UUID FK→auth.users.external_id (RESTRICT/CASCADE update),
  kind         varchar(20) ∈ {home, billing, shipping},
  zipcode      varchar(8)  NOT NULL,
  street       varchar(200) NOT NULL,
  number       varchar(20)  NULL,
  complement   varchar(100) NULL,
  neighborhood varchar(100) NULL,
  city         varchar(100) NOT NULL,
  state        varchar(2)   NOT NULL,
  country      varchar(2)   NOT NULL DEFAULT 'BR',
  lat          varchar(30)  NULL,   -- feature do LOCAL (geo)
  lng          varchar(30)  NULL,   -- feature do LOCAL (geo)
  created_at, updated_at  timestamptz NOT NULL,
)

entity_addresses(             -- vínculo polimórfico (feature do LOCAL)
  id, entity_type, external_id (string), proof_file NULL,
  address_id FK→entity_address_details.id NULL,
  created_at, updated_at,
  UNIQUE(entity_type, external_id),
)

entity_address_details(       -- endereço genérico nullable das entidades
  id, street, number, complement, neighborhood, city, state, zipcode, lat, lng,
  created_at, updated_at,
)
```

Múltiplos endereços por `(external_id, kind)` são permitidos — o "atual" é o mais recente por `created_at`.

## Endpoints

### Endereços de usuário (`auth.users`)
| Verbo  | Rota                                                    | Descrição                          |
| ------ | ------------------------------------------------------- | ---------------------------------- |
| POST   | `/api/v1/addresses`                                     | cria endereço                      |
| GET    | `/api/v1/addresses?external_id=&kind=&limit=&offset=`   | lista com filtros + paginação      |
| GET    | `/api/v1/addresses/{id}`                                | detalhe                            |
| PATCH  | `/api/v1/addresses/{id}`                                | atualização parcial                |
| DELETE | `/api/v1/addresses/{id}`                                | hard delete                        |
| GET    | `/api/v1/addresses/by-external-id/{eid}`               | todos os endereços do usuário      |
| GET    | `/api/v1/addresses/by-external-id/{eid}/{kind}/current`| endereço mais recente do kind      |
| GET    | `/api/v1/addresses/cep/{zipcode}`                       | lookup ViaCEP (implementado)       |

### Entidades (vínculo polimórfico)
| Verbo  | Rota                                                | Descrição                              |
| ------ | --------------------------------------------------- | -------------------------------------- |
| GET    | `/api/v1/entities/{entity_type}/{external_id}`      | get-or-create (endereço vazio)         |
| POST   | `/api/v1/entities/{entity_type}/{external_id}/cep?cep=` | preenche endereço via ViaCEP        |
| POST   | `/api/v1/entities/{entity_type}/{external_id}/proof`   | upload de comprovante (multipart)    |
| POST   | `/api/v1/entities/{entity_type}/{external_id}/unlink`  | desvincula e cria novo (histórico)   |

### Operacional
| Verbo | Rota | Descrição |
| ----- | ---- | --------- |
| GET   | `/health`, `/ready`, `/status` | liveness / readiness (SELECT 1) / info |

## Eventos (webhook)

Toda criação/alteração/deleção de Address dispara um `POST` para `WEBHOOK_URL`
(`{event, payload}`), best-effort — falhas são logadas e não quebram a operação.

## Rodando

```bash
make install            # uv sync
make migrate            # alembic upgrade head (requer auth.users existente)
make dev                # uvicorn --reload em :8000
```

Config via `.env` (ver `.env.example`).

## Diferenças vs. produção / histórico de unificação

Este código unifica a versão "mais desenvolvida" (LOCAL, antes em Tortoise/SQLite)
com a versão de produção (SQLAlchemy/Postgres). Ver `docs/diferencas-local-vs-producao.md`
e `docs/alteracoes-aplicadas.md`.
