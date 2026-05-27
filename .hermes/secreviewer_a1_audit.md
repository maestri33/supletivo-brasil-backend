# COD-45: A1 Endpoint Auth Audit — Complete Classification

## Classification Legend (CONVENTION §5)
- 🔓 **Desmilitarizado** — sem auth, uso interno entre serviços
- 🔐 **Autenticado** — requer JWT + role
- 🌐 **Público** — sem auth, mas com rate-limit + logging máximo + sanitização

---

## 1. address
| File | Endpoint | Classification | Notes |
|------|----------|---------------|-------|
| addresses.py | POST / | 🔓 Desmilitarizado | CRUD interno, chamado por entity_addresses. No user-facing access |
| | GET / | 🔓 | List all addresses, internal use |
| | GET /by-external-id/ | 🔓 | Internal lookup |
| | GET /current | 🔓 | Internal |
| | GET /cep/{zipcode} | 🌐 Público | ViaCEP lookup — needs rate limit |
| | GET /{address_id} | 🔓 | Internal |
| | PATCH /{address_id} | 🔓 | Internal |
| | DELETE /{address_id} | 🔓 | Internal |
| entity_addresses.py | all 5 | 🔓 Desmilitarizado | Called by auth service during provisioning |

## 2. ai
| File | Endpoint | Classification | Notes |
|------|----------|---------------|-------|
| image.py | POST / | 🔓 Desmilitarizado | Internal AI generation |
| | POST /vision | 🔓 | Internal |
| json_endpoint.py | POST / | 🔓 | Internal |
| text.py | POST / | 🔓 | Internal |
| tts.py | POST / | 🔓 | Internal, no auth (uses API key in integration) |
| ocr.py | POST /, /document | 🔓 | Internal |
| v1.py | all 3 | 🔓 | Internal chat/summarize/extract |

## 3. asaas
| File | Endpoint | Classification | Notes |
|------|----------|---------------|-------|
| charge.py | all | 🔓 Desmilitarizado | Called by candidate service internally |
| payment.py | all | 🔓 | Payment operations via internal calls |
| pixkey.py | all | 🔓 | PIX key management internal |
| config.py | all | 🔓 | Asaas config set by infra scripts |
| webhook.py | POST /security-validator | 🌐 Público | Asaas webhook — HMAC-SHA256 verified + IP allow-list |
| | POST /receive | 🌐 Público | Asaas webhook — same security |

## 4. auth
| File | Endpoint | Classification | Notes |
|------|----------|---------------|-------|
| atomic.py | POST /, DELETE /{id} | 🔐 Autenticado | **MISSING AUTH** — atomic cleanup endpoint can wipe ecosystem |
| check.py | POST / | 🌐 Público | CPF/phone check for login flow — user enumeration already mitigated via uniform responses (COD-32) |
| log.py | GET /, DELETE / | 🔐 Autenticado | **MISSING AUTH** — query/clear logs |
| login.py | POST / | 🌐 Público | Login flow with OTP |
| recover.py | POST / | 🌐 Público | Password recovery flow |
| register.py | POST / | 🌐 Público | Registration — requires OTP verification |

## 5. candidate
| File | Endpoint | Classification | Notes |
|------|----------|---------------|-------|
| authenticated/* (8 files) | all | 🔐 Autenticado | Uses auth dependencies ✅ |
| public/auth.py | all | 🌐 Público | Intended public endpoint ✅ |
| demilitarized/candidates.py | all | 🔓 Desmilitarizado | Internal calls ✅ |

## 6. documents
| File | Endpoint | Classification | Notes |
|------|----------|---------------|-------|
| documents.py | all 6 | 🔓 Desmilitarizado | **NO AUTH** — called internally via auth/candidate provisioning. Should use desmilitarizado internal pattern |

## 7. enrollment
| enrollments.py | GET | 🔓 Desmilitarizado | Internal enrollment lookup |
| webhooks.py | POST / | 🌐 Público | Notify webhook callback |
| | GET /events | 🔓 Desmilitarizado | Internal event log |

## 8. hub
| hubs.py | GET /, GET /{id} | 🌐 Público | Public listing — rate limit needed |
| | POST, PATCH, PUT | 🔐 Autenticado | Uses get_current_external_id ✅ |

## 9. infinitepay
| checkout.py | all | 🔓 Desmilitarizado | Checkout operations called internally |
| webhooks.py | POST / | 🌐 Público | InfinitePay webhook — HMAC verified (COD-30) ✅ |
| | GET / | 🌐 Público | Checkout status query |

## 10. jwt
| tokens.py | POST /issue | 🔓 Desmilitarizado | Token issue called by auth service |
| | POST /refresh | 🔓 | Token refresh |
| | GET /.well-known/jwks.json | 🌐 Público | JWKS endpoint for JWT verification |

## 11. notify
| contacts.py | all | 🔓 Desmilitarizado | Contact CRUD internal |
| messages.py | all | 🔓 | Message sending internal |
| templates.py | all | 🔓 | Template management internal |
| logs.py | all | 🔓 | Log queries internal |
| instructions.py | GET / | 🔓 | Instructions internal |
| whatsapp.py | all | 🔓 | WhatsApp API internal |

## 12. otp
| otp.py | all | 🔓 Desmilitarizado | OTP management internal |
| webhook.py | POST /notify/{id} | 🌐 Público | Notify callback |
| status.py | GET /status | 🔓 | Status page internal |
| deps.py | http_client_dep | N/A | Helper |

## 13. profiles
| profiles.py | all | 🔓 Desmilitarizado | Profile CRUD internal |

## 14. promoter
| authenticated/me.py | all | 🔐 Autenticado | ✅ Uses auth deps |
| public/auth.py | all | 🌐 Público | ✅ Intended public |
| demilitarized/promoters.py | all | 🔓 Desmilitarizado | ✅ Internal |

## 15. roles
| role.py | all | 🔓 Desmilitarizado | Role management internal |
| role_rules.py | all | 🔓 | Role rules internal |
| users.py | all | 🔓 | User listing internal |

## 16. staff
(no api/ directory — proxy endpoints)

## 17. training
| demilitarized/materials.py | all | 🔓 Desmilitarizado | ✅ Internal, explicitly desmilitarized |

---

## Findings Summary

### 🔴 Critical — Needs auth fix

| Service | Endpoints | Risk |
|---------|-----------|------|
| **auth/atomic.py** | POST /, DELETE /{id} | Can wipe ENTIRE ecosystem — user, roles, profiles, addresses, leads deleted. **Must add auth guard** |
| **auth/log.py** | GET /, DELETE / | Anyone can query/clear all API logs |

### 🟡 Advisory — Needs verification

| Service | Status | Action |
|---------|--------|--------|
| **documents** | 🔓 (should be desmilitarizado) | Confirm callers are internal only |
| **hub** | 🌐 public reads | Add rate limiting to public endpoints |
| **jwt/jwks.json** | 🌐 public | OK, this is standard |

### ✅ Properly categorized — no action needed
address, ai, asaas, candidate, enrollment, infinitepay, notify, otp, profiles, promoter, roles, training
