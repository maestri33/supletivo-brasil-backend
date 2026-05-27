# Lead — Production-Ready (cobertura + conformidade Fase 4)

## Problem
O microsserviço `lead` está funcionalmente completo (funil `captured → waiting → checkout → completed`, integrações de pagamento InfinitePay/Asaas e webhooks de retorno) e em uso, mas **não está apto a produção** pelos critérios da CONVENTION (§9/§15): há **zero teste automatizado** (bloqueio ❌), e restam **débitos de conformidade (Fase 4)** que ameaçam justamente o caminho do dinheiro — backoff síncrono bloqueando o event loop, handler de notificação fora do padrão de clients, e recibo PIX exibindo um valor-fallback fixo em vez do valor real cobrado. Sem cobertura, qualquer regressão no fluxo de pagamento passa silenciosa para produção, afetando os serviços que dependem dos webhooks do `lead` (enrollment, promoters, notify).

## Evidence
- `wiki/lead.md §16`: *"Ausência total de testes (`tests/` não existe) — único bloqueio para classificar como apto a produção com cobertura."* Confirmado ao vivo (2026-05-25): `lead/tests/` não existe.
- `wiki/lead.md §205`: webhook PIX do Asaas não traz o `amount`; usa `PIX_DEFAULT_AMOUNT` como fallback no recibo em vez do valor real do checkout.
- `wiki/lead.md §207`: `request_with_retry` (em `integrations/__init__.py`) usa `time.sleep()` síncrono no backoff, bloqueando o event loop durante as re-tentativas.
- `wiki/lead.md §209`: `notify_lead_captured` (em `notify/handlers.py`) faz chamadas HTTP diretas (`httpx.AsyncClient`) sem usar `NotifyClient`/`ProfilesClient` — inconsistente com o resto do serviço.
- `CONVENTION §15`: o serviço só fecha com teste do comportamento novo + `ruff` limpo + `wiki/<app>.md` atualizado.
- Contexto desta branch: TODOs inline do `lead` já resolvidos (`9251e4e`, `f59e046`); restam exatamente estes débitos não-marcados.

## Users
- **Primary**: o engenheiro que mantém o `lead` e precisa declará-lo apto a produção com confiança de que regressões no funil/pagamento são capturadas antes do deploy; e os serviços internos que consomem os webhooks/transições do `lead` (enrollment, promoters, notify) e dependem da confiabilidade do caminho do dinheiro.
- **Not for**: usuários finais (lead/candidato) — este ciclo **não muda comportamento visível nem contrato de API pública**; é dívida técnica e cobertura.

## Hypothesis
We believe **uma suíte de testes do caminho do dinheiro + a quitação dos 3 débitos Fase 4 que o afetam** will **permitir declarar `lead` "apto a produção" com a garantia de que regressões no funil e nos webhooks de pagamento são detectadas antes do deploy** for **o mantenedor do serviço e os consumidores internos dos seus webhooks**.
We'll know we're right when **`pytest` cobre verde o funil (`captured → waiting → checkout → completed`) e os 3 webhooks (infinitepay, asaas, notify), `ruff` está limpo, o backoff do retry é assíncrono, a notificação de captura passa pelos clients padronizados, o recibo PIX reflete o valor real, e `wiki/lead.md` registra o novo estado**.

## Success Metrics
| Metric | Target | How measured |
|---|---|---|
| Cobertura do caminho do dinheiro | funil (4 transições) + 3 webhooks com teste | inventário de fluxo × testes; `pytest` verde |
| Lint | 0 erros | `ruff check` + `ruff format --check` nos arquivos tocados |
| Bloqueio de event loop no retry | 0 `time.sleep()` em path async | revisão + `grep` |
| Débitos Fase 4 do caminho do dinheiro | 0 abertos (dos 3) | revisão §15 |
| Recibo PIX | valor real, sem fallback fixo | teste do webhook asaas com `amount` real |

## Scope
**MVP** — Tornar `lead` apto a produção pela cobertura do caminho do dinheiro + quitação dos débitos Fase 4 que o afetam: (1) suíte de testes cobrindo o funil `captured → waiting → checkout → completed` e os 3 webhooks de retorno (infinitepay confirma cartão, asaas confirma PIX, notify reporta entrega), com degradação graciosa das integrações externas (§12); (2) backoff **assíncrono** no retry de integrações (`await asyncio.sleep`), sem travar o event loop; (3) notificação de captura via os **clients padronizados** (`NotifyClient`/`ProfilesClient`), sem HTTP solto; (4) recibo PIX com o **valor real** cobrado, não o fallback fixo; (5) atualizar `wiki/lead.md` como fonte de verdade — somente após aprovado (§15).

**Out of scope**
- **PK→UUID (§4)** — aceito o padrão atual (`BigInteger` PK + `external_id` UUID); o `PLANO_ADEQUACAO` não listou `lead` para essa migração. Registrado como open question, não como trabalho deste ciclo.
- **Housekeeping de conformidade** — criar `CLAUDE.md` (justificando `pyjwt[crypto]` e `fastapi-structured-logging` fora da §2) e remover/implementar o `ROLES_BASE_URL` morto: sessão dedicada posterior.
- **Mover schemas inline de `api/` para `schemas/`** — desvio menor já documentado em `wiki/lead.md`; não bloqueia produção.
- **Cobertura exaustiva** — CRUD desmilitarizado de leads/checkouts e edge/erros amplos ficam além do caminho do dinheiro neste ciclo.
- **Novos recursos / mudança de API pública.**

## Delivery Milestones
<!-- Business outcomes, not engineering tasks. /plan turns each into a plan. -->
<!-- Status: pending | in-progress | complete -->

| # | Milestone | Outcome | Status | Plan |
|---|---|---|---|---|
| 1 | Caminho do dinheiro coberto por testes | Funil e os 3 webhooks têm testes automatizados verdes; regressão de pagamento é detectada antes do deploy; `ruff` limpo | pending | — |
| 2 | Retry não bloqueia o event loop | Backoff das integrações é assíncrono; chamadas concorrentes não travam durante re-tentativas | pending | — |
| 3 | Notificação de captura no padrão | Handler de captura usa os clients padronizados, consistente e testável, sem HTTP solto | pending | — |
| 4 | Recibo PIX com valor real | O recibo de pagamento PIX reflete o valor efetivamente cobrado, não um fallback fixo | pending | — |
| 5 | Doc fonte-de-verdade | `wiki/lead.md` atualizado para refletir o estado apto a produção | pending | — |

## Open Questions
- [ ] **Valor real do PIX**: o `amount` vem do checkout já persistido localmente (tabela `lead.checkouts`) ou exige consultar o serviço `asaas`? Define se há nova integração ou só leitura local. **TBD — needs validation.**
- [ ] **Testes**: rodar contra `sqlite+aiosqlite` async (como `asaas`/`infinitepay` já fazem) é suficiente, ou os tipos Postgres (ENUM `lead_status`, JSONB) exigem Postgres real no CI? **TBD — needs validation.**
- [ ] **PK→UUID §4**: aceitar `BigInteger` PK permanentemente para `lead`, ou agendar migração futura num ciclo de conformidade? **TBD — needs validation com o engenheiro.**

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `tests/` é greenfield (nenhuma base existente) | Alta | Médio | Espelhar o `conftest` async de `asaas`/`infinitepay` (padrão já validado: `sqlite+aiosqlite`, `httpx.AsyncClient`/ASGITransport, mocks de integração) |
| Trocar `time.sleep()` por async altera timing dos retries | Média | Médio | Cobrir o retry com teste **antes** de trocar o backoff; preservar a política de tentativas |
| Valor real do PIX exigir nova consulta externa ao `asaas` | Média | Médio | Preferir o valor já persistido no `lead.checkouts`; só integrar se indisponível (open question) |
| Refactor do `notify_lead_captured` quebrar o fluxo de captura | Média | Alto | Teste do `lead_captured` antes/depois; degradação graciosa (§12) — falha de notify nunca quebra o registro |
| Edição concorrente do worktree (candidate/notify em refactor) | Baixa p/ lead | Médio | `lead` está limpo e commitado; escopo fechado — não tocar outros apps neste ciclo |

---
*Status: DRAFT — requirements only. Implementation planning pending via /plan.*
