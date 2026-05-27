# Enrollment — Fluxo de Matrícula

> Serviço: `enrollment/` · Spec de origem: `enrollment/TODO` · Convenção: `CONVENTION.md`
> Espelho de implementação: `candidate/` (mesma orquestração profiles/address/documents/ai/roles).

## Problem
Quando um lead **paga**, não existe caminho para coletar os dados de matrícula e
torná-lo `student`. Hoje o `enrollment` é só um **stub auditivo**: recebe o webhook
`lead.completed`, grava o evento em `enrollment_events` e expõe 2 GETs de auditoria
(`processed_at` nunca é preenchido). O lead pago fica parado — não tem onde enviar
perfil, endereço, RG, dados educacionais e selfie, e nunca progride para aluno.

## Evidence
- **Spec do dono do produto** (`enrollment/TODO`): descreve o fluxo completo (perfil →
  endereço → RG → dados educacionais → selfie → `aguardando_liberacao` → notificar
  coordenador → liberação → `student`).
- **Código atual** (`enrollment/app/`): só webhook + auditoria; `wiki/enrollment.md`
  confirma "toda a lógica de matrícula descrita no TODO está ausente".
- **Funil paralelo já provado** (`candidate/app/services/selfie.py`): mesma orquestração
  (documents + ai + roles) já roda em produção — o padrão existe e é reaproveitável.
- *Métricas de adoção: Assumption — needs validation via analytics quando em produção.*

## Users
- **Primary**: **lead pago (matriculando)** — pessoa que pagou e precisa enviar os
  próprios dados para virar `student`. Gatilho: evento `lead.completed` abre a matrícula;
  ele envia cada etapa por endpoints autenticados.
- **Secondary**: **coordenador do polo** — notificado quando os dados ficam completos e
  faz a **liberação manual** que conclui a matrícula. *(Serviço `coordinator`/`hub` ainda
  não existe → tratado best-effort/documentado.)*
- **Not for**: candidatos do funil de promotor (isso é `training`); leads que não pagaram;
  o próprio serviço `student` (Parte B, não construído aqui).

## Hypothesis
We believe um **fluxo de coleta de dados guiado por status, orquestrando
profiles/address/documents/ai e encerrando em liberação do coordenador** will
**permitir que o lead pago complete a matrícula e seja promovido a `student`** for
**leads pagos**.
We'll know we're right when **um lead pago consegue, via API, sair de `lead.completed`
até `student`, com perfil, endereço, RG, dados educacionais e selfie capturados, e a
promoção de papel registrada no `roles`**.

## Success Metrics
| Metric | Target | How measured |
|---|---|---|
| Etapas disponíveis ponta-a-ponta (perfil, endereço, RG, educação, selfie) | 100% | Teste E2E + verificação manual |
| Matrícula completa atinge `aguardando_liberacao` | sim | Teste de integração |
| Liberação manual promove role → `student` no `roles` | sim | Teste de integração |
| Selfie validada via `ai` **sem bloquear** quando `ai` cai (§13) | não bloqueia | Teste com `ai` indisponível |
| `ruff` limpo + suíte verde + `alembic upgrade head` | verde | CI/local |

## Scope
**MVP** — Orquestrar a coleta de matrícula no `enrollment`, espelhando o `candidate`:
- Endpoints **autenticados** para o matriculando enviar cada etapa, delegando a gravação
  aos serviços donos via `integrations/` httpx: **perfil → `profiles`**, **endereço →
  `address`**, **RG → `documents`**, **selfie → `documents` (slot foto) + validação
  best-effort no `ai`** (§13, não bloqueia).
- **Dados educacionais** (último ano estudado, quando, em que escola) gravados em tabela
  **própria do schema `enrollment`**.
- **Agregado de matrícula próprio** (PK UUID, §4) com **progressão por status**: avança
  conforme cada etapa é postada; ao completar todas → `aguardando_liberacao`.
- **Notificação ao coordenador** ao completar os dados: **best-effort via `notify`**,
  com a resolução do coordenador documentada como pendência até `hub`/`coordinator`
  existirem (mesmo tratamento que o `candidate` deu ao `training`).
- **Liberação manual** (aprovação) que conclui a matrícula → **promove role → `student`
  no `roles`** → grava `processed_at`.
- Migração Alembic, `ruff` limpo, `pytest` (sqlite), checklist §15, `wiki/enrollment.md`
  reescrita e `.claude/` do serviço.

**Out of scope**
- Construir `hub`, `coordinator`, `student` — Parte B do plano; não neste PR.
- Resolver **qual** coordenador notificar — depende do `hub`; fica best-effort/adiado.
- Pagamento (`asaas`) e o funil de `lead` em si — fora do serviço.
- Guardar cópia de perfil/endereço/RG/selfie no schema `enrollment` — delegado aos donos.
- Refatorar o stub auditivo além do necessário (mantém webhook + auditoria existentes).

## Delivery Milestones
<!-- Business outcomes, not engineering tasks. /plan turns each into a plan. -->
<!-- Status: pending | in-progress | complete -->

| # | Milestone | Outcome | Status | Plan |
|---|---|---|---|---|
| 1 | Abertura da matrícula | A partir de `lead.completed`, existe um agregado de matrícula (status inicial) vinculado ao matriculando e ao promotor que o indicou | complete | `.claude/plans/enrollment-matricula-flow.plan.md` |
| 2 | Perfil + endereço | Matriculando autentica e envia perfil e endereço; orquestrado para `profiles`/`address`; status progride | pending | — |
| 3 | RG + dados educacionais | Matriculando envia RG (`documents`) e dados educacionais (schema `enrollment`); status progride | pending | — |
| 4 | Selfie + completar | Matriculando envia selfie (`documents` + validação `ai` best-effort); ao completar tudo → `aguardando_liberacao` e coordenador notificado (best-effort) | pending | — |
| 5 | Liberação → student | Aprovação manual conclui a matrícula → role promovido a `student` no `roles` → `processed_at` gravado | pending | — |

## Open Questions
- [ ] Como o matriculando **autentica** nos endpoints (JWT via `auth`/`jwt`; qual role/status
      faz o gate)? Espelhar `candidate` — confirmar em `/plan`.
- [ ] Nomes/ordem exatos do **enum de status** da progressão.
- [ ] Qual **slot** do `documents` recebe o RG (e se selfie reusa o slot `foto` do candidate).
- [ ] Quem **dispara a criação do agregado**: no recebimento do webhook ou na 1ª chamada
      autenticada do matriculando? (idempotência por `external_id`).
- [ ] Como **autorizar a liberação manual** antes de `coordinator` existir (endpoint
      desmilitarizado/admin temporário?).
- [ ] O agregado novo usa **PK UUID** (§4); manter o `enrollment_events` legado em BIGINT
      ou padronizar junto?

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Dependência de `hub`/`coordinator`/`student` inexistentes | Alta | Médio | Espelhar `candidate`: promover role no `roles`; notificação best-effort/documentada |
| Falha parcial na orquestração cross-service | Média | Médio | Best-effort + padrões §12/§13; progressão idempotente por etapa |
| Dívida estrutural do stub (`PK BIGINT`, sem `services/`, CORS `*`, `fastapi-structured-logging` fora da §2) | Média | Baixo | Agregado novo com PK UUID + `services/`; alinhar à CONVENTION durante o build |
| Selfie/`ai` indisponível travar o funil | Média | Alto | Validação best-effort §13 (não bloqueia), igual `candidate` |

---
*Status: DRAFT — requirements only. Implementation planning pending via /plan.*
