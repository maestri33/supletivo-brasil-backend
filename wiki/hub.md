# Hub Service — Wiki

> Fonte de verdade operacional do servico `hub`. Atualizado sempre que o servico
> muda. §15 da CONVENTION.md.

## O que faz

Gerencia **polos (hubs)** — unidades fisicas da operacao educacional. Cada polo
tem nome, marca (estacio/wyden), endereco e coordenador. Entidade raiz que conecta
promotores, alunos e coordenadores a uma localidade.

## Como rodar

```bash
cd hub
uv sync
cp .env.example .env  # edite DATABASE_URL e JWT_BASE_URL
uv run alembic upgrade head
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Healthcheck

- `GET /health` — liveness (retorna `{"status":"ok"}`)
- `GET /ready` — readiness (verifica conexao com banco)
- `GET /status` — versao + uptime

## Endpoints

### Desmilitarizados (uso interno, sem auth)

| Metodo | Rota | Descricao |
|--------|------|-----------|
| GET | `/api/v1/hubs` | Lista todos os polos (ordem alfabetica) |
| GET | `/api/v1/hubs/{id}` | Busca polo por external_id |

### Autenticados (requer JWT com role admin/staff)

| Metodo | Rota | Descricao |
|--------|------|-----------|
| POST | `/api/v1/hubs` | Cria polo |
| PATCH | `/api/v1/hubs/{id}` | Edita polo |
| PUT | `/api/v1/hubs/{id}/coordinator` | Define coordenador |

## Modelo

Tabela `hub.hub`:

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| id | UUID PK | Identificador do polo |
| name | varchar(120) | Nome do polo |
| brand | varchar(40) | Marca (estacio, wyden) |
| address_external_id | UUID nullable | Referencia logica ao address |
| coordinator_external_id | UUID nullable | Referencia logica ao coordinator |
| created_at | timestamptz | Criacao |
| updated_at | timestamptz | Ultima atualizacao |

## Marcas validas

`estacio`, `wyden`. Validadas no schema Pydantic. Para adicionar nova marca,
altere `VALID_BRANDS` em `app/schemas/hub.py`.

## Migracoes

```bash
uv run alembic revision --autogenerate -m "descricao"
uv run alembic upgrade head
```

## Testes

```bash
# Requer Postgres de teste (testcontainers ou TEST_DATABASE_URL)
uv run pytest -q
```

## Dependencias de outros servicos

- `staff` chama os endpoints autenticados para criar/editar polos e definir coordenador
- `candidate`, `promoter`, `student` leem polos via GET desmilitarizado

## Nao faz

- Nao gerencia enderecos (dominio do `address`)
- Nao gerencia coordenadores (dominio do `coordinator`)
- Nao tem endpoints publicos externos — uso interno apenas
