# hub

## Função

Gerencia os **polos (hubs)** — unidades físicas da operação educacional. Cada polo tem um nome, marca (ex.: Estácio, Wyden), endereço e coordenador. O hub é a entidade raiz que conecta promotores, alunos e coordenadores a uma localidade física.

---

## Status

**Em desenvolvimento (Milestone 1).** Spine funcional com health/ready/status. Model `Hub` implementado. Endpoints de CRUD e regras de negócio pendentes.

---

## Estrutura

```
hub/
├── app/
│   ├── main.py          # FastAPI, lifespan, middlewares, health/ready/status
│   ├── config.py         # Settings (pydantic-settings)
│   ├── db.py             # engine async, Base, metadata com schema hub
│   ├── exceptions.py     # DomainError
│   ├── seed.py           # seed de dados iniciais
│   └── models/
│       ├── __init__.py   # reexport Hub
│       └── hub.py        # model Hub
├── alembic/
├── tests/
├── pyproject.toml
└── Makefile
```

---

## Modelo de dados

### Tabela `hub.hub`

| Coluna | Tipo | Constraints | Descrição |
|---|---|---|---|
| `id` | UUID | PK, default uuid4 | ID do polo |
| `name` | String(120) | NOT NULL | Nome do polo |
| `brand` | String(40) | NOT NULL, indexed | Marca (estacio, wyden) |
| `address_external_id` | UUID | nullable, indexed | FK lógica para address |
| `coordinator_external_id` | UUID | nullable, indexed | FK lógica para coordinator |
| `created_at` | timestamptz | server_default now() | Criação |
| `updated_at` | timestamptz | server_default now(), onupdate | Última atualização |

**Marcas conhecidas:** `estacio`, `wyden` (validação no schema Pydantic, futuro).

---

## Endpoints

### Health/Status (disponíveis)

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/health` | Healthcheck simples |
| GET | `/ready` | Readiness (testa conexão com DB) |
| GET | `/status` | Versão, ambiente, uptime |

### Planejados (próximos milestones)

| Método | Rota | Tipo | Descrição |
|--------|------|------|-----------|
| POST | `/api/v1/demilitarized/hubs` | Desmilitarizado | Criar polo (staff) |
| GET | `/api/v1/demilitarized/hubs` | Desmilitarizado | Listar polos |
| GET | `/api/v1/demilitarized/hubs/{id}` | Desmilitarizado | Detalhe do polo |
| PATCH | `/api/v1/demilitarized/hubs/{id}` | Desmilitarizado | Atualizar polo |
| DELETE | `/api/v1/demilitarized/hubs/{id}` | Desmilitarizado | Remover polo |

---

## Notas técnicas

- **Sem FK cross-schema:** `address_external_id` e `coordinator_external_id` são UUID puro, nullable. Não usa shadow table — hub é registro fino.
- **Schema:** `hub` (próprio, conforme CONVENTION §4).
- **Engine:** async (`create_async_engine` + `asyncpg`).
- **Naming convention:** padrão do projeto (copiado de `address/app/db.py`).

---

## Dependências

- **address** — endereço do polo (referência por external_id)
- **coordinator** — coordenador do polo (referência por external_id, ainda não criado)
- **staff** — quem cadastra e gerencia polos

---

## Variáveis de ambiente

| Variável | Descrição | Exemplo |
|---|---|---|
| `DATABASE_URL` | URL de conexão Postgres | `postgresql+asyncpg://...` |
| `DATABASE_SCHEMA` | Schema do serviço | `hub` |
| `ENV` | Ambiente | `dev` / `staging` / `prod` |
| `LOG_LEVEL` | Nível de log | `INFO` |
