# Integrações — asaas

> Toda integração externa mora em `app/integrations/` (§12). O fluxo não quebra
> por falha de integração quando houver alternativa segura.

## Asaas — API v3 (externa)
- **Client:** `app/integrations/asaas_client.py` (`AsaasClient`, `httpx.AsyncClient`).
- **Base URL:** `ASAAS_BASE_URL` (default `https://api.asaas.com`,
  **production-only** salvo `ASAAS_ALLOW_SANDBOX=true` p/ chaves `$aact_hmlg_`).
- **API key:** vem da tabela `asaas.config` (`config_store`), não do `.env`
  direto após o bootstrap.
- **Usado por:** `services/{payment,pixkey,charge,customer,config_key}.py`.
- **Fluxos:** customers + payments (charges, entrada) e transfers (payouts,
  saída). Idempotência de payout: `asaas_id` commitado antes de confirmar.
- É o **único** serviço autorizado a falar com o Asaas (§12).

## Webhook do Asaas (entrada — público externo)
- `POST /webhook/` com header `asaas-access-token`, validado por
  `services/security_validator.py` (o "Mecanismo de Segurança" do Asaas;
  onboarding via `POST /api/v1/config/key` + `/key/confirm`).
- Persiste `webhook_event` (bruto + `source_ip`/`user_agent` via `utils/net.py`)
  e roteia `TRANSFER_*` (payouts) / `PAYMENT_*` (charges).

## Notificações internas (saída — desmilitarizado)
- `services/notifications.py` faz POST a cada transição de status:
  - `ASAAS_INTERNAL_URL_CHARGE` (`target=charge`)
  - `ASAAS_INTERNAL_URL_SCHEDULING` (`target=scheduling`)
  - `ASAAS_INTERNAL_URL_PAYOUT` (`target=payout`)
  - fallback `ASAAS_INTERNAL_URL` (`target=default`).
- URLs configuradas via `.env` (bootstrap) ou `POST /api/v1/config/internal`.

## Verificação de URL externa
- `POST /api/v1/config/url` gera um `url_verify_nonce` (TTL
  `URL_VERIFY_NONCE_TTL`) para confirmar o domínio público antes de registrar o
  webhook no Asaas.

## Banco (cross-schema)
- Schema próprio `asaas`. **Sem FK cross-schema:** `external_id` é fornecido
  pelo cliente (string), não é o `external_id` do `auth`.
