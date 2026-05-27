# Commissions — Pagamento Automático de Promotores e Coordenadores

> Serviço: `commissions/` · Schema: `commissions` · Porta: `8014`
> Parte B do `wiki/PLANO_ADEQUACAO.md`, item 8 · Spec original: `commissions/TODO`
> Status desta SPEC: **pronto para review** — código MVP implementado (milestones 1-4 parcial).

---

## 1. Contexto de Negócio

A plataforma precisa remunerar automaticamente dois perfis de beneficiários:

1. **Promotores** — recebem comissão por cada **lead completo** (lead que pagou e foi confirmado).
2. **Coordenadores de hub** — recebem comissão por cada **student concluído** (aluno que postou foto com diploma).

Hoje esse serviço não existe — cálculo e pagamento seriam manuais, sujeitos a erro, duplicidade e atraso. Sem ele, o incentivo que move a captação (promotores) e a conclusão (coordenadores) não fecha o ciclo.

O módulo `commissions` orquestra todo o fluxo:

1. **Geração por evento** — quando um lead é concluído (`lead.completed`) ou um student finaliza, uma comissão é criada automaticamente com valor definido em variáveis de ambiente.
2. **Lote semanal idempotente** — toda sexta-feira às 18h (America/Sao_Paulo), o worker agrega todas as comissões pendentes, aplica bônus de promotor (se atingir threshold de leads), marca como processadas e cria um `PaymentBatch`.
3. **Payout via Asaas** — o lote é submetido ao serviço `asaas` para emissão de PIX. O status é atualizado via callback interno.

**Estado atual:** O serviço é **MVP funcional** — possui modelos (`Commission`, `PaymentBatch`), endpoints CRUD, worker asyncio agendado, integração stub com Asaas, e testes. Faltam: webhook de recebimento de eventos do `lead`/`student`, resolução real de PIX key via `promoter`/`coordinator`, callback de status do Asaas, e payout real em produção.

## 2. Atores

| Ator | Role | Ação |
|------|------|------|
| **Sistema (lead)** | serviço `lead` | Dispara evento `lead.completed` quando lead muda para status `completed` → gera comissão para o promotor vinculado |
| **Sistema (student)** | serviço `student` (futuro) | Dispara evento `student.completed` quando student posta foto com diploma → gera comissão para o coordenador do hub |
| **Promotor** | `promoter` (serviço `promoter` — stub) | Beneficiário da comissão por lead. Recebe PIX semanal |
| **Coordenador do hub** | `coordinator` (serviço `coordinator`/`hub` — futuro) | Beneficiário da comissão por student. Recebe PIX semanal |
| **Operador financeiro** | admin interno | Confere lotes de pagamento via endpoints de listagem; pode disparar processamento manual |
| **Sistema (asaas)** | serviço `asaas` | Executa o PIX payout e reporta status via callback interno (categoria `payout`) |

**Nota:** Os serviços `promoter`, `coordinator` e `student` ainda não existem (Parte B do plano). Até lá, a resolução de PIX key e o gatilho de student são tratados como stubs/contratos definidos.

## 3. Estados / Máquina de Estados

### CommissionStatus (StrEnum)

```
PENDING → PROCESSED → PAID
                  ↘ FAILED
          → CANCELLED
```

| Status | Significado | Transição para |
|--------|-------------|----------------|
| `pending` | Comissão criada, aguardando processamento semanal | `processed`, `cancelled` |
| `processed` | Incluída em lote de pagamento (PaymentBatch) | `paid`, `failed` |
| `paid` | PIX enviado com sucesso pelo Asaas | — (terminal) |
| `failed` | PIX falhou no Asaas | — (pode ser reprocessado manualmente) |
| `cancelled` | Cancelada manualmente pelo operador | — (terminal) |

### PaymentBatchStatus (StrEnum)

```
PENDING → PROCESSING → COMPLETED
                    ↘ FAILED
```

| Status | Significado | Transição para |
|--------|-------------|----------------|
| `pending` | Lote criado, aguardando envio ao Asaas | `processing` |
| `processing` | Enviado ao Asaas, aguardando confirmação | `completed`, `failed` |
| `completed` | PIX confirmado com sucesso | — (terminal) |
| `failed` | PIX falhou; `last_error` contém detalhes | — (pode reprocessar) |

**Regras de transição:**
- Commission: `pending` → `processed` ocorre em lote (todas as pendentes de uma vez) durante o processamento semanal.
- Commission: `processed` → `paid`/`failed` ocorre via callback do Asaas.
- PaymentBatch: Um lote por semana (`week_of` é UNIQUE conceitualmente). Rodar o worker 2× na mesma janela não duplica.
- Transições são unidirecionais (exceto `failed` que pode ser reprocessado manualmente).

## 4. Entidades & Campos

### Schema `commissions`

#### `commissions` — Registro de comissão por evento (MVP implementado)

| Coluna | Tipo | Nullable | Default | FK / Índice | Descrição |
|--------|------|----------|---------|-------------|-----------|
| `id` | `BigInteger` PK | NOT NULL | autoincrement | — | PK do registro |
| `recipient_external_id` | `UUID` | NOT NULL | — | FK → `auth.users.external_id` (RESTRICT/CASCADE), INDEX | UUID do beneficiário (promotor ou coordenador) |
| `recipient_role` | `String(32)` | NOT NULL | — | INDEX | Função do receptor: `promoter`, `coordinator` |
| `source_type` | `String(32)` | NOT NULL | — | INDEX | Tipo da entidade de origem: `lead`, `student_completion` |
| `source_external_id` | `UUID` | NOT NULL | — | INDEX | UUID da entidade de origem (lead.external_id ou student.external_id) |
| `amount_cents` | `Integer` | NOT NULL | — | — | Valor da comissão em centavos |
| `status` | `Enum(CommissionStatus)` | NOT NULL | `'pending'` | INDEX | Status da comissão |
| `payment_batch_id` | `BigInteger` | NULL | — | FK → `payment_batches.id` (SET NULL), INDEX | Lote de pagamento ao qual pertence |
| `created_at` | `DateTime(tz)` | NOT NULL | `now()` | — | Timestamp de criação |
| `updated_at` | `DateTime(tz)` | NOT NULL | `now()` ON UPDATE | — | Timestamp de atualização |

**Invariante de idempotência:** A combinação `(source_type, source_external_id)` garante que exatamente 1 comissão é gerada por evento. Verificação no service layer antes do INSERT.

#### `payment_batches` — Lote semanal de pagamentos (MVP implementado)

| Coluna | Tipo | Nullable | Default | FK / Índice | Descrição |
|--------|------|----------|---------|-------------|-----------|
| `id` | `BigInteger` PK | NOT NULL | autoincrement | — | PK do lote |
| `week_of` | `String(10)` | NOT NULL | — | INDEX | Data ISO da segunda-feira da semana de referência (ex: `2026-05-25`) |
| `total_cents` | `Integer` | NOT NULL | `0` | — | Valor total do lote em centavos (comissões + bônus) |
| `bonus_cents` | `Integer` | NOT NULL | `0` | — | Valor total de bônus incluso no lote em centavos |
| `status` | `Enum(PaymentBatchStatus)` | NOT NULL | `'pending'` | INDEX | Status do lote |
| `pix_transaction_id` | `String` | NULL | — | — | ID da transação PIX no Asaas |
| `asaas_transfer_id` | `String` | NULL | — | — | ID da transferência no Asaas |
| `last_error` | `Text` | NULL | — | — | Último erro registrado na tentativa de pagamento |
| `created_at` | `DateTime(tz)` | NOT NULL | `now()` | — | Timestamp de criação |
| `updated_at` | `DateTime(tz)` | NOT NULL | `now()` ON UPDATE | — | Timestamp de atualização |

**Relacionamento:** Um `PaymentBatch` contém N `Commission` registros (via `commissions.payment_batch_id`).

### Variáveis de Ambiente (configuração de valores)

| Variável | Default | Descrição |
|----------|---------|-----------|
| `PROMOTER_COMMISSION_CENTS` | `100` (R$ 1,00) | Valor da comissão por lead completo |
| `COORDINATOR_COMMISSION_CENTS` | `50` (R$ 0,50) | Valor da comissão por student concluído |
| `BONUS_THRESHOLD_COUNT` | `10` | Número mínimo de leads comissionados para ativar bônus |
| `BONUS_COMISSION_CENTS` | `50` (R$ 0,50) | Valor do bônus por lead quando threshold atingido |
| `PROCESSING_CRON_HOUR` | `18` | Hora do processamento semanal (sexta-feira) |
| `PROCESSING_CRON_TIMEZONE` | `America/Sao_Paulo` | Timezone do cron |

## 5. Endpoints

### 5.1. Criar comissão (desmilitarizado — interno)

| Campo | Valor |
|-------|-------|
| **Método** | `POST` |
| **Rota** | `/api/v1/commissions` |
| **Tipo** | **Desmilitarizado** (chamado internamente pelo gateway ou pelo próprio serviço ao receber webhook) |
| **Auth** | Nenhuma (roda dentro da plataforma) |
| **Request body** | `{"recipient_external_id": "UUID", "recipient_role": "promoter|coordinator", "source_type": "lead|student_completion", "source_external_id": "UUID", "amount_cents": int}` |
| **Response** | `201` — `CommissionResponse` |
| **Idempotência** | Se já existe comissão para `(source_type, source_external_id)`, retorna a existente (não duplica) |
| **Side-effects** | Cria registro `Commission` com status `pending` |

### 5.2. Listar comissões (desmilitarizado — auditoria)

| Campo | Valor |
|-------|-------|
| **Método** | `GET` |
| **Rota** | `/api/v1/commissions` |
| **Tipo** | **Desmilitarizado** |
| **Query params** | `recipient_external_id` (UUID, opcional), `status` (string, opcional), `limit` (1-200, default 50), `offset` (default 0) |
| **Response** | `200` — `CommissionListResponse` (`{items: [...], total: int}`) |

### 5.3. Obter comissão por ID (desmilitarizado)

| Campo | Valor |
|-------|-------|
| **Método** | `GET` |
| **Rota** | `/api/v1/commissions/{commission_id}` |
| **Tipo** | **Desmilitarizado** |
| **Response** | `200` — `CommissionResponse` |
| **Erro** | `404` — comissão não encontrada |

### 5.4. Listar lotes de pagamento (desmilitarizado — auditoria)

| Campo | Valor |
|-------|-------|
| **Método** | `GET` |
| **Rota** | `/api/v1/batches` |
| **Tipo** | **Desmilitarizado** |
| **Query params** | `status` (string, opcional), `limit` (1-200, default 50), `offset` (default 0) |
| **Response** | `200` — `PaymentBatchListResponse` (`{items: [...], total: int}`) |

### 5.5. Obter lote por ID (desmilitarizado)

| Campo | Valor |
|-------|-------|
| **Método** | `GET` |
| **Rota** | `/api/v1/batches/{batch_id}` |
| **Tipo** | **Desmilitarizado** |
| **Response** | `200` — `PaymentBatchResponse` |
| **Erro** | `404` — lote não encontrado |

### 5.6. Disparar processamento manual (desmilitarizado — admin)

| Campo | Valor |
|-------|-------|
| **Método** | `POST` |
| **Rota** | `/api/v1/batches/trigger-processing` |
| **Tipo** | **Desmilitarizado** (admin interno; futuramente autenticado) |
| **Request body** | `{"week_of": "YYYY-MM-DD", "force_reprocess": false}` |
| **Response** | `200` — `TriggerProcessingResponse` |
| **Side-effects** | Executa o mesmo fluxo do worker: agrega pendentes, aplica bônus, cria lote, submete ao Asaas |
| **Idempotência** | Se já existe lote para a semana (não-FAILED), retorna mensagem informativa sem duplicar |

### 5.7. (PLANEJADO) Webhook — Receber evento de lead/student

| Campo | Valor |
|-------|-------|
| **Método** | `POST` |
| **Rota** | `/api/v1/webhook/commission-event` |
| **Tipo** | **Desmilitarizado** (webhook interno) |
| **Request body** | `{"event": "lead.completed|student.completed", "source_external_id": "UUID", "recipient_external_id": "UUID", "recipient_role": "promoter|coordinator"}` |
| **Response** | `202` — `{"ok": true, "commission_id": int}` |
| **Idempotência** | Por `(source_type, source_external_id)` — reenvio retorna comissão existente |
| **Side-effects** | Cria `Commission` pendente com valor do env correspondente |

### 5.8. (PLANEJADO) Callback de status do Asaas

| Campo | Valor |
|-------|-------|
| **Método** | `POST` |
| **Rota** | `/api/v1/webhook/asaas-payout-status` |
| **Tipo** | **Desmilitarizado** (callback interno do asaas, categoria `payout`) |
| **Request body** | Shape definido pelo asaas (TBD — confirmar com `/config/internal`) |
| **Response** | `200` — `{"ok": true}` |
| **Side-effects** | Atualiza `PaymentBatch.status` e `Commission.status` (pending→paid ou pending→failed) |

### 5.9. Health / Ready / Status

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/health` | Liveness probe — `{"status": "ok"}` |
| `GET` | `/ready` | Readiness probe — `{"status": "ok"}` |
| `GET` | `/status` | Diagnóstico — versão, uptime, service name |

## 6. Integrações Externas

| Serviço | Tipo de integração | Propósito | Status |
|---------|-------------------|-----------|--------|
| `asaas` | HTTP (httpx, via `AsaasPayoutClient`) | Executar PIX payout (chama endpoint interno do asaas, não a API externa diretamente) | **Stub** — mock em dev/test; real pendente de credentials de produção |
| `asaas` | Callback interno | Receber atualização de status do PIX (categoria `payout`) | **Planejado** — endpoint não implementado |
| `lead` | Webhook (inbound) | Receber evento `lead.completed` para gerar comissão de promotor | **Planejado** — endpoint de webhook não implementado |
| `student` | Webhook (inbound, futuro) | Receber evento `student.completed` para gerar comissão de coordenador | **Planejado** — depende de `student` existir |
| `promoter` | HTTP (httpx, desmilitarizado) | Resolver PIX key do promotor para payout | **Planejado** — `promoter` é stub; PIX key = placeholder |
| `coordinator` | HTTP (httpx, desmilitarizado) | Resolver PIX key do coordenador para payout | **Planejado** — `coordinator` não existe |

**Padrão de integração:** Todas as chamadas HTTP são via `httpx.AsyncClient` com timeout configurável. Clientes ficam em `app/integrations/`. O `AsaasPayoutClient` é o único ponto de contato com o Asaas (CONVENTION §12). Em modo `dev`/`test`, retorna mock de sucesso.

## 7. Eventos Disparados / Consumidos

### Consumidos (planejados)

| Evento | Origem | Reação |
|--------|--------|--------|
| `lead.completed` | Serviço `lead` (webhook POST) | Cria `Commission` com `source_type='lead'`, `recipient_role='promoter'`, valor do env `PROMOTER_COMMISSION_CENTS` |
| `student.completed` | Serviço `student` (webhook POST, futuro) | Cria `Commission` com `source_type='student_completion'`, `recipient_role='coordinator'`, valor do env `COORDINATOR_COMMISSION_CENTS` |

### Disparados (internos)

| Evento | Gatilho | Destino |
|--------|---------|---------|
| `commission.created` | INSERT em `commissions` | Log estruturado (observabilidade) |
| `commission.batch_created` | Lote semanal criado | Log estruturado |
| `commission.batch_submitted` | Lote enviado ao Asaas | Log estruturado |
| `commission.bonus_applied` | Bônus de promotor aplicado | Log estruturado |
| `worker.started` / `worker.next_run` / `worker.processing_batch` / `worker.batch_completed` | Ciclo do worker | Log estruturado |

### Disparados (planejados — outbound)

| Evento | Gatilho | Destino |
|--------|---------|---------|
| PIX payout request | Lote `PENDING` → `PROCESSING` | Serviço `asaas` (interno) |
| Status update callback | Resposta do Asaas | Atualização de `PaymentBatch` + `Commission` status |

## 8. Regras de Negócio Invariantes

1. **1 comissão por evento** — A combinação `(source_type, source_external_id)` é verificada antes do INSERT. Se já existe, retorna o registro existente (idempotência no service layer). Teste: `test_commissions.py` valida cenário de duplicata.

2. **Valores definidos em env** — `promoter_commission_cents` (default 100 = R$ 1,00) e `coordinator_commission_cents` (default 50 = R$ 0,50) são configuráveis via variáveis de ambiente. Não hardcoded.

3. **Lote semanal idempotente** — Um `PaymentBatch` por semana (`week_of`). Se já existe lote para a semana em status `PENDING` ou `PROCESSING`, `process_weekly_batch()` retorna `None` (não duplica). O worker dorme 24h após execução bem-sucedida para evitar retrigger.

4. **Horário fixo: sexta 18h America/Sao_Paulo** — O worker calcula a próxima sexta-feira usando `ZoneInfo("America/Sao_Paulo")`. `_calculate_next_friday()` considera se já passou das 18h hoje. Teste de borda obrigatório.

5. **Bônus de promotor por threshold** — Se o número de comissões de promotor (`source_type='lead'`, `status='pending'`) no período ≥ `BONUS_THRESHOLD_COUNT` (default 10), é adicionado bônus de `BONUS_COMISSION_CENTS` (default 50) × número de leads comissionados. Bônus só para promotores (não coordenadores — leitura literal da spec).

6. **FK real para auth.users** — `recipient_external_id` referencia `auth.users.external_id` via shadow table no `db.py`. `IntegrityError` → erro de domínio (consistência dentro do serviço).

7. **Status transições unidirecionais** — `pending` → `processed` → `paid`/`failed`. `cancelled` pode vir de `pending` apenas. `failed` pode ser reprocessado manualmente (novo lote com `force_reprocess=True`).

8. **Payout exclusivamente via Asaas** — CONVENTION §12: o `asaas` é o **único serviço autorizado** a integrar com a API Asaas. O `commissions` fala com o `asaas` via HTTP interno, nunca diretamente com a API externa.

9. **Worker asyncio no lifespan** — O `worker_loop()` é iniciado como `asyncio.create_task()` no lifespan do FastAPI. Se falhar ao iniciar, loga warning mas o serviço continua (endpoints funcionam, processamento manual disponível).

10. **Timezone consistente** — Todas as operações de data/hora do worker usam `ZoneInfo("America/Sao_Paulo")`. O banco armazena em UTC com timezone. Conversão explícita ao comparar períodos.

## 9. Critérios de Aceite

1. [ ] `POST /api/v1/commissions` cria comissão com status `pending` e valor correto do env.
2. [ ] Tentativa de criar comissão duplicada para mesmo `(source_type, source_external_id)` retorna a existente (idempotência).
3. [ ] `GET /api/v1/commissions` lista comissões com filtros (`recipient_external_id`, `status`) e paginação.
4. [ ] `GET /api/v1/commissions/{id}` retorna comissão; `404` quando ausente.
5. [ ] `POST /api/v1/batches/trigger-processing` agrega comissões pendentes, aplica bônus se threshold atingido, cria `PaymentBatch`, marca comissões como `processed`, submete ao Asaas.
6. [ ] Rodar `trigger-processing` 2× na mesma semana não duplica o lote (idempotência do worker).
7. [ ] Bônus é calculado corretamente: se leads comissionados ≥ `BONUS_THRESHOLD_COUNT`, soma `BONUS_COMISSION_CENTS × lead_count`.
8. [ ] `GET /api/v1/batches` lista lotes com paginação.
9. [ ] `GET /api/v1/batches/{id}` retorna lote com suas comissões; `404` quando ausente.
10. [ ] Worker asyncio agenda processamento para sexta 18h America/Sao_Paulo corretamente (teste de `_calculate_next_friday`).
11. [ ] Asaas client retorna mock em `dev`/`test`; integração real é diferida para produção.
12. [ ] `ruff` limpo + suíte `pytest` verde + `alembic upgrade head` válido.

## 10. Riscos / Open Questions

### Riscos

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| Duplicidade de pagamento (job 2× / evento 2×) | Média | Alto | Verificação idempotente no service layer (source_type + source_external_id) + lote por semana (get_or_create) |
| Dependências inexistentes (promoter/coordinator/student) bloqueiam e2e | Alta | Médio | Contratos definidos + stubs; PIX key = placeholder; e2e diferido para deploy |
| Timezone / horário de verão errado | Baixa | Médio | `ZoneInfo("America/Sao_Paulo")` + teste de borda em `_calculate_next_friday` |
| Falha do Asaas no payout | Média | Alto | `PaymentBatch` fica `FAILED` + `last_error` preenchido; retry via `force_reprocess`; fluxo não quebra |
| Worker não inicia (erro no lifespan) | Baixa | Médio | Serviço continua com endpoints ativos; processamento manual disponível via `trigger-processing` |
| Bônus calculado incorretamente (mudança de interpretação do threshold) | Média | Médio | Lógica clara no `_calculate_promoter_bonus`; reconfigurável via env sem deploy |

### Open Questions

- [ ] **Contrato do webhook `lead.completed`** — campos mínimos do payload: `source_external_id` (do lead), `recipient_external_id` (do promotor), `recipient_role`. Confirmar shape com serviço `lead`.
- [ ] **Resolução da PIX key** — enquanto `promoter`/`coordinator` não existem, usar placeholder? Feature flag de "payout habilitado"? Onde buscar a PIX key real quando existirem?
- [ ] **Callback do Asaas** — a categoria `payout` do `/config/internal` já entrega o evento (shape) que o `commissions` precisa? Confirmar campos e formato.
- [ ] **Bônus: período de contagem** — "número de leads que geraram comissão" = só da semana correta ou todo pendente acumulado? Assumido: pendentes do período (sem `payment_batch_id`).
- [ ] **Bônus: cálculo atual** — O código atual calcula `bonus = lead_count × bonus_comission_cents` quando `lead_count ≥ threshold`. A spec original diz "+1 comissão bônus do env". Qual é o correto: bônus fixo ou proporcional?
- [ ] **Autenticação dos endpoints** — todos são desmilitarizados hoje. Quando implementar auth: quem pode criar comissão? Quem pode disparar processamento? Espelhar padrão do `enrollment` (JWT + role gate)?
- [ ] **Payout individual vs agregado** — O código atual submete o lote inteiro como 1 PIX. A spec sugere pagamento por beneficiário. Precisa de 1 `PaymentBatch` por beneficiário ou 1 PIX por beneficiário dentro do mesmo lote?
- [ ] **Cancellation** — `CommissionStatus.CANCELLED` existe no enum mas não há endpoint nem lógica para cancelar. Implementar? Quem autoriza?

---

*Status: DRAFT — requisitos consolidados do TODO + código existente + PRD anterior. Aguardando review humano antes de continuação da implementação.*
