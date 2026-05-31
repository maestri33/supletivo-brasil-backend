# Enrollment — Módulo de Matrícula

> Serviço: `enrollment/` · Schema: `enrollment` · Convenção: `CONVENTION.md`
> **GAP CRÍTICO** — módulo claramente sub-implementado vs o TODO escrito.
> Status desta SPEC: pronto para review.

---

## 1. Contexto de Negócio

Quando um **lead paga** (lead → `completed`), ele precisa passar por um processo de **matrícula** para se tornar um **student** oficial da plataforma. O módulo `enrollment` orquestra essa coleta de dados em etapas sequenciais:

1. Perfil pessoal
2. Endereço
3. Documento (RG — obrigatório)
4. Dados educacionais (último ano estudado, quando, em que escola)
5. Selfie (assinatura digital, mesma lógica do `candidate`)

Após preencher todas as etapas, o matriculando fica em `aguardando_liberacao`. O **coordenador do polo** é notificado e, ao liberar manualmente, a matrícula é concluída e o usuário vira `student`.

**Estado atual:** O serviço é um **stub auditivo** — recebe o webhook `lead.completed`, grava em `enrollment_events`, e expõe GETs de auditoria. O agregado de matrícula (`Enrollment`) já foi criado (milestone 1 implementado) com status machine completa, mas os endpoints de coleta (perfil, endereço, RG, educação, selfie) e a liberação **não existem** — é o gap crítico.

## 2. Atores

| Ator | Role | Ação |
|------|------|------|
| **Matriculando (lead pago)** | `lead` (status `completed`) | Autentica e envia dados para cada etapa da matrícula via endpoints autenticados |
| **Coordenador do polo** | `coordinator` (serviço `coordinator`/`hub` — ainda não existe) | Notificado quando os dados estão completos; faz liberação manual que conclui a matrícula |
| **Sistema (lead)** | serviço `lead` | Dispara webhook `lead.completed` na bifurcação de lead pago |
| **Sistema (notify)** | serviço `notify` | Envia notificações assíncronas ao coordenador |

**Nota:** O coordenador depende dos serviços `hub` e `coordinator` (Parte B do plano). Até existirem, a notificação e liberação são tratadas como best-effort/documentadas.

## 3. Estados / Máquina de Estados

### Status (EnrollmentStatus — StrEnum)

```
STARTED → PROFILE → ADDRESS → DOCUMENTS → EDUCATION → SELFIE → AWAITING_RELEASE → COMPLETED
```

| Status | Significado | Transição para |
|--------|-------------|-----------------|
| `started` | Matrícula criada (webhook recebido) | `profile` |
| `profile` | Perfil do matriculando enviado | `address` |
| `address` | Endereço enviado | `documents` |
| `documents` | RG enviado ao serviço `documents` | `education` |
| `education` | Dados educacionais enviados | `selfie` |
| `selfie` | Selfie enviada e validada (best-effort pelo `ai`) | `awaiting_release` |
| `awaiting_release` | Todos os dados completos, aguardando liberação do coordenador | `completed` |
| `completed` | Matrícula concluída, role promovida a `student` | — (terminal) |

**Regra:** A progressão é sequencial e unidirecional. Cada endpoint avança exatamente 1 status. Não é possível pular etapas nem retroceder.

### Ordem definida em código:

```python
STATUS_ORDER = (
    EnrollmentStatus.STARTED,
    EnrollmentStatus.PROFILE,
    EnrollmentStatus.ADDRESS,
    EnrollmentStatus.DOCUMENTS,
    EnrollmentStatus.EDUCATION,
    EnrollmentStatus.SELFIE,
    EnrollmentStatus.AWAITING_RELEASE,
    EnrollmentStatus.COMPLETED,
)
```

## 4. Entidades & Campos

### Schema `enrollment`

#### `enrollments` — Agregado de matrícula (MVP implementado)

| Coluna | Tipo | Nullable | Default | FK / Índice | Descrição |
|--------|------|----------|---------|-------------|-----------|
| `id` | `UUID` PK | NOT NULL | `uuid4()` | — | PK do agregado |
| `external_id` | `UUID` | NOT NULL | — | FK → `auth.users.external_id` (RESTRICT/CASCADE), **UNIQUE INDEX** | UUID do matriculando (1 matrícula por usuário) |
| `status` | `String(24)` | NOT NULL | `'started'` | INDEX | Etapa atual da matrícula |
| `promoter_external_id` | `UUID` | NULL | — | INDEX | UUID do promotor que indicou o lead |
| `hub_external_id` | `UUID` | NULL | — | INDEX | UUID do hub do promotor (resolvido quando `hub` existir) |
| `created_at` | `DateTime(tz)` | NOT NULL | `now()` | — | Timestamp de criação |
| `updated_at` | `DateTime(tz)` | NOT NULL | `now()` ON UPDATE | — | Timestamp de atualização |

#### `enrollment_events` — Log auditivo de eventos (legado, fora do escopo de refatoração)

| Coluna | Tipo | Nullable | Default | Descrição |
|--------|------|----------|---------|-----------|
| `id` | `BIGINT` PK | NOT NULL | autoincrement | PK do evento (legado BIGINT) |
| `external_id` | `UUID` | NOT NULL | — | FK → `auth.users.external_id` |
| `event` | `String(64)` | NOT NULL | — | Nome do evento (ex: `lead.completed`) |
| `promoter_external_id` | `UUID` | NULL | — | Promotor que indicou |
| `payload` | `JSONB` | NOT NULL | `{}` | Payload completo do webhook |
| `received_at` | `DateTime(tz)` | NOT NULL | `now()` | Timestamp de recebimento |
| `processed_at` | `DateTime(tz)` | NULL | — | Quando foi processado (futuro) |

### Tabela planejada (não implementada)

#### `educational_data` — Dados educacionais do matriculando (milestone 3)

| Coluna | Tipo | Nullable | Default | Descrição |
|--------|------|----------|---------|-----------|
| `id` | `UUID` PK | NOT NULL | `uuid4()` | PK |
| `enrollment_id` | `UUID` | NOT NULL | — | FK → `enrollment.enrollments.id` |
| `last_year_studied` | `Integer` | NOT NULL | — | Último ano que estudou |
| `last_year_date` | `Date` | NOT NULL | — | Quando foi o último ano |
| `last_school` | `String(255)` | NOT NULL | — | Em que escola foi |
| `created_at` | `DateTime(tz)` | NOT NULL | `now()` | Timestamp |

**Decisão de design:** Dados educacionais são **próprios do schema `enrollment`** (não delegados a outro serviço), ao contrário de perfil, endereço e documentos que são delegados aos serviços donos.

## 5. Endpoints

### 5.1. Webhook — Receber bifurcação do lead (público)

| Campo | Valor |
|-------|-------|
| **Método** | `POST` |
| **Rota** | `/api/v1/webhook/new/{external_id}` |
| **Tipo** | **Público** (webhook externo) |
| **Auth** | Nenhuma (validação futura via verificação de origem) |
| **Idempotência** | Sim — por `(external_id, event)`; reenvio retorna `already_exists: true` |
| **Request body** | `{"promoter_external_id": "UUID (opcional)", "event": "lead.completed"}` |
| **Response** | `202` — `{"ok": true, "already_exists": false, "id": event.id, "enrollment_id": "...", "status": "started", "event": "lead.completed"}` |
| **Side-effects** | Cria `EnrollmentEvent` + `Enrollment` (get-or-create) na mesma transação. Se `external_id` não existir em `auth.users` → `409 Conflict` |

### 5.2. Obter matrícula (desmilitarizado — interno)

| Campo | Valor |
|-------|-------|
| **Método** | `GET` |
| **Rota** | `/api/v1/enrollments/{external_id}` |
| **Tipo** | **Desmilitarizado** (apenas apps internos) |
| **Auth** | Nenhuma (roda dentro da plataforma) |
| **Response** | `200` — `EnrollmentRead` schema |
| **Erro** | `404` — matrícula não encontrada |

### 5.3. Listar eventos (desmilitarizado — auditoria)

| Campo | Valor |
|-------|-------|
| **Método** | `GET` |
| **Rota** | `/api/v1/events` |
| **Tipo** | **Desmilitarizado** |
| **Query params** | `external_id` (UUID, opcional), `limit` (1-200, default 50), `offset` (default 0) |
| **Response** | `200` — `list[EnrollmentEventRead]` |

### 5.4. Obter evento por id (desmilitarizado)

| Campo | Valor |
|-------|-------|
| **Método** | `GET` |
| **Rota** | `/api/v1/events/{event_id}` |
| **Tipo** | **Desmilitarizado** |
| **Response** | `200` — `EnrollmentEventRead` |
| **Erro** | `404` — evento não encontrado |

### 5.5. (PLANEJADO) Enviar perfil

| Campo | Valor |
|-------|-------|
| **Método** | `POST` |
| **Rota** | `/api/v1/enrollments/{external_id}/profile` |
| **Tipo** | **Autenticado** (JWT — somente o matriculando dono da matrícula) |
| **Auth requerida** | JWT com `external_id` igual ao da URL |
| **Pré-condição** | Status atual = `started` |
| **Side-effects** | Orquestra chamada ao serviço `profiles` (httpx) para gravar perfil; avança status para `profile` |
| **Idempotência** | Se status já >= `profile`, retorna sucesso sem duplicar (idempotente progressivo) |

### 5.6. (PLANEJADO) Enviar endereço

| Campo | Valor |
|-------|-------|
| **Método** | `POST` |
| **Rota** | `/api/v1/enrollments/{external_id}/address` |
| **Tipo** | **Autenticado** |
| **Auth requerida** | JWT — somente o matriculando dono |
| **Pré-condição** | Status atual = `profile` |
| **Side-effects** | Orquestra chamada ao serviço `address` (httpx); avança para `address` |

### 5.7. (PLANEJADO) Enviar RG

| Campo | Valor |
|-------|-------|
| **Método** | `POST` |
| **Rota** | `/api/v1/enrollments/{external_id}/documents/rg` |
| **Tipo** | **Autenticado** |
| **Auth requerida** | JWT — somente o matriculando dono |
| **Pré-condição** | Status atual = `address` |
| **Side-effects** | Upload do RG para serviço `documents` (slot específico para RG); avança para `documents` |

**Nota:** RG é obrigatório (mencionado como "sim obrigatório RG" no TODO original).

### 5.8. (PLANEJADO) Enviar dados educacionais

| Campo | Valor |
|-------|-------|
| **Método** | `POST` |
| **Rota** | `/api/v1/enrollments/{external_id}/education` |
| **Tipo** | **Autenticado** |
| **Auth requerida** | JWT — somente o matriculando dono |
| **Pré-condição** | Status atual = `documents` |
| **Request body** | `{"last_year_studied": int, "last_year_date": "YYYY-MM-DD", "last_school": string}` |
| **Side-effects** | Grava em `enrollment.educational_data` (tabela própria); avança para `education` |

**Invariante extraída do TODO (MUITO IMPORTANTE):** "Este indivíduo diga o último ano que ele estudou, quando foi; e em que escola foi" — todos os 3 campos são obrigatórios.

### 5.9. (PLANEJADO) Enviar selfie

| Campo | Valor |
|-------|-------|
| **Método** | `POST` |
| **Rota** | `/api/v1/enrollments/{external_id}/selfie` |
| **Tipo** | **Autenticado** |
| **Auth requerida** | JWT — somente o matriculando dono |
| **Pré-condição** | Status atual = `education` |
| **Side-effects** | Upload da selfie para serviço `documents` (slot `foto`, mesma lógica do `candidate`); validação IA best-effort (não bloqueia se `ai` cair); avança para `selfie` |

**Após completar a selfie:** Se todas as etapas foram enviadas (profile + address + rg + education + selfie), o status avança automaticamente para `awaiting_release`.

### 5.10. (PLANEJADO) Liberar matrícula (coordenador)

| Campo | Valor |
|-------|-------|
| **Método** | `POST` |
| **Rota** | `/api/v1/enrollments/{external_id}/release` |
| **Tipo** | **Autenticado** (JWT — coordenador ou admin temporário) |
| **Auth requerida** | Role `coordinator` (ou admin enquanto `coordinator` não existe) |
| **Pré-condição** | Status = `awaiting_release` |
| **Side-effects** | Chama serviço `roles` para promover role de `lead` → `student`; grava `processed_at` no evento; avança para `completed` |

## 6. Integrações Externas

| Serviço | Tipo de integração | Propósito |
|---------|-------------------|-----------|
| `profiles` | HTTP (httpx, desmilitarizado) | Gravar perfil do matriculando (milestone 2) |
| `address` | HTTP (httpx, desmilitarizado) | Gravar endereço do matriculando (milestone 2) |
| `documents` | HTTP (httpx, desmilitarizado) | Upload de RG (slot específico) e selfie (slot `foto`) (milestones 3-4) |
| `ai` | HTTP (httpx, desmilitarizado) | Validação best-effort da selfie (não bloqueia se falhar) (milestone 4) |
| `roles` | HTTP (httpx, desmilitarizado) | Promover role de `lead` → `student` na liberação (milestone 5) |
| `notify` | HTTP (httpx, desmilitarizado) | Notificar coordenador quando dados estiverem completos (best-effort) (milestone 4) |
| `hub` (futuro) | HTTP (httpx, desmilitarizado) | Resolver `hub_external_id` a partir do `promoter_external_id` (futuro) |

**Padrão de integração:** Todas as chamadas são via `httpx.AsyncClient` com timeout configurável. Clientes ficam em `integrations/`. Falhas de integração não quebram o fluxo — operam em modo best-effort com logging estruturado.

## 7. Eventos Disparados / Consumidos

### Consumidos

| Evento | Origem | Reação |
|--------|--------|--------|
| `lead.completed` | Serviço `lead` (webhook POST) | Cria `EnrollmentEvent` + `Enrollment` (started) |

### Disparados (planejados)

| Evento | Gatilho | Destino |
|--------|---------|---------|
| `enrollment.completed` | Liberação do coordenador → `completed` | Serviço `student` (via webhook ou polling futuro) |
| `enrollment.awaiting_release` | Todas as etapas preenchidas | Notificação ao coordenador via `notify` |

## 8. Regras de Negócio Invariantes

1. **1 matrícula por usuário** — `external_id` é UNIQUE na tabela `enrollments`. Se o lead pagou, já existe matrícula; tentativa de criar outra é idempotente.

2. **RG é obrigatório** — "sim obrigatório RG" (TODO original). O endpoint de documentos deve exigir RG antes de permitir progressão.

3. **Dados educacionais são obrigatórios** — "MUITO IMPORTANTE que este indivíduo diga o último ano que ele estudou, quando foi; e em que escola foi" (TODO original). Todos os 3 campos são requeridos.

4. **Selfie vinculada ao promotor** — A selfie segue a mesma lógica do `candidate`: tipo assinatura digital, vinculada ao processo do indivíduo.

5. **Progressão é unidirecional** — Cada status só avança para o próximo. Não há retrocesso nem pulo de etapas.

6. **Matrícula vinculada ao hub do promotor** — "O enrollment deve ser relacionado ao hub do promotor que indicou ele" (TODO original). Ao criar a matrícula, o `promoter_external_id` é registrado; quando `hub` existir, resolve-se o `hub_external_id`.

7. **Liberação dependente do coordenador** — Quando todas as etapas estão completas, o sistema fica em `awaiting_release`. A conclusão exige ação explícita do coordenador do polo.

8. **Notificação ao coordenador ao completar dados** — "Quando ele preencher tudo o coordenador do polo dele deve ser notificado" (TODO original). A notificação deve ser disparada assincronamente ao atingir `awaiting_release`.

9. **Validação de IA é best-effort** — A validação da selfie pelo serviço `ai` nunca pode bloquear o progresso. Se `ai` estiver indisponível, a selfie é aceita e a matrícula prossegue (igual `candidate`).

10. **FK real para auth.users** — Diferente do `candidate` (que usa ref lógico), o `enrollment` usa FK real com shadow table + `IntegrityError` → `Conflict` (consistência dentro do serviço).

## 9. Critérios de Aceite

1. [ ] Webhook `lead.completed` cria `Enrollment` com status `started` e `promoter_external_id`, idempotente — reenvio não duplica.
2. [ ] GET `/enrollments/{external_id}` retorna o agregado; `404` quando ausente.
3. [ ] GET `/events` lista eventos com paginação e filtro por `external_id`.
4. [ ] POST `.../profile` avança de `started` → `profile` e orquestra chamada ao `profiles`.
5. [ ] POST `.../address` avança de `profile` → `address` e orquestra chamada ao `address`.
6. [ ] POST `.../documents/rg` avança de `address` → `documents` e orquestra upload ao `documents`.
7. [ ] POST `.../education` avança de `documents` → `education` e persiste na tabela `educational_data`.
8. [ ] POST `.../selfie` avança de `education` → `selfie` (ou `awaiting_release` se for a última etapa) e orquestra upload + validação IA best-effort.
9. [ ] POST `.../release` (autenticado como coordenador) promove role `lead` → `student` no `roles` e marca matrícula como `completed`.
10. [ ] Tentativa de pular etapa (ex: enviar endereço antes do perfil) retorna erro de validação.
11. [ ] Tentativa de enviar etapa com `external_id` que não é do matriculando autenticado retorna `403` (ou similar).
12. [ ] `ruff` limpo + suíte `pytest` verde + `alembic upgrade head` válido.

## 10. Riscos / Open Questions

### Riscos

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| Dependência de `hub`/`coordinator`/`student` inexistentes | Alta | Médio | Notificação best-effort; liberação com admin temporário; role promovida no `roles` sem validação de hub |
| Falha de integração cross-service na coleta (profiles/address/documents/ai) | Média | Médio | Best-effort + logging; progressão não quebra; transações independentes |
| Selfie/`ai` indisponível travar funil | Média | Alto | Validação best-effort (não bloqueia), igual `candidate` |
| Matriculando não autenticado tenta endpoints (sem JWT/infra de auth) | Alta | Alto | Endpoints autenticados exigem JWT; gate de role/status |

### Open Questions

- [ ] Como o matriculando **autentica** nos endpoints? JWT via `auth`/`jwt` — qual role/status faz o gate? Espelhar `candidate` (JWT do próprio usuário, validação de `external_id`).
- [ ] Nomes/ordem exatos do **enum de status** da progressão — confirmar com dono do produto.
- [ ] Qual **slot** do `documents` recebe o RG? E a selfie reusa o slot `foto` do candidate?
- [ ] Como **autorizar a liberação manual** antes de `coordinator` existir? Endpoint desmilitarizado/admin temporário?
- [ ] `hub_external_id` é resolvido **na criação** da matrícula (quando `hub` existir) ou **sob demanda**?
- [ ] Precisa de Tabela `brands` dedicada ou enum/string suficiente? (decidir: String + validação Pydantic, como hub)
- [ ] O coordenador notificado precisa ser o coordenador **do polo do promotor** — como resolver antes de `hub`/`coordinator` existirem?

---

*Status: DRAFT — requisitos consolidados do TODO + código existente + PRD anterior. Aguardando review humano antes de implementação.*
