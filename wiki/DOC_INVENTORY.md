# Inventário de Documentação — Backend Supletivo

> **Sprint 0 (WS-DOCS)** — levantamento do estado atual da documentação.
> Data: 2026-05-27 | Issue: COD-20

---

## 1. Resumo

| Artefato | Estado | Notas |
|---|---|---|
| CONVENTION.md | ✓ completo | 202 linhas, §1–§15, checklist de revisão |
| RUNBOOK.md | ✓ esqueleto | 289 linhas, 8 seções (§1 inventário, §2 subir/derrubar, §3 backup/restore, §4 rotacão segredos, §5 escalar, §6 on-call, §7 checklist deploy, §8 links) |
| PULL_REQUEST_TEMPLATE.md | ✓ completo | 68 linhas, checklist §10 + §15, 22 serviços + infra |
| wiki/<app>.md | 19/22 | Faltam: staff, student, training |
| <app>/.claude/CLAUDE.md | 12/22 | 10 faltam (5 são Parte B não criados) |
| <app>/README.md | 7/22 | 15 faltam |

---

## 2. CLAUDE.md por serviço

| Serviço | Status | Parte | CLAUDE.md | README.md | wiki/<app>.md |
|---|---|---|---|---|---|
| address | ativo | A | ✓ | ✗ | ✓ |
| ai | ativo | A | ✓ | ✗ | ✓ |
| asaas | ativo (F5) | A | ✓ | ✓ | ✓ |
| auth | ativo | A | ✓ | ✗ | ✓ |
| candidate | ativo | A | ✓ | ✓ | ✓ |
| commissions | não criado | B | ✗ | ✗ | ✓ |
| coordinator | não criado | B | ✗ | ✗ | ✓ |
| documents | ativo | A | ✗ | ✗ | ✓ |
| enrollment | ativo | A | ✗ | ✗ | ✓ |
| fees | ativo | A | ✓ | ✓ | ✓ |
| hub | não criado | B | ✗ | ✗ | ✓ |
| infinitepay | ativo (F5) | A | ✓ | ✓ | ✓ |
| jwt | ativo | A | ✗ | ✗ | ✓ |
| lead | ativo (ref.) | A | ✗ | ✗ | ✓ |
| notify | ativo | A | ✓ | ✗ | ✓ |
| otp | ativo | A | ✓ | ✗ | ✓ |
| profiles | ativo | A | ✓ | ✓ | ✓ |
| promoter | ativo | A | ✓ | ✓ | ✓ |
| roles | ativo | A | ✗ | ✗ | ✓ |
| staff | não criado | B | ✗ | ✗ | ✗ |
| student | não criado | B | ✗ | ✗ | ✗ |
| training | ativo | A | ✓ | ✓ | ✗ |

### Gaps priorizados

**P0 — Ativos sem CLAUDE.md (bloqueia trabalho dos agentes):**
1. documents — ativo, sem CLAUDE.md, sem README.md
2. enrollment — ativo, sem CLAUDE.md, sem README.md (modelo de referência ao lado de lead!)
3. jwt — ativo, sem CLAUDE.md, sem README.md
4. lead — ativo (modelo de referência!), sem CLAUDE.md, sem README.md
5. roles — ativo, sem CLAUDE.md, sem README.md

**P1 — Wiki ausente para serviço ativo:**
6. training — ativo, tem CLAUDE.md e README.md, mas falta wiki/training.md

**P2 — README.md ausente (não bloqueia, mas útil para devs humanos):**
7. address, ai, auth, documents, enrollment, jwt, lead, notify, otp, roles (10 serviços ativos sem README)

**Parte B (baixa prioridade até o serviço ser criado):**
- commissions, coordinator, hub, staff, student — criar CLAUDE.md junto com o código

---

## 3. wiki/<app>.md — Cobertura

19/22 serviços têm wiki. Faltam:
- **training.md** — ativo, prioridade P1
- **staff.md** — Parte B, criar quando o serviço nascer
- **student.md** — Parte B, criar quando o serviço nascer

---

## 4. README.md — Cobertura

7/22 serviços têm README.md: asaas, candidate, fees, infinitepay, profiles, promoter, training.

Template padrão esperado (CONVENTION.md §3):
```markdown
# <serviço>
O que faz, como rodar, variáveis de ambiente.
```

---

## 5. Artefatos transversais

| Arquivo | Estado | Notas |
|---|---|---|
| CONVENTION.md | ✓ | Fonte de verdade; checklist §15 |
| RUNBOOK.md | ✓ esqueleto | Sprint 0 baseline; preencher com docker-compose e CI/CD |
| .github/PULL_REQUEST_TEMPLATE.md | ✓ | Alinhado com §10 + §15 |
| wiki/PLANO_ADEQUACAO.md | ✓ | Plano tático Parte A + Parte B |
| wiki/db.md | ✓ | Documentação do banco de dados |
| wiki/TODO | ✓ | Lembrete: não encher código de .md, criar wiki quando aprovado |

---

## 6. Próximos passos (Sprint 1 →)

1. Criar CLAUDE.md para os 5 serviços ativos sem: documents, enrollment, jwt, lead, roles
2. Criar wiki/training.md
3. Iniciar Sprint 1: preencher CLAUDE.md por serviço, atualizar conforme refactors
4. Quando WS-INFRA entregar docker-compose: expandir RUNBOOK.md §2–§5 com comandos reais
