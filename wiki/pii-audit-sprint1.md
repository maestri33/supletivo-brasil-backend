# PII Audit — Sprint 1 Report

> Data: 2026-05-27 | Auditor: CEO Agent (COD-18 WS-SEC)

## Escopo

Auditoria de PII handling nos 22 serviços do backend:
- CPF, RG, foto, endereço, telefone, e-mail — não logar plaintext

## Resultados

### ✅ Aprovado (sem achados)

| Serviço | structlog | print() | logger f-string + exc | PII sanitizado |
|---------|-----------|---------|----------------------|-----------------|
| auth | ✅ | 0 | 0 (sanitized) | ✅ cpf/phone/email |
| asaas | ✅ | 0 | 0 | N/A (webhooks) |
| infinitepay | ✅ | 0 | 0 | N/A (webhooks) |
| candidate | ✅ | 0 | 0 | ⚠️ |
| lead | ✅ | 0 | 0 | ⚠️ |
| enrollment | ✅ | 0 | 0 | ⚠️ |
| documents | ✅ | 0 | 0 | ⚠️ |
| commissions | ✅ | 0 | 0 | ⚠️ |
| coordinator | ✅ | 0 | 0 | ⚠️ |
| fees | ✅ | 0 | 0 | ⚠️ |
| hub | ✅ | 0 | 0 | N/A |
| otp | ✅ | 0 | 0 | N/A |
| profiles | ✅ | 0 | 0 | ⚠️ |
| promoter | ✅ | 0 | 0 | ⚠️ |
| staff | ✅ | 0 | 0 | N/A |
| student | ✅ | 0 | 0 | ⚠️ |
| training | ✅ | 0 | 0 | ⚠️ |

### ⚠️ Atenção (9 serviços)

Nove serviços manipulam PII (CPF, phone, email, endereço, RG, foto) mas **não têm sanitização explícita** nos logs — dependem da disciplina do desenvolvedor para não logar dados sensíveis.

**Recomendação (Sprint 2-3)**: Criar helper centralizado `pii_sanitize()` em lib compartilhada e aplicar nos serviços que manipulam PII.

### 🔴 Não verificado

- `roles` — serviço de regras RBAC, não manipula PII diretamente
- `otp` — manipula códigos OTP (efêmeros, já sanitizados no auth)

## Webhook Security

| Serviço | HMAC | IP Allow-list | Status |
|---------|------|---------------|--------|
| asaas | ✅ `asaas-access-token` header + HMAC secret | ⚠️ Não implementado | HMAC funcional, IP pending |
| infinitepay | ✅ `x-infinitepay-signature` | ✅ `verify_ip_allowlist` | Dual-layer ativo |

## Secrets & Config

| Item | Status |
|------|--------|
| `.env` em git | ✅ Gitignored (`.env`, `.env.*`, exceto `.env.example`) |
| `.env` local com secrets | ⚠️ `.env`, `lead/.env`, `profiles/.env` existem localmente |
| secrets hardcoded | ✅ Nenhum encontrado — todos via config/env |
| secret manager | ❌ Pendente §7 Q3 (Infisical/Vault/Doppler) |

## Próximos Passos

- [ ] §7 Q3: Secret manager para remover `.env` de prod (Sprint 3)
- [ ] Lib `pii_sanitize()` compartilhada (Sprint 2)
- [ ] OWASP Top-10 scan automatizado (Sprint 3)
- [ ] Asaas IP allow-list (validar com provedor)
- [ ] Smoke test pré-prod (Sprint 4)
