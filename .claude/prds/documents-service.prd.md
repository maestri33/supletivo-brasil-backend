# documents — Serviço de Documentos (reescrita conforme CONVENTION)

## Problem
O microsserviço `documents` guarda os documentos de identificação dos usuários (RG, CNH, CTPS, passaporte, certidão, serviço militar, comprovante de residência, foto), vinculados por `external_id`. Hoje ele é **não-conforme e incompleto**: roda em Tortoise+SQLite sem migrações, PK inteira, Pydantic v1, sem testes e com a regra de negócio do dono ("ao criar o usuário, criar o Document com todos os sub-documentos juntos") nunca implementada. Deixá-lo assim trava a padronização do backend e impede que outros serviços confiem nele em produção.

## Evidence
- Auditoria do próprio dono em `wiki/documents.md`: 14 desvios catalogados da CONVENTION (Tortoise/SQLite, sem Alembic, PK IntField, `class Config` v1, py3.11, sem testes, sem `integrations/`, mídia servida direto, etc.).
- Spec do dono em `documents/TODO`: "ao ser criado usuário, um document é criado com seu external_id e todos documentos são criados juntos respectivamente, com campos null"; certidão "só uma por document"; serviço militar "só pra homens, mas tem que criar".
- CONVENTION.md §1/§15: TODO sem dono é defeito; todo serviço deve seguir a stack canônica e ter wiki como fonte de verdade.

## Users
- **Primary**: os outros microsserviços da plataforma (ex.: o serviço que cria o usuário, e os apps de role como candidate) que provisionam e leem/escrevem documentos via HTTP interno (zona desmilitarizada). O usuário final consome indiretamente, anexando fotos e dados dos seus documentos.
- **Not for**: acesso público externo. Não há autenticação porque o serviço só é chamado de dentro da plataforma (endpoints desmilitarizados, §5).

## Hypothesis
We believe **reescrever o `documents` na stack canônica com provisionamento eager de todos os sub-documentos** will **dar à plataforma um serviço de documentos único, confiável e padronizado** for **os serviços internos que criam e gerenciam documentos de usuários**.
We'll know we're right when **o serviço sobe na stack canônica (Postgres/Alembic/SQLAlchemy async), reimplementa 100% dos endpoints atuais, provisiona Document+sub-documentos em uma chamada, passa nos testes e zera os 14 desvios da auditoria**.

## Success Metrics
| Metric | Target | How measured |
|---|---|---|
| Desvios da CONVENTION (§15) | 0 | Revisão pelo checklist §15 contra a auditoria de `wiki/documents.md` |
| Paridade de endpoints | 100% dos endpoints atuais reimplementados | Diff endpoints novos × `app/api/documents.py` atual |
| Comportamentos cobertos por teste | provisionamento, CRUD textual, imagens, validações (tipo/tamanho/slot), regra serviço-militar | `pytest` verde |
| Lint | `ruff check`/`ruff format` limpos | execução de CI/local |
| Fonte de verdade | `wiki/documents.md` reescrita refletindo o serviço novo | revisão |

## Scope
**MVP** — Reescrita completa do `documents` na stack canônica (Python 3.12, FastAPI, SQLAlchemy 2.0 async + asyncpg, Postgres com schema próprio `documents`, Alembic, Pydantic v2, structlog, httpx), mantendo **toda a funcionalidade atual** e cumprindo o spec do dono:
- **Provisionamento eager**: endpoint desmilitarizado que, ao criar o usuário, cria o Document (PK UUID, ligado por `external_id`) e **todos os sub-documentos vazios** numa só operação.
- **Tipos de documento**: RG, CNH, CTPS, passaporte, certidão (tipada — nascimento/casamento/óbito — **uma por Document**), serviço militar (**criado só para homens** — condicional por gênero), comprovante de residência, foto.
- **CRUD textual** de todos os tipos.
- **Imagens por slot**: upload/download/delete com validação de tipo e tamanho.
- **Eventos via notify**: mudanças relevantes emitem notificação assíncrona pelo serviço `notify` (`integrations/notify.py`, §11/§12), sem quebrar o fluxo se o notify falhar.
- **Idioma**: identificadores em inglês (tabelas/colunas/rotas), comentários pt-br verdadeiros (§7) — corrige nomes em português apontados no TODO.
- **Testes** + `ruff` limpo + `wiki/documents.md` reescrita como fonte de verdade.

**Out of scope**
- Autenticação/JWT — endpoints são desmilitarizados (uso interno); trava de segurança fica para um passe explícito futuro.
- OCR/extração automática de dados por IA a partir das fotos — candidato a evolução (§13), não MVP.
- Migração dos dados do SQLite atual — tratado como greenfield salvo decisão contrária (ver Open Questions).
- UI/portal de upload — responsabilidade de outro serviço.

## Delivery Milestones
<!-- Business outcomes, not engineering tasks. /plan turns each into a plan. -->
<!-- Status: pending | in-progress | complete -->

| # | Milestone | Outcome | Status | Plan |
|---|---|---|---|---|
| 1 | Base canônica + provisionamento | Serviço sobe em Postgres (schema `documents`) com migrações Alembic e PK UUID; uma chamada provisiona Document + todos os sub-documentos vazios para um `external_id` | in-progress | `.claude/plans/documents-service.plan.md` |
| 2 | CRUD textual com paridade | Dados textuais de todos os tipos (incl. certidão tipada única e serviço militar condicional) são editáveis e recuperáveis | pending | — |
| 3 | Imagens por slot | Upload/download/delete de imagens por slot nomeado, com validação de tipo/tamanho e acesso controlado | pending | — |
| 4 | Eventos via notify | Mudanças relevantes disparam notificação assíncrona pelo notify, tolerante a falha | pending | — |
| 5 | Qualidade & fonte de verdade | Testes do comportamento verdes, `ruff` limpo, `wiki/documents.md` reescrita | pending | — |

## Open Questions
- [ ] **Fonte do gênero** para a regra "serviço militar só pra homens": o gênero vem no payload do provisionamento, ou `documents` consulta o serviço `profiles` via integração?
- [ ] **Quais notificações** via notify são realmente úteis (provisionado? lembrete de documento pendente há X tempo, §11)? Definir o catálogo mínimo.
- [ ] **Controle de acesso à mídia**: como gatear o download de imagens sensíveis num endpoint desmilitarizado (restrição de rede interna? URL/token assinado?).
- [ ] **FK cross-schema `external_id`**: declarar shadow table read-only de `auth.users` (§4) ou manter só coluna UUID indexada sem FK?
- [ ] **Dados existentes**: há dados no SQLite atual que precisam migrar, ou é greenfield?

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Mídia sensível (documentos) exposta sem auth em endpoint desmilitarizado | Média | Alto | Restringir a download a rede interna e/ou token assinado; nunca montar `StaticFiles` aberto (resolver Open Question de acesso) |
| `external_id` sem garantia de usuário existente gera documentos órfãos | Média | Médio | Provisionamento confiável a partir do serviço de usuário + (opcional) shadow table de `auth.users` |
| `notify` indisponível trava criação/edição de documento | Média | Médio | Emissão assíncrona, fire-and-forget, sem re-raise no fluxo principal (§12) |
| Provisionamento eager cria muitos registros vazios | Baixa | Baixo | Aceitável (1 Document + N sub-docs por usuário); índices por `external_id` |
| Regra de gênero depende de dado externo (profiles) que pode faltar | Média | Médio | Definir fallback (não criar serviço militar quando gênero desconhecido) na Open Question |

---
*Status: DRAFT — requirements only. Implementation planning pending via /plan.*
