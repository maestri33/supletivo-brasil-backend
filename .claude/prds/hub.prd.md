# Hub (Polo) — Serviço base de polos

> Parte B, item 1 do `wiki/PLANO_ADEQUACAO.md` (green-field). Spec: `hub/TODO`.
> Convenção: `../CONVENTION.md`. Modelo de estrutura: `lead`/`enrollment`; stack: `asaas`/`infinitepay`.

## Problema
A plataforma precisa do conceito de **polo** (campus/unidade) como âncora de todos os papéis:
promotores (candidato → treinamento → promotor) e alunos (lead → matrícula → estudante/veterano)
pertencem a um polo. Hoje esse serviço **não existe** (`hub/` só tem o `TODO`), então nenhum
outro serviço consegue referenciar um polo, e não há um polo default para iniciar a operação.

## Evidence
- `hub/TODO` (spec do dono): "Este é o polo, vamos criar um default… deve ter um endereço
  (relacionado a address), uma marca (estácio ou wyden ou outro) e um coordenador (external_id).
  Possui seus promotores… e alunos…"
- `wiki/PLANO_ADEQUACAO.md`: hub é o **item 1** da Parte B — "base de todos os papéis";
  `staff` (item 2) é quem cadastra hub e define o coordenador.

## Users
- **Primary (consumidor):** os demais microsserviços de papéis (`promoter`, `student`, `lead`,
  `training`, `enrollment`…) que precisam ler um polo e guardar `hub_external_id`.
- **Primary (gestor):** serviço `staff` — cadastra/edita polos e define o coordenador.
- **Not for:** usuários finais (candidato/aluno) não interagem direto com o hub; não é superfície pública.

## Hypothesis
We believe que **um serviço hub fino, dono do schema `hub`, expondo polos por `external_id`**
will **dar a todos os papéis uma âncora consistente de polo (endereço + marca + coordenador)**
for **os serviços de papéis e o staff**.
We'll know we're right when **um polo default existe após a migração inicial e pode ser lido por
outro serviço via API desmilitarizada pelo seu `external_id`**.

## Success Metrics
| Metric | Target | How measured |
|---|---|---|
| Polo default criado | 1 polo após `alembic upgrade head` | query no schema `hub` |
| Leitura por external_id | GET retorna o polo default | teste de integração (httpx + ASGITransport) |
| Conformidade §15 | checklist item a item ✅ | revisão + `ruff` limpo + `pytest` verde |

## Scope

**MVP**
- Schema `hub` próprio (Postgres async, §4) + migração Alembic.
- Entidade `hub` (registro fino): PK UUID; `name`; `brand` (enum/string: `estacio`/`wyden`/…);
  `address_external_id` (UUID, nullable); `coordinator_external_id` (UUID, nullable);
  timestamps `timestamptz`.
- **Não** armazena promotores/alunos: a relação é deles (carregam `hub_external_id`); hub só é lido.
- API **desmilitarizada** (§5): leitura por `external_id` para apps internos + health.
- API **autenticada** (§5): escrita (criar/editar polo, definir coordenador) — consumida pelo `staff`.
- **Seed do polo default** na migração inicial: `name="Polo Default"`, `brand="estacio"`,
  refs nullable (preenchidas quando `address`/`coordinator` estiverem disponíveis).
- Espelhar estrutura `lead`/`enrollment` e stack canônica `asaas`/`infinitepay`.
- Encerrar: `ruff` limpo + `pytest` (sqlite) + `alembic upgrade head`; aplicar §15;
  atualizar `wiki/hub.md` (fonte de verdade); criar `.claude/` do serviço.

**Out of scope**
- Shadow table / FK cross-schema para `address` — adiado: começa com `external_id` UUID puro (decidido).
- Serviço `coordinator` — não existe ainda; hub só guarda o `coordinator_external_id` (nullable).
- Listas de membros (promotores/alunos) dentro do hub — pertencem aos serviços de papéis (§6).
- Tabela `brands` dedicada — adiado; começa como enum/string (§14). Reavaliar se a marca ganhar
  metadados (logo/cores) para `notify` (§11) / IA (§13).
- Notificações de status (§11) — hub não tem ciclo de vida de status; reavaliar ao fechar.

## Delivery Milestones
<!-- Status: pending | in-progress | complete -->

| # | Milestone | Outcome | Status | Plan |
|---|---|---|---|---|
| 1 | Spine + schema + migração + seed default | `alembic upgrade head` cria schema `hub` e 1 polo default | complete | `.claude/plans/hub.plan.md` |
| 2 | API desmilitarizada (read por external_id) + health | outro serviço lê o polo default por API | pending | — |
| 3 | API autenticada (criar/editar polo, definir coordenador) | staff cadastra/edita polo | pending | — |
| 4 | Fechamento §15 (testes + ruff + wiki/hub.md + .claude/) | serviço apto a produção, documentado | pending | — |

## Open Questions
- [ ] Valores definitivos do polo default (marca, e quando houver: endereço e coordenador). Placeholder atual: `estacio` + refs null.
- [ ] `brand` deve ser `Enum` Postgres ou `String` validado por Pydantic? (decidir no `/plan`; default: String + validação).
- [ ] A escrita de polo é feita por chamada autenticada do `staff` ou também por endpoint desmilitarizado interno? (assumido: autenticada).

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Acoplar hub a serviços inexistentes (`coordinator`) | Média | Médio | refs como `external_id` UUID nullable; sem shadow table agora (§14) |
| Over-engineering (tabela brands, membros) | Média | Baixo | manter registro fino; enum/string p/ marca (§14) |
| Divergir da estrutura padrão | Baixa | Médio | espelhar `lead`/`enrollment` + `asaas`/`infinitepay`; agente de conformidade §15 |

---
*Status: DRAFT — requirements only. Implementation planning pending via /plan.*
