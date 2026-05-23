# infinitepay

## Função

Microsserviço de integração com a API de checkout da InfinitePay: cria links de pagamento, recebe webhooks externos de confirmação de pagamento e reenvia eventos internos via fila de saída (outbound_jobs).

---

## Status

**Parcial — funcional no núcleo, com pendências de IA e configuração.**

- Endpoints de checkout (criar, listar, consultar) e webhook implementados com testes.
- 2 migrações Alembic presentes e coerentes com os models.
- Endpoints `/ask` e `/report` (IA) existem mas possuem TODOs explícitos de remoção.
- `db.py` usa engine **síncrono** (`create_engine` / `sessionmaker`) — violação crítica da convenção.

---

## Estrutura

**Aninhado** — pacote real em `infinitepay/infinitepay/app/` (nível extra `infinitepay/`). Deveria ser `infinitepay/app/` conforme a convenção (§3).

```
infinitepay/
└── infinitepay/        ← aninhamento indevido
    ├── app/
    │   ├── main.py
    │   ├── config.py
    │   ├── db.py
    │   ├── exceptions.py
    │   ├── api/
    │   ├── models/
    │   ├── schemas/
    │   ├── services/
    │   ├── integrations/
    │   ├── ai/
    │   ├── utils/
    │   └── workers/
    ├── alembic/
    ├── tests/
    └── pyproject.toml
```

---

## Endpoints

### `api/health.py`
| Método | Rota | Descrição | Tipo |
|--------|------|-----------|------|
| GET | `/health` | Liveness/readiness probe | Desmilitarizado |

### `api/checkout.py` — prefixo `/api/v1/checkout`
| Método | Rota | Descrição | Tipo |
|--------|------|-----------|------|
| POST | `/` | Cria link de pagamento na InfinitePay | Desmilitarizado |
| GET | `/` | Lista todos os checkouts (mais recente primeiro) | Desmilitarizado |
| GET | `/{external_id}/` | Consulta checkout por external_id; retorna receipt_url se pago | Desmilitarizado |

### `api/config.py` — prefixo `/api/v1/config`
| Método | Rota | Descrição | Tipo |
|--------|------|-----------|------|
| GET | `/` | Retorna configuração atual (handle, preços, URLs) | Desmilitarizado |
| PATCH | `/` | Atualiza campos da configuração parcialmente | Desmilitarizado |

### `api/webhooks.py` — prefixo `/api/v1/webhook`
| Método | Rota | Descrição | Tipo |
|--------|------|-----------|------|
| POST | `/` | Recebe webhook server-to-server da InfinitePay com `?external_id=` criptografado | Público |
| GET | `/` | Consulta status de checkout por `?order_nsu=` | Público |

### `api/ask.py` — prefixo `/api/v1/ask`
| Método | Rota | Descrição | Tipo |
|--------|------|-----------|------|
| POST | `/` | Pergunta em linguagem natural sobre checkouts (DeepSeek) — **marcado para remoção** | Desmilitarizado |

### `api/report.py` — prefixo `/api/v1/report`
| Método | Rota | Descrição | Tipo |
|--------|------|-----------|------|
| POST | `/` | Gera relatório executivo daily/weekly/full (DeepSeek) — **marcado para remoção** | Desmilitarizado |

---

## Dados

**Schema Postgres:** `infinitepay`  
**Shadow table cross-schema:** `auth.users(external_id UUID PK)` — lida como read-only via FK.

| Tabela | PK | Campos-chave | Observações |
|--------|-----|-------------|-------------|
| `config` | `id` (Integer) | `handle`, `price`, `quantity`, `description`, `redirect_url`, `backend_webhook`, `public_api_url` | Singleton (row id=1); seeded via `.env` no lifespan |
| `checkouts` | `id` (Integer) | `external_id` UUID (FK→auth.users RESTRICT, UNIQUE), `checkout_url` TEXT, `is_paid` bool, `receipt_url`, `invoice_slug`, `transaction_nsu`, `request_payload` JSON, `response_payload` JSON | 1:1 com usuário |
| `webhook_logs` | `id` (Integer) | `external_id` UUID (FK→auth.users SET NULL), `direction`, `kind`, `status_code`, `payload` JSON | Auditoria de webhooks in/out |
| `outbound_jobs` | `id` (Integer) | `url`, `payload` JSON, `external_id`, `attempts`, `max_attempts`, `next_attempt_at`, `delivered_at`, `last_error` | Fila de reenvio com retry exponencial |

**Migrações Alembic:** 2 versões (`0001` schema inicial, `0002` widen url columns para TEXT).

---

## Integrações

### Externas
| Serviço | Client | Operações |
|---------|--------|-----------|
| InfinitePay API (`api.checkout.infinitepay.io`) | `integrations/infinitepay_client.py` via `httpx.Client` **síncrono** | `POST /links` (criar checkout), `POST /payment_check` (verificar pagamento) |
| DeepSeek API (`api.deepseek.com`) | `ai/client.py` via `openai.OpenAI` | Perguntas analíticas e relatórios — chamada **direta** sem passar pelo app `ai` |

### Internas
| Serviço | Client | Uso |
|---------|--------|-----|
| `ai` (interno, `http://ai:8000`) | `ai/ai_service_client.py` via httpx | Usado por `ai/receipt.py` e `ai/monitor.py` (sem tool calling) |

---

## Pendências

### Arquivo `app/ai/TODO`
> "Com bastante cuidado remova toda essa questão de ia que tem neste app, ficou algo bem sem sentido..."

### TODOs no código
| Arquivo | TODO |
|---------|------|
| `models/models.py:34` | `#TODO: REMOVA, coloque lógica em .env` — tabela `config` inteira deve ser eliminada |
| `api/config.py:9` | `#TODO: Remova isso, configuração e outras deve estar em .env` — endpoints GET/PATCH config |
| `api/ask.py:20` | `#TODO: Remova` — endpoint POST /ask |
| `api/report.py:7` | `#TODO REMOVA` — endpoint POST /report |
| `ai/client.py:9` | `#TODO: Lógica duplicada` — client DeepSeek duplicado em vez de usar app `ai` |

### Desvios da CONVENTION

| # | Desvio | Severidade |
|---|--------|-----------|
| 1 | **Aninhamento indevido** `infinitepay/infinitepay/app` — viola §3 | Alta |
| 2 | **`db.py` usa engine síncrono** (`create_engine`, `sessionmaker`, `Session`) — viola §4 (async obrigatório) | Crítica |
| 3 | **`database_url` usa `psycopg2`** em vez de `asyncpg` (`postgresql+psycopg2://`) — viola §4 | Crítica |
| 4 | **`config.py` usa `lru_cache`** em vez de padrão `get_settings()` cacheado via `@lru_cache` — ok, é o mesmo padrão, sem desvio |
| 5 | **IA chamada diretamente** via `openai.OpenAI` + DeepSeek — viola §13 (deve ir via app `ai`) | Alta |
| 6 | **`main.py` usa `logging` cru** (`import logging`) em vez de `structlog` — viola §2 | Média |
| 7 | **`integrations/infinitepay_client.py` usa `httpx.Client` síncrono** — viola §2 (usar `httpx.AsyncClient`) | Alta |
| 8 | **PKs são Integer** em vez de UUID — viola §4 (`PK = UUID`) | Alta |
| 9 | **Tabela `config` e endpoints `/config`** devem ser removidos; config deve vir exclusivamente de `.env` | Alta |
| 10 | **Módulo `ai/`** inteiro marcado para remoção; endpoints `/ask` e `/report` idem | Alta |
| 11 | **`NAMING_CONVENTION`** para constraints não está definida em `db.py` — viola §4 | Média |
