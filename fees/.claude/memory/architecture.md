# Arquitetura — fees

> Decisões com data. Atualize ao terminar mudanças relevantes.

## 2026-05-24 — criação (green-field)

Serviço criado do zero, espelhando `enrollment`/`lead` (estrutura) e
`asaas`/`infinitepay` (stack canônica async). Decisões confirmadas com o usuário
antes de codar (fluxo §1):

- **Fluxo = payout** (não cobrança): o coordenador paga **dois BR Codes** via
  `asaas` — um à vista (`/payment/qrcode`) e um agendado
  (`/payment/qrcode/scheduled`). Valores e data do agendamento vêm no POST do
  coordenador.
- **fees só guarda status + notifica** (§6): quando a 1ª parte é paga, o acesso
  fica liberável; quem libera lê o status do fees depois. fees **não** chama
  student/auth/enrollment (esses serviços ainda nem existem).
- **`external_id` opaco, sem FK** — igual ao asaas (o id é do cliente da API).

## Modelo de dados

- `fee` (1) → `fee_payment` (2: upfront/scheduled), referência por **valor**
  (`fee_id`), sem FK declarada (portável p/ sqlite nos testes + sem acoplamento).
- PK = UUID `as_uuid=False` (string) → cai para CHAR no sqlite (truque do asaas
  que mantém os testes rodando sem Postgres).
- `fee.status` é **derivado** (`services/fee_service.derive_fee_status`), nunca
  setado à mão fora do serviço.

## Idempotência (caminho do dinheiro)

1. Cria `fee` + 2 `fee_payment` e **commita** (intenção persistida).
2. Só então chama o asaas com `payment_id` determinístico
   (`fee-<fee_id>-<kind>`). Re-submit → `payment_id_already_exists` no asaas →
   nunca duplica. Falha de rede → status local `SUBMIT_ERROR` (taxa fica
   `PENDING`, não falha o request).
3. Webhook idempotente: aplica status, re-deriva a taxa; mesmo status reentregue
   não re-transiciona nem re-notifica.

## Pendências conhecidas

- Lembrete por inatividade (§11) exigiria worker agendado — fora do v1.
- Endpoint de retry/cancel de payout não existe ainda (coordenador hoje só
  cria/consulta). Adicionar se o produto pedir.
