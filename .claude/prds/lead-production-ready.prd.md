# Lead — Production-Ready (cobertura + conformidade Fase 4)

> Serviço: `lead/` · Schema: `lead` · Convenção: `CONVENTION.md`
> **BLOQUEIO** — serviço funcionalmente completo mas sem testes e com 3 débitos Fase 4 no caminho do dinheiro.
> Status desta SPEC: DRAFT — requirements only. Implementation planning pending via /plan.

---

## 1. Contexto de Negócio

O microsserviço `lead` orquestra o **funil de captação e pagamento** de leads. Quando um candidato demonstra interesse, o sistema cria um registro `captured` e move-o através de um funil de 4 estados até a conclusão do pagamento:

1. **Captured** — lead registrado no sistema (via webhook ou integração)
2. **Waiting** — aguardando ação do lead (preenchimento de dados, decisão)
3. **Checkout** — lead iniciou processo de pagamento (gera checkout no gateway)
4. **Completed** — pagamento confirmado, lead pago

O serviço integra-se com dois gateways de pagamento:
- **InfinitePay** — confirmação de pagamento por cartão (webhook de retorno)
- **Asaas** — confirmação de pagamento PIX (webhook de retorno)

Quando o pagamento é confirmado, o `lead` dispara o evento `lead.completed` que alimenta os serviços downstream: `enrollment` (matrícula), `promoters` (comissão), `notify` (notificações).

**Estado atual:** O serviço é **funcionalmente completo** e em uso, mas **não está apto a produção**. Há 3 bloqueios:
1. **Zero teste automatizado** — `lead/tests/` não existe; única barreira contra regressões no caminho do dinheiro
2. **Backoff síncrono** — `request_with_retry` em `integrations/__init__.py` usa `time.sleep()`, bloqueando o event loop durante retentativas
3. **Recibo PIX com valor fallback** — webhook do Asaas não traz `amount`; usa `PIX_DEFAULT_AMOUNT` em vez do valor real do checkout
4. **Notify fora do padrão** — `notify_lead_captured` faz chamadas HTTP diretas (`httpx.AsyncClient`) sem usar `NotifyClient`/`ProfilesClient`

## 2. Atores

| Ator | Role | Ação |
|------|------|------|
| **Lead (candidato)** | `lead` (visitante autenticado ou anônimo) | Interage com o funil: preenche dados, inicia checkout, confirma pagamento |
| **Sistema (gateway InfinitePay)** | serviço externo | Dispara webhook de confirmação de pagamento por cartão |
| **Sistema (gateway Asaas)** | serviço externo | Dispara webhook de confirmação de pagamento PIX |
| **Sistema (enrollment)** | serviço interno | Consome evento `lead.completed` para criar matrícula |
| **Sistema (promoters)** | serviço interno | Consome evento `lead.completed` para registrar comissão |
| **Sistema (notify)** | serviço interno | Envia notificações (captura concluída, pagamento confirmado) |
| **Engenheiro mantenedor** | `developer` | Declara serviço apto a produção após cobertura de testes e quitação de débitos |

**Nota:** Este ciclo **não muda comportamento visível nem contrato de API pública**. É exclusivamente dívida técnica e cobertura.

## 3. Estados / Máquina de Estados

### LeadStatus (enum)

```
CAPTURED → WAITING → CHECKOUT → COMPLETED
```

| Status | Significado | Transição para |
|--------|-------------|----------------|
| `captured` | Lead registrado no sistema (webhook de captação recebido) | `waiting` |
| `waiting` | Aguardando ação do lead (preenchimento de dados) | `checkout` |
| `checkout` | Checkout criado no gateway de pagamento; aguardando confirmação | `completed` |
| `completed` | Pagamento confirmado; dispara `lead.completed` para downstream | — (terminal) |

**Regras de transição:**
- A progressão é **unidirecional e sequencial**. Não é possível retroceder.
- A transição `checkout → completed` é disporada **externamente** pelo webhook do gateway de pagamento (InfinitePay ou Asaas).
- A transição `captured → waiting` pode ser automática ou dependente de ação do lead.

### CheckoutStatus (enum associado)

| Status | Significado |
|--------|-------------|
| `pending` | Checkout criado, aguardando pagamento |
| `paid` | Pagamento confirmado pelo gateway |
| `failed` | Pagamento falhou (cartão recusado, erro de gateway) |
| `expired` | Checkout expirou sem pagamento |

## 4. Entidades & Campos

### Schema `lead`

#### `leads` — Agregado principal do lead

| Coluna | Tipo | Nullable | Default | FK / Índice | Descrição |
|--------|------|----------|---------|-------------|-----------|
| `id` | `BigInteger` PK | NOT NULL | autoincrement | — | PK do agregado (legado BigInteger) |
| `external_id` | `UUID` | NOT NULL | `uuid4()` | UNIQUE INDEX | UUID público do lead |
| `status` | `ENUM(lead_status)` | NOT NULL | `'captured'` | INDEX | Status atual no funil |
| `name` | `String(255)` | NULL | — | — | Nome do lead |
| `email` | `String(255)` | NULL | — | INDEX | Email do lead |
| `phone` | `String(32)` | NULL | — | — | Telefone do lead |
| `promoter_external_id` | `UUID` | NULL | — | INDEX | UUID do promotor que indicou |
| `source` | `String(64)` | NULL | — | — | Origem do lead (web, whatsapp, etc) |
| `metadata` | `JSONB` | NULL | `{}` | — | Dados adicionais flexíveis |
| `created_at` | `DateTime(tz)` | NOT NULL | `now()` | — | Timestamp de criação |
| `updated_at` | `DateTime(tz)` | NOT NULL | `now()` ON UPDATE | — | Timestamp de atualização |

#### `checkouts` — Registros de checkout/pagamento

| Coluna | Tipo | Nullable | Default | FK / Índice | Descrição |
|--------|------|----------|---------|-------------|-----------|
| `id` | `BigInteger` PK | NOT NULL | autoincrement | — | PK do checkout |
| `external_id` | `UUID` | NOT NULL | `uuid4()` | UNIQUE INDEX | UUID público do checkout |
| `lead_id` | `BigInteger` | NOT NULL | — | FK → `leads.id`, INDEX | Lead associado |
| `gateway` | `String(32)` | NOT NULL | — | — | Gateway utilizado (`infinitepay` / `asaas`) |
| `status` | `ENUM(checkout_status)` | NOT NULL | `'pending'` | INDEX | Status do checkout |
| `amount` | `Numeric(10,2)` | NOT NULL | — | — | Valor cobrado (centavos ou reais) |
| `gateway_payment_id` | `String(255)` | NULL | — | INDEX | ID do pagamento no gateway externo |
| `payment_method` | `String(32)` | NULL | — | — | Método (`card` / `pix`) |
| `paid_at` | `DateTime(tz)` | NULL | — | — | Timestamp de confirmação do pagamento |
| `payload` | `JSONB` | NULL | `{}` | — | Payload completo do webhook de retorno |
| `created_at` | `DateTime(tz)` | NOT NULL | `now()` | — | Timestamp de criação |
| `updated_at` | `DateTime(tz)` | NOT NULL | `now()` ON UPDATE | — | Timestamp de atualização |

#### `lead_events` — Log auditivo de eventos

| Coluna | Tipo | Nullable | Default | Descrição |
|--------|------|----------|---------|-----------|
| `id` | `BigInteger` PK | NOT NULL | autoincrement | PK do evento |
| `lead_id` | `BigInteger` | NOT NULL | — | FK → `leads.id` |
| `event` | `String(64)` | NOT NULL | — | Nome do evento |
| `payload` | `JSONB` | NOT NULL | `{}` | Payload completo |
| `received_at` | `DateTime(tz)` | NOT NULL | `now()` | Timestamp de recebimento |

## 5. Endpoints

### 5.1. Webhook — Confirmar pagamento InfiniteCartão (público)

| Campo | Valor |
|-------|-------|
| **Método** | `POST` |
| **Rota** | `/api/v1/webhook/infinitepay` |
| **Tipo** | **Público** (webhook externo) |
| **Auth** | Verificação de origem / assinatura do gateway |
| **Request body** | Payload do gateway com `payment_id`, `status`, dados do cartão |
| **Response** | `200 OK` |
| **Side-effects** | Atualiza checkout para `paid`, avança lead para `completed`, dispara evento `lead.completed` |

### 5.2. Webhook — Confirmar pagamento PIX Asaas (público)

| Campo | Valor |
|-------|-------|
| **Método** | `POST` |
| **Rota** | `/api/v1/webhook/asaas` |
| **Tipo** | **Público** (webhook externo) |
| **Auth** | Verificação de origem / assinatura Asaas |
| **Request body** | Payload do Asaas com `payment_id`, `status` |
| **Response** | `200 OK` |
| **Side-effects** | Atualiza checkout para `paid`, avança lead para `completed`, dispara evento `lead.completed` |
| **Débito conhecido** | Webhook não traz `amount`; recibo usa `PIX_DEFAULT_AMOUNT` como fallback |

### 5.3. Webhook — Notificação de entrega (público)

| Campo | Valor |
|-------|-------|
| **Método** | `POST` |
| **Rota** | `/api/v1/webhook/notify` |
| **Tipo** | **Público** (webhook interno) |
| **Auth** | Verificação de origem |
| **Side-effects** | Registra confirmação de entrega da notificação |

### 5.4. Endpoints internos de consulta (desmilitarizados)

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/api/v1/leads/{external_id}` | Obter lead por UUID |
| `GET` | `/api/v1/leads` | Listar leads com filtros e paginação |
| `GET` | `/api/v1/checkouts/{external_id}` | Obter checkout por UUID |
| `GET` | `/api/v1/checkouts` | Listar checkouts com filtros |

## 6. Integrações Externas

| Serviço | Tipo de integração | Propósito | Status |
|---------|-------------------|-----------|--------|
| **InfinitePay** (gateway) | HTTP webhook (inbound) | Receber confirmação de pagamento por cartão | ✅ Implementado |
| **Asaas** (gateway) | HTTP webhook (inbound) | Receber confirmação de pagamento PIX | ✅ Implementado |
| **Notify** (`notify/`) | HTTP (httpx, outbound) | Notificar sobre captura e pagamento | ⚠️ Débito: HTTP direto, sem usar `NotifyClient` |
| **Profiles** (`profiles/`) | HTTP (httpx, outbound) | Consultar dados do perfil | ⚠️ Débito: HTTP direto, sem usar `ProfilesClient` |
| **Enrollment** (`enrollment/`) | Webhook (outbound) | Enviar evento `lead.completed` | ✅ Implementado |
| **Promoters** (`promoters/`) | Webhook (outbound) | Enviar evento para cálculo de comissão | ✅ Implementado |

**Padrão de integração:** Chamadas outbound devem usar os **clients padronizados** (`NotifyClient`, `ProfilesClient`) em `integrations/`. Retry com backoff **assíncrono** (`await asyncio.sleep`), nunca `time.sleep()` síncrono. Falhas de integração externa nunca quebram o fluxo principal (degradação graciosa — §12 da CONVENTION).

**Débito conhecido:** `request_with_retry` em `integrations/__init__.py` usa `time.sleep()` síncrono, bloqueando o event loop durante retentativas. Deve ser migrado para `await asyncio.sleep()`.

## 7. Eventos Disparados / Consumidos

### Consumidos (webhooks inbound)

| Evento | Origem | Reação |
|--------|--------|--------|
| Pagamento InfinitePay confirmado | Gateway InfinitePay (webhook POST) | Atualiza checkout → `paid`, lead → `completed` |
| Pagamento Asaas PIX confirmado | Gateway Asaas (webhook POST) | Atualiza checkout → `paid`, lead → `completed` |
| Notificação entregue | Serviço `notify` (webhook POST) | Registra confirmação de entrega |

### Disparados (webhooks outbound)

| Evento | Gatilho | Destino |
|--------|---------|---------|
| `lead.completed` | Transição lead → `completed` (pagamento confirmado) | `enrollment` (criar matrícula), `promoters` (calcular comissão), `notify` (notificar) |
| `lead.captured` | Novo lead registrado | `notify` (notificar captura) |

**Débito conhecido:** O handler `notify_lead_captured` dispara o evento via chamadas HTTP diretas (`httpx.AsyncClient`) em vez de usar os clients padronizados. Deve ser refatorado para usar `NotifyClient`/`ProfilesClient`.

## 8. Regras de Negócio Invariantes

1. **Funil é unidirecional** — `captured → waiting → checkout → completed`. Não há retrocesso. Tentativa de reverter status é rejeitada.

2. **1 checkout ativo por lead** — Um lead em status `checkout` não pode criar novo checkout sem que o anterior seja resolvido (pago, falhou ou expirou).

3. **Pagamento só via webhook de gateway** — A transição `checkout → completed` só pode ser disparada por webhook autenticado do gateway de pagamento (InfinitePay ou Asaas). Nunca por ação direta do lead ou endpoint interno.

4. **Checkout expira** — Checkouts pendentes têm TTL configurável. Após expirar, o status vai para `expired` e o lead pode gerar novo checkout.

5. **Valor do recibo = valor do checkout** — O recibo de pagamento PIX deve exibir o valor real persistido em `checkouts.amount`, nunca um fallback fixo (`PIX_DEFAULT_AMOUNT`).

6. **Retry assíncrono** — Chamadas de integração outbound usam backoff exponencial com `await asyncio.sleep()`. Nunca `time.sleep()` em contextos async.

7. **Clients padronizados** — Toda chamada HTTP outbound usa os clients em `integrations/` (`NotifyClient`, `ProfilesClient`). Chamadas HTTP diretas (`httpx.AsyncClient` solto) são proibidas.

8. **Degradação graciosa** — Falha em integração outbound (notify, profiles) não quebra o fluxo do funil. O lead progride normalmente; a notificação é best-effort.

9. **Idempotência de webhooks** — Webhooks de gateway são idempotentes por `gateway_payment_id`. Reenvio do mesmo evento não duplica registros nem re-dispara downstream.

10. **Evento downstream após pagamento** — Ao atingir `completed`, o `lead.completed` é disparado exatamente uma vez para cada consumidor (enrollment, promoters, notify). Falha de delivery é logged mas não impede o lead de estar `completed`.

## 9. Critérios de Aceite

1. [ ] Suíte `pytest` cobre o funil completo: `captured → waiting → checkout → completed` com transições de estado verdes.
2. [ ] Teste do webhook InfinitePay: pagamento confirmado → checkout `paid` → lead `completed` → evento `lead.completed` disparado.
3. [ ] Teste do webhook Asaas: pagamento PIX confirmado → checkout `paid` → lead `completed` → evento `lead.completed` disparado.
4. [ ] Teste do webhook notify: confirmação de entrega registrada.
5. [ ] Teste de idempotência: reenvio de webhook de gateway não duplica registros.
6. [ ] `request_with_retry` usa `await asyncio.sleep()` — zero `time.sleep()` em paths async (verificável via grep + inspeção).
7. [ ] `notify_lead_captured` usa `NotifyClient`/`ProfilesClient` — zero chamadas `httpx.AsyncClient` diretas fora de clients.
8. [ ] Recibo PIX reflete `checkouts.amount` real — teste com valor dinâmico, sem `PIX_DEFAULT_AMOUNT` no output.
9. [ ] Degradação graciosa: falha de notify não impede transição de estado do lead (teste com mock que retorna erro).
10. [ ] `ruff check` + `ruff format --check` limpo nos arquivos tocados.
11. [ ] `wiki/lead.md` atualizado refletindo estado apto a produção (débitos quitados, cobertura existente).

## 10. Riscos / Open Questions

### Riscos

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| `tests/` é greenfield (nenhuma base existente) | Alta | Médio | Espelhar `conftest` async de `asaas`/`infinitepay` (padrão validado: `sqlite+aiosqlite`, `httpx.AsyncClient`/ASGITransport, mocks de integração) |
| Trocar `time.sleep()` por async altera timing dos retries | Média | Médio | Cobrir retry com teste **antes** de trocar backoff; preservar política de tentativas |
| Recibo PIX exigir valor de consulta externa ao Asaas | Média | Médio | Preferir valor já persistido em `lead.checkouts`; só integrar se indisponível (open question) |
| Refactor do `notify_lead_captured` quebrar fluxo de captura | Média | Alto | Teste do `lead_captured` antes/depois; degradação graciosa (§12) — falha de notify nunca quebra registro |
| Edição concorrente do worktree (candidate/notify em refactor) | Baixa | Médio | `lead` está limpo e commitado; escopo fechado — não tocar outros apps neste ciclo |
| Testes rodando contra SQLite vs tipos Postgres (ENUM, JSONB) | Média | Médio | Validar se `sqlite+aiosqlite` é suficiente ou se CI exige Postgres real (open question) |

### Open Questions

- [ ] **Valor real do PIX**: o `amount` vem do checkout já persistido localmente (`lead.checkouts`) ou exige consultar o serviço Asaas? Define se há nova integração ou só leitura local. **TBD — needs validation.**
- [ ] **Testes**: rodar contra `sqlite+aiosqlite` async é suficiente, ou os tipos Postgres (ENUM `lead_status`, JSONB) exigem Postgres real no CI? **TBD — needs validation.**
- [ ] **PK→UUID (§4)**: aceitar `BigInteger` PK permanentemente para `lead`, ou agendar migração futura num ciclo de conformidade? Registrado como open question, não como trabalho deste ciclo. **TBD — needs validation com o engenheiro.**
- [ ] **Housekeeping de conformidade**: criar `CLAUDE.md` (justificando `pyjwt[crypto]` e `fastapi-structured-logging` fora da §2) e remover/implementar o `ROLES_BASE_URL` morto — sessão dedicada posterior.
- [ ] **Schemas inline**: mover schemas inline de `api/` para `schemas/` — desvio menor já documentado em `wiki/lead.md`; não bloqueia produção.

### Fora de Escopo

- **PK→UUID (§4)** — aceito o padrão atual (`BigInteger` PK + `external_id` UUID)
- **Cobertura exaustiva** — CRUD desmilitarizado de leads/checkouts e edge/erros amplos ficam além do caminho do dinheiro neste ciclo
- **Novos recursos / mudança de API pública**
- **Housekeeping de conformidade** — sessão dedicada posterior

---

*Status: DRAFT — requirements only. Implementation planning pending via /plan.*
