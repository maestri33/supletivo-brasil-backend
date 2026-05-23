# asaas — middleware PIX

Middleware FastAPI sobre a API Asaas v3. Suporta dois fluxos:

- **Payouts (saída)** — `kind=pixkey | qrcode` — transferência por chave PIX cadastrada ou pagamento de BR Code.
- **Charges (entrada)** — `kind=charge` — cobranças PIX recebidas via Asaas `/payments` com `billingType=PIX`.

> Documentação interativa completa: `/docs` (Swagger) e `/redoc` no container.
> Catálogo de endpoints + erros vive em [API.md](API.md).

## Stack

| | |
|---|---|
| Linguagem | Python 3.12 |
| Framework | FastAPI 0.115 |
| ORM | SQLAlchemy 2.0 async (`AsyncSession`) |
| Driver | asyncpg |
| Schema | `v7m.asaas` (Postgres central) |
| Migrations | Alembic |

## Configuração

### Variáveis de ambiente

```bash
# Database
ASAAS_APP_DB_URL=postgresql+asyncpg://v7m:v7m@postgres:5432/v7m   # obrigatório (vem do .env, sem default)

# Asaas
ASAAS_BASE_URL=https://api.asaas.com                # production (default)
# ou: https://sandbox.asaas.com                     # homologação
ASAAS_ALLOW_SANDBOX=false                           # true para aceitar $aact_hmlg_*

# Charges
ASAAS_APP_CHARGE_DEFAULT_DUE_DAYS=3                 # dias até vencimento por default
```

### Onboarding (uma vez por instância)

```bash
# 1. URL pública (gera link de verificação de domínio)
curl -X POST https://asaas.v7m.net/api/v1/config/url \
  -H "Content-Type: application/json" \
  -d '{"url":"https://asaas.v7m.net"}'
# -> abra a verify_url no browser para confirmar

# 2. URLs internas (uma por categoria de evento)
curl -X POST https://asaas.v7m.net/api/v1/config/internal \
  -H "Content-Type: application/json" \
  -d '{"url":"http://lead:8000/api/v1/webhook/charge","target":"charge"}'

curl -X POST https://asaas.v7m.net/api/v1/config/internal \
  -H "Content-Type: application/json" \
  -d '{"url":"http://payments:8000/scheduling","target":"scheduling"}'

curl -X POST https://asaas.v7m.net/api/v1/config/internal \
  -H "Content-Type: application/json" \
  -d '{"url":"http://payments:8000/payout","target":"payout"}'

# 3. API key Asaas (production-only por default, salvo ASAAS_ALLOW_SANDBOX=true)
curl -X POST https://asaas.v7m.net/api/v1/config/key \
  -H "Content-Type: application/json" \
  -d '{"api_key":"$aact_prod_xxxxxx"}'
# -> retorna security_token + instruções HTML

# 4. Configurar o Mecanismo de Segurança no painel Asaas, depois:
curl -X POST https://asaas.v7m.net/api/v1/config/key/confirm
```

## Cobrança PIX (charges)

### Criar cobrança

```bash
# Primeira chamada para um external_id: payer é obrigatório
curl -X POST https://asaas.v7m.net/api/v1/charge/pix \
  -H "Content-Type: application/json" \
  -d '{
    "external_id": "aluno_42",
    "amount": 250.00,
    "description": "Mensalidade junho/2026",
    "due_date": "2026-06-05",
    "payer": {
      "name": "Maria Aluna",
      "cpf_cnpj": "07426367980",
      "email": "maria@example.com",
      "mobile_phone": "+5543999999999"
    }
  }'
```

Resposta (HTTP 200):

```json
{
  "payment_id": "pay_a1b2c3d4e5f6a7b8",
  "external_id": "aluno_42",
  "amount": 250.00,
  "description": "Mensalidade junho/2026",
  "due_date": "2026-06-05",
  "status": "PENDING",
  "asaas_id": "pay_8120829379393283",
  "pix": {
    "payload": "00020126360014br.gov.bcb.pix...",
    "encoded_image": "iVBORw0KGgoAAAANSUhEUgA...",
    "expiration_date": null
  },
  "created_at": "2026-05-15T16:00:00",
  "updated_at": "2026-05-15T16:00:00"
}
```

Chamadas subsequentes para o **mesmo `external_id`** podem omitir `payer`:

```bash
curl -X POST https://asaas.v7m.net/api/v1/charge/pix \
  -H "Content-Type: application/json" \
  -d '{"external_id":"aluno_42","amount":50.00,"description":"Material"}'
```

### Consultar / cancelar

```bash
# Cobrança completa (com BR Code e QR Code base64)
curl https://asaas.v7m.net/api/v1/charge/pay_a1b2c3d4e5f6a7b8

# Versão leve — só status (para polling)
curl https://asaas.v7m.net/api/v1/charge/pay_a1b2c3d4e5f6a7b8/status
# -> {"payment_id":"...","status":"PAID","asaas_id":"...","updated_at":"..."}

# Re-buscar QR Code no Asaas (refresh)
curl -X POST https://asaas.v7m.net/api/v1/charge/pay_a1b2c3d4e5f6a7b8/qr

# Cancelar (só PENDING)
curl -X DELETE https://asaas.v7m.net/api/v1/charge/pay_a1b2c3d4e5f6a7b8
```

### Listar

```bash
# Filtros: status, external_id, limit, offset
curl "https://asaas.v7m.net/api/v1/charge?status=PENDING&external_id=aluno_42&limit=50"
```

## Máquina de estados — charge

```
PENDING ──── PAYMENT_CONFIRMED|PAYMENT_RECEIVED ────► PAID
   │
   ├──── PAYMENT_OVERDUE ────────────────────────────► EXPIRED
   │
   ├──── DELETE /charge ou PAYMENT_DELETED ──────────► CANCELLED
   │
   └──── PAYMENT_REFUNDED (após PAID) ───────────────► REFUNDED
```

## Webhook do Asaas

O Asaas chama `POST /webhook/` (header `asaas-access-token`). O handler:

1. Persiste o evento bruto em `webhook_event`
2. Roteia:
   - `TRANSFER_*` → bridge de payouts (existente)
   - `PAYMENT_*` → bridge de charges (novo)
3. Atualiza o `Payment.status` correspondente e dispara notificação interna

## Notificações internas — 3 destinos

Cada transição de status faz `POST` ao destino apropriado:

| Evento | Destino | Configurar com |
|---|---|---|
| Charge: PENDING, PAID, EXPIRED, CANCELLED, REFUNDED | `internal_url_charge` | `target=charge` |
| Outbound criado/scheduled: SCHEDULED, QUEUED | `internal_url_scheduling` | `target=scheduling` |
| Outbound execução: SUBMITTED, PAID, FAILED, AWAITING_BALANCE, CANCELLED | `internal_url_payout` | `target=payout` |

Fallback: se uma URL específica não está setada, cai em `internal_url` (legacy catch-all, `target=default`).

Payload comum (POST JSON):

```json
{
  "payment_id": "pay_...",
  "kind": "pixkey | qrcode | charge",
  "external_id": "aluno_42 | null",
  "status": "PAID"
}
```

## Desenvolvimento

```bash
# Instalar deps
uv sync

# Rodar testes
uv run pytest

# Coverage do novo código
uv run pytest --cov=app.services.charge --cov=app.services.customer \
              --cov=app.services.notifications --cov-report=term-missing

# Lint
uv run ruff format app/ tests/
uv run ruff check app/ tests/

# Migrations
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "..."
```

## Erros do domínio charge

| Código | HTTP | Significado |
|---|---|---|
| `invalid_amount` | 400 | amount <= 0 |
| `invalid_due_date` | 400 | due_date no passado ou fora do formato YYYY-MM-DD |
| `invalid_cpf_cnpj` | 400 | cpf_cnpj deve ter 11 (CPF) ou 14 (CNPJ) dígitos |
| `customer_required` | 400 | external_id novo sem payer no body |
| `asaas_customer_create_failed` | 400 | Asaas rejeitou create customer (ver sufixo) |
| `asaas_charge_create_failed` | 400 | Asaas rejeitou create payment (ver sufixo) |
| `asaas_charge_delete_failed` | 400 | Asaas rejeitou DELETE da cobrança |
| `asaas_qr_fetch_failed` | 400 | Asaas falhou ao retornar BR Code/QR |
| `cannot_cancel_status` | 400 | Cobrança em estado terminal |
| `payment_id_already_exists` | 400 | payment_id duplicado (idempotência) |
| `not_found` | 404 | payment_id não existe |
