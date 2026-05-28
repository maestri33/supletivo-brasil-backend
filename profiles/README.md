# profiles

Microsserviço de **dados cadastrais**: perfil (nome, gênero, estado civil,
filiação, descrição), nascimento e escolaridade — vinculados 1-para-1 a
`auth.users` via `external_id`. Enriquecimento automático por CPF via
CPFHub.io na criação (best-effort).

## Stack
Python 3.12 · FastAPI · SQLAlchemy 2 (async) + asyncpg · Alembic · Pydantic v2
+ pydantic-settings · httpx · structlog. Gerenciado com `uv`.

## Como rodar
```bash
uv sync                      # instala dependências
cp .env.example .env         # preencha DATABASE_URL (obrigatório)
make migrate                 # alembic upgrade head
make dev                     # uvicorn :80 com reload  (make run = prod)
make test                    # pytest
make lint                    # ruff check
```

## Variáveis de ambiente (`.env`)
| Var | Obrigatório | Default | Descrição |
|---|---|---|---|
| `DATABASE_URL` | **sim** | — | Postgres async, ex.: `postgresql+asyncpg://user:pass@host:5432/db` |
| `DATABASE_SCHEMA` | não | `profiles` | Schema próprio do serviço |
| `ENV` / `LOG_LEVEL` / `PORT` | não | `dev` / `INFO` / `8000` | Núcleo |
| `CORS_ORIGINS` | não | `*` | Lista separada por vírgula |
| `CPFHUB_API_KEY` | não | _(vazio)_ | Vazio = enriquecimento desabilitado |
| `CPFHUB_BASE_URL` / `CPFHUB_TIMEOUT_SECONDS` | não | `https://api.cpfhub.io` / `5.0` | Integração CPFHub |

> `DATABASE_URL` **não tem default no código** — sem `.env` configurado o
> serviço não sobe (evita credencial hardcoded).

## Endpoints
Base `/api/v1/profiles` (internos/desmilitarizados) + `/health` (público).

| Método | Rota | Descrição |
|---|---|---|
| POST | `/api/v1/profiles` | Cria perfil; dispara enriquecimento CPFHub pós-save |
| GET | `/api/v1/profiles` | Lista com paginação (`limit`/`offset`) e filtros prefix (`q`, `cpf`) |
| GET | `/api/v1/profiles/{external_id}` | Perfil completo (+ birth_info, educational) |
| GET | `/api/v1/profiles/cpf/{cpf}` | Existência + validade de CPF |
| GET | `/api/v1/profiles/first-name/{external_id}` | Primeiro nome + nome completo |
| PATCH | `/api/v1/profiles/{external_id}` | Atualização parcial (profile + birth_info + educational) |
| DELETE | `/api/v1/profiles/{external_id}` | Remove (cascade em birth_info e educational) |

## Dados
Schema Postgres `profiles`, 3 tabelas: `profiles` (raiz, PK serial,
`external_id` UNIQUE → `auth.users`, `cpf` UNIQUE), `birth_info` e
`educational` (1-1, FK `profile_id` CASCADE). FK cross-schema via **shadow
table** `auth.users` (só `external_id`) em `app/db.py`. `updated_at` é mantido
por `onupdate` no ORM **e** por trigger no Postgres (migração `0003`).

## Integrações
- **CPFHub.io** (`app/integrations/cpfhub.py`): lookup de identidade por CPF.
  Best-effort com retry (429/5xx); falha não quebra a criação do perfil.
  Desabilitada quando `CPFHUB_API_KEY` vazio.

## Convenção
Estrutura e estilo seguem a `../CONVENTION.md`. Particularidades em
`.claude/CLAUDE.md`. Fonte de verdade do serviço: `../wiki/profiles.md`.
