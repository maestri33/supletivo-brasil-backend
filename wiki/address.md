# address

## Função

Microsserviço responsável por armazenar e gerenciar endereços da plataforma. Oferece dois contratos distintos: endereços tipados vinculados a `auth.users` (tabela `addresses`) e um vínculo polimórfico genérico para qualquer entidade da plataforma (tabela `entity_addresses`).

---

## Status

**Funcional e conforme à CONVENTION (§4 UUID).** Transição PK int→UUID concluída (Fase 4, 2026-05-27). Validado via `ruff check` + `ruff format --check` verdes.

- Todos os endpoints dos dois recursos implementados com migração Alembic (0001 inicial, 0002 UUID).
- Healthcheck `/health`, `/ready`, `/status` implementados.
- Webhook de eventos (create/update/delete) em `integrations/webhook.py`.
- Integração ViaCEP em `integrations/viacep.py`.
- **Ausência de testes** — não há diretório `tests/` nem arquivo de teste (task futura: COD-25).
- **Validação PG pendente** — `alembic upgrade head` não executado neste ambiente (PG não disponível). Validar antes de deploy.

---

## Estrutura

**Achatado** — pacote em `address/app/`, conforme CONVENTION §3.

```
address/
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
│                   2026-05-25_0002_addresses_pk_uuid.py
├── pyproject.toml
└── uploads/       ← .gitignore'd (não versionado)
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
| GET | `/api/v1/addresses/{address_id}` | Busca endereço por ID interno (UUID) |
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
| `id` | UUID | PK (gerado na app via `uuid4`) |
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

Índices: `external_id`, `kind`, `zipcode`, composto `(external_id, kind)`.

### Tabela `addresses.entity_address_details`

| Coluna | Tipo | Restrições |
|--------|------|-----------|
| `id` | UUID | PK (gerado na app via `uuid4`) |
| `street`, `number`, `complement`, `neighborhood`, `city`, `state`, `zipcode`, `lat`, `lng` | varchar | todos nullable |
| `created_at` / `updated_at` | timestamptz | NOT NULL |

### Tabela `addresses.entity_addresses`

| Coluna | Tipo | Restrições |
|--------|------|-----------|
| `id` | UUID | PK (gerado na app via `uuid4`) |
| `entity_type` | varchar(50) | NOT NULL |
| `external_id` | varchar(100) | NOT NULL |
| `proof_file` | varchar(255) | nullable |
| `address_id` | UUID | nullable, FK → `entity_address_details.id` (SET NULL) |
| `created_at` / `updated_at` | timestamptz | NOT NULL |

UNIQUE: `(entity_type, external_id)`.

### Shadow table (cross-schema)

```python
# db.py — necessário pro SQLAlchemy resolver FK cross-schema
auth_users = Table("users", metadata,
    Column("external_id", PG_UUID(as_uuid=True), primary_key=True),
    schema="auth")
```

---

## Integrações

### Externas

| Serviço | Arquivo | Protocolo | Comportamento em falha |
|---------|---------|-----------|------------------------|
| **ViaCEP** (`viacep.com.br`) | `integrations/viacep.py` | `httpx.AsyncClient` GET | CEP inexistente → `None`; ViaCEP fora do ar → `IntegrationError(502)` |
| **Webhook de eventos** (`WEBHOOK_URL`) | `integrations/webhook.py` | `httpx.AsyncClient` POST | Best-effort — falha logada e ignorada, nunca quebra a operação |

### Internas

- `auth/app/integrations/address.py` — cliente HTTP que chama `POST /api/v1/addresses` no registro.
- `candidate/app/integrations/address.py` — cliente HTTP que chama endpoints de address e entity_address no funil.

---

## Pendências

### Testes

Nenhum arquivo de teste. Task [COD-25](/COD/issues/COD-25) cobre a criação da suíte de testes para address.

### Validação PG

`alembic upgrade head` não executado — PG não disponível no ambiente de desenvolvimento atual. Validar migration 0002 antes de deploy em staging/produção.

### Desvios da CONVENTION (pós-Fase 4)

| # | Desvio | Severidade |
|---|--------|-----------|
| 1 | **Sem testes** — nenhum arquivo em `tests/`; task [COD-25](/COD/issues/COD-25) | Alta |
| 2 | **Webhook desmilitarizado** (`webhook_url` hardcoded para `http://10.10.10.129`) — endpoint público sem verificação de origem; CONVENTION §5 recomenda verificação para webhooks externos | Média |
| 3 | **`POST /proof` salva em disco local** (`uploads/`) — sem storage externo, não adequado para produção distribuída | Média |

### Desvios resolvidos na Fase 4

| # | Desvio | Resolução |
|---|--------|-----------|
| ✅ | PK integer → UUID nas 3 tabelas | Migration 0002, models/service/schema/api atualizados |
| ✅ | Aninhamento `address/address/app/` | Corrigido — estrutura achatada `address/app/` |
| ✅ | `uploads/` versionado com PDFs reais | `.gitignore` cobre `uploads/`; arquivos não trackeados |
| ✅ | TODO órfão com funcionalidades já implementadas | Arquivo TODO removido |
