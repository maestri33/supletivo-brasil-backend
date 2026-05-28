# Student — Funil do Aluno

> Serviço: `student/` · Schema: `student` · Convenção: `CONVENTION.md`
> **GAP CRÍTICO** — módulo parcialmente implementado (milestone 1: promoção + consulta). Documentos, prova, diploma, veterano e comissão não existem.
> Status desta SPEC: pronto para review.

---

## 1. Contexto de Negócio

Após a conclusão da **matrícula** (`enrollment`), o usuário é promovido a `student` pelo coordenador do polo. A partir desse ponto, o módulo `student` orquestra todo o ciclo de vida do aluno até a formatura:

1. **Documentos** — coleta de documentos obrigatórios: certificado + histórico (último ano, obrigatórios), RG (obrigatório), comprovante de endereço (foto), certidão, serviço militar (se homem), tipo sanguíneo.
2. **Validação por IA** — worker assíncrono valida os documentos via serviço `ai`; só avança status se aprovado.
3. **Prova** — aluno é liberado para agendar; coordenador corrige e lança resultado; reprovação reabre para refazer.
4. **Diploma** — emissão (certificado + histórico), retirada com foto comprovando.
5. **Veterano** — ao concluir, aluno recebe role `veterano` (mantendo `student` — multi-role) e coordenador recebe comissão.

**Estado atual do código (2026-05-27):**
- Milestone 1 implementado: endpoint de promoção (`POST /api/v1/authenticated/students`) e consulta (`GET /api/v1/authenticated/students/me`).
- Modelo `Student` com PK UUID, `external_id` FK → `auth.users`, `status` enum completo (10 estados), `study_platform` JSONB.
- Testes de promoção (`test_promotion.py`) existem.
- **Gaps:** endpoints de documentos, prova, diploma, veterano, comissão, worker de validação IA, notificações — todos ausentes.

**Problema central:** Sem os milestones seguintes, o aluno fica travado em `awaiting_documents` para sempre. A secretaria de educação não tem os documentos exigidos para validar a conclusão.

## 2. Atores

| Ator | Role | Ação |
|------|------|------|
| **Aluno** | `student` (autenticado) | Envia documentos, agenda prova, acompanha status, registra retirada do diploma |
| **Coordenador do polo** | `coordinator` (autenticado) | Promove matriculado a aluno, corrige prova, lança resultado, libera diploma, confere pendências |
| **Sistema (enrollment)** | serviço `enrollment` | Conclui matrícula → coordenador promove a student |
| **Sistema (documents)** | serviço `documents` | Armazena arquivos (fotos, PDFs) — student guarda apenas `external_id` + status |
| **Sistema (ai)** | serviço `ai` | Validação assíncrona de documentos (foto do RG, comprovante, etc.) |
| **Sistema (commissions)** | serviço `commissions` | Recebe evento de comissão ao virar veterano |
| **Sistema (notify)** | serviço `notify` | Notificações assíncronas (status, lembretes) |
| **Sistema (roles/auth)** | serviços `roles`/`auth` | Atribuição de role `veterano` (multi-role) |

**Nota:** Os serviços `documents`, `ai`, `commissions`, `notify` ainda não existem como implementações completas. As integrações são tratadas via clients httpx com contratos assumidos.

## 3. Estados / Máquina de Estados

```
AWAITING_DOCUMENTS
  → (documentos enviados) → DOCUMENTS_UNDER_REVIEW
    → (IA aprova) → EXAM_RELEASED
      → (aluno agenda) → EXAM_SCHEDULED
        → (coordenador aprova) → AWAITING_DOCUMENTATION_DISPATCH
        → (coordenador reprova) → EXAM_FAILED
          → (refaz prova) → EXAM_RELEASED
      → (pendências) → PENDING
        → (pendências resolvidas) → AWAITING_DOCUMENTATION_DISPATCH
      → (docs ok) → AWAITING_DIPLOMA_ISSUANCE
        → (diploma emitido) → AWAITING_PICKUP
          → (foto retirada) → VETERAN
```

| Status | Significado | Transição para |
|--------|-------------|----------------|
| `awaiting_documents` | Aluno recém-promovido, aguardando envio de documentos | `documents_under_review` |
| `documents_under_review` | Documentos enviados, IA validando | `exam_released` (aprovado), `awaiting_documents` (rejeitado) |
| `exam_released` | Documentos aprovados, prova liberada para agendamento | `exam_scheduled` |
| `exam_scheduled` | Prova agendada, aguardando correção do coordenador | `exam_failed`, `awaiting_documentation_dispatch` |
| `exam_failed` | Reprovado na prova — precisa refazer | `exam_released` |
| `awaiting_documentation_dispatch` | Aprovado, aguardando envio de documentação final | `pending`, `awaiting_diploma_issuance` |
| `pending` | Pendência identificada — coordenador deve resolver | `awaiting_documentation_dispatch` |
| `awaiting_diploma_issuance` | Aguardando emissão do diploma (certificado + histórico) | `awaiting_pickup` |
| `awaiting_pickup` | Diploma emitido, aguardando retirada | `veteran` |
| `veteran` | Concluído — aluno é veterano (terminal) | — |

**Regras de transição:**
- Progressão é sequencial — não pular etapas.
- `exam_failed` → `exam_released` permite refazer a prova.
- `pending` é estado de exceção — coordenador deve resolver antes de prosseguir.
- `veteran` é terminal — ao atingir, atribui role `veterano` (mantendo `student`) e dispara comissão.

## 4. Entidades & Campos

### Schema `student`

#### `students` — Registro do aluno

| Coluna | Tipo | Nullable | Default | FK / Índice | Descrição |
|--------|------|----------|---------|-------------|-----------|
| `id` | `UUID` PK | NOT NULL | `uuid4()` | — | PK do aluno |
| `external_id` | `UUID` | NOT NULL | — | UNIQUE, FK → `auth.users.external_id` (RESTRICT/CASCADE) | UUID do usuário no auth |
| `status` | `Enum(StudentStatus)` | NOT NULL | `'awaiting_documents'` | INDEX | Status atual do funil |
| `study_platform` | `JSONB` | NOT NULL | `{}` | — | Dados da plataforma de estudo (informados pelo coordenador na promoção) |
| `created_at` | `DateTime(tz)` | NOT NULL | `now()` | — | Timestamp de criação |
| `updated_at` | `DateTime(tz)` | NOT NULL | `now()` ON UPDATE | — | Timestamp de atualização |

#### (PLANEJADO) `student_documents` — Referência a documentos enviados

| Coluna | Tipo | Nullable | Default | FK / Índice | Descrição |
|--------|------|----------|---------|-------------|-----------|
| `id` | `UUID` PK | NOT NULL | `uuid4()` | — | PK |
| `student_id` | `UUID` | NOT NULL | — | FK → `students.id` (CASCADE), INDEX | Aluno dono |
| `document_type` | `String(50)` | NOT NULL | — | INDEX | Tipo: `military_service`, `certificate`, `transcript`, `blood_type`, `address_proof`, `id_card`, `birth_certificate` |
| `document_external_id` | `UUID` | NOT NULL | — | INDEX | ID do documento no serviço `documents` |
| `validation_status` | `String(20)` | NOT NULL | `'pending'` | — | Status da validação IA: `pending`, `approved`, `rejected` |
| `validation_result` | `JSONB` | NULL | — | — | Resultado da validação IA (motivo da rejeição, confidence, etc.) |
| `created_at` | `DateTime(tz)` | NOT NULL | `now()` | — | Timestamp |
| `updated_at` | `DateTime(tz)` | NOT NULL | `now()` ON UPDATE | — | Timestamp |

**Constraint:** `UNIQUE(student_id, document_type)` — 1 registro por tipo de documento por aluno.

#### (PLANEJADO) `student_exams` — Registro de provas

| Coluna | Tipo | Nullable | Default | FK / Índice | Descrição |
|--------|------|----------|---------|-------------|-----------|
| `id` | `UUID` PK | NOT NULL | `uuid4()` | — | PK |
| `student_id` | `UUID` | NOT NULL | — | FK → `students.id` (CASCADE), INDEX | Aluno |
| `scheduled_at` | `DateTime(tz)` | NULL | — | — | Data/hora agendada |
| `result` | `String(20)` | NULL | — | — | Resultado: `passed`, `failed` (NULL = não corrigida) |
| `corrected_by` | `UUID` | NULL | — | FK → `auth.users.external_id` | Coordenador que corrigiu |
| `corrected_at` | `DateTime(tz)` | NULL | — | — | Timestamp da correção |
| `attempt_number` | `Integer` | NOT NULL | `1` | — | Número da tentativa |
| `created_at` | `DateTime(tz)` | NOT NULL | `now()` | — | Timestamp |
| `updated_at` | `DateTime(tz)` | NOT NULL | `now()` ON UPDATE | — | Timestamp |

#### (PLANEJADO) `student_diplomas` — Registro de diploma

| Coluna | Tipo | Nullable | Default | FK / Índice | Descrição |
|--------|------|----------|---------|-------------|-----------|
| `id` | `UUID` PK | NOT NULL | `uuid4()` | — | PK |
| `student_id` | `UUID` | NOT NULL | — | FK → `students.id` (CASCADE), INDEX | Aluno |
| `issued_at` | `DateTime(tz)` | NULL | — | — | Timestamp da emissão |
| `picked_up_at` | `DateTime(tz)` | NULL | — | — | Timestamp da retirada |
| `pickup_photo_external_id` | `UUID` | NULL | — | — | ID da foto de retirada no `documents` |
| `created_at` | `DateTime(tz)` | NOT NULL | `now()` | — | Timestamp |
| `updated_at` | `DateTime(tz)` | NOT NULL | `now()` ON UPDATE | — | Timestamp |

### Schemas Pydantic

| Schema | Uso | Campos obrigatórios |
|--------|-----|---------------------|
| `PromoteRequest` | POST /students (coordenador) | `external_id` |
| `StudentRead` | Response do aluno | `id`, `external_id`, `status`, `study_platform`, `created_at`, `updated_at` |
| (PLANEJADO) `DocumentSubmitRequest` | POST /students/{id}/documents | `document_type`, `document_external_id` |
| (PLANEJADO) `ExamScheduleRequest` | POST /students/{id}/exams | `scheduled_at` |
| (PLANEJADO) `ExamResultRequest` | PATCH /students/{id}/exams/{exam_id} | `result` |
| (PLANEJADO) `DiplomaPickupRequest` | POST /students/{id}/diploma/pickup | `photo_external_id` |

## 5. Endpoints

### 5.1. Implementados (Milestone 1)

| Método | Rota | Auth | Descrição |
|--------|------|------|-----------|
| `POST` | `/api/v1/authenticated/students` | `coordinator` | Coordenaor promove matriculado a aluno. Cria registro com `status=awaiting_documents`. Idempotente (409 se já existe). |
| `GET` | `/api/v1/authenticated/students/me` | `student` | Aluno consulta próprios dados a qualquer momento. |

### 5.2. Health / Status

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/health` | Liveness probe |
| `GET` | `/ready` | Readiness probe — testa conexão PG |
| `GET` | `/status` | Status com versão e uptime |

### 5.3. (PLANEJADO) Documentos

| Método | Rota | Auth | Descrição |
|--------|------|------|-----------|
| `POST` | `/api/v1/authenticated/students/{student_id}/documents` | `student` | Envia referência a documento (tipo + ID do `documents`). Valida tipo obrigatório. |
| `GET` | `/api/v1/authenticated/students/{student_id}/documents` | `student` | Lista documentos enviados e status de validação. |
| `POST` | `/api/v1/authenticated/students/{student_id}/documents/submit-for-review` | `student` | Submete todos os documentos para validação IA. Transição `awaiting_documents` → `documents_under_review`. |

### 5.4. (PLANEJADO) Prova

| Método | Rota | Auth | Descrição |
|--------|------|------|-----------|
| `POST` | `/api/v1/authenticated/students/{student_id}/exams` | `student` | Agenda prova. Transição `exam_released` → `exam_scheduled`. |
| `PATCH` | `/api/v1/authenticated/students/{student_id}/exams/{exam_id}` | `coordinator` | Coordenador lança resultado (`passed`/`failed`). Transição para `awaiting_documentation_dispatch` ou `exam_failed`. |
| `GET` | `/api/v1/authenticated/students/{student_id}/exams` | `student` | Lista provas e resultados. |

### 5.5. (PLANEJADO) Diploma

| Método | Rota | Auth | Descrição |
|--------|------|------|-----------|
| `POST` | `/api/v1/authenticated/students/{student_id}/diploma/issue` | `coordinator` | Emite diploma. Transição `awaiting_diploma_issuance` → `awaiting_pickup`. |
| `POST` | `/api/v1/authenticated/students/{student_id}/diploma/pickup` | `student` | Registra retirada com foto. Transição `awaiting_pickup` → `veteran`. Dispara comissão. |

### 5.6. (PLANEJADO) Pendências

| Método | Rota | Auth | Descrição |
|--------|------|------|-----------|
| `GET` | `/api/v1/authenticated/students/{student_id}/pending-items` | `student`, `coordinator` | Lista pendências do aluno (docs reprovados, comissões pendentes, etc.) |

### 5.7. Erros padronizados

| Status | Code | Quando |
|--------|------|--------|
| `404` | `student_not_found` | Aluno não encontrado |
| `409` | `student_already_exists` | Tentativa de duplicar promoção |
| `422` | `validation_error` | Transição de status inválida, campo obrigatório ausente |
| `403` | `forbidden` | Role insuficiente para a ação |

## 6. Integrações Externas

| Serviço | Tipo | Propósito | Status |
|---------|------|-----------|--------|
| `documents` | HTTP (httpx) | Armazenar/consultar documentos (fotos, PDFs) | **Planejado** — client em `integrations/documents.py` |
| `ai` | HTTP (httpx) | Validação assíncrona de imagens (RG, comprovante, etc.) | **Planejado** — worker_loop espelha padrão do `asaas` |
| `commissions` | HTTP (httpx) | Disparar comissão do coordenador ao virar veterano | **Planejado** — idempotente por `student_id` |
| `notify` | HTTP (httpx) | Notificações assíncronas (mudança de status, lembretes) | **Planejado** |
| `roles` / `auth` | HTTP (httpx) | Atribuição de role `veterano` (multi-role) | **Planejado** |
| `auth.users` | FK referencial | `students.external_id` → `auth.users.external_id` | **Implementado** |

**Padrão de integração:** Todas as chamadas externas via `httpx.AsyncClient` em `app/integrations/`. Shadow tables read-only para cross-schema (CONVENTION §4). IA via app `ai` (§13) — validação best-effort, nunca bloqueia o fluxo se indisponível.

## 7. Eventos Disparados / Consumidos

### Consumidos

| Evento | Origem | Reação |
|--------|--------|--------|
| `enrollment.completed` | Serviço `enrollment` | Coordenador chama POST para promover a student (não é webhook — é ação manual do coordenador) |

### Disparados (planejados)

| Evento | Gatilho | Destino |
|--------|---------|---------|
| `student.promoted` | POST /students (criação) | Log estruturado + notify |
| `student.documents_submitted` | Submit for review | Worker IA (async) |
| `student.documents_validated` | IA aprova/rejeita | Notify (aluno + coordenador) |
| `student.exam_scheduled` | Aluno agenda prova | Notify (coordenador) |
| `student.exam_result` | Coordenador lança resultado | Notify (aluno) |
| `student.veteran` | Diploma retirado + foto | `commissions` (comissão coordenador) + `roles` (role veterano) |

## 8. Regras de Negócio Invariantes

1. **1 student por usuário** — `external_id` é UNIQUE. Tentativa de duplicar retorna 409.

2. **Documentos obrigatórios** — Para avançar de `awaiting_documents`, todos os documentos obrigatórios devem estar enviados e aprovados: `certificate` (certificado do último ano), `transcript` (histórico do último ano), `id_card` (RG). Os demais são opcionais mas recomendados.

3. **Serviço militar só para homens** — `military_service` é obrigatório apenas se o aluno for do sexo masculino. Campo `gender` deve existir no perfil (via `profiles` ou `auth`).

4. **Validação IA é best-effort** — Se o serviço `ai` estiver indisponível, documentos ficam em `pending` (não bloqueia outros fluxos). Só avança status se IA aprovar explicitamente.

5. **Prova: coordenação por polo** — Apenas o coordenador do polo do aluno pode corrigir a prova. Autorização por polo via shadow `hub` (quando existir).

6. **Reprovação reabre ciclo** — `exam_failed` → aluno pode refazer a prova. `attempt_number` incrementa. Sem limite de tentativas (política do coordenador).

7. **Multi-role: veterano mantém student** — Ao virar veterano, a role `veterano` é adicionada (não substitui `student`). Mesmo padrão de promotor que é coordenador.

8. **Comissão idempotente** — A chamada ao `commissions` na virada para veterano é idempotente por `student_id`. Reenvio retorna comissão existente.

9. **PK UUID** — Todas as tabelas usam PK UUID (CONVENTION §4).

10. **Integrações só em `integrations/`** — Nunca importar modelos de outros serviços. Comunicação exclusivamente via httpx clients (CONVENTION §12).

## 9. Critérios de Aceite

1. [ ] **Milestone 1** — `POST /students` cria aluno com `awaiting_documents`; `GET /students/me` retorna dados. 409 em duplicata.

2. [ ] **Documentos** — Aluno envia documentos (refs ao `documents`); lista docs com status de validação; submit for review transiciona status.

3. [ ] **Validação IA** — Worker assíncrono valida documentos via `ai`; aprovação libera prova; rejeição mantém em `documents_under_review` com motivo.

4. [ ] **Prova** — Aluno agenda; coordenador lança resultado; aprovação avança para `awaiting_documentation_dispatch`; reprovação vai para `exam_failed` e permite refazer.

5. [ ] **Diploma** — Coordenador emite diploma; aluno registra retirada com foto; transição para `veteran`.

6. [ ] **Veterano** — Ao virar veterano: role `veterano` atribuída (mantendo `student`); comissão disparada ao `commissions` (idempotente).

7. [ ] **Pendências** — GET de pendências retorna docs reprovados, comissões pendentes, itens faltantes.

8. [ ] **Notify** — Notificações assíncronas em mudanças de status relevantes (aluno e/ou coordenador).

9. [ ] **Conformidade** — API nos 3 tipos (§5), PK UUID (§4), integrações em `integrations/` (§12), IA via `ai` (§13), simplicidade (§14).

10. [ ] **Testes** — `ruff` limpo + `pytest` (sqlite) verde + `alembic upgrade head` válido.

## 10. Riscos / Open Questions

### Riscos

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| Serviços dependentes (`documents`, `ai`, `commissions`) inexistentes | Alta | Médio | Clients httpx com contratos assumidos; fluxo não quebra se integração falhar; testes com fakes |
| Validação IA indisponível deixa aluno travado | Média | Alto | Worker idempotente com retry/backoff; status de erro reprocessável; só avança em aprovação |
| Acoplamento indevido com `documents`/`commissions` | Média | Alto | §6/§12: armazenar só `external_id` + status; nunca importar modelo alheio |
| Multi-role inconsistente com `roles`/`auth` | Média | Médio | Confirmar contrato de role antes do milestone 4 |
| Escopo grande estourar ciclo de entrega | Alta | Médio | Milestones fatiados; 1 commit por milestone |

### Open Questions

- [ ] **Contrato do `documents`** — quais endpoints/payload o `student` assume para criar/consultar referência de documento e obter o PDF?
- [ ] **Contrato do `ai`** — qual endpoint de validação de imagem e formato de resposta aprovado/reprovado?
- [ ] **Contrato do `commissions`** — payload e chave de idempotência para "comissão do coordenador na virada para veterano".
- [ ] **Atribuição da role `veterano`** — é o `student` que chama `roles`/`auth`, ou emite evento?
- [ ] **Tipo sanguíneo** — é um campo do aluno (dado) ou um "documento" no `documents`?
- [ ] **Quem corrige a prova** — sempre o coordenador do polo do aluno? Autorização por polo via shadow `hub`?
- [ ] **Limite de tentativas de prova** — sem limite (política do coordenador) ou definir máximo?

---

*Status: DRAFT — requisitos consolidados do TODO + código existente + PRD anterior. Aguardando review humano antes de continuação da implementação.*
