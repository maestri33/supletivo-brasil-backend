# asaas-app — Documentação da API v0.1.0

Middleware de pagamentos PIX sobre a API Asaas v3 — **somente produção** (`$aact_prod_*`).

**Base URL:** `https://asaas.v7m.net` | **OpenAPI:** `/openapi.json` | **Swagger:** `/docs` | **ReDoc:** `/redoc`

---

## ⚙️ Fluxo de Onboarding

1. `POST /api/v1/config/url` — registra URL pública, obtém `verify_url`
2. Acesse a `verify_url` retornada para confirmar o domínio
3. `POST /api/v1/config/internal` — URL interna que receberá notificações de status
4. `POST /api/v1/config/key` — salva API key Asaas, retorna `security_token` + instruções
5. Configure o token e a URL validadora no painel Asaas (Mecanismo de Segurança)
6. `POST /api/v1/config/key/confirm` — registra o webhook em `<url>/webhook/`

---

## 📊 Dashboard

### `GET /`
Dashboard HTML com status da conta, saldo Asaas, badges de pagamentos por status e links para documentação.

### `GET /healthz`
Health check. Resposta:
```json
{"app": "asaas-app", "status": "up", "version": "0.1.0"}
```

---

## 🔁 Máquina de Estados

```
SCHEDULED → QUEUED → SUBMITTING → SUBMITTED → PAID
                 ↘ AWAITING_BALANCE ↗         ↘ FAILED
                                               ↘ CANCELLED
```

| Status | Significado |
|---|---|
| `SCHEDULED` | Agendado para data/hora futura (America/Sao_Paulo) |
| `QUEUED` | Pronto para submeter ao Asaas |
| `SUBMITTING` | Claim atômico local; chamada ao Asaas em andamento |
| `SUBMITTED` | Asaas aceitou; aguardando webhook `TRANSFER_DONE` |
| `AWAITING_BALANCE` | Saldo insuficiente; reprocessado automaticamente a cada 30s |
| `PAID` | `TRANSFER_DONE` recebido via webhook |
| `FAILED` | Erro permanente (chave inválida, `TRANSFER_FAILED`, etc) |
| `CANCELLED` | Cancelado pelo usuário |

---

## 🔔 Notificação Interna

A cada transição de status, o app envia `POST` para a `internal_url` configurada:

```json
{
  "payment_id": "pay_a1b2c3d4e5f6a7b8",
  "kind": "pixkey",
  "external_id": "0f41a42a-cf2d-425d-8912-c865a55ec1b6",
  "status": "SUBMITTED"
}
```

| Campo | Descrição |
|---|---|
| `payment_id` | ID do pagamento (`pay_` + 16 hex) |
| `kind` | `"pixkey"` (external_id preenchido) ou `"qrcode"` (external_id `null`) |
| `external_id` | UUID da pixkey (só para `kind=pixkey`) |
| `status` | Um dos 8 status da máquina de estados |

Deduplicação: `AWAITING_BALANCE` só dispara na primeira transição, não nos retries do worker.

---

## 📦 Formato de Erros

Todos os erros de domínio retornam `HTTP 4xx/5xx` com corpo:

```json
{"detail": "<codigo>"}
```

Quando o código tem contexto dinâmico, usa prefixo + `:` + detalhe:
```json
{"detail": "holder_mismatch: expected 074... got 123..."}
```

### Catálogo de Erros

#### `payment`
| Código | Significado |
|---|---|
| `pixkey_not_found` | external_id da pixkey não cadastrado |
| `invalid_amount` | amount <= 0 |
| `invalid_date` | Data inválida |
| `payment_id_already_exists` | ID idempotente já usado |
| `not_found` | Pagamento não existe |
| `cannot_cancel_status` | Status atual não permite cancelamento |
| `asaas_cancel_failed` | Asaas rejeitou o cancelamento |
| `invalid_qrcode_payload` | BR Code inválido ou muito curto |
| `qrcode_amount_required` | QR sem valor fixo exige amount |
| `qrcode_fixed_amount_mismatch` | Amount diverge do valor fixo do QR |
| `dynamic_qrcode_scheduling_not_supported` | QR dinâmico não pode ser agendado |
| `invalid_kind` | kind deve ser `pixkey` ou `qrcode` |
| `invalid_status` | status informado nao e valido |
| `cannot_delete_status` | DELETE so permitido para SCHEDULED e AWAITING_BALANCE |

#### `pixkey`
| Código | Significado |
|---|---|
| `external_id_required` | external_id vazio |
| `invalid_key_type` | Tipo não suportado (use: CPF, CNPJ, EMAIL, PHONE, EVP) |
| `invalid_cpf_format` | CPF deve ter 11 dígitos |
| `invalid_cnpj_format` | CNPJ deve ter 14 dígitos |
| `invalid_email_format` | Email sem @ ou domínio |
| `invalid_phone_format_expected_+55DDDNNNNNNNNN` | Telefone fora do padrão |
| `invalid_evp_format` | EVP deve ter 36 caracteres com 4 hifens |
| `invalid_document_length` | Documento deve ter 11 ou 14 dígitos |
| `external_id_already_exists` | external_id duplicado |
| `pix_key_already_registered` | Chave PIX já cadastrada |
| `dict_lookup_failed` | Falha na consulta DICT do Asaas |
| `holder_mismatch` | Documento não confere com titular da chave |
| `not_found` | PixKey não encontrada |
| `asaas_api_key_not_set` | API key Asaas não configurada |

#### `config`
| Código | Significado |
|---|---|
| `production_key_required` | API key precisa começar com `$aact_prod_` |
| `asaas_rejected_key` | Asaas rejeitou a API key |
| `set_key_not_done` | Precisa chamar `/config/key` antes |
| `external_url_not_set` | Precisa configurar URL pública antes |
| `nonce_not_found_or_expired` | Link de verificação expirado ou inválido |
| `invalid_token` | Token de segurança inválido (webhook/validator) |

---

## 🔗 Endpoints — Config (`/api/v1/config`)

### `POST /api/v1/config/url`
Registra a URL pública base do app. Retorna link de verificação (nonce único, TTL 600s).

**Request:**
```json
{"url": "https://asaas.v7m.net"}
```

**Response `200`:**
```json
{
  "external_url": "https://asaas.v7m.net",
  "verify_url": "https://asaas.v7m.net/api/v1/config/url/verify/abc123def456",
  "message": "Acesse a verify_url para confirmar o dominio"
}
```

### `GET /api/v1/config/url/verify/{nonce}`
Callback de verificação de domínio. Consome o nonce (single-use). Redireciona para `GET /api/v1/config/status`.

### `POST /api/v1/config/internal`
Registra a URL interna que receberá notificações de status. Envia um POST de onboarding com a documentação do formato.

**Request:**
```json
{"url": "http://10.10.10.129/"}
```

**Response `200`:**
```json
{"ok": true, "status_code": 200}
```

### `POST /api/v1/config/key`
Salva a API key Asaas (production-only). Retorna o `security_token` para configurar no painel Asaas.

**Request:**
```json
{"api_key": "$aact_prod_XXXXXXXXXXXXXXXXXXX"}
```

**Response `200`:**
```json
{
  "security_token": "abc123...",
  "account": {
    "name": "V7M EMPRESARIAL LTDA",
    "email": "financeiro@v7m.net",
    "walletId": "00000000-0000-0000-0000-000000000000"
  }
}
```

### `POST /api/v1/config/key/confirm`
Após configurar o Mecanismo de Segurança no painel Asaas, registra o webhook oficial em `<external_url>/webhook/`.

**Response `200`:**
```json
{
  "webhook_registered": {
    "id": "wh_...",
    "url": "https://asaas.v7m.net/webhook/",
    "name": "asaas-app",
    "enabled": true
  }
}
```

### `GET /api/v1/config/status`
Status completo da configuração (sem expor secrets).

**Response `200`:**
```json
{
  "configured": {
    "external_url": "https://asaas.v7m.net",
    "internal_url": "http://10.10.10.129/",
    "asaas_api_key": "masked",
    "asaas_security_token": "masked",
    "asaas_wallet_id": "...",
    "asaas_account_name": "V7M EMPRESARIAL LTDA",
  },
  "account": {"name": "V7M EMPRESARIAL LTDA", "email": "..."},
  "balance": {"balance": 1234.56},
  "webhook_registered": {"url": "https://asaas.v7m.net/webhook/", "enabled": true},
  "errors": []
}
```

---

## 🔑 Endpoints — PixKey (`/api/v1/pixkey`)

### `POST /api/v1/pixkey`
Cadastra e valida uma chave PIX via DICT do Asaas.

**Request:**
```json
{
  "external_id": "victor_celular",
  "document": "07426367980",
  "key": "+5543996648750",
  "key_type": "PHONE"
}
```

**Response `200`:**
```json
{
  "external_id": "victor_celular",
  "key": "+5543996648750",
  "key_type": "PHONE",
  "holder_document": "***.263.679-**",
  "holder_name": "VICTOR VANDERLEY MAESTRI",
  "bank_name": "BANCO C6 S.A.",
  "validated_at": "2026-05-05T12:00:00"
}
```

**Erros:** `400` — `invalid_key_type`, `external_id_already_exists`, `pix_key_already_registered`, `holder_mismatch`

### `GET /api/v1/pixkey`
Lista todas as chaves cadastradas (paginação: `?limit=200&offset=0`).

**Response `200`:**
```json
[
  {
    "external_id": "victor_celular",
    "key": "+5543996648750",
    "key_type": "PHONE",
    "holder_document": "***.263.679-**",
    "holder_name": "VICTOR VANDERLEY MAESTRI",
    "bank_name": "BANCO C6 S.A.",
    "validated_at": "2026-05-05T12:00:00"
  }
]
```

### `GET /api/v1/pixkey/{external_id}`
Consulta uma chave específica pelo external_id.

**Erros:** `404` — `not_found`

### `DELETE /api/v1/pixkey/{external_id}`
Remove uma chave cadastrada.

**Response `200`:**
```json
{"ok": true}
```

**Erros:** `404` — `not_found`

### `GET /api/v1/pixkey/check/{key}`
Verifica uma chave PIX (DB first, fallback DICT). Não persiste.

**Response `200`:**
```json
{
  "source": "db",
  "data": {
    "key": "+5543996648750",
    "holder_document": "***.263.679-**",
    "holder_name": "VICTOR VANDERLEY MAESTRI",
    "bank_name": "BANCO C6 S.A."
  }
}
```

`source` = `"db"` (cadastrada localmente) ou `"dict"` (lookup online).

---

## 💰 Endpoints — Payment (`/api/v1/payment`)

### `POST /api/v1/payment`
Cria pagamento imediato por pixkey.

**Request:**
```json
{
  "external_id": "victor_celular",
  "amount": 0.03,
  "payment_id": "meu_id_idempotente_20260505",
  "description": "Pagamento salario maio/2026"
}
```

| Campo | Obrigatório | Descrição |
|---|---|---|
| `external_id` | Sim | external_id da pixkey cadastrada |
| `amount` | Sim | Valor em BRL (> 0) |
| `payment_id` | Não | ID idempotente (cliente controla dedup) |
| `description` | Não | Descrição enviada ao Asaas |

**Response `200`:** `PaymentResponse` (ver schema abaixo)

**Erros:** `400` — `pixkey_not_found`, `invalid_amount`, `payment_id_already_exists`

---

### `POST /api/v1/payment/scheduled`
Agenda pagamento por pixkey para data/hora futura (timezone America/Sao_Paulo).

**Request:**
```json
{
  "external_id": "victor_celular",
  "amount": 1.50,
  "date": "2026-05-10",
  "hour": 16,
  "minute": 15,
  "payment_id": "agendamento_20260510",
  "description": "Pagamento agendado"
}
```

| Campo | Obrigatório | Descrição |
|---|---|---|
| `date` | Sim | `YYYY-MM-DD` |
| `hour` | Não | 0-23 (default 8) |
| `minute` | Não | 0-59 (default 0) |

**Response `200`:** `PaymentResponse` com `status: "SCHEDULED"` e `scheduled_for` preenchido.

**Erros:** `400` — `pixkey_not_found`, `invalid_amount`, `invalid_date`, `payment_id_already_exists`

---

### `POST /api/v1/payment/qrcode`
Cria pagamento imediato por QR Code (BR Code copia-e-cola).

**Regras:**
- QR com valor fixo (tag 54): **não aceita** `amount` diferente
- QR sem valor fixo: **exige** `amount`
- QR dinâmico: **não pode** ser agendado

**Request (QR com valor fixo):**
```json
{
  "qrcode_payload": "00020126360014br.gov.bcb.pix0114+554299938406952040000530398654040.025802BR...",
  "description": "Pagamento via QR Code"
}
```

**Request (QR sem valor fixo — amount obrigatório):**
```json
{
  "qrcode_payload": "00020126360014br.gov.bcb.pix...",
  "amount": 50.00,
  "description": "Pagamento via QR Code"
}
```

**Erros:** `400` — `invalid_qrcode_payload`, `qrcode_amount_required`, `qrcode_fixed_amount_mismatch`, `invalid_amount`, `payment_id_already_exists`

---

### `POST /api/v1/payment/qrcode/scheduled`
Agenda pagamento por QR Code (apenas QR estático).

**Request:** Igual ao `/qrcode` + campos `date`, `hour?`, `minute?`

**Erros:** `400` — mesmos do `/qrcode` + `dynamic_qrcode_scheduling_not_supported`, `invalid_date`

---

### `POST /api/v1/payment/qrcode/analyze`
Analisa BR Code sem pagar — parse TLV técnico.

**Request:**
```json
{
  "qrcode_payload": "00020126360014br.gov.bcb.pix0114+554299938406952040000530398654040.025802BR..."
}
```

**Response `200`:**
```json
{
  "valid_tlv": true,
  "kind": "static",
  "point_of_initiation_method": null,
  "amount": 0.01,
  "allows_amount_edit": false,
  "can_schedule": true,
  "pix_key": "+5542999384069",
  "dynamic_url": null,
  "merchant_name": "VICTOR VANDERLEY MAESTRI",
  "merchant_city": null,
  "reference": null,
  "has_crc": false,
  "warnings": ["crc_missing"],
  "raw_fields": {},
  "merchant_account_fields": {},
  "additional_data_fields": {}
}
```

---

### `GET /api/v1/payment`
Lista pagamentos. Ordenado do mais recente para o mais antigo.

**Query params:**

| Parâmetro | Default | Descrição |
|---|---|---|
| `limit` | 200 | Máximo 500 |
| `offset` | 0 | Paginação |
| `kind` | — | `pixkey` ou `qrcode`. Se omitido, retorna ambos. |
| `status` | — | `SCHEDULED`, `QUEUED`, `SUBMITTING`, `SUBMITTED`, `AWAITING_BALANCE`, `PAID`, `FAILED`, `CANCELLED`. Se omitido, retorna todos. |

**Response `200`:** `[PaymentResponse, ...]`

**Erros:** `400` — `invalid_kind`, `invalid_status`

---

### `GET /api/v1/payment/awaiting-balance`
Lista pagamentos com status `AWAITING_BALANCE` (aguardando saldo).

**Response `200`:** `[PaymentResponse, ...]`

---

### `GET /api/v1/payment/awaiting-balance/sum`
Soma dos valores de todos os pagamentos em `AWAITING_BALANCE`.

**Response `200`:**
```json
{"status": "AWAITING_BALANCE", "count": 3, "total": 150.75}
```

---

### `DELETE /api/v1/payment/{payment_id}`
Cancela localmente um pagamento agendado ou aguardando saldo. Dispara notificacao interna.

**Só permitido para:** `SCHEDULED`, `AWAITING_BALANCE`.

**Response `200`:** `PaymentResponse` com `status: "CANCELLED"`

**Erros:** `400` — `cannot_delete_status` | `404` — `not_found`

---

### `GET /api/v1/payment/{payment_id}`
Consulta um pagamento específico.

**Response `200`:** `PaymentResponse`

**Erros:** `404` — `not_found`

---

### `POST /api/v1/payment/{payment_id}/cancel`
Cancela um pagamento (local se SCHEDULED/QUEUED; chama Asaas se SUBMITTED).

**Response `200`:** `PaymentResponse` com `status: "CANCELLED"`

**Erros:** `400` — `cannot_cancel_status`, `asaas_cancel_failed` | `404` — `not_found`

---

### PaymentResponse Schema

```json
{
  "payment_id": "pay_a1b2c3d4e5f6a7b8",
  "kind": "pixkey",
  "external_id": "victor_celular",
  "qrcode_payload": null,
  "amount": 0.03,
  "description": "Pagamento salario maio/2026",
  "scheduled_for": null,
  "status": "SUBMITTED",
  "asaas_id": "ce044b8c-e226-48a6-b5b8-f09269096962",
  "last_error": null,
  "created_at": "2026-05-05T12:06:32",
  "updated_at": "2026-05-05T12:06:53"
}
```

| Campo | Tipo | Descrição |
|---|---|---|
| `payment_id` | string | ID do pagamento (`pay_` + 16 hex) |
| `kind` | string | `"pixkey"` ou `"qrcode"` |
| `external_id` | string\|null | UUID da pixkey (null para qrcode) |
| `qrcode_payload` | string\|null | BR Code original (null para pixkey) |
| `amount` | float | Valor em BRL |
| `description` | string\|null | Descrição do pagamento |
| `scheduled_for` | string\|null | ISO 8601 da data agendada (UTC) |
| `status` | string | Status atual da máquina de estados |
| `asaas_id` | string\|null | ID da transferência no Asaas |
| `last_error` | string\|null | Último erro registrado |
| `created_at` | string | ISO 8601 de criação |
| `updated_at` | string | ISO 8601 da última atualização |

---

## 🔐 Endpoints — Asaas Inbound (raiz, não versionados)

### `POST /webhook/`
Recebe eventos do Asaas. **Header obrigatório:** `asaas-access-token`.

Eventos processados:
- `TRANSFER_DONE` → status `PAID`
- `TRANSFER_FAILED` → status `FAILED`

**Headers:**
```
asaas-access-token: <security_token>
```

**Erros:** `401` — `invalid_token`

### `POST /security-validator`
Validação do Mecanismo de Segurança Asaas. **Header obrigatório:** `asaas-access-token`.

Retorna `200` se o token confere, `401` caso contrário.

---

## 📐 Arquitetura

```
                      ┌── asaas.v7m.net (público)
                      │   Só 3 rotas: /webhook/, /security-validator,
                      │              /api/v1/config/url/verify/*
Asaas ──→ internet ──┤
                      └── asaas.internal.v7m.net (rede local)
                          Acesso completo ao microsserviço

                          │
                     Caddy (LXC separada)
                          │
                          ▼
                    uvicorn :80 (esta LXC)
                    ├── /api/v1/*      (FastAPI)
                    ├── /webhook/       (Asaas inbound)
                    ├── /               (Dashboard HTML)
                    └── worker loop     (asyncio, 30s tick)

Asaas API v3 ←── app/integrations/asaas_client.py
SQLite         ←── app/db.py (SessionLocal)
Notificações   ──→ internal_url (POST JSON)
```

### Worker Loop
Task asyncio no próprio uvicorn, tick a cada 30 segundos:
1. Move `SCHEDULED` cujo `scheduled_for <= now` → `QUEUED`
2. Para cada `QUEUED` ou `AWAITING_BALANCE`: chama `submit_one` (claim atômico → Asaas)
3. Reconcilia `SUBMITTED` (consulta status no Asaas, dispara notificação se mudou)

---

## 🔧 Configuração

### Variáveis de ambiente (`.env`)
```bash
# Database (opcional — default: sqlite:///data/app.db)
ASAAS_APP_DB_URL=sqlite:///data/app.db
```

### ConfigStore (persistido no SQLite)
| Key | Descrição |
|---|---|
| `external_url` | URL pública base |
| `internal_url` | URL para notificações |
| `asaas_api_key` | Asaas API key (`$aact_prod_*`) |
| `asaas_security_token` | Token Mecanismo de Segurança |
| `asaas_wallet_id` | Wallet ID Asaas |
| `asaas_account_name` | Nome da conta Asaas |

---

## 🔒 Segregação de Rotas (Caddy)

O asaas-app é um microsserviço interno. O Caddy (em outra LXC) faz proxy reverso e deve expor **apenas as 3 rotas que o Asaas chama**. Todo o resto fica acessível somente na rede interna.

### Rotas públicas (Asaas → internet)

São as únicas que o Caddy deve encaminhar via `asaas.v7m.net`:

| Método | Rota | Quem chama |
|---|---|---|
| `POST` | `/webhook/` | Asaas — notifica transferências |
| `POST` | `/security-validator` | Asaas — Mecanismo de Segurança |
| `GET` | `/api/v1/config/url/verify/{nonce}` | Navegador — verificação de domínio |

### Caddyfile exemplo

```caddy
# ============================================
# asaas.v7m.net — exposto publicamente
# ============================================
asaas.v7m.net {
    # Só permite as 3 rotas que o Asaas precisa chamar.
    # Tudo que nao bate retorna 403.

    @public path /webhook/ /webhook/*
    @public path /security-validator /security-validator/*
    @public path /api/v1/config/url/verify/*

    route {
        # Bloqueia qualquer rota nao listada acima
        respond @public 403

        reverse * asaas-app:80
    }
}

# ============================================
# asaas.internal.v7m.net — rede local apenas
# (nao resolve publicamente, DNS interno ou /etc/hosts)
# ============================================
asaas.internal.v7m.net {
    # Acesso completo ao microsservico
    reverse * asaas-app:80
}
```

### Resumo

| Domínio | Acesso | Exposto |
|---|---|---|
| `asaas.v7m.net` | Público | Só `/webhook/`, `/security-validator`, `/api/v1/config/url/verify/*` |
| `asaas.internal.v7m.net` | Rede interna | Acesso completo (dashboard, API, docs) |

> **Nota:** `asaas-app:80` é o nome do container/DNS interno. Ajuste para o IP real do microsserviço se não estiver usando service discovery.
