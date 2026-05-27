# QA Strategy — WS-QA

> Baseline audit: 2026-05-27 (refresh) | QA Engineer: COD-9
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

## 2. Baseline Coverage (2026-05-27 — fresh audit)

### Global Stats

- **23 módulos** top-level (19 com código fonte, 4 stubs vazios)
- **32,219 linhas** de código fonte / **8,103 linhas** de teste = **25.1% test/source ratio**
- **13 serviços** com testes, **6 sem testes**, **4 stubs** (commissions, coordinator, staff, wiki)

### Services with runnable tests

| Service | Tests | Pass | Fail/Err/Skip | WS | Money Path? | Status |
|---------|-------|------|---------------|-----|-------------|--------|
| asaas | 191 | 191 | 0 | WS-PARTEB | ✅ critical | 🟢 Bom — 74% cov |
| profiles | 148 | 68 | 80 fail | WS-CONFA | — | 🔴 80 falhas de assertion |
| fees | 36 | 36 | 0 | WS-PARTEB | — | 🟢 OK |
| auth | 29 | 12 | 17 err (OSError) | WS-CONFA | — | 🔴 multiprocessing quebrado |
| infinitepay | 20 | 20 | 0 | WS-PARTEB | ✅ critical | 🟡 Baixo — expandir |
| promoter | 16 | 16 | 0 | WS-CONFA | — | 🟢 OK |
| candidate | 13 | 13 | 0 | WS-CONFA | ✅ | 🟡 Baixo |
| enrollment | 12 | 0 | 12 skipped | WS-CONFA | ✅ | 🔴 Todos skipped |
| training | 11 | 11 | 0 | WS-CONFA | ✅ | 🟡 Baixo |
| hub | 7 | 0 | 7 skipped | WS-INFRA | — | 🔴 Todos skipped |
| student | 5 | 5 | 0 | WS-CONFA | — | 🔴 0% coverage (tests não testam app) |

### Services with ZERO tests (critical gaps)

| Service | src LOC | src files | Impact |
|---------|---------|-----------|--------|
| **lead** | 3,058 | 37 | 🔴 CRITICAL — entry point do money path |
| **address** | 1,266 | 27 | 🔴 Usado por lead, candidate, promoter |
| **ai** | 1,674 | 22 | 🟡 Dependência de training |
| **notify** | 4,474 | 42 | 🔴 803L de teste quebrado (import error) |
| **roles** | 787 | 18 | 🟡 RBAC cross-service |
| documents | 731 | 21 | 🟡 Sem .venv buildável |
| jwt | 660 | 17 | 🟡 Sem .venv buildável |

### Serviços com problemas

| Service | Issue |
|---------|-------|
| **notify** | `ModuleNotFoundError: No module named 'app.integrations.smtp'` — testes não coletam |
| **otp** | pytest não está instalado no .venv — testes não rodam |
| **auth** | 17 erros `OSError: Mul...` — provável multiprocessing/spawn |
| **profiles** | 80 falhas (assert 422 == 201, 422 == 404) — endpoints divergiram dos testes |
| **enrollment** | 12/12 skipped — nenhum teste executa |
| **hub** | 7/7 skipped — nenhum teste executa |
| **student** | 5 passam mas **0% coverage** — tests/test_student.py não importa app |

### Stubs (sem app code)

commissions, coordinator, staff, wiki — OK, ainda não implementados.

## 3. Money Path Coverage (60% target)

Fluxo: `lead create → checkout → asaas PIX charge → webhook paid → enrollment`

| Step | Service | Tests | Pass | Coverage Assessment |
|------|---------|-------|------|---------------------|
| Lead creation | lead | 0 | 0 | 🔴 ZERO |
| Auth (lead login) | auth | 29 | 12 (17 err) | 🔴 Quebrado |
| Checkout (GET/POST) | lead | 0 | 0 | 🔴 ZERO |
| Asaas PIX charge | asaas | 191 | 191 | 🟢 Bom (74%) |
| Asaas webhook | asaas | 191 (incl) | 191 | 🟢 Bom |
| Enrollment | enrollment | 12 | 0 (skipped) | 🔴 ZERO efetivo |

**Money path coverage efetiva: ~25%** (asaas funciona, resto quebrado/zerado)

## 4. Priority Roadmap

### Sprint 0 (this heartbeat — COD-19 baseline)
- [x] Audit baseline publicado (este documento)
- [ ] Fix notify: corrigir import `app.integrations.smtp` ou ajustar conftest
- [ ] Fix otp: instalar pytest no .venv
- [ ] Fix auth: investigar OSError (multiprocessing)
- [ ] Fix enrollment/hub: investigar por que todos os testes são skipped

### Sprint 1 (next)
- [ ] Test suite para lead service (prioridade máxima — 3,058L sem cobertura)
- [ ] Expandir infinitepay tests (20 → 50+)
- [ ] Expandir candidate tests (13 → 30+)
- [ ] Fix profiles: 80 assertions (verificar mudanças de API)
- [ ] Address service test suite (1,266L sem cobertura)

### Sprint 2+
- [ ] CI pipeline com coverage gate (pytest-cov em todos os serviços)
- [ ] Coverage gate: <60% money path = PR rejected
- [ ] Regression suite automatizada asaas/infinitepay
- [ ] E2E smoke: lead → checkout → PIX sandbox asaas → webhook → enrollment

## 5. Test Conventions

- **Framework**: pytest + pytest-asyncio (`asyncio_mode = "auto"`)
- **Coverage**: pytest-cov configurado por serviço (atual: só asaas e student têm)
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
