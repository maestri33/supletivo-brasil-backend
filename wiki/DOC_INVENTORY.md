# Inventário de Documentação — Backend Supletivo

> **Sprint 0 (WS-DOCS)** — levantamento do estado atual da documentação.
> Data: 2026-05-27 | Issue: COD-20

---

## 1. Resumo

| Artefato | Estado | Notas |
|---|---|---|
| CONVENTION.md | ✓ completo | 202 linhas, §1–§15, checklist de revisão |
| RUNBOOK.md | ✓ Sprint 2 | ~320 linhas, 8 seções com dados reais do docker-compose.dev.yml |
| PULL_REQUEST_TEMPLATE.md | ✓ completo | 68 linhas, checklist §15, 22 serviços + infra |
| <app>/.env.example | 23 total | ✅ 20 ativos + 2 Parte B + 1 raiz (COD-14) |
| wiki/<app>.md | 22/22 | ✅ Completo |
| <app>/.claude/CLAUDE.md | 22/22 | ✅ Completo (commissions e coordinator com stub Parte B) |
| <app>/README.md | 22/22 | ✅ Completo (commissions e coordinator com stub Parte B) |

---

## 2. CLAUDE.md por serviço

| Serviço | Status | Parte | CLAUDE.md | README.md | wiki/<app>.md |
|---|---|---|---|---|---|
| address | ativo | A | ✓ | ✓ | ✓ |
| ai | ativo | A | ✓ | ✓ | ✓ |
| asaas | ativo (F5) | A | ✓ | ✓ | ✓ |
| auth | ativo | A | ✓ | ✓ | ✓ |
| candidate | ativo | A | ✓ | ✓ | ✓ |
| commissions | não criado | B | ✓ | ✓ | ✓ |
| coordinator | não criado | B | ✓ | ✓ | ✓ |
| documents | ativo | A | ✓ | ✓ | ✓ |
| enrollment | ativo | A | ✓ | ✓ | ✓ |
| fees | ativo | A | ✓ | ✓ | ✓ |
| hub | ativo | A | ✓ | ✓ | ✓ |
| infinitepay | ativo (F5) | A | ✓ | ✓ | ✓ |
| jwt | ativo | A | ✓ | ✓ | ✓ |
| lead | ativo (ref.) | A | ✓ | ✓ | ✓ |
| notify | ativo | A | ✓ | ✓ | ✓ |
| otp | ativo | A | ✓ | ✓ | ✓ |
| profiles | ativo | A | ✓ | ✓ | ✓ |
| promoter | ativo | A | ✓ | ✓ | ✓ |
| roles | ativo | A | ✓ | ✓ | ✓ |
| staff | ativo (spine) | A | ✓ | ✓ | ✓ |
| student | ativo (M1) | A | ✓ | ✓ | ✓ |
| training | ativo | A | ✓ | ✓ | ✓ |

### Gaps priorizados

**P0 — Ativos sem CLAUDE.md (bloqueia trabalho dos agentes):**
- Nenhum. Todos os 20 serviços com código têm CLAUDE.md. ✓

**P1 — Wiki ausente para serviço ativo:**
- Nenhum. Todos os 22 serviços têm wiki/<app>.md. ✓

**P2 — README.md ausente (não bloqueia, mas útil para devs humanos):**
- Nenhum. Todos os 22 serviços têm README.md. ✓

**Parte B**
- commissions, coordinator — criar CLAUDE.md + wiki.md + README.md + código

---

## 3. wiki/<app>.md — Cobertura

**22/22 completos.** ✅ Todos os serviços têm wiki.

---

## 4. README.md — Cobertura

20/22 serviços têm README.md. Faltam 2: commissions, coordinator (ambos sem código ainda).

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

1. Manter CLAUDE.md dos 17 serviços ativos atualizados conforme refactors e novas features
2. Criar CLAUDE.md + wiki.md + README.md para os 5 serviços Parte B (commissions, coordinator, hub, staff, student) quando nascerem
3. Quando WS-INFRA entregar docker-compose de produção: expandir RUNBOOK.md §2–§5 com comandos reais
4. Sprint 4: RUNBOOK completo + on-call playbook (cross com WS-OBS)
