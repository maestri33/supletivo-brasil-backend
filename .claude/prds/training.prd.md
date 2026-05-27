# training — LMS de onboarding de promotores

## Problem
Candidatos aprovados precisam ser treinados e avaliados antes de virarem promotores, mas hoje não existe nenhum mecanismo para isso: não há trilha de conteúdo, nem correção, nem um portão objetivo entre `candidate` e `promoter`. Sem isso, ou a promoção é feita "no olho" (inconsistente e não auditável) ou candidatos ficam parados sem caminho claro para avançar.

## Evidence
- Spec do dono do produto em `training/TODO` (descreve LMS: matérias com vídeo/foto/texto/questão, correção por IA, nota ≥ 6 aprova, entrevista com coordenador, virar promotor).
- Catálogo do serviço `roles` hoje tem transição **direta** `candidate → promoter`, sem etapa de treinamento no meio — confirma a lacuna.
- `Assumption` — não há métrica histórica de quantos candidatos hoje viram promotores nem do tempo desse processo; **needs validation via analytics** após o MVP rodar.

## Users
- **Primary — Trainee (candidato em treinamento)**: usuário que já é `candidate` e foi colocado na trilha de treinamento. Gatilho: precisa concluir todas as matérias para virar promotor.
- **Secondary — Coordenador do hub**: aprova/rejeita o trainee após a entrevista (chamada interna desmilitarizada vinda de outro app da plataforma que valida o coordenador).
- **Secondary — Autor de conteúdo (admin)**: cria as matérias (texto/questão/resposta esperada) e envia vídeo/foto. Operação desmilitarizada (interna).
- **Not for**: leads, students, veterans — não passam por esta trilha; o serviço só trata o intervalo `candidate → promoter`.

## Hypothesis
Acreditamos que **uma trilha de matérias com correção automática por IA e um portão de entrevista** vai **padronizar e tornar auditável a virada de candidato para promotor** para **candidatos e coordenadores**.
Saberemos que acertamos quando **candidatos conseguirem concluir o treinamento de forma autônoma e a promoção a promotor passar a ser registrada com nota, justificativa e decisão do coordenador — sem etapa manual fora do sistema**.

## Success Metrics
| Metric | Target | How measured |
|---|---|---|
| Candidatos que concluem todas as matérias (entre os que iniciam) | TBD — baseline via analytics | contagem de trainees com todas matérias aprovadas ÷ trainees iniciados |
| Tempo de correção da resposta (submissão → nota) | assíncrono, < 2 min p95 | timestamp submissão vs. timestamp nota gravada |
| Promoções a promotor com trilha completa + decisão de coordenador registrada | 100% | nenhuma promoção `candidate→promoter` ocorre fora do fluxo training |
| Reprovações com justificativa textual preenchida | 100% | toda nota < 6 tem justificativa da IA gravada |

## Scope
**MVP** — *Núcleo de autoria + treinamento corrigido por IA:*
- Autoria de matérias (desmilitarizado): criar matéria (vídeo nulo na criação, foto, texto, 1 questão, 1 resposta esperada); **upload de vídeo/foto armazenado pelo próprio `training`**.
- Trainee busca uma matéria → registra a data do primeiro acesso.
- Trainee envia resposta da matéria.
- Correção **assíncrona por IA** (via serviço `ai` da plataforma, sem client DeepSeek próprio — §12): compara resposta do trainee com a resposta esperada, gera **nota 0–10 + justificativa + comentário de correção**.
- Nota **≥ 6 → aprovado**; abaixo → pode reenviar (reenvio sem limite no MVP).

**Out of scope** (viram milestones seguintes ou ficam de fora)
- Portão "todas aprovadas → aguardando entrevista" e endpoint do coordenador — Milestone 3.
- Papel intermediário `trainee` e promoção a `promoter` no serviço `roles` — Milestone 4.
- Notificações de mudança de status via `notify` — Milestone 5.
- Trilhas/turmas múltiplas, pré-requisitos entre matérias, ordenação obrigatória — não no MVP (matérias são um conjunto plano).
- Limite/cooldown de reenvio, antifraude na correção por IA — deferido.
- Painel/UI de coordenador ou de autoria — fora (este serviço expõe só API).

## Delivery Milestones
<!-- Business outcomes, not engineering tasks. /plan turns each into a plan. -->
<!-- Status: pending | in-progress | complete -->

| # | Milestone | Outcome | Status | Plan |
|---|---|---|---|---|
| 1 | Autoria de matérias | Admin cria matérias e envia vídeo/foto; conteúdo fica disponível para trainees | complete | `.claude/plans/training.plan.md` |
| 2 | Treinamento + correção por IA | Trainee busca matéria (data registrada), envia resposta, recebe nota 0–10 + justificativa assíncrona; ≥6 aprova, reenvio se reprovado | pending | — |
| 3 | Conclusão + entrevista + decisão | Todas as matérias aprovadas → status "aguardando entrevista"; coordenador (desmilitarizado) aprova ou rejeita com motivo | pending | — |
| 4 | Papel `trainee` no roles + promoção | Catálogo `roles` passa a ter `candidate → trainee → promoter`; aprovação do coordenador promove o trainee a `promoter` | pending | — |
| 5 | Notificações de status | `notify` é acionado (assíncrono) nas mudanças: aprovado/reprovado em matéria, aguardando entrevista, promovido, rejeitado | pending | — |

## Open Questions
- [ ] Nome exato do papel intermediário no `roles` (proposto: `trainee`). Confirmar e definir se a entrada na trilha faz `candidate → trainee` (replace) automaticamente ou por chamada explícita.
- [ ] Como o candidato **entra** na trilha (gatilho automático ao virar candidate, ou um POST de entrada quando a plataforma decide)?
- [ ] Rejeição do coordenador: o trainee volta para qual estado? (refazer matérias? aguardar nova entrevista? permanece `candidate`?)
- [ ] Limites do upload de mídia no `training`: tamanho/formatos aceitos de vídeo e foto, e onde o binário fica fisicamente (volume/disco do container).
- [ ] Estrutura da resposta esperada vs. resposta livre — qual endpoint do `ai` usar para nota+justificativa estruturada (decisão de `/plan`, mas precisa caber no contrato do `ai`).
- [ ] Métrica-baseline (taxa/tempo de promoção atual) — coletar para definir targets reais.

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Serviço `ai` indisponível/lento trava a correção | Média | Alta | Correção é assíncrona; resposta fica pendente e é reprocessada; trainee não fica bloqueado e há fallback de correção manual (§12 "não quebre se a integração falhar") |
| IA dá nota injusta/inconsistente | Média | Média | Justificativa sempre gravada; reenvio permitido; possibilidade de revisão manual da nota |
| Mudança no `roles` (novo papel) impacta outros serviços que assumem `candidate → promoter` direto | Média | Alta | Tratar Milestone 4 como mudança coordenada no `roles` (dono do catálogo, §6); revisar quem depende dessa transição antes de alterar |
| Armazenamento de vídeo no próprio serviço cresce sem controle | Média | Média | Definir limites de tamanho/formato; avaliar storage externo se volume justificar (não over-engineering no MVP, §14) |
| Endpoint do coordenador desmilitarizado sendo decisão sensível (promoção) | Baixa | Alta | Confiar na validação do app chamador (interno); registrar quem/quando/motivo de cada decisão para auditoria |

---
*Status: DRAFT — requirements only. Implementation planning pending via /plan.*
