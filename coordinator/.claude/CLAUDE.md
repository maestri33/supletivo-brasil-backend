# CLAUDE.md — Memória e regras do microsserviço `coordinator`

> Fonte da verdade para você (Claude Code) sobre o serviço `coordinator`.
> Leia inteiro antes de agir. A convenção geral é `CONVENTION.md` (raiz);
> este arquivo só pode ser **mais restritivo**. Doc funcional completa:
> `wiki/coordinator.md`.

---

## ⚠️ Status: NÃO CRIADO (Parte B — Sprint futuro)

Este serviço **ainda não tem código**. O diretório contém apenas stub:
`.env.example`, `Makefile` e este `CLAUDE.md`. O desenvolvimento está planejado
para sprints futuros da Parte B do PLANO_ADEQUACAO.md.

**Enquanto não houver código, este CLAUDE.md serve como especificação de
requisitos. Qdo o serviço for implementado, atualizar este arquivo com
informações reais da implementação.**

---

## 1. Quem é você aqui

- Claude Code **exclusivo deste serviço**. Fala com outros serviços só por HTTP.
- Papel: gerenciar **coordenadores de polo** — administradores locais de
  operações acadêmicas. Possui tudo de um promotor + funções administrativas.
- **É caminho de dinheiro?** Indiretamente — coordena matrículas, taxas e
  pagamentos, mas a cobrança em si é feita pelos serviços `enrollment`/`fees`.
- Schema `coordinator`. PK = UUID.

## 2. Responsabilidades (planejadas)

| Função | Serviço alvo | Endpoint |
|---|---|---|
| Aprovar conclusão de treinamento | training | Demilitarized: promover candidato a promotor |
| Promover candidato a aluno | student | Authenticated: POST /promote |
| Enviar documentos do aluno → instituição | documents | Demilitarized: upload/dispatch |
| Incluir dados de acesso à plataforma | student | Authenticated: atualizar study_platform |
| Pagar e cadastrar taxas de matrícula | enrollment, fees | Autenticado: criar cobrança |
| Aplicar prova | training | Demilitarized: liberar exame |
| Corrigir e postar resultado | training | Demilitarized: submeter resposta, IA corrige |
| Juntar docs e enviar p/ instituição | documents | Demilitarized: dispatch batch |
| Postar histórico e diploma do aluno | documents, student | Demilitarized: upload diploma |
| Postar foto do aluno c/ diploma | student | Demilitarized: trigger veteran status |

## 3. Stack (planejada)

| Camada | Tecnologia |
|---|---|
| Runtime | Python 3.12 + `uv` |
| Web | FastAPI + uvicorn |
| ORM | SQLAlchemy 2.0 async (`Mapped`/`mapped_column`, `select()`) |
| Driver | asyncpg (Postgres central, schema `coordinator`) |
| Migrations | Alembic |
| Validação/Config | Pydantic v2 + pydantic-settings (`.env`) |
| HTTP cliente | httpx.AsyncClient |
| Logs | structlog |
| Testes | pytest + pytest-asyncio |

## 4. Modelo de dados (planejado)

### `coordinator.coordinators`

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | UUID | PK |
| `external_id` | UUID | FK → auth.users |
| `hub_external_id` | UUID | FK lógica → hub.hubs |
| `status` | enum | `active`, `inactive`, `suspended` |
| `created_at` | timestamptz | Criação |
| `updated_at` | timestamptz | Última atualização |

## 5. Dependências

- **auth** — autenticação e JWT
- **hub** — polo ao qual o coordenador pertence
- **student** — gestão de alunos
- **training** — aprovação de treinamentos e provas
- **documents** — gestão documental
- **enrollment** — matrículas
- **fees** — taxas
- **roles** — verificação de papel
- **notify** — notificações

## 6. O que NÃO fazer

- ❌ Criar coordenador sem associar a um hub existente.
- ❌ Permitir que coordenador gerencie alunos de outro polo.
- ❌ Fazer upload de documentos sem validação de tipo/tamanho.
- ❌ Importar modelo de outro serviço.
- ❌ Commitar `.env` ou segredo.

---

**Antes de qualquer tarefa**, leia também `wiki/coordinator.md` e
`CONVENTION.md` (raiz).
