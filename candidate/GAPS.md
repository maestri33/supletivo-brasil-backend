# GAPS.md — Delta: candidate vs lead (2026-05-27)

Gerado automaticamente a partir da inspeção de `backend/lead/app/` vs `backend/candidate/app/`.

## Resumo

| Aspecto                        | lead | candidate | Status       |
|--------------------------------|------|-----------|--------------|
| Rotas públicas (auth)          | ✅   | ✅        | Paridade     |
| Rotas autenticadas (perfil)    | 4    | 7         | candidate+   |
| Rotas demilitarized            | 3    | 1         | **GAP**      |
| Integrações                    | 6    | 9         | candidate+   |
| Background tasks               | ❌   | ❌        | Ambos sem    |
| Webhook handling               | ✅   | ❌        | **GAP**      |
| Checkout/pagamento             | ✅   | ❌        | **GAP**      |
| Notify integration             | ✅   | ✅        | Paridade     |
| Health check                   | ✅   | ✅        | Paridade     |

---

## 1. Rotas Autenticadas — candidate tem MAIS que lead

### lead (4 rotas autenticadas)
- `authenticated/captured.py` — dados capturados do lead
- `authenticated/checkout.py` — fluxo de checkout/pagamento
- `authenticated/completed.py` — perfil completo
- `authenticated/waiting.py` — fila de espera

### candidate (7 rotas autenticadas)
- `authenticated/address.py` — endereço
- `authenticated/birth.py` — dados de nascimento
- `authenticated/captured.py` — dados capturados
- `authenticated/documents.py` — documentos (RG, CPF, etc.)
- `authenticated/educational.py` — dados educacionais
- `authenticated/personal.py` — dados pessoais
- `authenticated/pixkey.py` — chave PIX
- `authenticated/selfie.py` — selfie/verificação facial

**Observação:** candidate tem perfil mais completo (endereço, documentos, educacional, selfie, PIX) que lead. Falta apenas checkout/pagamento.

---

## 2. Integrações — candidate tem extras

### lead (6 integrações)
- `asaas.py` — gateway de pagamento
- `auth.py` — auth service (register/login/check)
- `infinitepay.py` — gateway alternativo
- `jwt.py` — validação JWT
- `notify.py` — notificações (WhatsApp, email)
- `profiles.py` — serviço de perfis

### candidate (9 integrações)
- `address.py` — serviço de endereço (via CEP/Correios)
- `ai.py` — serviço AI (TTS, imagem, visão)
- `asaas.py` — gateway de pagamento
- `auth.py` — auth service (register/login/check)
- `documents.py` — upload/armazenamento de documentos
- `jwt.py` — validação JWT
- `notify.py` — notificações
- `profiles.py` — serviço de perfis
- `roles.py` — gestão de roles/papéis

**Extras do candidate:** `address.py`, `ai.py`, `documents.py`, `roles.py`

---

## 3. GAPS Críticos do candidate vs lead

### 3.1 Webhooks (ASAAS + InfinitePay)
**lead tem:** `demilitarized/webhooks.py` — recebe webhooks de pagamento
**candidate não tem.** Sem webhooks, pagamentos não atualizam status automaticamente.

### 3.2 Checkout/Pagamento
**lead tem:** `authenticated/checkout.py` — fluxo completo de pagamento
**candidate não tem.** Candidatos não conseguem pagar taxa de inscrição.

### 3.3 Demilitarized endpoints
**lead tem 3:**
- `demilitarized/checkouts.py` — listar/gerenciar checkouts
- `demilitarized/leads.py` — listar/gerenciar leads (admin)
- `demilitarized/webhooks.py` — webhooks de pagamento

**candidate tem 1:**
- `demilitarized/candidates.py` — listar/gerenciar candidatos (admin)

**Faltam:** checkouts demilitarized + webhooks

---

## 4. O que NÃO é gap (candidate já tem ou não precisa)

- **Notify:** candidate já tem `integrations/notify.py` ✅
- **JWT:** candidate já tem `integrations/jwt.py` ✅
- **Profiles:** candidate já tem `integrations/profiles.py` ✅
- **ASAAS:** candidate já tem `integrations/asaas.py` ✅
- **Auth:** candidate já tem `integrations/auth.py` ✅ (corrigido role=lead → candidate em COD-93)
- **Background tasks:** nem lead nem candidate tem tasks assíncronas — ambos precisam

---

## 5. Recomendações de próximos passos

1. **Alta prioridade:** Adicionar webhooks de pagamento ao candidate (copiar de lead e adaptar)
2. **Alta prioridade:** Implementar checkout/pagamento para taxa de inscrição
3. **Média:** Criar endpoints demilitarized para checkouts e webhooks
4. **Baixa:** Avaliar se candidate precisa de background tasks (ex: processamento assíncrono de documentos)
