# Commissions — pagamento automático de promotores e coordenadores

> Serviço green-field (Parte B do `wiki/PLANO_ADEQUACAO.md`, item 8). Spec: `commissions/TODO`.
> Escopo restrito a `commissions/`. Espelha `lead`/`enrollment` (estrutura) e `asaas`/`infinitepay` (stack canônica).

## Problem
A plataforma precisa remunerar **promotores** (por lead completo) e **coordenadores de hub** (por student concluído) de forma automática, periódica e auditável. Hoje esse serviço não existe — cálculo e pagamento seriam manuais, sujeitos a erro, duplicidade e atraso. Sem ele, o incentivo que move a captação (promotores) e a conclusão (coordenadores) não fecha o ciclo.

## Evidence
- Spec interna `commissions/TODO` — fonte do requisito: geração por evento, lote semanal, payout via asaas, "horário America/Sao_Paulo, garanta que não se repita".
- `wiki/PLANO_ADEQUACAO.md` Parte B item 8 — commissions planejado: `worker_loop` asyncio espelhando asaas, idempotente, job sexta 18h America/Sao_Paulo.
- Dependências já existentes: `lead` tem `LeadStatus.COMPLETED` + `promoter_external_id`; `asaas` já faz **payout PIX** e é o **único serviço autorizado** a integrar com a API Asaas (§12), com callback interno por categoria (`payout`) via `/config/internal`.
- Assumption — sem métricas de uso (serviço novo); validação real só no deploy.

## Users
- **Primary (interno):** os serviços `lead` (e futuramente `student`) que disparam o gatilho de conclusão; o operador financeiro que confere o lote de pagamentos de sexta.
- **Beneficiários finais:** promotores (comissão por lead) e coordenadores de hub (comissão por student).
- **Not for:** taxas de matrícula (é do `fees`); cobrança/entrada de dinheiro (é do `asaas`); regras de papel/transição (é do `roles`).

## Hypothesis
We believe **um serviço dedicado que gera comissões por evento e paga em lote semanal via asaas** will **eliminar o pagamento manual e fechar o ciclo de incentivo** for **promotores e coordenadores**.
We'll know we're right when **toda lead completa / student concluído gera exatamente uma comissão, e o lote de sexta dispara o PIX correto sem duplicidade**.

## Success Metrics
| Metric | Target | How measured |
|---|---|---|
| Comissão por evento (sem duplicata) | exatamente 1 por evento | teste de idempotência + constraint única por evento |
| Job semanal idempotente (rodar 2× na janela não duplica) | 0 duplicatas | teste do worker (lock + marcador de período) |
| Horário do lote | sexta 18h America/Sao_Paulo | teste de timezone (ZoneInfo) |
| Conformidade técnica | 100% verde | `ruff` + `pytest` (sqlite) + `alembic upgrade head` |

## Scope
**MVP** — serviço completo dentro de `commissions/`:
- 2 tabelas: `commission` (registro por evento, status pendente→processada) e `payment_request` (1 por beneficiário/lote, status pendente→pago/falha).
- Gatilho via **webhook interno desmilitarizado** (§5): lead real agora; student pronto pra quando existir. Cada evento → 1 comissão (valores via `.env`: lead=100, student=50).
- **Lote semanal idempotente** (worker espelhando asaas), sexta 18h America/Sao_Paulo: agrega comissões pendentes por beneficiário; aplica **bônus de promotor** (se nº de leads-comissão do período ≥ LIMIAR do env → soma 1 comissão bônus do env); marca comissões como "processada"; cria `payment_request`.
- **Payout** via client interno `asaas` (httpx); recebimento de status via **callback interno** do asaas (categoria `payout`).
- **Resolução da pix key** do beneficiário via HTTP em `promoter`/`coordinator` (contrato definido; retorno TBD enquanto stubs).
- Verde em `ruff` + `pytest` (sqlite) + `alembic upgrade head`; `wiki/commissions.md` (fonte de verdade, §15) + `.claude/`.

**Out of scope**
- Payout real em produção — depende do onboarding da security key do asaas (operação de deploy) → diferido.
- Caminho coordenador ponta-a-ponta — `student` não existe ainda → gatilho pronto, sem teste e2e.
- Resolução real da pix key — `promoter`/`coordinator` são stubs → contrato definido, valor TBD.
- Bônus para coordenadores — fora (só promotores, leitura literal da spec).
- UI / relatórios financeiros / dashboards.

## Delivery Milestones
<!-- Resultados de negócio, não tarefas de engenharia. /plan transforma cada um em plano. -->

| # | Milestone | Outcome | Status | Plan |
|---|---|---|---|---|
| 1 | Espinha + modelos | serviço sobe; `alembic upgrade head` cria schema próprio + 2 tabelas | in-progress | `.claude/plans/commissions.plan.md` |
| 2 | Gatilho de comissão | lead completo (e student, pronto) → exatamente 1 comissão pendente, valor do env | pending | — |
| 3 | Lote semanal | sexta 18h America/Sao_Paulo: agrega por beneficiário, aplica bônus de promotor, cria payment_request — não-duplicável | pending | — |
| 4 | Payout asaas | client interno cria PIX no asaas e atualiza payment_request via callback de status | pending | — |
| 5 | Conformidade §15 | ruff/pytest/alembic verdes; `wiki/commissions.md` + `.claude/` publicados | pending | — |

## Open Questions
- [ ] Contrato exato do payload do gatilho (campos mínimos: external_id do lead/student, promoter/coordinator external_id, hub).
- [ ] Como resolver a pix key enquanto `promoter`/`coordinator` não existem — stub que retorna TBD? feature flag de "payout habilitado"?
- [ ] Nomes/valores exatos das envs (lead=100, student=50, LIMIAR do bônus, valor do bônus).
- [ ] "Número de leads que geraram comissão" do bônus = só do período da semana ou todo pendente acumulado? (assumido: pendentes do período).
- [ ] Callback de payout do asaas: a categoria `payout` do `/config/internal` já entrega o evento (shape) que o commissions precisa? confirmar.

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Duplicidade de pagamento (job 2× / evento 2×) | média | alto | constraint única por evento + lock/marcador de período no worker (espelhar asaas) |
| Dependências inexistentes (promoter/coordinator/student) bloqueiam e2e | alta | médio | contratos definidos + stubs; e2e diferido pro deploy |
| Timezone / horário de verão errado | baixa | médio | `ZoneInfo("America/Sao_Paulo")` + teste de borda |
| Falha do asaas no payout | média | alto | payment_request fica pendente + retry idempotente; fluxo não quebra (§12) |

---
*Status: DRAFT — requirements only. Implementation planning pending via /plan.*
