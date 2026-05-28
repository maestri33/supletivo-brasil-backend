# fees

Serviço de **taxas de matrícula**. O coordenador do polo registra, por aluno,
uma taxa com **dois payouts PIX por QR Code** (à vista + agendado), executados
pelo serviço `asaas`. O status é derivado dos pagamentos; quando a parte à vista
é paga, o acesso à plataforma fica liberável. Doc completa: `../wiki/fees.md`.

## Rodar

```bash
make install          # uv sync
cp .env.example .env  # ajuste DATABASE_URL (obrigatório) e as *_BASE_URL
make migrate          # alembic upgrade head — cria o schema fees
make run              # uvicorn :8000
make test             # 13 testes (sqlite, sem Postgres)
make lint             # ruff
```

## Variáveis (`.env`)

| Var | Obrigatória | Descrição |
|-----|:-:|-----------|
| `DATABASE_URL` | ✅ | Postgres async (`postgresql+asyncpg://...`) |
| `DATABASE_SCHEMA` | | schema (default `fees`) |
| `ASAAS_BASE_URL` | | URL do serviço `asaas` |
| `NOTIFY_BASE_URL` | | URL do serviço `notify` |
| `JWT_BASE_URL` | | URL do serviço `jwt` (JWKS) |
| `COORDINATOR_ROLE` | | role exigida (default `coordinator`) |

## Endpoints

Autenticados (JWT + role coordenador), prefixo `/api/v1/authenticated/fees`:

```bash
# Criar taxa (2 payouts: à vista + agendado)
curl -X POST localhost:8000/api/v1/authenticated/fees \
  -H "Authorization: Bearer <jwt>" -H "Content-Type: application/json" \
  -d '{
    "student_external_id": "<uuid-do-aluno>",
    "description": "Taxa de matrícula 2026/1",
    "upfront":   {"qrcode_payload": "<br-code>", "amount": 250.0},
    "scheduled": {"qrcode_payload": "<br-code>", "amount": 250.0,
                  "date": "2026-07-01", "hour": 8}
  }'

# Consultar
curl localhost:8000/api/v1/authenticated/fees/{fee_id}            -H "Authorization: Bearer <jwt>"
curl localhost:8000/api/v1/authenticated/fees/student/{ext_id}   -H "Authorization: Bearer <jwt>"
curl "localhost:8000/api/v1/authenticated/fees?status=FIRST_PAID" -H "Authorization: Bearer <jwt>"
```

Webhook do asaas (desmilitarizado) — configurar `internal_url_payout` /
`internal_url_scheduling` do asaas para cá:

```
POST /api/v1/webhook/asaas-payout   {"payment_id","kind","external_id","status"}
```
