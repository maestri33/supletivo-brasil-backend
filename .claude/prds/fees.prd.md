# Fees — Módulo de Taxas de Matrícula

> Serviço: `fees/` · Schema: `fees` · Convenção: `CONVENTION.md`
> Status desta SPEC: pronto para review.

---

## 1. Contexto de Negócio

O módulo **fees** gerencia as taxas de matrícula dos alunos (students). O coordenador do polo (hub) cria uma taxa para um aluno, composta de **dois pagamentos PIX por QR Code** (BR Code): um **à vista** e outro **agendado**. Ambos são processados via serviço interno `asaas` (que é o dono exclusivo da integração Asaas/PIX).

O status da taxa é **derivado** dos status dos dois pagamentos. Quando a parte à vista é paga (`FIRST_PAID`), o acesso à plataforma do aluno é liberável — o `fees` apenas guarda o status; quem libera o acesso consulta o serviço depois.

**Estado atual:** O módulo está **completamente implementado**. Endpoints autenticados (coordenador cria/consulta taxas), webhook interno do asaas (recebe atualizações de status de payout), notificações assíncronas ao aluno e coordenador, e testes unitários.

**Money path:** A intenção (linhas no DB) é commitada **antes** de chamar o asaas. O `payment_id` é determinístico (`fee-{fee_id}-{kind}`), garantindo idempotência — re-submits recebem `payment_id_already_exists` do asaas e nunca duplicam pagamento.

---

## 2. Atores

| Ator | Role | Ação |
|------|------|------|
| **Coordenador do polo** | `coordinator` (JWT com role `coordinator`) | Cria taxas para alunos, consulta status de taxas |
| **Aluno (student)** | `student` (serviço externo) | Receptor da taxa; notificado quando acesso é liberado ou taxa quitada |
| **Sistema (asaas)** | serviço `asaas` | Processa os dois payouts PIX (à vista + agendado), envia webhooks de status |
| **Sistema (notify)** | serviço `notify` | Envia notificações assíncronas ao aluno e coordenador |

---

## 3. Estados / Máquina de Estados

### FeeStatus (StrEnum)

```
PENDING → FIRST_PAID → FULLY_PAID
    ↓
  FAILED
    ↓
 CANCELLED
```

| Status | Significado | Condição |
|--------|-------------|----------|
| `PENDING` | Criada; nenhuma parte paga | Ambos pagamentos em estado não-terminal |
| `FIRST_PAID` | Parte à vista paga → **acesso à plataforma liberável** | `upfront.status == "PAID"` |
| `FULLY_PAID` | Ambas as partes pagas | `upfront.status == "PAID" AND scheduled.status == "PAID"` |
| `FAILED` | A parte à vista falhou no Asaas | `upfront.status in {"FAILED", "CANCELLED"}` |
| `CANCELLED` | Cancelada manualmente | (reservado para implementação futura) |

**Regra de derivação:** O status da taxa é recalculado a cada webhook. A falha da parcela agendada **não** rebaixa uma taxa já `FIRST_PAID`.

### FeePaymentStatus (espelhado do asaas)

```
PENDING → (SCHEDULED|QUEUED) → SUBMITTING → SUBMITTED → PAID
Ramos: AWAITING_BALANCE, FAILED, CANCELLED, NEEDS_RECONCILE
Marcador local: SUBMIT_ERROR (falha de rede ao chamar o asaas)
```

---

## 4. Entidades & Campos

### Schema `fees`

#### `fee` — Agregado da taxa

| Coluna | Tipo | Nullable | Default | FK / Índice | Descrição |
|--------|------|----------|---------|-------------|-----------|
| `id` | `UUID` PK | NOT NULL | `uuid4()` | — | PK do agregado |
| `student_external_id` | `UUID` | NOT NULL | — | INDEX | UUID do aluno (opaco, sem FK cross-schema) |
| `coordinator_external_id` | `UUID` | NOT NULL | — | INDEX | UUID do coordenador que criou (vem do JWT) |
| `status` | `String(20)` | NOT NULL | `'PENDING'` | INDEX | Status derivado dos pagamentos |
| `description` | `Text` | NULL | — | — | Descrição da taxa (default: "Taxa de matrícula") |
| `created_at` | `DateTime(tz)` | NOT NULL | `now()` | — | Timestamp de criação |
| `updated_at` | `DateTime(tz)` | NOT NULL | `now()` ON UPDATE | — | Timestamp de atualização |

#### `fee_payment` — Um dos dois pagamentos PIX

| Coluna | Tipo | Nullable | Default | FK / Índice | Descrição |
|--------|------|----------|---------|-------------|-----------|
| `id` | `UUID` PK | NOT NULL | `uuid4()` | — | PK |
| `fee_id` | `UUID` | NOT NULL | — | INDEX | Referência ao Fee (sem FK declarada) |
| `kind` | `String(16)` | NOT NULL | — | — | `"upfront"` ou `"scheduled"` |
| `payment_id` | `String(80)` | NOT NULL | — | UNIQUE INDEX | Idempotency-Key enviada ao asaas; chave de correlação do webhook |
| `qrcode_payload` | `Text` | NOT NULL | — | — | BR Code copia-e-cola |
| `amount` | `Float` | NOT NULL | — | — | Valor em BRL |
| `scheduled_date` | `Date` | NULL | — | — | Data do agendamento (apenas para `kind=scheduled`) |
| `status` | `String(24)` | NOT NULL | `'PENDING'` | INDEX | Status do payout (espelhado do asaas) |
| `asaas_id` | `String(64)` | NULL | — | — | ID retornado pelo asaas |
| `last_error` | `Text` | NULL | — | — | Último erro de integração |
| `created_at` | `DateTime(tz)` | NOT NULL | `now()` | — | Timestamp de criação |
| `updated_at` | `DateTime(tz)` | NOT NULL | `now()` ON UPDATE | — | Timestamp de atualização |

---

## 5. Endpoints

### Autenticadas (exigem JWT com role `coordinator`)

| Verbo | Rota | Request | Response | Descrição |
|-------|------|---------|----------|-----------|
| `POST` | `/api/v1/authenticated/fees` | `FeeCreate` | `FeeRead` | Cria taxa (2 payouts PIX: à vista + agendado) |
| `GET` | `/api/v1/authenticated/fees` | `?status=&limit=&offset=` | `list[FeeRead]` | Lista taxas com filtros |
| `GET` | `/api/v1/authenticated/fees/student/{student_external_id}` | — | `FeeRead` | Última taxa de um aluno |
| `GET` | `/api/v1/authenticated/fees/{fee_id}` | — | `FeeRead` | Taxa por ID |

### Desmilitarizadas (webhook interno, sem auth de usuário)

| Verbo | Rota | Request | Response | Descrição |
|-------|------|---------|----------|-----------|
| `POST` | `/api/v1/webhook/asaas-payout` | `AsaasPayoutWebhook` | `{ok, fee_status?}` | Recebe status de payout do asaas; idempotente |

### Health/Status (públicas)

| Verbo | Rota | Response | Descrição |
|-------|------|----------|-----------|
| `GET` | `/health` | `{status: "ok"}` | Health check |
| `GET` | `/ready` | `{status, db}` | Readiness (testa SELECT 1) |
| `GET` | `/status` | `{status, service, version, environment, uptime_seconds}` | Status detalhado |

---

## 6. Integrações Externas

| Serviço | Direção | Mecanismo | Descrição |
|---------|---------|-----------|-----------|
| `asaas` | ↔ sincroniza | HTTP interno | Dono exclusivo da integração Asaas/PIX. fees chama `POST /api/v1/payment/qrcode` (à vista) e `POST /api/v1/payment/qrcode/scheduled` (agendado). Recebe webhooks de status via `POST /api/v1/webhook/asaas-payout`. |
| `notify` | → dispara | Background task | Envia notificações ao aluno (acesso liberado, taxa quitada) e ao coordenador (falha de pagamento) |
| `jwt` | ← consome | HTTP interno | Valida JWT RS256 via JWKS (`/.well-known/jwks.json`), extrai `external_id` e `roles` |

---

## 7. Eventos Disparados / Consumidos

| Evento | Direção | Descrição |
|--------|---------|-----------|
| `fee.created` | → dispara (log) | Disparado quando uma taxa é criada (structlog `fee_created`) |
| `fee.first_paid` | → dispara | Quando status muda para `FIRST_PAID` — notifica aluno sobre acesso liberado |
| `fee.fully_paid` | → dispara | Quando status muda para `FULLY_PAID` — notifica aluno sobre quitação |
| `fee.payment_failed` | → dispara | Quando uma parcela falha — alerta coordenador |
| `asaas.payout_status` | ← consome | Webhook do asaas com atualização de status de payout (correlação por `payment_id`) |

**Nota:** Todos os eventos de notificação são disparados via `BackgroundTasks` do FastAPI (assíncronos, não bloqueantes). Falha de notificação apenas loga — nunca quebra o fluxo principal.

---

## 8. Regras de Negócio Invariantes

1. **Uma taxa ativa por aluno:** Se já existe uma taxa com status `PENDING`, `FIRST_PAID` ou `FULLY_PAID` para o mesmo `student_external_id`, não é possível criar outra. Retorna 409 `FEE_ALREADY_EXISTS`.
2. **Status derivado, não declarado:** O status da taxa nunca é setado diretamente — é sempre recalculado a partir dos status dos dois pagamentos via `derive_fee_status()`.
3. **Idempotência do money path:** As linhas de pagamento são commitadas no DB **antes** de chamar o asaas. O `payment_id` é determinístico (`fee-{fee_id}-{kind}`). Re-submits são ignorados pelo asaas.
4. **Falha da agendada não rebaixa:** Se a parte à vista já foi paga (`FIRST_PAID`), falha da parcela agendada **não** muda o status da taxa para `FAILED`.
5. **Acesso liberado na primeira parte:** O acesso à plataforma é liberável quando `status == FIRST_PAID`. O `fees` apenas armazena o status — quem libera é quem consulta.
6. **Coordenador-only:** Todos os endpoints autenticados exigem role `coordinator` no JWT. Aluno não opera taxas.
7. **Sem FK cross-schema:** `student_external_id` e `coordinator_external_id` são referências lógicas (UUIDs opacos), não FKs declaradas.
8. **Notificações tolerantes a falha:** Falha no `notify` apenas loga (`fee_notify_failed`). Nunca propaga exceção.
9. **Rate limiting:** 200 requests/minuto por IP (slowapi).
10. **Webhook idempotente:** Re-entregar o mesmo status de payout não gera nova transição nem re-notifica.

---

## 9. Critérios de Aceite

1. `POST /api/v1/authenticated/fees` cria uma taxa com dois pagamentos (upfront + scheduled) e retorna `FeeRead` com status `PENDING`.
2. Tentar criar taxa para aluno que já tem taxa ativa retorna 409 `FEE_ALREADY_EXISTS`.
3. O webhook `POST /api/v1/webhook/asaas-payout` atualiza o status do pagamento e re-deriva o status da taxa.
4. Quando `upfront` muda para `PAID`, o status da taxa vira `FIRST_PAID` e notificação é enviada ao aluno.
5. Quando ambos ficam `PAID`, status vira `FULLY_PAID` e notificação de quitação é enviada.
6. Falha do `upfront` leva a taxa para `FAILED` e alerta o coordenador.
7. Falha do `scheduled` **não** rebaixa uma taxa `FIRST_PAID`.
8. Re-entregar o mesmo webhook (mesmo `payment_id` + mesmo `status`) é idempotente — sem nova notificação.
9. Endpoints autenticados rejeitam JWT sem role `coordinator` (403).
10. `GET /api/v1/authenticated/fees/student/{id}` retorna a última taxa do aluno (404 se nenhuma).

---

## 10. Riscos / Open Questions

1. **CANCELLED status:** O status `CANCELLED` existe no enum mas não há endpoint ou lógica para cancelar uma taxa manualmente. É futuro ou deve ser removido do enum?
2. **Reconciliação:** Se o asaas nunca envia webhook (perda de conexão), o pagamento fica `PENDING` indefinidamente. Existe processo de reconciliação (polling `GET /api/v1/payment/{payment_id}`)? O campo `NEEDS_RECONCILE` no asaas sugere que sim, mas não há implementação no fees.
3. **Duplo QR Code:** O coordenador precisa gerar os BR Codes (qrcode_payload) antes de chamar a API. De onde vêm esses payloads? Do asaas? De outro serviço? O fees não gera QR Codes — apenas os repassa.
4. **Integração com student/roles:** Quando `FIRST_PAID` ocorre, o fees apenas notifica. Quem realmente libera o acesso do aluno na plataforma? O `roles`? O `student`? Precisa confirmar o downstream.
5. **Valor da taxa:** O amount é definido pelo coordenador no momento da criação. Não há validação de valor mínimo/máximo nem tabela de referência. É intencional?
6. **Múltiplas tentativas:** Se uma taxa vai para `FAILED`, o coordenador pode criar outra (a restrição de taxa ativa não bloqueia FAILED). Mas o `payment_id` determinístico mudará (novo `fee_id`). Confirmar se esse é o fluxo desejado.
