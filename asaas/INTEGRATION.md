---
name: asaas-charge-integration
description: |
  Como integrar um checkout/frontend com o microsserviço asaas-app para gerar
  cobranças PIX (entrada). Cobre: campos mínimos do request, resposta completa,
  códigos de erro, polling vs webhook, e fluxo end-to-end do checkout.
  Use quando precisar criar PIX charge, consultar status, ou cancelar cobrança.
---

# Integração — Cobrança PIX via `asaas-app`

Microsserviço FastAPI que encapsula a Asaas v3 e expõe cobranças PIX inbound
com find-or-create de customer, BR Code + QR Code, e notificação out-webhook
quando o status muda.

---

## TL;DR — chamada mínima

**Primeira cobrança de um cliente:**

```bash
curl -X POST http://asaas:8000/api/v1/charge/pix \
  -H "Content-Type: application/json" \
  -d '{
    "external_id": "aluno_42",
    "amount": 250.00,
    "payer": {
      "name": "Maria Aluna",
      "cpf_cnpj": "07426367980"
    }
  }'
```

**Cobranças seguintes para o mesmo `external_id`:**

```bash
curl -X POST http://asaas:8000/api/v1/charge/pix \
  -H "Content-Type: application/json" \
  -d '{
    "external_id": "aluno_42",
    "amount": 99.00
  }'
```

---

## Endpoints

| Método | Path | Função |
|---|---|---|
| `POST` | `/api/v1/charge/pix` | cria cobrança PIX |
| `GET` | `/api/v1/charge/{payment_id}` | consulta completa (com `pix.payload` e `pix.encoded_image`) |
| `GET` | `/api/v1/charge/{payment_id}/status` | versão leve para polling: `{payment_id, status, asaas_id, updated_at}` |
| `POST` | `/api/v1/charge/{payment_id}/qr` | re-busca BR Code/QR no Asaas (se cache local estiver fora) |
| `DELETE` | `/api/v1/charge/{payment_id}` | cancela cobrança (somente `PENDING`) |
| `GET` | `/api/v1/charge?status=PAID&external_id=aluno_42` | lista filtrada |

Documentação interativa: `GET /docs` e `GET /redoc`.

---

## Request — `POST /api/v1/charge/pix`

### Schema

```jsonc
{
  // OBRIGATÓRIOS
  "external_id": "string",   // seu ID do cliente; chave do find-or-create
  "amount": 5.00,            // float em BRL, > 0, MÍNIMO R$ 5,00 em prod

  // OBRIGATÓRIO na PRIMEIRA cobrança de um external_id novo,
  // ignorado nas seguintes (customer já está em DB local + Asaas)
  "payer": {
    "name": "string",        // obrigatório
    "cpf_cnpj": "string",    // obrigatório; 11 (CPF) ou 14 (CNPJ) dígitos
    "email": "string",       // opcional
    "mobile_phone": "string" // opcional; preferir +55DDDXXXXXXXXX
  },

  // OPCIONAIS sempre
  "description": "string",   // mostrada no PIX ao pagador; default: "charge <payment_id>"
  "due_date": "YYYY-MM-DD",  // vencimento; default: hoje + 3 dias (env-configurável)
  "payment_id": "string"     // idempotency key; default: gerado "pay_<uuid16hex>"
}
```

### Regras importantes

- **`external_id`** é seu identificador interno do pagador. O asaas-app faz
  find-or-create: na primeira vez cria customer no Asaas, salva no DB local;
  nas vezes seguintes reusa. **Você deve usar o mesmo external_id consistente
  para o mesmo pagador** — caso contrário cria customers duplicados.

- **`cpf_cnpj`** aceita com pontuação ou só dígitos. Internamente normalizamos
  para só dígitos. Asaas em **produção valida CPF/CNPJ via Receita Federal** —
  CPFs inválidos (ex: `12345678909`) são rejeitados em prod (aceitos em sandbox).

- **`amount`** em **produção** o Asaas exige mínimo **R$ 5,00**.
  Sandbox aceita qualquer valor > 0.

- **`due_date`** define quando a cobrança expira. Após esse dia, o Asaas
  dispara `PAYMENT_OVERDUE` → asaas-app marca `EXPIRED`. Não pode ser no
  passado.

- **`payment_id`** garante idempotência. Repetir o mesmo `payment_id` retorna
  `400 payment_id_already_exists`. Útil para retry seguro no seu checkout.

---

## Response — sucesso (HTTP 200)

```json
{
  "payment_id": "pay_a1b2c3d4e5f6a7b8",
  "external_id": "aluno_42",
  "amount": 250.00,
  "description": "Mensalidade junho/2026",
  "due_date": "2026-06-05",
  "status": "PENDING",
  "asaas_id": "pay_iz1m65xx0g27hr5t",
  "pix": {
    "payload": "00020101021226800014br.gov.bcb.pix...6304BC5D",
    "encoded_image": "iVBORw0KGgoAAAANSUhEUgAA...",
    "expiration_date": null
  },
  "last_error": null,
  "created_at": "2026-05-16T16:00:00",
  "updated_at": "2026-05-16T16:00:00"
}
```

### O que fazer com cada campo

| Campo | Uso no checkout |
|---|---|
| `payment_id` | **guarda no seu DB** — chave para polling de status e correlação da notificação |
| `asaas_id` | ID no Asaas; serve só para debug, não é necessário expor |
| `pix.payload` | **BR Code copia-e-cola** — input "PIX copiar e colar" do checkout |
| `pix.encoded_image` | **PNG base64** do QR — renderiza com `<img src="data:image/png;base64,{...}">` |
| `pix.expiration_date` | (atualmente null — preencheremos quando capturarmos da Asaas) |
| `due_date` | mostre ao usuário ("Pague até DD/MM/YYYY") |
| `status` | sempre `PENDING` na criação |
| `created_at` / `updated_at` | timestamps ISO 8601 UTC |

---

## Máquina de estados (`status`)

```
PENDING ──── PAYMENT_CONFIRMED|PAYMENT_RECEIVED ────► PAID
   │
   ├──── PAYMENT_OVERDUE ─────────────────────────► EXPIRED
   ├──── DELETE /charge | PAYMENT_DELETED ────────► CANCELLED
   └──── PAYMENT_REFUNDED (após PAID) ────────────► REFUNDED
```

| Status | Significado |
|---|---|
| `PENDING` | criada, aguardando pagamento |
| `PAID` | pagamento confirmado pelo Asaas (já compensado) |
| `EXPIRED` | venceu o `due_date` sem pagamento |
| `CANCELLED` | cancelada via `DELETE /api/v1/charge/{id}` ou pelo Asaas |
| `REFUNDED` | estornada após ter sido `PAID` |

`PAID`, `EXPIRED`, `CANCELLED`, `REFUNDED` são **terminais**.

---

## Erros — formato `{"detail": "<código>"}`

| Código | HTTP | Quando |
|---|---|---|
| `customer_required` | 400 | `external_id` novo e `payer` ausente |
| `invalid_cpf_cnpj` | 400 | `cpf_cnpj` com !=11 e !=14 dígitos |
| `invalid_amount` | 400 | `amount ≤ 0` |
| `invalid_due_date` | 400 | data malformada ou no passado |
| `payment_id_already_exists` | 400 | `payment_id` já usado (idempotência) |
| `asaas_customer_create_failed: {asaas error body}` | 400 | Asaas rejeitou create customer (ex: CPF inválido em prod) |
| `asaas_charge_create_failed: {asaas error body}` | 400 | Asaas rejeitou create payment (ex: amount < R$ 5,00 em prod) |
| `asaas_charge_delete_failed: {asaas error body}` | 400 | Asaas rejeitou cancelar |
| `cannot_cancel_status: <status>` | 400 | tentativa de cancelar cobrança em estado terminal |
| `not_found` | 404 | `payment_id` não existe |
| `asaas_api_key_not_set` | 400 | onboarding incompleto (não setou key no asaas-app) |

Quando o código vem com sufixo `: <detalhe>`, o detalhe é o erro original do
Asaas (estrutura `{"errors": [{"code": "...", "description": "..."}]}`).
Útil para logar; **não exponha cru para o usuário final**.

---

## Notificação out-webhook quando muda de status

A cada transição de status do `Payment(kind=charge)`, o asaas-app dispara
`POST` no `internal_url_charge` configurado:

```json
POST <internal_url_charge>
Content-Type: application/json

{
  "payment_id": "pay_a1b2c3d4e5f6a7b8",
  "kind": "charge",
  "external_id": "aluno_42",
  "status": "PAID"
}
```

**Disparos:**
- `PENDING` ao criar
- `PAID` quando Asaas confirma (`PAYMENT_CONFIRMED` ou `PAYMENT_RECEIVED`)
- `EXPIRED` quando passa do `due_date`
- `CANCELLED` ao cancelar
- `REFUNDED` em estorno

**Resposta esperada:** qualquer 2xx, body opcional. Falhas são logadas como
`internal_notify_failed` mas não bloqueiam o fluxo nem cancelam o pagamento.

**Configurar destino:**

```bash
curl -X POST http://asaas:8000/api/v1/config/internal \
  -H "Content-Type: application/json" \
  -d '{
    "url": "http://meu-checkout:8000/webhook/asaas-charge",
    "target": "charge"
  }'
```

Existem 3 destinos separados:

| target | Recebe | Sua URL deveria... |
|---|---|---|
| `charge` | `kind=charge` (cobranças entrada) | atualizar status do pedido |
| `payout` | `kind=pixkey/qrcode` em SUBMITTED/PAID/FAILED/AWAITING_BALANCE/CANCELLED | atualizar logs de pagamentos enviados |
| `scheduling` | `kind=pixkey/qrcode` em SCHEDULED/QUEUED | acompanhar agendamentos |
| `default` | catch-all (compat) | fallback quando os específicos não estão setados |

---

## Fluxos do checkout — duas estratégias

### A. Polling (mais simples, ideal para single-page)

```
1. POST /api/v1/charge/pix         → guarda payment_id + renderiza QR/payload
2. Loop a cada 3-5s:
     GET /api/v1/charge/{payment_id}/status
     se status != PENDING:
       break + reage (PAID = sucesso; EXPIRED/CANCELLED = falha)
3. Timeout de polling: ~10min (antes do due_date)
```

Pros: trivial, sem backend extra.
Contras: latência ~3-5s; se o usuário fechar a aba, não detecta o pagamento.

### B. Webhook + push (robusto, ideal para backend)

```
1. Backend do checkout cria charge via POST /api/v1/charge/pix
2. Backend guarda {payment_id ↔ pedido} no seu DB
3. Frontend recebe payment_id + QR/payload
4. asaas-app envia POST no internal_url_charge quando muda status
5. Seu backend:
     - atualiza estado do pedido no seu DB
     - notifica o frontend via WebSocket/SSE/push
6. Frontend mostra o resultado
```

Pros: realtime, funciona mesmo se o usuário fechar a aba.
Contras: precisa do backend escutando o webhook + canal de push pro frontend.

---

## Exemplo end-to-end (HTML + fetch)

```html
<button id="pay-pix" type="button">Pagar com PIX</button>
<div id="qr-area" hidden>
  <img id="qr-img" />
  <textarea id="payload" readonly></textarea>
  <p id="status">Aguardando pagamento…</p>
</div>

<script>
async function pagarComPix() {
  const r = await fetch('http://asaas:8000/api/v1/charge/pix', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      external_id: 'aluno_42',
      amount: 250.00,
      description: 'Curso XYZ',
      payer: { name: 'Maria Aluna', cpf_cnpj: '07426367980', email: 'maria@x.com' }
    })
  });
  if (!r.ok) {
    const err = await r.json();
    alert('Erro: ' + err.detail);
    return;
  }
  const j = await r.json();

  document.getElementById('qr-img').src = 'data:image/png;base64,' + j.pix.encoded_image;
  document.getElementById('payload').value = j.pix.payload;
  document.getElementById('qr-area').hidden = false;

  pollStatus(j.payment_id);
}

async function pollStatus(paymentId) {
  for (let i = 0; i < 200; i++) {  // ~10min de polling
    await new Promise(r => setTimeout(r, 3000));
    const r = await fetch(`http://asaas:8000/api/v1/charge/${paymentId}/status`);
    const j = await r.json();
    if (j.status === 'PAID') {
      document.getElementById('status').textContent = '✅ Pagamento confirmado!';
      // dispara confirmação no seu backend → libera produto
      return;
    }
    if (['EXPIRED', 'CANCELLED', 'REFUNDED'].includes(j.status)) {
      document.getElementById('status').textContent = '❌ ' + j.status;
      return;
    }
  }
  document.getElementById('status').textContent = '⏱ Timeout — verifique manualmente';
}

document.getElementById('pay-pix').addEventListener('click', pagarComPix);
</script>
```

---

## Configuração one-time (operador)

Antes do checkout poder usar o asaas-app, é preciso:

1. **`POST /api/v1/config/url`** — URL pública para o Asaas chamar webhooks
   (TLS válido; em dev usa ngrok ou Tailscale Funnel)
2. **`GET /api/v1/config/url/verify/{nonce}`** — consome o nonce do passo 1
3. **`POST /api/v1/config/internal` com `target=charge`** — URL do seu backend
   para receber notificações de cobrança
4. **`POST /api/v1/config/key`** — API key Asaas (`$aact_prod_*` ou `$aact_hmlg_*`
   se `ASAAS_ALLOW_SANDBOX=true`)
5. **`POST /api/v1/config/key/confirm`** — registra webhook na Asaas

Veja `/api/v1/config/status` para checar o que está configurado e o que falta.

---

## Onde estão os fees

Asaas cobra fee no PIX **inbound** (recebimento). Valor depende do plano:
- Sua conta atual: **R$ 1,99 por PIX recebido** (visto nos `netValue` da API)
- `originalValue` (campo Asaas) = valor que o pagador transferiu
- `netValue` (campo Asaas, exposto em `GET /v3/payments/{id}`) = `originalValue - fee`

Para o pagador: paga exatamente `amount`. O fee é descontado do que cai na
sua conta Asaas.

PIX **outbound** nesta conta = R$ 0 de fee (verificado em 82 transfers).

---

## Operações que **não** estão expostas aqui

Este endpoint é só de **cobrança** (incoming). Para outras coisas:

- **Payout / transferência PIX** (saída): `POST /api/v1/payment` com `external_id`
  de uma pix key cadastrada via `POST /api/v1/pixkey`
- **Pagamento de BR Code** (saída): `POST /api/v1/payment/qrcode`
- Veja `app/api/payment.py` e `app/api/pixkey.py`

---

## Resumo dos campos mínimos (cheatsheet)

```
POST /api/v1/charge/pix

Primeira vez do external_id:
  external_id        REQ
  amount             REQ  (>= R$ 5,00 em prod)
  payer.name         REQ
  payer.cpf_cnpj     REQ  (CPF real em prod)

Próximas vezes do mesmo external_id:
  external_id        REQ
  amount             REQ
  (payer pode ser omitido)

Opcionais sempre:
  description
  due_date           (YYYY-MM-DD)
  payment_id         (idempotência)
  payer.email
  payer.mobile_phone

Resposta inclui:
  payment_id           ← guarde para polling/correlação
  pix.payload          ← BR Code copia-e-cola
  pix.encoded_image    ← PNG base64 do QR
  asaas_id, status, due_date, created_at, updated_at
```
