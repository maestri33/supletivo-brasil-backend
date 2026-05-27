# A1 — Endpoint Auth Audit (CONVENTION §5)
**Date:** 2026-05-27 | **22 services** | **~200 endpoints classified**

## Classification Legend
- 🔓 Desmilitarizado — internal-only, no auth needed
- 🔐 Autenticado — requires JWT + role
- 🌐 Publico — no auth, needs rate-limit + max logging

## 🔴 CRITICAL — Fixed (2026-05-27)

| Service | Endpoint | Fix Applied |
|---------|----------|-------------|
| auth/atomic | POST / | `Depends(require_admin)` added |
| auth/atomic | DELETE /{atomic_id} | `Depends(require_admin)` added |
| auth/log | GET / | `Depends(require_admin)` added |
| auth/log | DELETE / | `Depends(require_admin)` added |

## 🟡 Advisory (Low Priority)

| Service | Endpoint | Classification | Note |
|---------|----------|---------------|------|
| address | GET /cep/{zipcode} | 🌐 Publico | Add rate-limit (calls ViaCEP externally) |
| hub | GET /, GET /{id} | 🌐 Publico | Add rate-limit to public list/detail |
| documents | ALL (6 endpoints) | 🔓 Desmilitarizado | Confirm internal-only callers |
| infinitepay | GET /checkout | 🌐 Publico | Check if auth needed for status query |

## ✅ Properly Classified (18 services)

### Desmilitarizado (no auth, internal)
address (except /cep), ai, asaas (except webhook), candidate,
enrollment (webhook public), infinitepay (checkout internal),
jwt (except jwks), notify, otp (except webhook), profiles,
promoter, roles, training

### Autenticado (JWT + role required)
candidate/authenticated/* (8 modules), hub (POST/PATCH/PUT),
promoter/authenticated/me

### Publico (no auth, rate-limit + logging needed)
auth: check, login, recover, register
asaas: webhooks (HMAC ✅)
infinitepay: webhooks (HMAC ✅)
jwt: /.well-known/jwks.json
enrollment: webhook callback
otp: /webhook/notify
