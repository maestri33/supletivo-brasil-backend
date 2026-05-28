# OWASP Top 10 Assessment — WS-SEC (COD-18)

> **Assessor:** CEO (Agent 2d6b0774) / WS-SEC Sprint 3  
> **Date:** 2026-05-27  
> **Scope:** 22 microservices, FastAPI + asyncpg + structlog stack  
> **Methodology:** OWASP Top 10:2021, paper assessment based on code review  

---

## A01:2021 — Broken Access Control

| Check | Status | Evidence |
|-------|:------:|----------|
| JWT-based auth | ✅ | RS256 asymmetric signing, JWKS endpoint for verification |
| Role-based access | ✅ | 7-role hierarchy, `require_admin` guard on destructive endpoints |
| Cross-service isolation | ✅ | Shadow tables read-only, no model imports across services |
| Rate limiting on public endpoints | ✅ | `slowapi` on all services, stricter on OTP/login |
| CORS configuration | ✅ | `CORS_ORIGINS` from `.env`, dev allows `*`, prod restricted |
| Missing function-level checks | ⚠️ | `documents` service is DMZ — should verify callers are internal |
| Error message leak | ⚠️ | `auth_guard.py:79`: raw exception in HTTPException message |

**Verdict:** 🟢 Pass (with minor findings)

---

## A02:2021 — Cryptographic Failures

| Check | Status | Evidence |
|-------|:------:|----------|
| JWT algorithm | ✅ | RS256 (asymmetric) — no HS256 downgrade risk |
| Private key protection | ✅ | `private.pem` in `.gitignore`, never committed, auto-generated |
| Password storage | ✅ | Delegated to auth service (no plaintext passwords) |
| TLS/HTTPS | ⚠️ | Not configured yet — pre-production; nginx planned for prod |
| Secret management | 🔴 | `.env` files used; secret manager migration pending (§7 Q3) |
| Hardcoded credentials | ✅ | Fase 1 fix: `database_url` no longer has `v7m:v7m` default |

**Verdict:** 🟡 Needs improvement (TLS + secret manager pending)

---

## A03:2021 — Injection

| Check | Status | Evidence |
|-------|:------:|----------|
| SQL injection | ✅ | SQLAlchemy async + asyncpg: parameterized queries only |
|    | ✅ | Only `text("SELECT 1")` in health checks (no user input) |
| NoSQL injection | N/A | No MongoDB/NoSQL in use |
| LDAP/OS injection | N/A | No shell commands in API handlers |
| XSS (reflected) | N/A | JSON API, no HTML rendering in backend |

**Verdict:** 🟢 Pass

---

## A04:2021 — Insecure Design

| Check | Status | Evidence |
|-------|:------:|----------|
| Threat model documented | ✅ | Risk policy in RBAC_MATRIX.md §5 + CONVENTION §4.8 |
| Webhook verification | ✅ | HMAC signature on asaas/infinitepay (COD-30, COD-31) |
| PII handling policy | ✅ | PII audit complete, mask utilities in place |
| Rate limiting by design | ✅ | Default 200/min on all services via `slowapi` |
| Input validation | ✅ | `validate_cpf`, `validate_phone`, Pydantic v2 schemas |
| Cross-service boundaries | ✅ | 1 service = 1 schema, HTTP-only communication |
| Secret rotation | ⚠️ | No automated rotation; jwt keys regenerate on missing only |

**Verdict:** 🟢 Pass

---

## A05:2021 — Security Misconfiguration

| Check | Status | Evidence |
|-------|:------:|----------|
| CORS allowed origins | ✅ | Prod restricted to `CORS_ORIGINS` env var |
| Debug mode disabled | ✅ | No Flask debug; `ENV` controls CORS, not debug |
| Security headers | ⚠️ | Missing: HSTS, CSP, X-Content-Type-Options, X-Frame-Options |
| Error stack traces in responses | ⚠️ | `auth_guard.py:79`: exception detail in 401 response |
| Default credentials | ✅ | None; all config via `.env` |
| Unnecessary features | ✅ | No default accounts/pages/APIs enabled |
| Database hardening | ⚠️ | No connection pooling limits documented |

**Verdict:** 🟡 Needs improvement (headers + error masking)

---

## A06:2021 — Vulnerable and Outdated Components

| Check | Status | Evidence |
|-------|:------:|----------|
| Python version | ✅ | 3.12 (current, supported until 2028-10) |
| FastAPI | ✅ | 0.115+ (current) |
| SQLAlchemy | ✅ | 2.0+ async (current) |
| asyncpg | ✅ | 0.30+ (current) |
| Dependency tracking | ⚠️ | `uv.lock` exists but no automated CVE scanning |
| Known vulnerabilities | ⚠️ | No `pip-audit` or `safety` scan configured |

**Verdict:** 🟡 Needs improvement (automated CVE scanning)

---

## A07:2021 — Identification and Authentication Failures

| Check | Status | Evidence |
|-------|:------:|----------|
| OTP rate limiting | ✅ | 1 request per 30 seconds per phone |
| User enumeration mitigation | ✅ | COD-32: generic responses on `/check` and `/recover` |
| Brute force protection | ✅ | Rate limiting on login endpoints |
| Session management | ✅ | JWT with short-lived access tokens |
| Multi-factor | ✅ | OTP-based second factor via `otp` service |
| Weak password checks | ⚠️ | No password strength policy documented |
| Credential recovery | ✅ | OTP-based recovery flow |

**Verdict:** 🟢 Pass (password policy is advisory)

---

## A08:2021 — Software and Data Integrity Failures

| Check | Status | Evidence |
|-------|:------:|----------|
| Deserialization of untrusted data | ✅ | Pydantic v2 for all input; no `pickle` usage |
| CI/CD pipeline integrity | ⚠️ | No pipeline configured yet (pre-production) |
| Third-party library integrity | ⚠️ | No hash/pin verification; `uv.lock` provides version pinning |
| Auto-update of dependencies | ⚠️ | No automated update policy |

**Verdict:** 🟡 Needs improvement (pipeline + integrity verification)

---

## A09:2021 — Security Logging and Monitoring Failures

| Check | Status | Evidence |
|-------|:------:|----------|
| Structured logging | ✅ | `structlog` on all services (CONVENTION §2) |
| Login success/failure logging | ✅ | `login_success` + `login_role_denied` events (COD-18) |
| Atomic operations logging | ✅ | `atomic_token_created` + `atomic_wipe_executed` (COD-18) |
| OTP dispatch failure logging | ✅ | Was silently swallowed; now logged (COD-18 fix) |
| PII masking in logs | ✅ | `mask_phone()`, `mask_email()`, `mask_number()` utilities |
| Log sanitization | ✅ | `_sanitize_log_body()` removes tokens, CPF, phone, email |
| Centralized log aggregation | ⚠️ | Grafana+Loki+Promtail configured (COD-17) but pre-prod |
| Alerting on security events | ❌ | No alert rules for login failures, admin operations |
| Audit trail retention | ⚠️ | No retention policy defined |

**Verdict:** 🟡 Needs improvement (alerting + retention)

---

## A10:2021 — Server-Side Request Forgery (SSRF)

| Check | Status | Evidence |
|-------|:------:|----------|
| User-controlled URLs in requests | ⚠️ | `cep/{zipcode}` proxies ViaCEP — input validated but URL constructed |
| External service isolation | ✅ | Webhooks go through dedicated app first, then DMZ internally |
| Network segmentation | ⚠️ | All services on same Docker network (pre-prod) |
| URL allow-listing | ❌ | No allow-list for external service calls |

**Verdict:** 🟡 Needs improvement (URL validation + network segmentation)

---

## Summary

| OWASP Category | Verdict | Priority |
|----------------|:-------:|:--------:|
| A01 — Broken Access Control | 🟢 Pass | — |
| A02 — Cryptographic Failures | 🟡 Needs work | P0 (secret manager §7 Q3) |
| A03 — Injection | 🟢 Pass | — |
| A04 — Insecure Design | 🟢 Pass | — |
| A05 — Security Misconfiguration | 🟡 Needs work | P1 (headers + error masking) |
| A06 — Vulnerable Components | 🟡 Needs work | P2 (CVE scanning) |
| A07 — Auth Failures | 🟢 Pass | — |
| A08 — Data Integrity | 🟡 Needs work | P2 (CI/CD pipeline) |
| A09 — Logging & Monitoring | 🟡 Needs work | P1 (alerting rules) |
| A10 — SSRF | 🟡 Needs work | P2 (URL allow-listing) |

**Overall: 4 Green, 5 Yellow, 1 Red (secret manager — blocked on §7 Q3)**

### Immediate Actions (this sprint)
1. ~~Auth endpoint hardening (require_admin)~~ ✅ COD-45
2. ~~Webhook signature verification~~ ✅ COD-30, COD-31
3. ~~PII audit + log masking~~ ✅ COD-18 PII fix
4. 🔴 Secret manager migration — blocked on §7 Q3

### Short-term Actions (Sprint 3-4)
5. Error message hardening: mask exception details in HTTPException responses
6. Security headers: HSTS, CSP, X-Content-Type-Options, X-Frame-Options
7. Security alert rules: login failures, admin operations, rate-limit hits

### Medium-term (pre-production)
8. Automated CVE scanning (`pip-audit` in CI)
9. URL allow-listing for external service calls
10. Database connection pooling limits
11. Log retention policy
