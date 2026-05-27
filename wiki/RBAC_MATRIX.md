# RBAC Matrix — WS-SEC (COD-18)

> **Author:** CEO (Agent 2d6b0774) / Security Review WS-SEC  
> **Date:** 2026-05-27  
> **Basis:** CONVENTION.md §5 — 3 categorias de endpoint  
> **Input:** A1 Endpoint Auth Audit (`.hermes/secreviewer_a1_audit.md`)  

---

## 1. Categories (CONVENTION §5)

| # | Categoria | Auth Required | Rate Limit | Logging | Uso |
|---|-----------|:---:|:---:|:---:|------|
| 1 | **Desmilitarizado** (DMZ) | ❌ Nenhuma | Opcional | Mínimo | Comunicação interna entre apps da plataforma |
| 2 | **Autenticado** | ✅ JWT + Role | Por endpoint | Log de acesso | Usuários autenticados com role válida |
| 3 | **Público** | ❌ Nenhuma | ✅ Obrigatório | Máximo (IP, UA, payload hash) | Login, registro, webhooks externos |

---

## 2. Role Hierarchy

| Role | Scope | Admin? | Can Issue JWT? | Notes |
|------|-------|:------:|:---------------:|-------|
| `admin` | Global | ✅ | ✅ | Full system access; can call `/atomic`, `/log` |
| `staff` | Hub-level | ⚠️ Own hub | ❌ | Operations boss — manages hub + coordinator |
| `coordinator` | Hub-level | ⚠️ Own hub | ❌ | Manages training, exams, documents per hub |
| `promoter` | Self | ❌ | ❌ | Captures leads via `/ref=<external_id>` |
| `candidate` | Self | ❌ | ❌ | Pre-enrollment — check/register/login |
| `student` | Self | ❌ | ❌ | Enrolled student — docs, exams, diploma |
| `lead` | Self | ❌ | ❌ | Pre-candidate — raw lead from landing page |

**Rules:**
- `admin` bypasses all role checks — has `require_admin` guard on destructive endpoints
- Hub-scoped roles can only access their hub's resources
- Self-scoped roles can only access their own data
- Token issuance (`JWTClient.issue`) validates role exists in user's role set

---

## 3. Endpoint Classification by Service

### 3.1 auth

| Endpoint | Method | Category | Auth | Rate Limit | Notes |
|----------|--------|-----------|------|:----------:|-------|
| `/check` | POST | Público | ❌ | ✅ 1/30s per phone | User enumeration mitigated (COD-32) |
| `/login` | POST | Público | ❌ | ✅ per-IP | Returns JWT on success |
| `/recover` | POST | Público | ❌ | ✅ per-phone | Password recovery |
| `/register` | POST | Público | ❌ | ✅ per-phone | New user registration |
| `/atomic` | POST/DELETE | Autenticado | `require_admin` | — | Destructive op — admin only |
| `/log` | GET/DELETE | Autenticado | `require_admin` | — | Audit log — admin only |

### 3.2 asaas

| Endpoint | Method | Category | Auth | Rate Limit | Notes |
|----------|--------|-----------|------|:----------:|-------|
| `/webhooks/asaas` | POST | Público | ❌ (HMAC ✅) | ✅ | Webhook signature verified (COD-31) |
| All others | CRUD | Desmilitarizado | ❌ | — | Internal payment processing |

### 3.3 infinitepay

| Endpoint | Method | Category | Auth | Rate Limit | Notes |
|----------|--------|-----------|------|:----------:|-------|
| `/webhooks/infinitepay` | POST | Público | ❌ (HMAC ✅) | ✅ | Webhook signature verified (COD-30) |
| All others | CRUD | Desmilitarizado | ❌ | — | Internal payment processing |

### 3.4 jwt

| Endpoint | Method | Category | Auth | Rate Limit | Notes |
|----------|--------|-----------|------|:----------:|-------|
| `/.well-known/jwks.json` | GET | Público | ❌ | ✅ | Public key distribution |
| All others | — | Desmilitarizado | ❌ | — | Internal token operations |

### 3.5 candidate

| Endpoint | Method | Category | Auth | Rate Limit | Notes |
|----------|--------|-----------|------|:----------:|-------|
| `/public/*` | POST | Público | ❌ | ✅ | Check/register/login |
| `/authenticated/*` | CRUD | Autenticado | JWT + candidate role | — | 8 modules |

### 3.6 hub

| Endpoint | Method | Category | Auth | Rate Limit | Notes |
|----------|--------|-----------|------|:----------:|-------|
| `GET /`, `GET /{id}` | GET | Público | ❌ | ✅ advisory | Public hub listing |
| `POST/PATCH/PUT` | CUD | Autenticado | JWT + staff/admin | — | Hub management |

### 3.7 enrollment

| Endpoint | Method | Category | Auth | Rate Limit | Notes |
|----------|--------|-----------|------|:----------:|-------|
| Webhook callback | POST | Público | ❌ | ✅ | External enrollment webhook |
| All others | CRUD | Desmilitarizado | ❌ | — | Internal enrollment processing |

### 3.8 otp

| Endpoint | Method | Category | Auth | Rate Limit | Notes |
|----------|--------|-----------|------|:----------:|-------|
| `/webhook/notify` | POST | Público | ❌ | ✅ | Internal webhook (notify→otp) |
| All others | — | Desmilitarizado | ❌ | — | Internal OTP operations |

### 3.9 address

| Endpoint | Method | Category | Auth | Rate Limit | Notes |
|----------|--------|-----------|------|:----------:|-------|
| `GET /cep/{zipcode}` | GET | Público | ❌ | ✅ advisory | Proxies ViaCEP — add rate-limit |
| All others | — | Desmilitarizado | ❌ | — | Internal address operations |

### 3.10 Remaining Services (all Desmilitarizado, internal-only)

| Service | Category | Notes |
|---------|-----------|-------|
| ai | Desmilitarizado | Internal AI/OCR processing |
| commissions | Desmilitarizado | Commission calculation (worker loop) |
| coordinator | Desmilitarizado | Hub-level admin operations |
| documents | Desmilitarizado | Document storage/retrieval |
| fees | Desmilitarizado | Fee calculation via asaas |
| lead | Desmilitarizado | Lead capture pipeline |
| notify | Desmilitarizado | Notification dispatch |
| profiles | Desmilitarizado | User profile management |
| promoter | Desmilitarizado | Promoter landing/leads |
| roles | Desmilitarizado | Role management |
| staff | Desmilitarizado | Staff operations |
| student | Desmilitarizado | Student lifecycle |
| training | Desmilitarizado | LMS content |

---

## 4. Cross-Cutting Security Rules

### 4.1 Authentication
- JWT signed with RS256 (private key in `jwt/`, never committed)
- JWKS endpoint serves public key for verification
- Token includes: `external_id`, `roles[]`, `exp`, `iat`
- All authenticated endpoints validate via `get_current_user` dependency

### 4.2 Authorization
- `require_admin` guard on destructive endpoints (`/atomic`, `/log`)
- Role validation: requested role must be in user's role set
- Cross-service: shadow tables read-only, no importing models from other services

### 4.3 Rate Limiting
- `slowapi` with `get_remote_address` key function
- Default: 200/minute on all services
- Stricter limits on public endpoints (OTP: 1/30s, login: per-IP)
- `RateLimitExceeded` → 429 with retry-after header

### 4.4 Webhook Security
- External webhooks: HMAC signature verification (asaas, infinitepay)
- Internal webhooks: desmilitarized, source IP logging
- Rule: external webhooks NEVER go directly to app code — route through service-specific app

### 4.5 PII Protection
- No PII in logs (CPF, RG, phone, email, address, photos)
- `notify` service: exemplary — `mask_phone()`, `mask_email()` on all PII
- `documents` service: document numbers masked before logging (COD-18 fix)
- Defense in depth: consider structlog processor for PII pattern redaction

### 4.6 Secrets
- `.env` files NEVER committed (`.gitignore` enforced)
- `private.pem` NEVER committed (jwt — `.gitignore` enforced)
- No hardcoded credentials (Fase 1 fix: `database_url` no longer has `v7m:v7m` default)
- Future: secret manager migration (§7 Q3 — pending)

---

## 5. Risk Policy (CONVENTION §4.8 + WS-SEC veto)

**Prohibited without human approval:**
1. Running destructive migration in production
2. Moving real money (asaas/infinitepay payments)
3. Exposing public endpoint without auth/rate-limit
4. Modifying keys/secrets
5. Bypassing webhook signature verification

**WS-SEC has veto power over:**
- Onboarding new external service (CONVENTION §4.8)
- Public endpoint without auth/rate-limit must pass SEC review

---

## 6. Gaps & Recommendations

| Gap | Priority | Issue | Status |
|-----|:--------:|-------|:------:|
| address `/cep` rate-limit | 🟡 Low | COD-18 advisory | Open |
| hub GET rate-limit | 🟡 Low | COD-18 advisory | Open |
| documents DMZ confirmation | 🟡 Low | Verify internal-only callers | Open |
| Secret manager migration | 🔴 High | §7 Q3 pending | Blocked |
| structlog PII processor | 🟡 Medium | Defense in depth | Open |
| CI PII audit automation | 🟡 Medium | grep for PII patterns in CI | Open |

---

## 7. Verification

- [x] All 22 services classified (A1 audit)
- [x] 4 critical auth fixes applied (COD-45: `require_admin` on atomic/log)
- [x] Webhook signatures verified (COD-30, COD-31)
- [x] User enumeration mitigated (COD-32)
- [x] PII audit complete + docs fix applied
- [ ] Secret manager migration (blocked — §7 Q3)
- [ ] OWASP-10 assessment (pending)
- [ ] Pre-prod security smoke test (pending)
