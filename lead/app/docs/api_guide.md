---
name: supletivo-api
description: "API completa do Supletivo (produto operado pela V7M EMPRESARIAL LTDA) — captação de leads, OTP, pagamento PIX/cartão, notificação multicanal e webhooks. Use quando perguntarem sobre endpoints, fluxo de matrícula, integração de gateway, preço, descrição, webhook, deploy, ou debug de produção em api.v7m.org."
trigger: /supletivo-api
---

# Supletivo API — Plataforma de matrícula online

> **Convenção de nomes deste projeto:**
> - **V7M / V7M EMPRESARIAL LTDA** = empresa operadora (aparece em containers `v7m-*`, network `v7m_backend`, beneficiário Asaas, domínio público `api.v7m.org` por enquanto)
> - **Supletivo** = nome do produto (a plataforma educacional)
> - **lead, auth, notify, asaas, …** = nomes dos serviços (parts do produto)
> - O serviço `lead` é só a **captação inicial**. O produto vai expandir pra `candidate`, `enrollment`, `student`, etc. Quando este guia menciona "produto" leia "Supletivo"; quando menciona o "service `lead`" leia o microserviço específico de captação.

API multicanal de matrícula online: lead chega da landing page, valida CPF/telefone, recebe OTP, paga via PIX (Asaas) ou cartão até 12× (InfinitePay), confirma matrícula. Pagamentos disparam WhatsApp/Email no mesmo fluxo.

**Domínio público:** `https://api.v7m.org` (Caddy LXC 200) → docker compose LXC 201 (`10.1.30.20`)

---

## 1. Topologia de produção

```
┌──── public internet ────┐
│                         │
│  POST /api/v1/public/*  │ ── lead (anônimo: check, register, login, refresh)
│  GET  /api/v1/authenticated/* │ ── lead (JWT-gated: captured, waiting, checkout, completed)
│  POST /api/v1/webhook/* │ ── lead recebe callbacks Asaas/InfinitePay/notify
│  POST /webhook/         │ ── asaas (eventos PAYMENT_*)
│  POST /security-validator │ ── asaas (autorização de saídas)
│  GET  /api/v1/public/media/qrcodes/<png> │ ── QR PIX estático
│                         │
└──────────┬──────────────┘
           ↓ HTTPS (Caddy LXC 200, Let's Encrypt + Cloudflare DNS-01)
┌──────────┴──────────────┐
│  Proxmox LXC 201 (v7m)  │
│  10.1.30.20             │
│  /opt/v7m/              │
│  docker compose stack   │
└──┬──────────────────────┘
   │
   ├── v7m-caddy        :8081 público / :80 admin (DMZ via Tailscale)
   ├── v7m-lead         :8000 (porta exposta no Caddy)  ← orquestrador
   ├── v7m-auth         :8000 (interno)  ← external_id authority
   ├── v7m-jwt          :8000 (interno)  ← JWKS RS256
   ├── v7m-otp          :8000 (interno)  ← códigos descartáveis
   ├── v7m-notify       :8000 (interno)  ← WhatsApp + Email orchestrator
   ├── v7m-mail         :8000 (interno)  ← MailcowSMTPClient
   ├── v7m-whats-api    :8080 (interno)  ← Evolution API v2
   ├── v7m-profiles     :8000 (interno)  ← nome / CPF / dados cadastrais
   ├── v7m-roles        :8000 (interno)  ← transição lead→student
   ├── v7m-addresses    :8000 (interno)
   ├── v7m-enrollment   :8000 (interno)
   ├── v7m-promoter     :8000 (interno)
   ├── v7m-asaas        :8000 (interno)  ← cobrança PIX (api.asaas.com prod)
   ├── v7m-infinitepay  :8000 (interno)  ← cartão até 12× (checkout.infinitepay.io)
   ├── v7m-ai           :8000 (interno)  ← DeepSeek/Gemini/ElevenLabs
   ├── v7m-postgres     :5432 (interno)  ← 1 instância, schema-por-serviço
   └── v7m-redis        :6379 (interno)
```

**Cada serviço tem seu schema no mesmo Postgres** (`auth.*`, `lead.*`, `notify.*`, `infinitepay.*` etc.) — **NÃO** quebra a regra "cada serviço, seu banco" porque schemas são isolados via grants e FKs cross-schema.

---

## 2. Fluxo de captação (state machine)

```
LANDING PAGE                                  api.v7m.org
─────────────                                 ────────────
                                              
[1] Form CPF + telefone     ─POST─→  /api/v1/public/check
                            ←────  { found: false }     (não existia)
                                              
[2] Form completar         ─POST─→  /api/v1/public/register
                                    { phone, cpf, ref? }
                                    ↓
                                    auth → cria user (external_id UUID)
                                    profiles → CPFHub puxa nome+nascimento
                                    notify → cria contact (phone)
                                    lead → INSERT lead { status: CAPTURED }
                                    notify_lead_captured → WhatsApp+Email msg
                            ←────  { external_id, message: "OTP enviado" }
                                              
[3] Cliente recebe OTP via SMS/WhatsApp/Email (notify dispara)
                                              
[4] Form com OTP            ─POST─→  /api/v1/public/login
                                    { external_id, otp }
                            ←────  { access_token, refresh_token, status }
                                              
[5] App authenticated (Bearer access_token)
                                              
[6] Cliente preenche email + escolhe forma de pagamento
                            ─POST─→  /api/v1/authenticated/captured
                                    { email, name?, payment_method: "pix"|"credit_card" }
                                    ↓
                            ┌── if payment_method=pix ───────────────┐
                            │ asaas POST /charge/pix (síncrono)      │
                            │ retorna PIX copia-e-cola + QR PNG      │
                            │ lead → UPDATE status=CHECKOUT          │
                            │ notify dispara mensagem com QR+CTA     │
                            └── if payment_method=credit_card ───────┘
                              infinitepay POST /checkout/ (BG task)
                              retorna apenas message="aguarde"
                              frontend polla GET /demilitarized/checkouts/{ext_id}
                              quando checkout_url estiver pronto, retorna
                              lead → UPDATE status=CHECKOUT
                            ←────  { status, pix?: { payload, qr_url, payment_id } }
                                              
[7] Cliente paga (PIX ou cartão)
                                              
[8] Gateway dispara webhook  ─POST─→ /api/v1/webhook/asaas-charge (PIX)
                            ─POST─→ /api/v1/webhook/infinitepay   (cartão)
                                    ou /webhook/infinitepay  (alias curto)
                                    ↓
                                    lead → UPDATE status=COMPLETED
                                    roles → transition lead → student
                                    notify_payment_received → recibo
                                              
[9] App polla GET /api/v1/authenticated/completed
    confirma e mostra próximos passos
```

**Estados do `Lead.status`** (`services/lead/app/models/__init__.py`):

| Estado    | Significado                                         |
| --------- | --------------------------------------------------- |
| CAPTURED  | Cadastro feito, OTP enviado, falta logar+escolher   |
| WAITING   | (não usado no fluxo atual; reservado p/ checkpoint) |
| CHECKOUT  | Cobrança criada, aguardando pagamento               |
| COMPLETED | Pagamento confirmado, virou student                 |

---

## 3. Endpoints públicos do `lead` (única superfície externa)

### Anônimos — `/api/v1/public/*`

| Verb   | Path          | Quando usar                                           |
| ------ | ------------- | ----------------------------------------------------- |
| `POST` | `/check`      | Validar se CPF/phone/external_id existe + envia OTP   |
| `POST` | `/register`   | Criar lead novo (auth+profiles+notify+OTP no atômico) |
| `POST` | `/login`      | Trocar OTP por par `access_token`+`refresh_token`     |
| `POST` | `/refresh`    | Renovar tokens via `refresh_token`                    |

**Body do `/register`:**
```json
{
  "phone": "11999998888",
  "cpf": "12345678909",
  "ref": "uuid-do-promoter-opcional"
}
```

> **`ref` = código de indicação.** Padrão URL `?ref=<uuid>` (Stripe/YouTube/etc).
> É o UUID do promoter que indicou esse lead. Opcional — sem `ref`, o lead é
> atribuído ao `PROMOTER_DEFAULT` do servidor. Na landing, capture via
> `new URLSearchParams(location.search).get("ref")` e repasse no body.

> **Formato do `phone`:** **10 ou 11 dígitos, sem DDI** (sem o `55` do Brasil).
> Aceita máscara — caracteres não-numéricos (`(`, `)`, `-`, espaço) são removidos
> antes da validação. Exemplos válidos: `11999998888`, `(11) 99999-8888`,
> `1133334444`. **Inválidos:** `5511999998888` (13 dígitos, tem DDI),
> `+5511999998888`. A normalização pra E.164 (`+5511...`) acontece internamente
> nos serviços que falam com WhatsApp/Asaas — você não precisa enviar com DDI.

**Body do `/login`:**
```json
{
  "external_id": "uuid-do-register",
  "otp": "123456"
}
```

### JWT-gated — `/api/v1/authenticated/*`

Todos exigem header `Authorization: Bearer <access_token>`.

| Verb   | Path        | Função                                              |
| ------ | ----------- | --------------------------------------------------- |
| `POST` | `/captured` | Completa dados (email/nome) e gera cobrança        |
| `GET`  | `/captured` | Estado atual da fase captured                       |
| `GET`  | `/waiting`  | Estado da fase waiting                              |
| `GET`  | `/checkout` | Devolve `pix_payload`/`checkout_url` quando pronto |
| `GET`  | `/completed`| Confirma matrícula concluída                        |

**Body do `POST /captured`:**
```json
{
  "email": "aluno@exemplo.com",
  "name": "Nome Sobrenome",      
  "payment_method": "pix"        
}
```

- `name` é **imutável** se `profiles` já tem (CPFHub auto-popula no `register`)
- `payment_method`: `"pix"` (síncrono, retorna QR na hora) ou `"credit_card"` (BG, app polla)

**Resposta `/captured` com PIX:**
```json
{
  "status": "ok",
  "payment_method": "pix",
  "pix": {
    "payload": "00020101021226...6304XXXX",
    "qr_url": "https://api.v7m.org/api/v1/public/media/qrcodes/<file>.png",
    "payment_id": "pay_..."
  }
}
```

### Webhooks de entrada — `/api/v1/webhook/*`

| Verb   | Path                            | Quem chama                |
| ------ | ------------------------------- | ------------------------- |
| `POST` | `/asaas-charge`                 | Asaas (eventos PAYMENT_*) |
| `POST` | `/infinitepay`                  | InfinitePay (TX paga)     |
| `POST` | `/notify/{message_id}`          | notify reporta delivery   |

Aliases curtos pelo Caddy: `/webhook/infinitepay`, `/webhook/asaas-charge`, `/webhook/` (asaas).

---

## 4. Gateways de pagamento

### 4.1 PIX — Asaas (síncrono)

**Conta:** `V7M EMPRESARIAL LTDA` em produção (`api.asaas.com`).

**Endpoint interno:** `http://asaas:8000/api/v1/charge/pix`

**Modelo de preço:** valor em **REAIS DECIMAIS** (não centavos).

```python
# defaults em services/lead/app/config.py
PIX_DEFAULT_AMOUNT      = 999.99      # R$ 999,99
PIX_DEFAULT_DESCRIPTION = "Matrícula Supletivo: Material didático..."
PIX_DEFAULT_DUE_DAYS    = None        # delega ao ASAAS_APP_CHARGE_DEFAULT_DUE_DAYS
```

**Atenção: Asaas PROD exige mínimo R$ 5,00** — abaixo disso rejeita com `asaas_charge_create_failed`. Sandbox aceita qualquer.

**Resposta** traz:
- `pix.payload` — string copia-e-cola (BR Code EMV)
- `pix.encoded_image` — PNG base64 (lead salva em `/app/media/qrcodes/<file>.png` e expõe via Caddy público em `/api/v1/public/media/...`)
- `asaas_id` (`pay_xxxxx`) — id no Asaas
- `payment_id` (`pay_xxxxx`) — id local

**Link da fatura web** (página de pagamento Asaas):
```
https://www.asaas.com/i/{asaas_id_sem_prefixo}
```
Não vem na resposta padrão — buscar via `GET https://api.asaas.com/v3/payments/{asaas_id}` (campo `invoiceUrl`).

**Webhook:** Asaas POSTa em `https://api.v7m.org/webhook/` autenticado por header `asaas-access-token` (validado em `asaas-app`). Eventos relevantes: `PAYMENT_RECEIVED`, `PAYMENT_CONFIRMED`, `PAYMENT_OVERDUE`.

### 4.2 Cartão — InfinitePay (background)

**Conta:** handle `v7m` em `checkout.infinitepay.io`.

**Endpoint interno:** `http://infinitepay:8000/api/v1/checkout/`

**Modelo de preço:** valor em **CENTAVOS** (integer).

```json
{
  "handle": "v7m",
  "price": 99990,                                          // R$ 999,90 = base
  "quantity": 1,
  "description": "Matrícula Supletivo: Material didático...",
  "redirect_url": "https://api.v7m.org",
  "backend_webhook": "http://lead:8000/api/v1/webhook/infinitepay",
  "public_api_url": "https://api.v7m.org"
}
```

Config defaults vivem **na DB** (`infinitepay.config` schema). PATCH via:
```bash
curl -X PATCH http://infinitepay:8000/api/v1/config/ \
  -H "Content-Type: application/json; charset=utf-8" \
  -d '{"price": 99990, "description": "Matrícula Supletivo: Material didático..."}'
```

**Modelo de taxa do parcelamento (CRÍTICO):**

InfinitePay **adiciona 20% em cima do `price` quando o buyer parcela em 12×** (sem antecipação pra vendedor). Esse acréscimo é repassado ao buyer, **não** descontado do vendedor.

| `price` configurado | Buyer vê (12×)    | Você recebe (bruto) |
| ------------------- | ----------------- | ------------------- |
| 99990 (R$ 999,90)   | 12× R$ 99,99 = R$ 1.199,88 | R$ 999,90 |
| 119988 (R$ 1.199,88) | 12× R$ 119,98 = R$ 1.439,76 | R$ 1.199,88 |

**Equação:**
```
buyer_total_parcelado = price_em_reais × 1.20
parcela_12x           = buyer_total_parcelado / 12
```

Pra buyer ver parcela `P` em 12×, configurar `price = P × 12 / 1.20`. Pra **R$ 99,99 × 12** → `price = 999.90 = 99990 centavos`.

**Constraint do schema:** `external_id` da tabela `infinitepay.checkouts` é **UUID** e tem FK pra `auth.users.external_id`. Não dá pra criar checkout pra UUID inexistente — o sistema só cria checkout via fluxo lead (que já tem user). Pra testes manuais, usar um UUID que já existe em `auth.users`.

**Schema básico do POST:**
```json
{
  "external_id": "uuid-de-auth.users",
  "customer": {
    "name": "Nome Sobrenome",
    "email": "x@y.com",
    "phone_number": "11999998888"
  }
}
```

Resposta traz `checkout_url` (link clicável longo com query `?lenc=...`).

**Webhook:** InfinitePay POSTa em `https://api.v7m.org/webhook/infinitepay` (alias curto) ou no endpoint completo `/api/v1/webhook/?external_id=<encrypted>` configurado em `public_api_url`. Lead atualiza `is_paid=true`, `receipt_url`, `transaction_nsu`, `installments`, `capture_method`.

---

## 5. Notify — orquestrador multicanal

**Stack:** WhatsApp (Evolution API v2 → `whats-api`) + Email (MailcowSMTPClient `mail.v7m.org`) + TTS opcional (ElevenLabs via `ai`).

**POST `/api/v1/messages/send`** (interno, chamado pelo `lead`):
```json
{
  "external_id": "uuid",
  "context": "welcome|checkout|receipt|parabens",
  "channels": ["whatsapp","email"],
  "title": "Olá, João!",
  "body_md": "Markdown com {{first_name}}, {{amount}}, etc.",
  "flags": { "tts": true },
  "media_url": "data:image/png;base64,iVBOR...|https://..."
}
```

**Templates de email** (DB `notify.templates`): variantes por contexto com paleta diferente:
- `welcome` — azul (acolhimento)
- `checkout` — âmbar (CTA pagamento)
- `receipt` — verde (confirmação)
- `parabens` — roxo (celebração)
- `default` — fallback

Rodapé fixo: `supletivo.net.br`.

**Conversão de Markdown:**
- Pra WhatsApp: `**X**` → `*X*` (negrito WhatsApp)
- Pra HTML email: `**X**` e `*X*` → `<strong>X</strong>` (com negative-lookahead pra ignorar multiplicação)
- Pra TTS: strip asteriscos, prepend `title` no início pra evitar "começou no meio"

**Templates de mensagem (lead):**
- `services/lead/app/notify/messages/lead_captured.md` — boas-vindas, multicanal, urgência
- `services/lead/app/notify/messages/lead_receipt_pix.md` — confirmação PIX
- `services/lead/app/notify/messages/lead_receipt_cc.md` — confirmação cartão + recibo URL

**Renderização:** Jinja2-like `{{var}}` substitution feita em `notify` antes de enviar pros canais.

**Image inline no email:** quando `media_url` começa com `data:image/...`, notify decodifica base64, anexa como CID `notify-img-1`, e referencia inline (`<img src="cid:notify-img-1">`). Pra WhatsApp, envia como mídia separada.

**Encoding:** charset `utf-8` explicito em `set_content` e `add_alternative` (corrigido — antes vinha como `informa����es`).

**Callback de delivery:** notify POSTa em `{NOTIFY_CALLBACK_URL}/{message_id}` (default `http://lead:8000/api/v1/webhook/notify`). Sem isso, lead grava apenas `sent` ao receber 2xx do POST `/messages/send`, sem confirmar entrega real.

---

## 6. OTP — códigos descartáveis

**Service:** `otp` (porta 8000 interna)

**POST `/api/v1/otp`** — gera código (4-10 dígitos), grava com TTL, dispara notify:
```json
{ "external_id": "uuid", "kind": "register|login|recover" }
```

**POST `/api/v1/otp/check`** — valida código:
```json
{ "external_id": "uuid", "code": "123456" }
```

**Template de mensagem:** `services/otp/app/services/otp.md` — usa `{{first_name}}`, `{{code}}`, `{{ttl_minutes}}`. Rodapé customizável via `OTP_FOOTER` env (atualmente vazio).

**Fluxo invocado por auth:** `auth.register` → `otp.create` → `notify.send` (template `otp.md`).

---

## 7. Auth — fonte única de external_id

**Service:** `auth` (porta 8000 interna)

| Verb   | Path           | Função                                    |
| ------ | -------------- | ----------------------------------------- |
| `POST` | `/atomic`      | Atômica: register-or-fetch user           |
| `DELETE` | `/atomic/{id}` | Rollback do atomic                       |
| `POST` | `/check`       | Lookup por CPF/phone/external_id          |
| `POST` | `/register`    | Cria user novo (gera external_id UUID)    |
| `POST` | `/login`       | Valida OTP, emite JWT via `jwt`           |
| `POST` | `/recover`     | Inicia fluxo de recuperação               |

`auth.register` é **idempotente por CPF** — se já existe user com aquele CPF, retorna o external_id existente sem criar novo. Usado pelo lead pra evitar duplicatas.

**JWT issuer:** `jwt.v7m.org` (mantido como interno propositalmente, é apenas identificador no token, não URL pública). Algoritmo RS256, chaves em volume `jwt_keys`.

---

## 8. Acesso à produção

### Por path no Caddy admin (`:80`, DMZ via Tailscale ou interno docker network):
```
http://10.1.30.20/lead/api/v1/...
http://10.1.30.20/auth/api/v1/...
http://10.1.30.20/notify/api/v1/...
http://10.1.30.20/asaas/api/v1/...
http://10.1.30.20/infinitepay/api/v1/...
http://10.1.30.20/ai/api/v1/...
http://10.1.30.20/jwt/.well-known/jwks.json
```

(prefixos: `/lead`, `/captacao`, `/auth`, `/jwt`, `/otp`, `/notify`, `/profiles`, `/roles`, `/ai`, `/infinitepay`, `/pay/cc`, `/asaas`, `/pay/pix`, `/mail`, `/whats`, `/whatsapp`)

### Acesso direto via docker exec (do LXC 201):
```bash
ssh root@10.1.30.20
docker exec v7m-lead       curl -s http://localhost:8000/health
docker exec v7m-asaas      curl -s http://localhost:8000/api/v1/config/status
docker exec v7m-infinitepay curl -s http://localhost:8000/api/v1/config/
```

### Caddy público (`:8081`, exposto via Cloudflare → `api.v7m.org`):
- só **6 prefixos** passam, resto vira 404 imediato no Caddy
- TLS via Let's Encrypt + DNS-01 (Cloudflare API token)

---

## 9. Operações comuns (cookbook)

### Criar uma cobrança PIX manual
```bash
ssh root@10.1.30.20 'docker exec v7m-asaas python3 -c "
import httpx, json, time
body = {
  \"external_id\": f\"manual_{int(time.time())}\",
  \"amount\": 999.99,
  \"description\": \"Matrícula Supletivo: Material didático...\",
  \"payer\": {
    \"name\": \"Teste Manual\",
    \"cpf_cnpj\": \"12345678909\",
    \"email\": \"teste@supletivo.net.br\"
  }
}
r = httpx.post(\"http://localhost:8000/api/v1/charge/pix\",
  content=json.dumps(body, ensure_ascii=False).encode(),
  headers={\"Content-Type\": \"application/json; charset=utf-8\"}, timeout=30)
print(r.status_code, r.text)
"'
```

### Criar link InfinitePay para user existente
```bash
ssh root@10.1.30.20 'docker exec v7m-infinitepay python3 -c "
import httpx, json
body = {
  \"external_id\": \"UUID-EXISTENTE-EM-auth.users\",
  \"customer\": {\"name\": \"X\", \"email\": \"x@y\", \"phone_number\": \"11999998888\"}
}
r = httpx.post(\"http://localhost:8000/api/v1/checkout/\",
  content=json.dumps(body, ensure_ascii=False).encode(),
  headers={\"Content-Type\": \"application/json; charset=utf-8\"}, timeout=30)
print(r.status_code, r.text)
"'
```

### Listar users do auth
```bash
ssh root@10.1.30.20 'docker exec v7m-auth python3 -c "
import asyncio
from sqlalchemy import select
from app.db import async_session
from app.models.user import User
async def main():
    async with async_session() as s:
        rows = (await s.execute(select(User).order_by(User.created_at.desc()).limit(5))).scalars().all()
        for r in rows:
            print(r.external_id, r.created_at)
asyncio.run(main())
"'
```

### Resetar Victor (lead de teste) para refazer fluxo
```bash
# Apaga lead, profile, infinitepay checkout — NÃO apaga user em auth (mantém UUID estável)
ssh root@10.1.30.20 '
docker exec v7m-lead python3 -c "
import asyncio
from sqlalchemy import delete
from app.db import async_session
from app.models import Lead
EXT=\"UUID-AQUI\"
async def main():
    async with async_session() as s:
        await s.execute(delete(Lead).where(Lead.external_id==EXT))
        await s.commit()
asyncio.run(main())
"
docker exec v7m-infinitepay python3 -c "
from app.db import SessionLocal
from app.models.models import Checkout
s = SessionLocal()
s.query(Checkout).filter_by(external_id=\"UUID-AQUI\").delete()
s.commit()
"
'
```

### Mudar descrição/preço PIX e CC (preservando UTF-8)
```bash
ssh root@10.1.30.20 '
# 1) PIX: ajusta .env e recria lead
cd /opt/v7m && python3 -c "
import re
p=\".env\"
s=open(p,encoding=\"utf-8\").read()
s=re.sub(r\"^PIX_DEFAULT_AMOUNT=.*$\", \"PIX_DEFAULT_AMOUNT=999.99\", s, flags=re.M)
s=re.sub(r\"^PIX_DEFAULT_DESCRIPTION=.*$\", \"PIX_DEFAULT_DESCRIPTION=Matrícula Supletivo: Material didático...\", s, flags=re.M)
open(p,\"w\",encoding=\"utf-8\").write(s)
"
docker compose up -d --force-recreate --no-deps lead

# 2) CC: PATCH InfinitePay config no DB
docker exec v7m-infinitepay python3 -c "
import httpx, json
body = json.dumps({\"price\": 99990, \"description\": \"Matrícula Supletivo: Material didático...\"}, ensure_ascii=False).encode()
r = httpx.patch(\"http://localhost:8000/api/v1/config/\", content=body,
  headers={\"Content-Type\": \"application/json; charset=utf-8\"})
print(r.status_code, r.text)
"
'
```

### Rodar registro completo (lead novo end-to-end)
```bash
curl -X POST https://api.v7m.org/api/v1/public/register \
  -H "Content-Type: application/json" \
  -d '{"phone":"11999998888","cpf":"12345678909"}'

# → recebe { external_id, message: "OTP enviado" }
# → cliente recebe OTP no WhatsApp/Email

curl -X POST https://api.v7m.org/api/v1/public/login \
  -H "Content-Type: application/json" \
  -d '{"external_id":"<uuid>","otp":"<código>"}'

# → recebe { access_token, refresh_token }

curl -X POST https://api.v7m.org/api/v1/authenticated/captured \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"email":"x@y.com","payment_method":"pix"}'

# → recebe { pix: { payload, qr_url, payment_id } }
```

### Inspecionar logs em tempo real
```bash
ssh root@10.1.30.20 'docker logs -f --tail 50 v7m-lead'
ssh root@10.1.30.20 'docker logs -f --tail 50 v7m-notify'
ssh root@10.1.30.20 'docker logs -f --tail 50 v7m-asaas'
ssh root@10.1.30.20 'docker logs -f --tail 50 v7m-infinitepay'
```

### Verificar status da config Asaas (sandbox vs prod, webhook registrado)
```bash
ssh root@10.1.30.20 'docker exec v7m-asaas curl -s http://localhost:8000/api/v1/config/status | python3 -m json.tool'
```

---

## 10. Comportamento esperado / contratos

### Idempotência
- `auth.register`: idempotente por CPF — re-chamar retorna mesmo external_id
- `lead.register`: idempotente — re-chamar com mesmo phone+cpf não duplica lead
- `infinitepay.checkout`: **não** idempotente por external_id — segundo POST retorna 409
- `asaas.charge`: idempotente se passar `payment_id` no body

### Retry/timeouts
- HTTP cliente padrão: `httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT)` (default 10s)
- Lead aumenta para `+5s` no `register` (auth.atomic é mais pesado por orquestrar profiles+notify+otp+jwt)
- Polling notify_lead_captured: até `LEAD_CONTACT_POLL_TIMEOUT_S=60s` esperando contact em notify

### Ordem de boot
- `roles.depends_on.auth: { condition: service_healthy }` — corrigida race em que roles inicia antes do auth ter schema
- Demais serviços confiam em healthchecks do compose
- Postgres / Redis sobem primeiro, depois os serviços

### Hairpin NAT (mailcow)
- Notify usa socat tunnel pra `mail.v7m.org:587` via IPv6 público (workaround do hairpin NAT do Mailcow):
  - LXC 201 roda socat IPv4 5587 → IPv6 mail.v7m.org:587
  - notify container tem `extra_hosts: ["mail.v7m.org:10.1.30.20"]`
  - TLS valida nome porque o cert é pra `mail.v7m.org`

### CORS
- `CORS_ORIGINS=["*"]` no lead — em produção real, fechar pra domínio do app

### Quando o pagamento falha
- Asaas: webhook `PAYMENT_OVERDUE` chega após `due_date` — lead **NÃO** muda status automaticamente (decisão de negócio: cobrar manualmente). PIX vencido fica `EXPIRED`.
- InfinitePay: 3 tentativas no cartão (configurável); se todas falharem, lead permanece `CHECKOUT` indefinidamente, frontend pode oferecer "tentar novamente" recriando checkout.

---

## 11. Códigos de erro frequentes

| HTTP | Detail                         | Onde                       | Causa típica                                            |
| ---- | ------------------------------ | -------------------------- | ------------------------------------------------------- |
| 422  | `name_immutable`               | lead `/captured`           | Tentou trocar nome após profiles ter setado             |
| 422  | `name_required`                | lead `/captured`           | Profile sem nome e payload sem nome                     |
| 400  | `invalid_amount`               | asaas `/charge/pix`        | Valor abaixo de R$ 5,00 em prod                         |
| 400  | `customer_required`            | asaas `/charge/pix`        | external_id sem customer + payer não fornecido          |
| 400  | `asaas_charge_create_failed`   | asaas `/charge/pix`        | Asaas rejeitou (valor mínimo, CPF inválido, etc.)       |
| 400  | `asaas_api_key_not_set`        | asaas vários               | Config sem chave de API                                 |
| 409  | `external_id já existe`        | infinitepay `/checkout/`   | Pode ser: já existe **OU** FK violation (UUID inexistente em auth.users — erro idêntico) |
| 502  | `Falha ao comunicar com auth`  | lead `/register`           | auth-app down ou network issue                          |
| 502  | `Auth nao retornou external_id`| lead `/register`           | auth respondeu mas sem campo `external_id`              |

---

## 12. Variáveis de ambiente críticas (`.env`)

```bash
# Identidade
SERVICE_NAME=lead
ENVIRONMENT=production
LOG_LEVEL=INFO

# Banco (1 postgres, schema por serviço)
DATABASE_URL=postgresql+asyncpg://v7m:***@postgres:5432/v7m

# Integrações
INFINITEPAY_BASE_URL=http://infinitepay:8000
ASAAS_BASE_URL=http://asaas:8000
AUTH_BASE_URL=http://auth:8000
JWT_BASE_URL=http://jwt:8000
NOTIFY_BASE_URL=http://notify:8000
PROFILES_BASE_URL=http://profiles:8000
ROLES_BASE_URL=http://roles:8000

# Promoter default (quando lead não informa de qual promotor veio)
PROMOTER_DEFAULT=uuid-do-promoter-padrão

# URL pública (montagem de absolute URLs em mensagens — QR PNG, etc.)
LEAD_PUBLIC_BASE_URL=https://api.v7m.org

# PIX defaults
PIX_DEFAULT_AMOUNT=999.99
PIX_DEFAULT_DESCRIPTION=Matrícula Supletivo: Material didático...
PIX_DEFAULT_DUE_DAYS=

# Callback notify
NOTIFY_CALLBACK_URL=http://lead:8000/api/v1/webhook/notify

# SMTP/Email
SMTP_FROM_NAME=Supletivo
MAILCOW_FROM_NAME=Supletivo
SMTP_RELAY_HOST=host-gateway        # ou IP do socat tunnel se hairpin NAT

# Media
MEDIA_DIR=/app/media                 # volume lead_media
```

---

## 13. Onde estão as coisas no repositório

```
v7m/
├── docker-compose.yml                    # toda a stack
├── .env                                  # secrets/prod (NÃO commitado)
├── infra/caddy/Caddyfile                 # rotas de proxy
└── services/
    ├── lead/
    │   ├── app/config.py                 # Settings (PIX defaults aqui)
    │   ├── app/main.py                   # FastAPI app + media mount
    │   ├── app/models/                   # Lead, LeadStatus
    │   ├── app/routers/public/auth.py    # check/register/login/refresh
    │   ├── app/routers/authenticated/    # captured/waiting/checkout/completed
    │   ├── app/routers/demilitarized/    # webhooks + CRUD admin
    │   ├── app/notify/handlers.py        # notify_lead_captured, ...
    │   └── app/notify/messages/*.md      # templates Markdown
    ├── notify/
    │   ├── app/services/message_service.py  # orquestrador
    │   ├── app/integrations/{mailcow,whatsapp}.py
    │   └── alembic/versions/*_seed_context_templates.py  # email templates
    ├── asaas/
    │   ├── app/services/charge.py        # POST /charge/pix lógica
    │   └── app/models/                   # ConfigKV (asaas_api_key etc.)
    └── infinitepay/
        ├── app/services/checkout_service.py  # cria checkout, FK external_id
        ├── app/models/models.py          # Checkout (UUID FK auth.users)
        └── app/api/config.py             # PATCH /config/ (price, description)
```

---

## 14. Quando invocar esta skill

- "como funciona o fluxo de matrícula"
- "criar um link de pagamento PIX/Asaas/cartão/InfinitePay manual"
- "mudar preço/descrição da matrícula"
- "calcular preço pra buyer ver X reais por parcela no 12×"
- "qual UUID usar pra testar"
- "como resetar um lead"
- "onde mexer no template de email/WhatsApp"
- "diagnosticar webhook que não chegou"
- "endpoint público vs interno"
- "qual ambiente tá rodando (sandbox vs prod)"
- "qual estado o lead está"
- "como rodar o E2E em produção"
- "porque o cliente vê 12× R$ 119,98 em vez de R$ 99,99"

---

## 15. Não-óbvios / pegadinhas

1. **InfinitePay 20% acréscimo:** o `price` que você configura é o que VOCÊ recebe. O buyer vê esse valor + 20% se parcelar em 12×. Pra buyer ver parcela exata `P`, configurar `price = P × 12 / 1.20`.

2. **InfinitePay external_id é UUID com FK:** não dá pra criar checkout pra UUID que não existe em `auth.users`. O erro retornado é "409 external_id já existe" mas pode ser FK violation — **mensagem semanticamente errada**, atenção ao debugar.

3. **Asaas PIX mínimo R$ 5,00 em prod:** abaixo rejeita silenciosamente como `asaas_charge_create_failed`.

4. **Acentos em `.env`:** usar Python (heredoc/UTF-8 explícito), não `sed` — bash strip diacríticos. Mesmo problema em `curl --data` sem `Content-Type: charset=utf-8`.

5. **InfinitePay storage em centavos, Asaas em reais decimais.** Não confundir.

6. **Caddy público bloqueia tudo fora dos 6 prefixos.** Adicionar rota nova → editar Caddyfile + reload. Sem isso, vira 404 antes de bater no serviço.

7. **MERGE de mensagem TTS:** notify prepende o título antes do body pro ElevenLabs, senão começa "no meio" (cortou o "Olá, X").

8. **`*X*` markdown em email:** sem conversão, vira literal `*682117*`. Função `_md_bold_to_html_after_escape` lida com `*X*` e `**X**` com negative-lookbehind/ahead pra não confundir com multiplicação.

9. **Asaas webhook precisa ser PRODUÇÃO real reachable:** rotação de URL usa nonce single-use + verify endpoint (`/api/v1/config/url/verify/{nonce}`).

10. **Race auth↔roles:** `roles.depends_on.auth: { condition: service_healthy }` é mandatório — sem isso, roles pode subir antes do schema de auth existir e quebrar.
