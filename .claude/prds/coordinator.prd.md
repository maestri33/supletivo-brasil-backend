# Coordinator — Coordenador de Polo

> Serviço: `coordinator/` · Schema: `coordinator` · Convenção: `CONVENTION.md`
> **Pré-requisito:** serviço `promoter` deve existir antes do MVP.
> Status desta SPEC: DRAFT — pronto para review.

---

## 1. Contexto de Negócio

O ciclo final do aluno (aprovação do training, prova, taxas, documentos, diploma, virada para
veterano e comissão) é hoje conduzido **manualmente** pelo coordenador do polo — fora do sistema
(planilha, e-mail, WhatsApp). Sem um serviço que execute/orquestre esse fluxo, não há rastro, não
há padronização entre polos, e o ciclo do aluno **não fecha dentro da plataforma**.

O coordenador de polo possui tudo de um *promoter* **mais funções administrativas**: aprovação de
training, aplicação/correção de prova, cadastro de taxas, envio de documentos, postagem de
diploma/histórico/foto e fechamento do ciclo (aluno vira veterano → comissão).

**MVP (milestone 1):** Aprovação de training → transforma candidato em promoter + provisiona
acesso à plataforma. Orquestração fina via HTTP, schema mínimo para registrar estado/decisão.

**Dono exclusivo do domínio:** ciclo de prova (aplicar, corrigir, postar resultado) — único
domínio com schema/entidades próprias dentro do serviço.

## 2. Atores

| Ator | Role | Ação |
|------|------|------|
| **Coordenador de polo** | `coordinator` | Aprova training, aplica/corrige prova, cadastra taxas, envio documentos, posta diploma, fecha ciclo |
| **Aluno / candidato** | `student` / `candidate` | Objeto do fluxo — recebe aprovação, faz prova, recebe diploma |
| **Promoter comum** | `promoter` | Não tem funções administrativas do polo; candidato aprovado vira promoter |
| **Sistema (training)** | serviço `training` | Informa se candidato concluiu/passou no training |
| **Sistema (roles)** | serviço `roles` | Promove role do usuário (candidate → promoter, student → veteran) |
| **Sistema (auth/profiles)** | serviço `auth` / `profiles` | Provisiona acesso/plataforma |
| **Sistema (notify)** | serviço `notify` | Notificações assíncronas (CONVENTION §11) |
| **Sistema (commissions)** | serviço `commissions` | Calcula/emite comissão ao virar veterano |
| **Instituição externa** | sistema externo (ex.: MEC/faculdade) | Recebe pacote de documentos/diploma (integração futura) |

## 3. Estados / Máquina de Estados

### Status do ciclo do coordenador (CoordinatorCycleStatus — StrEnum)

```
TRAINING_APPROVED → PROMOTER_ACTIVE → EXAM_PENDING → EXAM_APPLIED → EXAM_GRADED
→ FEES_REGISTERED → FEES_PAID → DOCUMENTS_SENT → DIPLOMA_POSTED → CYCLE_CLOSED
```

| Status | Significado | Transição para |
|--------|-------------|----------------|
| `training_approved` | Coordenador aprova conclusão do training | `promoter_active` |
| `promoter_active` | Candidato vira promoter, acesso provisionado | `exam_pending` |
| `exam_pending` | Prova liberada para aplicação | `exam_applied` |
| `exam_applied` | Aluno submeteu a prova | `exam_graded` |
| `exam_graded` | Coordenador corrigiu e postou resultado | `fees_registered` |
| `fees_registered` | Taxas de matrícula cadastradas | `fees_paid` |
| `fees_paid` | Pagamento confirmado (orquestra `fees`/`enrollment`) | `documents_sent` |
| `documents_sent` | Documentos/histórico enviados à instituição | `diploma_posted` |
| `diploma_posted` | Diploma/foto postados; aluno vira veterano | `cycle_closed` |
| `cycle_closed` | Ciclo encerrado; comissão disparada | — (terminal) |

**Regra:** Progressão sequencial e unidirecional. Cada ação avança exatamente 1 status. Não é
possível pular etapas nem retroceder.

### Domínio da prova (ExamStatus — StrEnum)

```
CREATED → IN_PROGRESS → SUBMITTED → GRADED → PASSED / FAILED
```

| Status | Significado | Transição para |
|--------|-------------|----------------|
| `created` | Prova criada pelo coordenador | `in_progress` |
| `in_progress` | Aluno iniciou a prova | `submitted` |
| `submitted` | Aluno submeteu respostas | `graded` |
| `graded` | Coordenador atribuiu nota | `passed` ou `failed` |
| `passed` | Nota >= mínima | — (terminal) |
| `failed` | Nota < mínima | — (terminal, permite retentativa?) |

## 4. Entidades & Campos

### Schema `coordinator`

#### `exam_cycles` — Ciclo do aluno no polo (agregado raiz)

| Coluna | Tipo | Nullable | Default | FK / Índice | Descrição |
|--------|------|----------|---------|-------------|-----------|
| `id` | `UUID` PK | NOT NULL | `uuid4()` | — | PK do agregado |
| `student_external_id` | `UUID` | NOT NULL | — | FK → `auth.users.external_id`, **UNIQUE INDEX** | UUID do aluno (1 ciclo por aluno) |
| `hub_external_id` | `UUID` | NULL | — | INDEX | UUID do polo/hub |
| `coordinator_external_id` | `UUID` | NOT NULL | — | INDEX | UUID do coordenador responsável |
| `status` | `String(24)` | NOT NULL | `'training_approved'` | INDEX | Status atual do ciclo |
| `created_at` | `DateTime(tz)` | NOT NULL | `now()` | — | Timestamp de criação |
| `updated_at` | `DateTime(tz)` | NOT NULL | `now()` ON UPDATE | — | Timestamp de atualização |

#### `exams` — Provas aplicadas (domínio próprio)

| Coluna | Tipo | Nullable | Default | FK / Índice | Descrição |
|--------|------|----------|---------|-------------|-----------|
| `id` | `UUID` PK | NOT NULL | `uuid4()` | — | PK da prova |
| `cycle_id` | `UUID` | NOT NULL | — | FK → `coordinator.exam_cycles.id`, INDEX | Ciclo ao qual pertence |
| `status` | `String(16)` | NOT NULL | `'created'` | INDEX | Status da prova |
| `score` | `Numeric(5,2)` | NULL | — | — | Nota atribuída (null até grading) |
| `min_score` | `Numeric(5,2)` | NOT NULL | — | — | Nota mínima para aprovação |
| `attempt` | `Integer` | NOT NULL | `1` | — | Número da tentativa |
| `applied_at` | `DateTime(tz)` | NULL | — | — | Quando o aluno submeteu |
| `graded_at` | `DateTime(tz)` | NULL | — | — | Quando o coordenador corrigiu |
| `created_at` | `DateTime(tz)` | NOT NULL | `now()` | — | Timestamp de criação |

#### `exam_audit_log` — Log de auditoria das ações do coordenador

| Coluna | Tipo | Nullable | Default | FK / Índice | Descrição |
|--------|------|----------|---------|-------------|-----------|
| `id` | `BIGINT` PK | NOT NULL | autoincrement | — | PK do log |
| `cycle_id` | `UUID` | NOT NULL | — | FK → `exam_cycles.id`, INDEX | Ciclo afetado |
| `actor_external_id` | `UUID` | NOT NULL | — | INDEX | Quem executou a ação |
| `action` | `String(64)` | NOT NULL | — | INDEX | Tipo da ação (ex: `approve_training`, `grade_exam`, `post_diploma`) |
| `from_status` | `String(24)` | NULL | — | — | Status anterior |
| `to_status` | `String(24)` | NOT NULL | — | — | Status resultante |
| `payload` | `JSONB` | NOT NULL | `{}` | — | Dados adicionais da ação |
| `created_at` | `DateTime(tz)` | NOT NULL | `now()` | — | Timestamp da ação |

### FK cross-schema (shadow table)

```python
# Shadow auth.users — FK cross-schema (CONVENTION §4)
auth_users = Table("users", metadata,
    Column("external_id", PG_UUID(as_uuid=True), primary_key=True),
    schema="auth")
```

## 5. Endpoints

### 5.1. Aprovar training → promoter (MVP)

| Campo | Valor |
|-------|-------|
| **Método** | `POST` |
| **Rota** | `/api/v1/coordinator/cycles` |
| **Tipo** | **Autenticado** (JWT — role `coordinator`) |
| **Request body** | `{"student_external_id": "UUID", "hub_external_id": "UUID (opcional)"}` |
| **Response** | `201` — `{"id": "UUID", "student_external_id": "...", "status": "training_approved"}` |
| **Side-effects** | 1) Cria `ExamCycle` com status `training_approved`. 2) Orquestra `roles` → promove candidate→promoter. 3) Orquestra `auth`/`profiles` → provisiona acesso. 4) Avança status para `promoter_active`. 5) Grava `exam_audit_log`. |
| **Idempotência** | Por `student_external_id` UNIQUE — reenvio retorna ciclo existente (`200` + `already_exists: true`) |
| **Erros** | `409` — ciclo já existe; `404` — `student_external_id` não encontrado em `auth.users` |

### 5.2. Listar ciclos (desmilitarizado)

| Campo | Valor |
|-------|-------|
| **Método** | `GET` |
| **Rota** | `/api/v1/coordinator/cycles` |
| **Tipo** | **Desmilitarizado** |
| **Query params** | `coordinator_external_id` (UUID, opcional), `status` (opcional), `limit` (1-200, default 50), `offset` (default 0) |
| **Response** | `200` — `list[ExamCycleRead]` |

### 5.3. Obter ciclo (desmilitarizado)

| Campo | Valor |
|-------|-------|
| **Método** | `GET` |
| **Rota** | `/api/v1/coordinator/cycles/{cycle_id}` |
| **Tipo** | **Desmilitarizado** |
| **Response** | `200` — `ExamCycleRead` com exames associados |
| **Erro** | `404` — ciclo não encontrado |

### 5.4. (PLANEJADO) Aplicar prova

| Campo | Valor |
|-------|-------|
| **Método** | `POST` |
| **Rota** | `/api/v1/coordinator/cycles/{cycle_id}/exams` |
| **Tipo** | **Autenticado** (JWT — role `coordinator`) |
| **Pré-condição** | Status do ciclo = `promoter_active` ou `exam_pending` |
| **Request body** | `{"min_score": "Numeric(5,2)"}` |
| **Side-effects** | Cria `Exam` com status `created`; avança ciclo para `exam_pending` |
| **Response** | `201` — `ExamRead` |

### 5.5. (PLANEJADO) Submeter prova (aluno)

| Campo | Valor |
|-------|-------|
| **Método** | `POST` |
| **Rota** | `/api/v1/coordinator/cycles/{cycle_id}/exams/{exam_id}/submit` |
| **Tipo** | **Autenticado** (JWT — role `student`, dono do ciclo) |
| **Pré-condição** | Status da prova = `created` ou `in_progress` |
| **Side-effects** | Marca prova como `submitted`, avança ciclo para `exam_applied` |

### 5.6. (PLANEJADO) Corrigir prova / postar resultado

| Campo | Valor |
|-------|-------|
| **Método** | `POST` |
| **Rota** | `/api/v1/coordinator/cycles/{cycle_id}/exams/{exam_id}/grade` |
| **Tipo** | **Autenticado** (JWT — role `coordinator`) |
| **Pré-condição** | Status da prova = `submitted` |
| **Request body** | `{"score": "Numeric(5,2)"}` |
| **Side-effects** | Atualiza nota, marca `graded`→`passed`/`failed`, avança ciclo para `exam_graded`, grava audit log |
| **Erros** | `422` — nota inválida; `409` — prova já corrigida |

### 5.7. (PLANEJADO) Avançar etapa do ciclo (taxas, documentos, diploma)

| Campo | Valor |
|-------|-------|
| **Método** | `POST` |
| **Rota** | `/api/v1/coordinator/cycles/{cycle_id}/advance` |
| **Tipo** | **Autenticado** (JWT — role `coordinator`) |
| **Request body** | `{"action": "register_fees" | "confirm_payment" | "send_documents" | "post_diploma" | "close_cycle"}` |
| **Side-effects** | Orquestra serviço correspondente (fees, documents, student, commissions); avança status; grava audit log |

### 5.8. Obter log de auditoria (desmilitarizado)

| Campo | Valor |
|-------|-------|
| **Método** | `GET` |
| **Rota** | `/api/v1/coordinator/audit` |
| **Tipo** | **Desmilitarizado** |
| **Query params** | `cycle_id` (UUID, opcional), `limit` (1-200, default 50), `offset` (default 0) |
| **Response** | `200` — `list[ExamAuditLogRead]` |

## 6. Integrações Externas

| Serviço | Tipo | Propósito | Quando |
|---------|------|-----------|--------|
| `roles` | HTTP (httpx, desmilitarizado) | Promover role: candidate→promoter, student→veteran | MVP (milestone 1) e milestone 5 |
| `auth` / `profiles` | HTTP (httpx, desmilitarizado) | Provisionar acesso/plataforma ao novo promoter | MVP (milestone 1) |
| `training` | HTTP (httpx, desmilitarizado) | Verificar conclusão/aprovação do training | MVP (milestone 1) |
| `fees` / `enrollment` | HTTP (httpx, desmilitarizado) | Cadastrar e disparar pagamento de taxas | Milestone 3 |
| `documents` | HTTP (httpx, desmilitarizado) | Enviar documentos/histórico/diploma | Milestones 4-5 |
| `student` | HTTP (httpx, desmilitarizado) | Atualizar status do aluno (veterano) | Milestone 5 |
| `commissions` | HTTP (httpx, desmilitarizado) | Disparar gatilho de comissão | Milestone 5 |
| `notify` | HTTP (httpx, desmilitarizado) | Notificações assíncronas (best-effort) | Todos os milestones |

**Padrão:** Clientes em `integrations/`. Timeout configurável. Falha não quebra fluxo principal (best-effort com logging estruturado). Ver CONVENTION §12.

## 7. Eventos Disparados / Consumidos

### Consumidos

| Evento | Origem | Reação |
|--------|--------|--------|
| `training.completed` | Serviço `training` | Validação de pré-condição ao aprovar training (opcional — pode ser polling síncrono) |

### Disparados

| Evento | Gatilho | Destino |
|--------|---------|---------|
| `cycle.training_approved` | Aprovação do coordenador | `notify` (notifica aluno) |
| `cycle.promoter_activated` | Provisionamento de acesso concluído | `notify` (notifica novo promoter) |
| `cycle.exam_graded` | Nota postada | `notify` (notifica aluno do resultado) |
| `cycle.diploma_posted` | Diploma/foto publicados | `commissions` (gatilho de comissão), `student` (vira veterano) |
| `cycle.closed` | Ciclo encerrado | `notify` (notifica todas as partes) |

## 8. Regras de Negócio Invariantes

1. **1 ciclo por aluno** — `student_external_id` é UNIQUE em `exam_cycles`. Não pode haver ciclo duplicado para o mesmo aluno.

2. **Progressão unidirecional** — Cada status avança para o próximo. Não há retrocesso nem salto de etapas.

3. **Aprovação exige conclusão do training** — Antes de criar ciclo, validar que o candidato concluiu e passou no training (via integração).

4. **Coordenador é quem opera** — Todas as ações administrativas (aprovar, aplicar, corrigir, avançar) exigem role `coordinator` autenticada.

5. **Dono exclusivo da prova** — Ciclo de prova (entidades `exams`, nota mínima, tentativa, correção) pertence ao `coordinator`. Nenhum outro serviço implementa isso.

6. **Comissão não é do coordinator** — Cálculo/valores de comissão pertencem a `commissions`. Coordinator só dispara o evento "virou veterano".

7. **Notificações são assíncronas** — Todas as notificações via `notify`, nunca síncronas no fluxo principal (CONVENTION §11).

8. **Auditoria obrigatória** — Toda ação do coordenador gera entrada em `exam_audit_log` com ator, ação, from/to status e payload.

9. **Prova exige nota mínima** — A nota mínima (`min_score`) é definida ao criar a prova. `score >= min_score` → `passed`, senão `failed`.

10. **Integração externa = app dedicado ou integração isolada** — Envio à instituição externa (MEC/faculdade) deve seguir CONVENTION §12. MVP só prepara o pacote.

## 9. Critérios de Aceite

1. [ ] POST `/cycles` (coordenador autenticado) cria ciclo com `training_approved`, chama `roles` para promoter, chama `auth` para acesso, avança para `promoter_active` — idempotente por `student_external_id`.
2. [ ] GET `/cycles` lista ciclos com paginação e filtros (coordenador, status).
3. [ ] GET `/cycles/{cycle_id}` retorna ciclo com exames; `404` quando ausente.
4. [ ] POST `.../exams` cria prova com nota mínima; ciclo avança para `exam_pending`.
5. [ ] POST `.../exams/{id}/submit` (aluno) marca prova como `submitted`, ciclo → `exam_applied`.
6. [ ] POST `.../exams/{id}/grade` (coordenador) corrige, marca `passed`/`failed`, ciclo → `exam_graded`.
7. [ ] POST `.../advance` com cada action válida avança o ciclo corretamente e orquestra o serviço correspondente.
8. [ ] GET `/audit` retorna log de auditoria com paginação e filtro por `cycle_id`.
9. [ ] Tentativa de criar ciclo para `student_external_id` já existente retorna `409` / idempotente.
10. [ ] Tentativa de pular etapa (ex: aplicar prova antes de aprovar training) retorna erro de validação.
11. [ ] Ação de não-coordenador retorna `403` (ou similar).
12. [ ] Toda ação do coordenador gera entrada em `exam_audit_log`.
13. [ ] `ruff` limpo + suíte `pytest` verde + `alembic upgrade head` válido.

## 10. Riscos / Open Questions

### Riscos

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| `promoter` inexistente bloqueia o MVP | Alta | Alto | Construir `promoter` primeiro (pré-requisito confirmado) |
| Violar fronteira §6 ao orquestrar muitos serviços | Média | Alto | `integrations/` por serviço; revisar §6 a cada rota; não reimplementar lógica alheia |
| Integração com instituição externa indefinida | Alta | Médio | App dedicado (§12); MVP só prepara o pacote |
| Escopo amplo (8+ funções no TODO) | Média | Médio | Milestones incrementais; MVP fino (só aprovação + acesso) |
| Sem evidência real (premissa greenfield) | Média | Médio | Validar via polo-piloto antes de escalar |

### Open Questions

- [ ] **Fronteira em `documents` e `fees`/`enrollment`**: quanto o coordinator executa vs. delega, sem ferir CONVENTION §6? Precisa definir antes do milestone 3.
- [ ] **Domínio da prova**: questões? gabarito? número máximo de tentativas? retentativa em caso de `failed`? Definir antes do milestone 2.
- [ ] **Provisionamento de acesso**: confirmar fluxo exato via `auth`/`profiles` no MVP.
- [ ] **Sequenciamento do `promoter`**: PRD/plan do promoter é pré-requisito — entra antes do MVP do coordinator quando?
- [ ] **Integração com instituição externa**: quando/qual instituição/protocolo? Pode exigir app dedicado (§12).
- [ ] **Métricas/targets**: definir números reais via polo-piloto (baseline não existe).
- [ ] **Quem é o coordenador**: como validar que o JWT é de um coordenador do polo correto? Depende de `hub` inexistente.

---

*Status: DRAFT — requirements only. Implementation planning pending via /plan.*
