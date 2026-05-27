# Integrações — fees

> Todas em `app/integrations/` (§12). Client base: `BaseClient` +
> `request_with_retry` (em `integrations/__init__.py`).

## asaas (`integrations/asaas.py`)

Dono **exclusivo** da integração Asaas/PIX (§12) — o fees nunca fala com a API
Asaas direto. Endpoints do serviço v7m-`asaas` (não da API pública):

- `POST /api/v1/payment/qrcode` — paga BR Code agora (parte à vista).
- `POST /api/v1/payment/qrcode/scheduled` — agenda QR estático (parte agendada).
- `GET /api/v1/payment/{payment_id}` — consulta status.

Envia `payment_id` determinístico (idempotente). Corpo: `qrcode_payload`,
`amount` (reais), `payment_id`, `description`; agendado acrescenta `date`
(YYYY-MM-DD), `hour`, `minute`.

## asaas → fees (out-webhook, entrada)

O asaas faz `POST` na URL configurada por categoria (`internal_url_payout` /
`internal_url_scheduling`) a cada transição, com
`{"payment_id", "kind", "external_id", "status"}`. Em payout de QR Code o
`external_id` vem **nulo** → correlação por `payment_id`. Receptor:
`POST /api/v1/webhook/asaas-payout` (desmilitarizado). Aceita o ping
`ASAAS_APP_ONBOARDING`. **Config do asaas** (operacional, não-código): apontar
essas URLs para o fees.

## notify (`integrations/notify.py`)

`POST /api/v1/messages/send` — `{external_id, content, flags?}`. Usado só nos
handlers de status (`app/notify/handlers.py`), sempre async (BackgroundTasks),
`max_retries=1` (envio não é idempotente). Falha só loga (§12).

## jwt (`dependencies.py`)

`GET /.well-known/jwks.json` (cache 5 min) para validar o JWT RS256 do
coordenador. Role exigida: `COORDINATOR_ROLE` (default `coordinator`).
