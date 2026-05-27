# PII Handling Audit — WS-SEC (COD-18)

> **Auditor:** SecReviewer (Agent 86907292-1481-437e-bc4c-a25c7446aacc)
> **Date:** 2026-05-27
> **Scope:** All 22 microservices — check for PII (CPF, RG, foto, endereço, telefone, e-mail) in plaintext logs

---

## Executive Summary

The project generally handles PII responsibly in logs — **most services log only identifiers** (external_id, payment_id, asaas_id) and never raw PII. However, **one definite PII leakage** was found in the `documents` service, and **one potential risk** identified in `candidate`.

---

## ✅ Good: Services with no PII in logs

These services log only event names, service names, and non-PII identifiers:

| Service | Verdict | Notes |
|---------|---------|-------|
| address | ✅ Clean | 0 logging calls |
| ai | ✅ Clean | 0 logging calls |
| asaas | ✅ Clean | Logs only `payment_id`, `asaas_id`, `external_id` |
| auth | ✅ Clean | Logs only `external_id` |
| commissions | ✅ Clean | Only startup/shutdown |
| coordinator | ✅ Clean | No PII in logs |
| enrollment | ✅ Clean | Only event names |
| fees | ✅ Clean | Logs only `payment_id` |
| hub | ✅ Clean | No PII in logs |
| jwt | ✅ Clean | Only health check |
| lead | ✅ Clean | Logs only service name |
| notify | ✅ **Exemplary** | Uses `mask_phone()` and `mask_email()` on all PII before logging |
| otp | ✅ Clean | 0 logging calls |
| profiles | ✅ Clean | Logs only event names + `digits_len` (non-reversible) |
| promoter | ✅ Clean | Only startup/shutdown |
| roles | ✅ Clean | Only logging utility, no PII |
| staff | ✅ Clean | No PII in logs |
| student | ✅ Clean | Only startup/shutdown |
| training | ✅ Clean | Only startup/shutdown |

---

## ❌ Issues Found

### 1. CRITICAL — `documents/app/services/document_service.py:164`

**Problem:** `logger.info("documento_atualizado", external_id=external_id, changes=changes)` logs the `changes` dict in full, which contains **raw PII values** including:
- `rg_numero`, `cnh_numero`, `carteira_trabalho_numero`, `passaporte_numero`
- `certidao_numero`, `certidao_cartorio`, `certidao_livro`, `certidao_folha`, `certidao_termo`
- `reservista_categoria`, `reservista_ra`
- `foto_frente`, `foto_verso`

**Risk:** All document numbers (RG, CNH, passport, etc.) are logged to structlog as plaintext without masking.

**Fix:** Mask document numbers before logging:
```python
from app.utils.pii import mask_document  # or inline masking
masked = {k: _mask_doc(v) if k.endswith('_numero') else v for k, v in changes.items()}
logger.info("documento_atualizado", external_id=external_id, changes=masked)
```

### 2. MEDIUM — `candidate/app/services/notifications.py:74`

**Problem:** `content=f"Novo candidato cadastrado. Telefone: {phone}"` — phone number exposed in a **notification message** content. While this is user-facing (not a log), the notification flows through `notify` service which may log the message body.

**Risk:** Phone number could appear in `notify` metrics/tracking if message content is logged downstream.

**Fix:** Mask phone in notification content or use a template with masked phone.

---

## Recommendations

### Immediate (P0)
1. **Mask `changes` dict** in `documents/app/services/document_service.py` before logging — document numbers are the most sensitive PII in the system.
2. **Add PII masking utility** to `documents` service (or import from `notify/app/utils/pii.py` if the services share a common lib).

### Short-term (P1)
3. **Audit exception handlers** across all services — `str(exc)` in error logs could include PII if the exception carries user data (CPF, email, etc.)
4. **Extend `notify/app/utils/pii.py`** to include `mask_document()` and `mask_name()` utilities.
5. **Extract common `pii.py`** as a shared library (or copy to services that need it).

### Cross-service
6. **structlog processor**: Consider adding a global structlog processor that redacts known PII patterns (CPF regex, email regex) from all log entries automatically — defense in depth.
7. **Periodic PII audit** should be automated (grep for known PII patterns in `logger.*` and `log_event(` calls in CI).

---

## Verdict

**Status:** 🔴 Needs fix — 1 critical, 1 medium issue found in 22 services.
**Notify service:** ✅ Exemplary — only service using PII masking.
**Documents service:** 🔴 Critical — logs raw RG/CNH/passport numbers.
**Remaining 20 services:** ✅ Clean.
