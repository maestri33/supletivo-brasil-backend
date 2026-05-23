# address

## Função

Microsserviço responsável por armazenar e gerenciar endereços da plataforma. Oferece dois contratos distintos: endereços tipados vinculados a `auth.users` (tabela `addresses`) e um vínculo polimórfico genérico para qualquer entidade da plataforma (tabela `entity_addresses`).

---

## Status

**Parcial — funcional, mas incompleto.**

- Todos os endpoints dos dois recursos estão implementados e com migração Alembic correspondente (0001).
- Webhook de eventos (create/update/delete) implementado em `integrations/webhook.py`.
- Integração ViaCEP implementada em `integrations/viacep.py`.
- **Ausência total de testes** — não há diretório `tests/` nem arquivo de teste.
- TODO presente com funcionalidades ainda não implementadas (ver §Pendências).
- Arquivos `uploads/` com PDFs reais versionados (violação de §9 da CONVENTION).

---

## Estrutura

**Aninhado** — pacote em `address/address/app/`, não em `address/app/` como exige a CONVENTION (§3: "Sem aninhamento de nome").

```
address/
└── address/          ← aninhamento indevido
    ├── app/
    │   ├── api/          addresses.py · entity_addresses.py · health.py · router.py
    │   ├── models/       address.py · entity_address.py
    │   ├── schemas/      address.py · entity_address.py
    │   ├── services/     address_service.py · entity_address_service.py
    │   ├── integrations/ viacep.py · webhook.py
    │   ├── utils/        logging.py
    │   └── validators/   address_fields.py · zipcode.py
    ├── alembic/
    │   └── versions/  2026-05-22_0001_initial_addresses_schema.py
    ├── pyproject.toml
    ├── TODO
    └── uploads/       ← dados locais versionados (violação §9)
```

---

## Endpoints

### `api/health.py` — infraestrutura (desmilitarizados)

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/health` | Liveness check simples |
| GET | `/ready` | Readiness com ping no banco (`SELECT 1`) |
| GET | `/status` | Versão, uptime e status do serviço |

### `api/addresses.py` — recurso Address (desmilitarizados)

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/api/v1/addresses` | Cria endereço vinculado a `auth.users` via `external_id`; dispara webhook `address.created` |
| GET | `/api/v1/addresses` | Lista com filtros opcionais `external_id`, `kind`, `limit`, `offset` |
| GET | `/api/v1/addresses/by-external-id/{external_id}` | Lista todos endereços de um usuário |
| GET | `/api/v1/addresses/by-external-id/{external_id}/{kind}/current` | Endereço mais recente de um usuário por tipo |
| GET | `/api/v1/addresses/cep/{zipcode}` | Lookup ViaCEP (não persiste; retorna dados do CEP) |
| GET | `/api/v1/addresses/{address_id}` | Busca endereço por ID interno |
| PATCH | `/api/v1/addresses/{address_id}` | Atualização parcial; dispara webhook `address.updated` |
| DELETE | `/api/v1/addresses/{address_id}` | Remove endereço; dispara webhook `address.deleted` |

### `api/entity_addresses.py` — vínculo polimórfico (desmilitarizados)

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/v1/entities/{entity_type}/{external_id}` | Retorna ou cria (get-or-create) vínculo de endereço para qualquer entidade |
| POST | `/api/v1/entities/{entity_type}/{external_id}/cep` | Preenche endereço via ViaCEP; degrada graciosamente se ViaCEP indisponível |
| POST | `/api/v1/entities/{entity_type}/{external_id}/proof` | Upload de comprovante de endereço (arquivo salvo em `uploads/`) |
| POST | `/api/v1/entities/{entity_type}/{external_id}/unlink` | Desvincula endereço atual (renomeia `external_id` para `_unlinked_`) e cria novo registro em branco |

---

## Dados

**Schema Postgres:** `addresses`

### Tabela `addresses.addresses`

| Coluna | Tipo | Restrições |
|--------|------|-----------|
| `id` | integer | PK, autoincrement |
| `external_id` | uuid | NOT NULL, FK → `auth.users.external_id` (RESTRICT/CASCADE), index |
| `kind` | varchar(20) | NOT NULL, index — valores: `home`, `billing`, `shipping` |
| `zipcode` | varchar(8) | NOT NULL, index |
| `street` | varchar(200) | NOT NULL |
| `number` | varchar(20) | nullable |
| `complement` | varchar(100) | nullable |
| `neighborhood` | varchar(100) | nullable |
| `city` | varchar(100) | NOT NULL |
| `state` | varchar(2) | NOT NULL |
| `country` | varchar(2) | NOT NULL, default `'BR'` |
| `lat` | varchar(30) | nullable |
| `lng` | varchar(30) | nullable |
| `created_at` | timestamptz | NOT NULL, default `now()` |
| `updated_at` | timestamptz | NOT NULL, default `now()` |

Índices compostos: `(external_id, kind)`.

### Tabela `addresses.entity_address_details`

| Coluna | Tipo | Restrições |
|--------|------|-----------|
| `id` | integer | PK, autoincrement |
| `street`, `number`, `complement`, `neighborhood`, `city`, `state`, `zipcode`, `lat`, `lng` | varchar | todos nullable |
| `created_at` / `updated_at` | timestamptz | NOT NULL |

### Tabela `addresses.entity_addresses`

| Coluna | Tipo | Restrições |
|--------|------|-----------|
| `id` | integer | PK, autoincrement |
| `entity_type` | varchar(50) | NOT NULL |
| `external_id` | varchar(100) | NOT NULL |
| `proof_file` | varchar(255) | nullable |
| `address_id` | integer | nullable, FK → `entity_address_details.id` (SET NULL) |
| `created_at` / `updated_at` | timestamptz | NOT NULL |

UNIQUE: `(entity_type, external_id)`.

### Shadow table (cross-schema)

```python
# db.py — necessário pro SQLAlchemy resolver FK cross-schema
auth_users = Table("users", metadata,
    Column("external_id", PG_UUID(as_uuid=True), primary_key=True),
    schema="auth")
```

**Observação:** PK das tabelas deste serviço é `integer` (autoincrement), não `UUID` — diverge da convenção §4 que determina `PK = UUID`.

---

## Integrações

### Externas

| Serviço | Arquivo | Protocolo | Comportamento em falha |
|---------|---------|-----------|------------------------|
| **ViaCEP** (`viacep.com.br`) | `integrations/viacep.py` | `httpx.AsyncClient` GET | CEP inexistente → `None`; ViaCEP fora do ar → `IntegrationError(502)` |
| **Webhook de eventos** (`WEBHOOK_URL`) | `integrations/webhook.py` | `httpx.AsyncClient` POST | Best-effort — falha logada e ignorada, nunca quebra a operação |

### Internas

Nenhuma integração com outros microsserviços da plataforma via httpx no código atual.

---

## Pendências

### Arquivo TODO

```
Veja... funcos totalmente desmilitarizadas (irao ser usadas so dentro do app)

get /external_id/ (procura endereco de um usuario)
get /id/ busca por id do endereco
get list / busca todos enderecos
post /external_id/{CEP} - Valida CEP, faz busca usando api externa já implementada,
  insere dados da busca (devolve no payload e já salva no db)
patch /external_id/ demais dados
post /webhook/external_id/ (cria endereco null, toda vez aque usuario é criado,
  implementar em auth)
```

Os 5 primeiros itens do TODO estão implementados nos endpoints de `addresses.py`. **Não implementado:** endpoint `POST /webhook/external_id/` que deveria criar endereço nulo automaticamente ao criar usuário no serviço `auth`.

### TODOs no código

Nenhum comentário `# TODO` encontrado no código-fonte.

### Desvios da CONVENTION

| # | Desvio | Severidade |
|---|--------|-----------|
| 1 | **Aninhamento** — pacote em `address/address/app/` (deveria ser `address/app/`) | Alta |
| 2 | **PK integer** nas 3 tabelas — CONVENTION §4 exige `PK = UUID` | Alta |
| 3 | **Sem testes** — nenhum arquivo em `tests/`; CONVENTION §15 exige testes para todo comportamento | Alta |
| 4 | **`uploads/` versionado** com PDFs reais — CONVENTION §9 proíbe dados locais no repositório | Média |
| 5 | **Webhook desmilitarizado** (`webhook_url` hardcoded para `http://10.10.10.129`) — endpoint público sem verificação de origem; CONVENTION §5 recomenda verificação para webhooks externos | Média |
| 6 | **`POST /proof` salva em disco local** (`uploads/`) — sem storage externo, não adequado para produção distribuída | Média |
| 7 | **Webhook `auth` não implementado** — `post /webhook/external_id/` do TODO é um webhook público que deveria ser tratado isoladamente conforme §5 | Média |
