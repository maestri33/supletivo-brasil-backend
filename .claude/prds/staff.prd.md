# Staff — Serviço de Administração ("Boss" da Operação)

## Problem
A plataforma é um conjunto de microsserviços independentes, mas não existe nenhuma camada central de operação. Hoje não há (a) um lugar único para ver a saúde de todos os serviços nem (b) uma autoridade única para cadastrar polos (hubs) e definir seus coordenadores. Sem essa camada "boss", diagnosticar a plataforma exige checar serviço por serviço, e a gestão de polos/coordenadores não tem dono.

## Evidence
- **Assumption — item de roadmap greenfield**; sem métrica/ticket ainda. Needs validation via uso operacional real (operação interna usando o painel).
- Fonte: `staff/TODO` — *"é o boss da operação… é só staff que cadastra hub como também define o coordenador… seria bom toda saúde de cada serviço ser consumido."*
- Contexto: `hub/`, `coordinator/` e `staff/` existem apenas como `TODO` e estão sendo construídos **em paralelo** (uma sessão por serviço).

## Users
- **Primary**: equipe interna de operação/administração da plataforma ("staff"/admin), autenticada via JWT com role admin/staff. Aciona o serviço quando precisa cadastrar/gerir polos, atribuir coordenadores, ou checar a saúde dos serviços num lugar só.
- **Not for**: usuários finais (leads, alunos, promotores, candidatos); o coordenador em suas funções operacionais (isso pertence ao serviço `coordinator/`).

## Hypothesis
We believe **uma camada admin (staff) que centraliza o cadastro de polos/coordenadores e agrega a saúde dos serviços** will **dar à operação visibilidade e controle únicos sobre a plataforma** for **a equipe interna de administração**.
We'll know we're right when **a operação cadastra um polo e atribui um coordenador pelo staff e enxerga o status de todos os serviços num único endpoint, sem checar serviço por serviço**.

## Success Metrics
| Metric | Target | How measured |
|---|---|---|
| Cadastrar polo + atribuir coordenador | 1 fluxo autenticado, < 2 min | medição manual no MVP |
| Cobertura de health | 100% dos serviços do registry com `/health` | endpoint agregador |
| Detecção de serviço fora do ar | refletida no agregado on-demand e no histórico | comparação com `/health` direto do serviço |

## Scope
**MVP** — serviço FastAPI conforme CONVENTION.md (estrutura espelhando `lead`), schema Postgres próprio (`staff`), entregando:
- **Auth**: JWT + verificação de role admin/staff (endpoints de gestão autenticados).
- **Gestão de hub** (staff é dono dos dados): CRUD de polo — endereço (referência a `address`), marca (Estácio/Wyden/outro), coordenador (`external_id`).
- **Definição de coordenador**: atribuir um usuário como coordenador de um polo.
- **Health aggregation on-demand**: endpoint que faz fan-out via `httpx` nos `/health` dos serviços do registry (`.env`) e devolve o agregado, tolerante a falha/timeout.
- **Health aggregation agendada**: job periódico grava status/histórico no Postgres; endpoint lê histórico/uptime.
- `/health`, `/ready`, `/status` próprios do staff (padrão `lead`).

**Out of scope**
- Funções operacionais do coordenador (aprovar training, enviar docs à instituição, taxas, prova, diploma) — pertencem ao serviço `coordinator/`.
- Agregação de promotores/alunos por polo (views read-only consumindo candidate/lead/training/student) — pós-MVP.
- UI/front-end do painel — somente back-end/API.
- Definição da fronteira de escrita com os serviços `hub/` e `coordinator/` (criados em paralelo) — coordenar depois.
- Concessão de role de coordenador via serviço `roles/` — confirmar (ver Open Questions).

## Delivery Milestones
<!-- Business outcomes, not engineering tasks. /plan turns each into a plan. -->
<!-- Status: pending | in-progress | complete -->

| # | Milestone | Outcome | Status | Plan |
|---|---|---|---|---|
| 1 | Scaffolding + Auth | Serviço sobe com `/health` próprio; operação autentica via JWT+role admin | in-progress | `.claude/plans/staff.plan.md` |
| 2 | Health aggregation (on-demand) | Operação vê a saúde de todos os serviços do registry na hora, num endpoint | pending | — |
| 3 | Health aggregation (agendada) | Operação vê histórico/uptime dos serviços (polling grava no Postgres) | pending | — |
| 4 | Gestão de hub | Operação cadastra/edita um polo (endereço, marca, coordenador) | pending | — |
| 5 | Definição de coordenador | Operação atribui um coordenador a um polo | pending | — |

## Open Questions
- [ ] **Fronteira staff ↔ hub/ ↔ coordinator/** (construídos em paralelo): com staff como dono dos dados, como hub/ e coordinator/ consomem? (read-only via API desmilitarizada do staff?) Coordenar entre as sessões paralelas antes de implementar escrita.
- [ ] **Registry de serviços** a monitorar: lista + URLs via `.env`. Quais serviços entram no MVP? (serviços com `/health` hoje: address, ai, documents, infinitepay, jwt, lead, notify, otp, profiles — e os demais conforme subirem.)
- [ ] **Polling agendado**: intervalo, retenção do histórico e onde roda o scheduler (in-process vs. externo); risco de duplicação em múltiplas réplicas.
- [ ] **Marcas** (Estácio/Wyden/outro): enum fixo no código ou tabela no banco?
- [ ] **Endereço do hub**: shadow table read-only de `address` (§4) ou apenas `external_id` + validação via `httpx`?
- [ ] **"Definir coordenador"** concede role de coordenador via serviço `roles/`? Confirmar fluxo de ativação.

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Dupla propriedade de hub/coordenador (staff dono vs. serviços hub/coordinator em paralelo) | Alta | Alto | Definir fronteira antes de codar escrita; staff como fonte única, hub/coordinator read-only |
| Fan-out de health trava se um serviço pendurar | Média | Médio | Timeouts curtos por serviço (httpx), agregação tolerante a falha (§12) |
| Registry desatualizado (serviço novo não monitorado) | Média | Médio | Registry via `.env` documentado; default cobre serviços com `/health` |
| Scheduler in-process duplica em múltiplas réplicas | Baixa | Médio | Lock (Redis) ou job único; decidir no /plan |

---
*Status: DRAFT — requirements only. Implementation planning pending via /plan.*
