# Training — LMS de Onboarding de Promotores

> Serviço: `training/` · Schema: `training` · Convenção: `CONVENTION.md`
> Status desta SPEC: pronto para review.

---

## 1. Contexto de Negócio

O módulo `training` é o **LMS (Learning Management System) de onboarding** da plataforma —
responsável por **treinar, avaliar e aprovar candidatos antes de se tornarem promotores**.

**Problema que resolve:** Hoje não existe mecanismo formal entre `candidate` e `promoter`.
Sem o training, a promoção é feita "no olho" (inconsistente, não auditável) ou candidatos
ficam parados sem caminho claro para avançar.

**Fluxo completo (MVP → Milestone 5):**
1. **Autoria** (desmilitarizado): admin cria matérias com texto, questão, gabarito + upload de vídeo/foto
2. **Treinamento**: trainee busca matérias, envia resposta, recebe nota 0–10 + justificativa via IA
3. **Conclusão**: todas aprovadas → "aguardando entrevista"; coordenador aprova/rejeita
4. **Promoção**: aprovação → `candidate → trainee → promoter` (via `roles`)

**Estado atual:** Apenas a **Milestone 1 (autoria de matérias)** está implementada.
Milestones 2–5 (correção por IA, entrevista, promoção, notificações) estão pendentes.

**Regra dura do TODO:** "se nota = ou maior que 6 flag aprovado" — a nota mínima para
aprovação é 6 (escala 0–10). "se nao aprovado pode enviar novamente" — reenvio sem limite.

## 2. Atores

| Ator | Role | Ação |
|------|------|------|
| **Autor de conteúdo (admin)** | Interno (app plataforma) | Cria matérias, envia vídeo/foto — operação desmilitarizada |
| **Trainee (candidato em treinamento)** | `candidate` (futuro `trainee`) | Busca matérias, envia resposta, acompanha nota |
| **Coordenador do hub** | Interno (app plataforma) | Aprova/rejeita trainee após entrevista — desmilitarizado |
| **Serviço `ai`** | Downstream | Corrige respostas assíncronamente: compara com gabarito, gera nota + justificativa |
| **Serviço `roles`** | Downstream | Gerencia transições de papel (`candidate → trainee → promoter`) |
| **Serviço `notify`** | Downstream | Envia notificações de mudança de status (M5) |

**Not for:** leads, students, veterans — não passam por esta trilha.

## 3. Estados / Máquina de Estados

### Material (já implementado — M1)

Material não tem máquina de estados. É uma entidade CRUD simples com timestamps.

### Trainee (planejado — M3/M4)

```
candidate → [entrar na trilha] → trainee
trainee → [todas matérias aprovadas] → awaiting_interview
awaiting_interview → [coordenador aprova] → promoter
awaiting_interview → [coordenador rejeita] → candidate (ou trainee, a definir)
```

### Submissão de resposta (planejado — M2)

```
submitted → [IA corrige] → graded
graded → [nota >= 6] → approved
graded → [nota < 6] → rejected → [reenvio] → submitted
```

**Nota:** A máquina de estados do trainee e das submissões será implementada nas
milestones futuras. Na M1, não há estados persistidos além do CRUD de materiais.

## 4. Entidades & Campos

### Schema `training`

#### `materials` — Conteúdo do treinamento

| Coluna | Tipo | Nullable | Default | FK / Índice | Descrição |
|--------|------|----------|---------|-------------|-----------|
| `id` | `UUID` PK | NOT NULL | `uuid4()` | — | PK (gerado na app, `UUIDStr` compatível SQLite) |
| `title` | `String(200)` | NOT NULL | — | — | Nome da matéria |
| `text_content` | `Text` | NOT NULL | — | — | Conteúdo textual da matéria |
| `question` | `Text` | NOT NULL | — | — | Questão única da matéria |
| `expected_answer` | `Text` | NOT NULL | — | — | Resposta esperada (gabarito) — base da correção por IA |
| `video_path` | `String(500)` | NULL | — | — | Caminho relativo do vídeo em `MEDIA_DIR`; null até upload |
| `photo_path` | `String(500)` | NULL | — | — | Caminho relativo da foto em `MEDIA_DIR`; null até upload |
| `created_at` | `DateTime(tz)` | NOT NULL | `now()` | — | Timestamp de criação |
| `updated_at` | `DateTime(tz)` | NOT NULL | `now()` | — | Timestamp de última atualização |

**Observações técnicas:**
- `UUIDStr = PG_UUID(as_uuid=False).with_variant(String(36), "sqlite")` — mesmo padrão do `candidate`
- `_mixins.py` provê `TimestampMixin` (created_at/updated_at com server_default)
- Mídia armazenada em `MEDIA_DIR/<material_id>/<kind><ext>` — servida via `FileResponse`, nunca `StaticFiles`

#### Entidades planejadas (M2–M4)

| Entidade | Milestone | Descrição |
|----------|-----------|-----------|
| `submissions` | M2 | Submissão de resposta do trainee: material_id, answer, grade, justification, status |
| `interviews` | M3 | Entrevista com coordenador: trainee_id, decision (approve/reject), reason |
| `trainee_progress` | M2 | Progresso do trainee: quais matérias aprovadas, data de conclusão |

## 5. Endpoints

### 5.1. Criar Matéria (desmilitarizado)

| Campo | Valor |
|-------|-------|
| **Método** | `POST` |
| **Rota** | `/api/v1/demilitarized/materials` |
| **Tipo** | **Desmilitarizado** (uso interno) |
| **Auth** | Nenhuma |
| **Request body** | `{"title": "string", "text_content": "string", "question": "string", "expected_answer": "string"}` |
| **Response** | `201` — `MaterialOut` |
| **Erros** | `422` campos inválidos/vazios |
| **Idempotência** | Não — cada chamada cria nova matéria |

### 5.2. Listar Matérias (desmilitarizado)

| Campo | Valor |
|-------|-------|
| **Método** | `GET` |
| **Rota** | `/api/v1/demilitarized/materials` |
| **Query params** | `limit` (1-500, default 200), `offset` (≥0, default 0) |
| **Response** | `200` — `{"total": N, "materials": [MaterialOut]}` |
| **Ordenação** | `created_at DESC, id DESC` (paginação estável) |

### 5.3. Buscar Matéria (desmilitarizado)

| Campo | Valor |
|-------|-------|
| **Método** | `GET` |
| **Rota** | `/api/v1/demilitarized/materials/{material_id}` |
| **Response** | `200` — `MaterialOut` |
| **Erros** | `404` matéria não encontrada |

### 5.4. Atualizar Matéria (desmilitarizado)

| Campo | Valor |
|-------|-------|
| **Método** | `PUT` |
| **Rota** | `/api/v1/demilitarized/materials/{material_id}` |
| **Request body** | `MaterialUpdate` (campos opcionais — apenas os informados são atualizados) |
| **Response** | `200` — `MaterialOut` |
| **Erros** | `404` matéria não encontrada; `422` campos inválidos |

### 5.5. Upload de Vídeo (desmilitarizado)

| Campo | Valor |
|-------|-------|
| **Método** | `POST` |
| **Rota** | `/api/v1/demilitarized/materials/{material_id}/video` |
| **Content-Type** | `multipart/form-data` |
| **Validação** | MIME type deve começar com `video/*`; tamanho ≤ `MAX_UPLOAD_MB` (default 200MB) |
| **Response** | `200` — `MaterialOut` (atualizado com `has_video: true`) |
| **Erros** | `404` matéria não encontrada; `422` tipo inválido ou tamanho excedido |
| **Storage** | `MEDIA_DIR/<material_id>/video<ext>` |

### 5.6. Upload de Foto (desmilitarizado)

| Campo | Valor |
|-------|-------|
| **Método** | `POST` |
| **Rota** | `/api/v1/demilitarized/materials/{material_id}/photo` |
| **Content-Type** | `multipart/form-data` |
| **Validação** | MIME type deve começar com `image/*`; tamanho ≤ `MAX_UPLOAD_MB` |
| **Response** | `200` — `MaterialOut` (atualizado com `has_photo: true`) |
| **Storage** | `MEDIA_DIR/<material_id>/photo<ext>` |

### 5.7. Download de Vídeo / Foto (desmilitarizado)

| Campo | Valor |
|-------|-------|
| **Método** | `GET` |
| **Rotas** | `/api/v1/demilitarized/materials/{material_id}/video`, `.../photo` |
| **Response** | `FileResponse` com `media_type` detectado |
| **Erros** | `404` matéria não encontrada ou mídia não enviada |

### 5.8. Health / Ready (desmilitarizado)

| Campo | Valor |
|-------|-------|
| **Método** | `GET` |
| **Rotas** | `/health`, `/ready` |
| **Response** | `{"status": "ok/ready", "version": "..."}` |

### 5.9. Métricas (desmilitarizado)

| Campo | Valor |
|-------|-------|
| **Método** | `GET` |
| **Rota** | `/metrics` |
| **Formato** | Prometheus |
| **Métricas** | `training_http_requests_total` (counter), `training_http_request_duration_seconds` (histogram) |

### Endpoints planejados (M2)

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `POST /api/v1/demilitarized/materials/{id}/submit` | POST | Trainee envia resposta |
| `POST /api/v1/demilitarized/materials/{id}/grade` | POST | Correção via IA (assíncrona) |
| `GET /api/v1/demilitarized/trainees/{id}/progress` | GET | Progresso do trainee |

## 6. Integrações Externas

| Serviço | Tipo de integração | Propósito | Status | Client em |
|---------|-------------------|-----------|--------|-----------|
| `ai` | HTTP (desmilitarizado) | Corrigir respostas: comparar com gabarito → nota 0–10 + justificativa | **Planejado (M2)** | `app/integrations/ai.py` |
| `roles` | HTTP (desmilitarizado) | Transições de papel: `candidate → trainee → promoter` | **Planejado (M4)** | — |
| `notify` | HTTP (desmilitarizado) | Notificações de status (aprovado, reprovado, entrevista, promoção) | **Planejado (M5)** | — |

**Padrão de integração (CONVENTION §12):**
- "Não quebre se a integração falhar" — chamadas são best-effort
- Timeout configurável via `AI_BASE_URL`, `AI_TIMEOUT` (Settings)
- Erros são logados (structlog) e não impedem o fluxo principal

**Estado atual:** Nenhuma integração implementada. O serviço `ai` será a primeira (M2).

## 7. Eventos Disparados / Consumidos

### Consumidos

Nenhum. O training não consome eventos de outros serviços.

### Disparados (planejados — M5)

| Evento | Gatilho | Destino |
|--------|---------|---------|
| `material.approved` | Nota ≥ 6 em submissão | `notify` → trainee |
| `material.rejected` | Nota < 6 em submissão | `notify` → trainee |
| `trainee.awaiting_interview` | Todas matérias aprovadas | `notify` → coordenador |
| `trainee.promoted` | Coordenador aprova | `notify` → trainee, `roles` → promoção |
| `trainee.rejected` | Coordenador rejeita | `notify` → trainee |

**Nota:** Na M1 não há eventos. Comunicação é HTTP síncrono ou background tasks.

## 8. Regras de Negócio Invariantes

1. **JAMAIS nota abaixo de 6 aprova** — "se nota = ou maior que 6 flag aprovado" (TODO). Invariante: `grade >= 6 → status = approved`; `grade < 6 → status = rejected`.

2. **MUITO IMPORTANTE: reenvio sem limite** — "se nao aprovado pode enviar novamente" (TODO). Não há cooldown ou limite de tentativas no MVP. O trainee pode reenviar quantas vezes necessário.

3. **JAMAIS correção síncrona** — A correção por IA é **assíncrona**. O endpoint de submissão registra a resposta e retorna imediatamente. A nota é gravada depois (callback ou poll). "de forma assincrona ia compara resposta do usuario com com a resposta da matéria" (TODO).

4. **MUITO IMPORTANTE: nota sempre com justificativa** — "dá nota de 0 a 10, justifica a mesma" (TODO). Toda nota gravada DEVE ter justificativa textual. Nota sem justificativa é invariante violada.

5. **Todas matérias aprovadas antes da entrevista** — "quando envia usuario tem todas matérias aprovado status esperando entrevista com coordenador" (TODO). O trainee só pode ir para entrevista quando TODAS as matérias estiverem com status `approved`.

6. **Decisão do coordenador é binária** — "simplesmente post/external_id/ aprova, ou rejeita, se rejeita texto com motivo" (TODO). Aprovação não tem texto; rejeição DEVE ter motivo.

7. **Mídia validada por MIME type** — Vídeo aceita apenas `video/*`, foto aceita apenas `image/*`. Upload com MIME incorreto → `422 ValidationError`.

8. **Tamanho de upload limitado** — `MAX_UPLOAD_MB` (default 200MB). Arquivo excedente → `422 ValidationError`.

9. **Storage local, servido via FileResponse** — Mídia fica em `MEDIA_DIR/<material_id>/<kind><ext>`. Nunca via `StaticFiles` aberto (controle de acesso).

10. **UUID como String(36)** — `PG_UUID(as_uuid=False).with_variant(String(36), "sqlite")` — compatível com SQLite nos testes e Postgres em produção.

## 9. Critérios de Aceite

### Milestone 1 (implementada)

1. [x] `POST /api/v1/demilitarized/materials` cria matéria com título, texto, questão, gabarito.
2. [x] `GET /api/v1/demilitarized/materials` lista matérias com paginação (limit/offset).
3. [x] `GET /api/v1/demilitarized/materials/{id}` busca matéria por ID.
4. [x] `PUT /api/v1/demilitarized/materials/{id}` atualiza campos informados.
5. [x] `POST .../video` e `POST .../photo` fazem upload de mídia com validação MIME.
6. [x] `GET .../video` e `GET .../photo` fazem download via FileResponse.
7. [x] `GET /health` e `GET /ready` respondem sem autenticação.
8. [x] `ruff` limpo + 11 testes verdes + SQLite em memória.

### Milestone 2 (pendente)

9. [ ] `POST .../submit` registra resposta do trainee e retorna `202 Accepted`.
10. [ ] Correção assíncrona via `ai` gera nota 0–10 + justificativa + comentário.
11. [ ] Nota ≥ 6 marca submissão como `approved`; < 6 marca como `rejected`.
12. [ ] Reenvio permitido sem limite para submissões `rejected`.
13. [ ] Toda nota gravada tem justificativa textual (invariante).

### Milestone 3 (pendente)

14. [ ] Todas matérias aprovadas → status do trainee muda para `awaiting_interview`.
15. [ ] `POST .../interview/{external_id}/approve` aprova trainee.
16. [ ] `POST .../interview/{external_id}/reject` rejeita com motivo obrigatório.

## 10. Riscos / Open Questions

### Riscos

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| Serviço `ai` indisponível/lento trava a correção | Média | Alto | Correção é assíncrona; resposta fica pendente e é reprocessada; trainee não fica bloqueado (CONVENTION §12) |
| IA dá nota injusta/inconsistente | Média | Médio | Justificativa sempre gravada; reenvio permitido; possibilidade de revisão manual |
| Armazenamento de vídeo cresce sem controle | Média | Médio | Limites de tamanho (200MB); avaliar storage externo se volume justificar |
| Mudança no `roles` (novo papel `trainee`) impacta outros serviços | Média | Alto | Tratar M4 como mudança coordenada; revisar quem depende de `candidate → promoter` direto |
| Decisão do coordenador sem auditoria | Baixa | Alto | Registrar quem/quando/motivo de cada decisão |

### Open Questions

- [ ] **Como o candidato entra na trilha?** Gatilho automático ao virar candidate, ou POST explícito?
- [ ] **Rejeição do coordenador:** trainee volta para qual estado? Refaz matérias? Aguarda nova entrevista?
- [ ] **Endpoint do `ai` para correção:** qual contrato? Precisa retornar nota + justificativa estruturada.
- [ ] **Limites de formato de vídeo/foto:** além do MIME type, aceitar apenas formatos específicos (mp4, jpg, png)?
- [ ] **Métrica baseline:** qual o tempo/promoção atual? Coletar para definir targets reais.
- [ ] **Nome do papel intermediário:** `trainee` confirmado? Ou outro nome no `roles`?
- [ ] **Cooldown de reenvio:** embora o TODO diga "pode enviar novamente", deve-se adicionar cooldown mínimo (ex: 30s)?

---

*Status: SPEC consolidado do TODO + código existente + CLAUDE.md + análise estática. Aguardando review humano antes de implementação das milestones 2–5.*
