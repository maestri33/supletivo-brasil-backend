# QA Strategy — WS-QA

> Baseline audit: 2026-05-27 (refresh) → Sprint 0 fix: 2026-05-27 | QA Engineer: COD-19
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

## 2. Baseline Coverage (2026-05-27 — 2º audit, Sprint 0 concluído)

### Global Stats

- **23 módulos** top-level (19 com código fonte, 4 stubs vazios)
- **~443 testes passando** (eram ~372 no 1º audit) — **+71 testes resgatados**
- **13 serviços** com testes, **6 sem testes**, **4 stubs** (commissions, coordinator, staff, wiki)

### Services with runnable tests

| Service | Tests | Pass | Fail/Err/Skip | WS | Money Path? | Status |
|---------|-------|------|---------------|-----|-------------|--------|
| asaas | 191 | 191 | 0 | WS-PARTEB | ✅ critical | 🟢 Bom — 74% cov |
| profiles | 148 | 68 | 80 fail | WS-CONFA | — | 🔴 80 falhas (422 ≠ 200/201/204/404) |
| fees | 36 | 36 | 0 | WS-PARTEB | — | 🟢 OK |
| auth | 29 | 12 | 2 fail + 15 err | WS-CONFA | — | 🟡 OSError resolvido. Falhas: Identity→User rename + roles service |
| infinitepay | 26 | 24 | 2 fail | WS-PARTEB | ✅ critical | 🟡 HMAC validation + health status |
| promoter | 16 | 16 | 0 | WS-CONFA | — | 🟢 OK |
| candidate | 13 | 13 | 0 | WS-CONFA | ✅ | 🟡 Baixo |
| enrollment | 12 | 12 | 0 | WS-CONFA | ✅ | 🟢 OK — resgatado! (era 0) |
| training | 11 | 11 | 0 | WS-CONFA | ✅ | 🟡 Baixo |
| hub | 16 | 15 | 1 fail | WS-INFRA | — | 🟢 OK — resgatado! (era 0). 1 bug: POST sem auth aceito |
| notify | 40 | 40 | 0 | WS-INFRA | — | 🟢 OK — resgatado! (era import error) |
| student | 5 | 5 | 0 | WS-CONFA | — | 🔴 0% coverage (tests não testam app) |
| otp | 13 | 0 | 13 skipped | — | — | ⚠️ Intencional — suíte legada Tortoise, aguardando reescrita SA |

### Services with ZERO tests (critical gaps)

| Service | src LOC | src files | Impact |
|---------|---------|-----------|--------|
| **lead** | 3,058 | 37 | 🔴 CRITICAL — entry point do money path |
| **address** | 1,266 | 27 | 🔴 Usado por lead, candidate, promoter |
| **ai** | 1,674 | 22 | 🟡 Dependência de training |
| **roles** | 787 | 18 | 🟡 RBAC cross-service |
| documents | 731 | 21 | 🟡 Sem .venv buildável |
| jwt | 660 | 17 | 🟡 Sem .venv buildável |

### Serviços com problemas

| Service | Issue | Ação necessária |
|---------|-------|-----------------|
| **profiles** | 80 falhas (assert 422 == 200/201/204/404) — endpoints divergiram | Revisar API de profiles, atualizar testes |
| **auth** | Identity→User rename (14 err) + /config/roles 404 (2 fail) | Reescrever test_role_logic.py |
| **infinitepay** | 2 fail: HMAC signature + health webhook status | Investigar validação HMAC |
| **hub** | POST /api/v1/hubs aceita request sem auth (201 ≠ 403) | Corrigir dependency injection na rota POST |
| **otp** | Todos skipped — suíte Tortoise legada | Rewrite completo com SQLAlchemy |
| **student** | 5 passam mas **0% coverage** — tests/test_student.py não importa app | Refatorar testes para usar o app real |
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

### Sprint 0 (COD-19 baseline — 2º refresh 2026-05-27 ~08:25)
- [x] Audit baseline publicado (este documento)
- [x] Fix notify: resolvido — 40/40 pass com testcontainers[postgres] + docker
- [x] Fix otp: pytest já instalado; 13/13 intencionalmente skip (suíte legada Tortoise, aguarda reescrita SQLAlchemy)
- [x] Fix auth: OSError resolvido. 12 pass, 2 fail (route /config/roles 404), 15 err (Identity→User rename). test_role_logic.py precisa reescrita.
- [x] Fix enrollment: 12/12 pass (skips resolvidos com testcontainers)
- [x] Fix hub: 15/16 pass, 1 fail (auth guard ausente — POST retorna 201 em vez de 403)
- [x] Fix profiles: diagnosticado — 68/148 pass, 80 fail (assert 422 → endpoints mudaram validação)
- [x] Fix infinitepay: diagnosticado — 24/26 pass, 2 fail (HMAC validation + health webhook status)

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
