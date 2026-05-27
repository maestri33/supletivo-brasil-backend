# Coordinator (Coordenador de Polo)

## Problem
O ciclo final do aluno (aprovação do training, prova, taxas, documentos, diploma, virada para
veterano e comissão) é hoje conduzido **manualmente** pelo coordenador do polo — fora do sistema
(planilha, e-mail, WhatsApp). Sem um serviço que execute/orquestre esse fluxo, não há rastro,
não há padronização entre polos, e o ciclo do aluno **não fecha dentro da plataforma**.

## Evidence
- **Premissa — validar via piloto com um polo.** Plataforma greenfield: ainda não há
  dados/métricas do processo manual atual. A dor é assumida com base no desenho do produto, não medida.

## Users
- **Primary**: **Coordenador de polo** — possui tudo de um *promoter* + funções administrativas do
  polo. É quem aprova quem concluiu o training, libera acesso, conduz prova, cuida de taxas/documentos
  e fecha o ciclo do aluno (diploma → veterano → comissão).
- **Not for**:
  - *Promoter* comum (sem as funções administrativas do polo).
  - Aluno / lead / candidate (são objeto do fluxo, não operadores).
  - Staff central da instituição externa (recebe o pacote, mas não opera o coordinator).

## Hypothesis
We believe um **serviço coordinator** que **orquestra os serviços existentes** (training, roles, auth,
documents, fees/enrollment, commissions, student, notify) e é **dono do ciclo de prova** will
**tirar o trabalho administrativo de fim de ciclo do polo de fora do sistema e padronizá-lo** for
**coordenadores de polo**.
We'll know we're right when **um polo-piloto fecha o ciclo do aluno inteiro dentro da plataforma,
com rastro/auditoria e sem etapas manuais fora do sistema**.

## Success Metrics
| Metric | Target | How measured |
|---|---|---|
| Etapas do ciclo executadas dentro do sistema | TBD — baseline via piloto | Contagem de etapas in-system vs. manuais no polo-piloto |
| Cobertura de rastro/auditoria das ações do coordenador | 100% das ações registradas | Logs/estado do serviço |
| Tempo para fechar o ciclo do aluno | TBD — baseline via piloto | Carimbo de tempo entre aprovação do training e virada para veterano |

> Targets numéricos: **TBD — validar via piloto.** Não inventados.

## Scope

**MVP** — **Aprovação training→promoter + liberação de acesso.**
O coordinator (assumindo o *promoter* já existente) aprova um candidato que **concluiu e passou** no
training, o **transforma em promoter** (via `roles`) e **provisiona o acesso à plataforma** (via
`auth`/`profiles`). Orquestração fina (HTTP), schema mínimo só para registrar o estado/decisão.
É a primeira fatia do ciclo e já exercita o padrão de orquestração + auditoria.

**Pré-requisito**: o serviço **`promoter` precisa existir primeiro** (decisão do solicitante). O
coordinator herda/estende o promoter; sem ele, o MVP não roda.

**Coordinator é DONO de**: o **ciclo de prova** (aplicar / corrigir / postar resultado) — único
domínio com schema/entidades próprias dentro do serviço.

**Out of scope** (coordinator só orquestra / emite evento — **não reimplementa**):
- **Cálculo/valores de comissão** — dono é `commissions`. Coordinator só dispara o gatilho "virou veterano".
- **Conteúdo/envio de notificações** — dono é `notify`. Coordinator só emite eventos assíncronos (CONVENTION §11).

> **Fronteira NÃO confirmada (vira Open Question):** `documents` e `fees`/`enrollment` **não** foram
> marcados como fora de escopo. Precisa definir, sem violar CONVENTION §6, até onde o coordinator vai
> (orquestrar/disparar vs. assumir parte do fluxo). Não assumido aqui.

## Delivery Milestones
<!-- Resultados de negócio, não tarefas de engenharia. /plan transforma cada um num plano. -->
<!-- Status: pending | in-progress | complete -->

| # | Milestone | Outcome | Status | Plan |
|---|---|---|---|---|
| 0 | Promoter existe (pré-req) | Serviço `promoter` disponível para o coordinator herdar/estender | pending | — |
| 1 | Aprovação training→promoter + acesso (MVP) | Coordenador aprova quem passou no training, vira promoter e ganha acesso à plataforma — in-system | pending | — |
| 2 | Ciclo de prova | Coordenador aplica, corrige e posta resultado da prova; resultado fica registrado (domínio próprio) | pending | — |
| 3 | Taxas de matrícula | Coordenador cadastra e dispara pagamento de taxas (orquestra `fees`/`enrollment` + asaas/infinitepay) | pending | — |
| 4 | Pacote de documentos → instituição | Coordenador junta documentos/histórico/diploma e prepara o envio à instituição (orquestra `documents`) | pending | — |
| 5 | Fechamento do ciclo | Postar diploma/foto → aluno vira veterano → gatilho de comissão (orquestra `documents`/`student`/`commissions`) | pending | — |

## Open Questions
- [ ] **Fronteira em `documents` e `fees`/`enrollment`**: quanto o coordinator executa vs. delega, sem ferir CONVENTION §6? (não confirmado nas respostas)
- [ ] **Integração com a INSTITUIÇÃO externa**: é sistema externo (ex.: MEC/faculdade). Por CONVENTION §12, integração externa pode exigir **app dedicado** — quando/qual instituição/protocolo? MVP só prepara o pacote.
- [ ] **Domínio da prova**: que entidades o coordinator precisa? (questões? gabarito? nota mínima de aprovação? tentativas?) — definir antes do milestone 2.
- [ ] **Provisão de acesso**: "incluir dados de acesso à plataforma" = via `auth`/`profiles`? Confirmar o fluxo exato de provisionamento.
- [ ] **Sequenciamento do `promoter`**: PRD/plan do promoter é pré-requisito — entra antes do MVP do coordinator quando?
- [ ] **Métricas/targets**: definir números reais via piloto.

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `promoter` inexistente bloqueia o coordinator | Alta | Alto | Construir `promoter` primeiro (milestone 0, já decidido) |
| Violar fronteira §6 ao orquestrar muitos serviços | Média | Alto | `integrations/` por serviço (httpx), sem reimplementar lógica alheia; revisar §6 a cada rota |
| Integração com instituição externa indefinida | Alta | Médio | Tratar como integração futura/app dedicado (§12); MVP só prepara o pacote |
| Escopo amplo (9 funções do TODO) | Média | Médio | Milestones incrementais; MVP fino (só aprovação + acesso) |
| Sem evidência real (premissa) | Média | Médio | Validar via polo-piloto antes de escalar |

---
*Status: DRAFT — requirements only. Implementation planning pending via /plan.*
