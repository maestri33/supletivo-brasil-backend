# RBAC Matrix — Backend Supletivo (CONVENTION §5)

> Última atualização: 2026-05-27
> Auditado por: CEO Agent (COD-18 WS-SEC Sprint 1)

## Categorias de Acesso (§5)

### Categoria 1 — Público (sem autenticação)
Qualquer endpoint sem JWT obrigatório.

| Serviço | Endpoints | Observações |
|---------|-----------|-------------|
| auth | `/health`, `/ready`, `/api/v1/register`, `/api/v1/login`, `/api/v1/recover`, `/api/v1/check` | Rate-limited (slowapi) |
| lead | `/api/v1/public/*`, `/api/v1/demilitarized/*` | Webhooks de captação |
| asaas | webhooks | Com validação de assinatura + IP allow-list |
| infinitepay | webhooks | Com validação de assinatura + IP allow-list |

### Categoria 2 — Autenticado (JWT obrigatório)
Qualquer role com JWT válido. Sem restrição de role específica — apenas a presença do token.

| Serviço | Endpoints | Roles aceitas |
|---------|-----------|---------------|
| auth | `/api/v1/atomic` | admin |
| auth | `/api/v1/log` | admin |
| candidate | `/api/v1/candidates/*` | lead, training |
| enrollment | `/api/v1/enrollments/*` | student, coordinator |
| student | `/api/v1/authenticated/students` | coordinator (GET todos), student (GET próprio) |
| staff | `/api/v1/authenticated/*` | admin, staff |
| hub | `/api/v1/hubs/*` | admin, staff |

### Categoria 3 — Restrito (endpoint sem auth/rate-limit entra com revisão SEC)
Qualquer novo endpoint público sem JWT ou rate-limit requer revisão de segurança antes do deploy.

## Matriz de Roles

| Role | Acesso | Progressão | Serviços |
|------|--------|------------|----------|
| **admin** | Full — todos endpoints protegidos | Fixo | auth, staff, hub, coordinator |
| **staff** | Gestão de hubs e configuração | Fixo | staff, hub |
| **coordinator** | Gestão de alunos, documentos, diplomas, provas, taxas | Fixo | coordinator, student, enrollment |
| **training** | Candidato em fase de treinamento | lead → training (selfie) | candidate |
| **lead** | Candidato — captação e pré-matrícula | unauthenticated → lead (registro) | candidate, lead |
| **student** | Aluno matriculado | training → student (coordinator aprova) | student, enrollment |

## Regras de Transição (Role Promotion)

```
unauthenticated ──[register]──→ lead
lead ──[selfie aprovada]──→ training
training ──[coordinator aprova]──→ student
```

Regras implementadas no **Roles Service** (`roles/app/services/role_service.py`):
- `assign`: atribui role inicial (register)
- `promote`: transição entre roles com validação de pré-requisitos
- `block`: bloqueia usuário (impede login)
- `unblock`: desbloqueia usuário

## Mecanismos de Gate

| Serviço | Mecanismo | Arquivo |
|---------|-----------|---------|
| auth | JWT JWKS + `require_admin` (role="admin") | `auth/app/api/auth_guard.py` |
| staff | JWT RS256 + interseção `STAFF_ROLES = ["admin", "staff"]` | `staff/app/dependencies.py` |
| hub | JWT RS256 + interseção `STAFF_ROLES` | `hub/app/dependencies.py` |
| candidate | JWT RS256 + `roles` contém "lead" | `candidate/app/dependencies.py` |
| lead | JWT RS256 + `roles` contém "lead" | `lead/app/dependencies.py` |
| student | `require_role("coordinator")` / `require_role("student")` | `student/app/dependencies.py` |

## Riscos Identificados

| Risco | Severidade | Status |
|-------|-----------|--------|
| Roles Service sem rate-limit por role | Médio | ⚠️ Pendente verificação |
| `pyjwt[crypto]` — versão acompanhada? | Baixo | ⚠️ Verificar CVE database |
| Endpoints públicos sem CSRF (register/login) | Baixo | ✅ SPA — token no header |
| `.env` local com secrets — gitignored corretamente | Baixo | ✅ |
| PII em logs — auth sanitizado, demais serviços dependem de disciplina | Médio | ⚠️ Auditoria contínua (Sprint 1) |

## Próximos Passos (Sprint 2+)

- [ ] Secret manager (§7 Q3) para remover `.env` de prod
- [ ] Rate-limit por role no Roles Service
- [ ] OWASP Top-10 scan nos 22 serviços
- [ ] IP allow-list para Asaas/InfinitePay webhooks (validar com provedores)
