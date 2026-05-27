# QA Strategy — WS-QA

> Baseline audit: 2026-05-27 | QA Engineer onboarding (COD-9)
> Charter: 60% money path + 40% global | E2E smoke | regression suite asaas/infinitepay

## 1. Test Pyramid

```
         ╱ E2E ╲          Smoke: money path completo (lead → checkout → asaas → webhook)
        ╱       ╲         Ferramenta: httpx (mesmo stack do projeto)
       ╱─────────╲
      ╱Integration╲       Testes cross-service: lead+asaas, auth+jwt, profiles+auth
     ╱─────────────╲      Banco real (Postgres) obrigatório nesta camada
    ╱───────────────╲
   ╱   Unit Tests    ╲    Maior volume — testa services/validators com mocks
  ╱───────────────────╲   SQLite in-memory aceitável (mas Postgres preferido)
```

### Camadas

| Camada | Escopo | DB | Mock Policy |
|--------|--------|----|-------------|
| **Unit** | 1 service, 1 function | SQLite :memory: OK | Mock integrations, real DB opcional |
| **Integration** | 1 service + Postgres real | Postgres | Mock external HTTP only |
| **E2E Smoke** | Multi-service money path | Postgres | Nada mockado (sandbox API externa OK) |

## 2. Baseline Coverage (2026-05-27)

### Services with runnable tests

| Service | Tests | WS | Money Path? | Status |
|---------|-------|-----|-------------|--------|
| asaas | 191 | WS-PARTEB | ✅ critical | Bom — expandir |
| profiles | 148 | WS-CONFA | — | Bom |
| fees | 36 | WS-PARTEB | — | OK |
| auth | 29 | WS-CONFA | — | OK |
| infinitepay | 20 | WS-PARTEB | ✅ critical | Baixo — expandir |
| promoter | 16 | WS-CONFA | — | OK |
| candidate | 13 | WS-CONFA | ✅ | Baixo |
| otp | 13 | WS-CONFA | — | OK |
| enrollment | 12 | WS-CONFA | ✅ | Baixo |
| training | 11 | WS-CONFA | ✅ | Baixo |
| hub | 5 | WS-INFRA | — | Baixo |
| student | 5 | WS-CONFA | — | Baixo |

**Total: ~499 tests across 12 services**

### Services with ZERO tests (critical gaps)

| Service | Has .venv | Has app/ | Impact |
|---------|-----------|----------|--------|
| **lead** | ✅ | ✅ | 🔴 CRITICAL — entry point do money path |
| **address** | ✅ | ✅ | 🔴 Usado por lead, candidate, promoter |
| **ai** | ✅ | ✅ | 🟡 Dependência de training |
| **roles** | ✅ | ✅ | 🟡 RBAC cross-service |
| documents | ❌ | ✅ | 🟡 Sem .venv, sem testes |
| jwt | ❌ | ✅ | 🟡 Sem .venv, sem testes |

### Skeletons (sem app code ainda)

commissions, coordinator, staff — OK, ainda não implementados.

### Serviços com problemas

- **notify**: 7 test files, mas falham coleta (SQLite URL inválida no .env)

## 3. Money Path Coverage (60% target)

Fluxo: `lead create → checkout → asaas PIX charge → webhook paid → enrollment`

| Step | Service | Tests | Coverage Assessment |
|------|---------|-------|---------------------|
| Lead creation | lead | 0 | 🔴 ZERO |
| Auth (lead login) | auth | 29 | 🟡 Parcial |
| Checkout (GET/POST) | lead | 0 | 🔴 ZERO |
| Asaas PIX charge | asaas | 191 | 🟢 Bom |
| Asaas webhook | asaas | 8 (webhook) | 🟢 Bom |
| Enrollment | enrollment | 12 | 🟡 Baixo |

**Money path coverage: ~41% (gap: lead + checkout = 0%)**

## 4. Priority Roadmap

### Sprint 0 (this heartbeat — COD-9 onboarding)
- [x] Audit baseline publicado (este documento)
- [ ] E2E smoke mínimo: lead → checkout → PIX sandbox asaas
- [ ] Fix notify test collection (SQLite URL)

### Sprint 1 (next)
- [ ] Test suite para lead service (prioridade máxima)
- [ ] Expandir infinitepay tests (20 → 50+)
- [ ] Expandir candidate/enrollment tests

### Sprint 2+
- [ ] Address service test suite
- [ ] CI pipeline com pytest + Postgres real
- [ ] Coverage gate: <60% money path = PR rejected
- [ ] Regression suite automatizada asaas/infinitepay

## 5. Test Conventions

- **Framework**: pytest + pytest-asyncio (`asyncio_mode = "auto"`)
- **Coverage**: pytest-cov configurado por serviço
- **DB**: Postgres real para integration/E2E; SQLite :memory: aceitável para unit
- **HTTP client**: httpx (mesmo do projeto — nunca requests)
- **Fixtures**: conftest.py por serviço com fixtures reutilizáveis
- **Naming**: `test_<modulo>.py` com funções `test_<comportamento>`

## 6. Quality Gates

- PR que reduz cobertura do money path abaixo de 60% → **rejeitado**
- PR sem testes para comportamento novo → **rejeitado**
- E2E smoke deve passar antes de deploy
- Regression suite roda em todo push na main

## 7. Dependencies

- WS-INFRA: docker-compose + Postgres real antes do gate de cobertura
- WS-CONFA: Fase 4 completa antes de expandir testes nos serviços refatorados
