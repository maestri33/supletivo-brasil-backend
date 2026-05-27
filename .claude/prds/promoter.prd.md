# Promoter Service

## Problem
Quando um candidato é aprovado no treinamento e na entrevista com o coordenador do polo, ele precisa virar um **promoter** — um divulgador que capta leads via link de indicação e recebe comissões. Hoje não existe serviço que represente o promoter, valide o `ref` de captação, nem consolide os leads e comissões dele. Sem isso não há como atribuir leads a um divulgador, nem pagá-lo.

## Evidence
- Specs internos do engenheiro: `promoter/TODO`, e cruzamento com `coordinator/TODO`, `training/TODO`, `commissions/TODO`, `hub/TODO`, `candidate/TODO`.
- Assumption — modelo de negócio definido pelo engenheiro; sem métricas de produção ainda (validar via uso real após go-live).

## Users
- **Primary**: **Promoter** (ex-candidato aprovado) — divulga seu link `/ref=<external_id>` e acompanha seus leads e comissões.
- **Também consomem**: `coordinator` (dispara a criação do promoter pós-entrevista), `lead` (valida o `ref` na captação), `commissions` (paga o promoter).
- **Not for**: leads/alunos finais (falam com a landing/serviço `lead`); candidatos ainda não aprovados (vivem em `candidate`/`training`).

## Hypothesis
Acreditamos que um serviço **promoter** (criação via `coordinator` + validação de `ref` + visão read-only de leads/comissões) vai **permitir captação atribuída e pagamento de promotores** para os **promoters e serviços internos**.
Saberemos que acertamos quando **todo lead captado tiver um promoter atribuído via `ref` válido e o promoter conseguir ver seus leads e comissões**.

## Success Metrics
| Metric | Target | How measured |
|---|---|---|
| Leads com `ref` válido atribuído | 100% dos refs válidos resolvidos | logs do endpoint de validação + serviço `lead` |
| Criação de promoter pós-entrevista | end-to-end sem erro | chamada do `coordinator` → registro criado |
| Visão consolidada (leads/comissões) | promoter lista os próprios | endpoints autenticados read-only |

## Scope
**MVP (serviço completo, conforme alinhado)**
1. **Criação do promoter** — endpoint **desmilitarizado** chamado pelo `coordinator` (após a entrevista) com o `external_id` do candidato aprovado; monta o registro, resolvendo dados de `profiles`/`address` via `httpx` quando necessário.
2. **Validação de `ref`** — endpoint **desmilitarizado** que resolve/valida `ref=external_id` (usado pelo `lead`, já que a landing chama o `lead` direto). Retorna se é um promoter ativo + `hub`.
3. **Visão de leads** — endpoint **autenticado** read-only, agregando do serviço `lead` por `httpx`, filtrado pelo `external_id` do promoter.
4. **Visão de comissões** — endpoint **autenticado** read-only, agregando do serviço `commissions` por `httpx`, filtrado pelo `external_id` do promoter.

**Out of scope**
- Captação do lead dentro do promoter — a landing chama o `lead` direto; promoter só valida o `ref` (fronteira §6).
- Cálculo/pagamento de comissão — domínio de `commissions`/`asaas`.
- Gestão do hub — domínio de `hub`.
- Fluxo de candidate/training — outros serviços.

## Delivery Milestones
<!-- Status: pending | in-progress | complete -->

| # | Milestone | Outcome | Status | Plan |
|---|---|---|---|---|
| 1 | Esqueleto do serviço | estrutura lead-like (app/, config, db, main, alembic, pyproject) sobe e responde /health | pending | — |
| 2 | Modelo + criação | coordinator cria o promoter via endpoint desmilitarizado | pending | — |
| 3 | Validação de ref | lead valida ref e recebe promoter+hub | pending | — |
| 4 | Visão de leads | promoter lista seus leads (read-only via httpx) | pending | — |
| 5 | Visão de comissões | promoter lista suas comissões (read-only via httpx) | pending | — |
| 6 | Notify/IA + testes + wiki | notificações por status, testes, ruff limpo, wiki/promoter.md | pending | — |

## Open Questions
- [ ] Quais dados o promoter **guarda** vs **resolve por httpx**? (mínimo: `external_id` do user + `hub`; profile/address/pix resolvidos sob demanda?)
- [ ] O `ref` é o `external_id` do **user** (auth) do promoter, ou um id próprio do registro de promoter? (spec diz `ref=external_id`)
- [ ] Validação de `ref`: o que o `lead` precisa de volta? (apenas `valid` + `hub`, ou também dados do promoter?)
- [ ] Status do promoter (ativo/suspenso) — o que bloqueia captação/comissão?

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Duplicar domínio de lead/commission (fere §6) | média | alto | read-only via httpx; sem tabela de lead/comissão aqui |
| Integração lead/commissions fora do ar | média | médio | §12 — não quebrar fluxo; tratar falha e degradar visão |
| `ref` inválido/abuso na validação | média | médio | validar + logar (structlog); status do promoter |

---
*Status: DRAFT — requirements only. Implementation planning pending via /plan.*
