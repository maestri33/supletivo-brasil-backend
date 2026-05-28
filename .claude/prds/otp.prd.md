# OTP — Módulo de Código de Verificação Descartável

> Serviço: `otp/` · Schema: `otp` · Convenção: `CONVENTION.md`
> Status desta SPEC: pronto para review.

---

## 1. Contexto de Negócio

O módulo `otp` é o **serviço de autenticação por código descartável** da plataforma —
responsável por gerar, enviar, validar e auditar códigos OTP (One-Time Password)
numéricos de uso único. O código é enviado ao usuário via WhatsApp pelo serviço
**notify**, e todo o ciclo de vida é registrado no banco para auditoria.

**Estado atual:** O módulo está **funcional e operacional**. Implementa:
- **Geração** de código numérico seguro (`secrets.randbelow`) com SHA256 hash
- **Envio** via serviço notify (WhatsApp) com template Markdown
- **Validação** com TTL configurável, tentativas limitadas, timing-safe comparison
- **Rate limit** dedicado por `external_id` (janela curta + janela horária)
- **Retry de envio** com backoff exponencial via fila `pending_notify`
- **Cleanup automático** de logs antigos como task de fundo
- **Métricas** Prometheus (`/metrics`) e endpoint `/status` com dashboard completo
- **Webhook** de callback do notify para status de entrega WhatsApp

**Pendências conhecidas:**
1. **PK Integer vs UUID** — `otp_logs` usa `Integer` autoincrement em vez de UUID (CONVENTION §4)
2. **Webhook sem autenticação** — `POST /webhook/notify/{message_id}` é público sem verificação de assinatura (CONVENTION §5)
3. **Endpoint duplicado** — `GET /api/v1/otp` e `GET /api/v1/otp/logs` são idênticos
4. **Testes em skip** — suíte legada não passa após migração SQLite → Postgres (conftest desatualizado)
5. **CORS aberto** — `allow_origins=["*"]` em dev/staging; prod exige `CORS_ORIGINS` (COD-18 P0.2)

## 2. Atores

| Ator | Role | Ação |
|------|------|------|
| **Auth service** | Serviço upstream (desmilitarizado) | Chama `POST /api/v1/otp` para gerar OTP no registro/check/recover/login |
| **Auth service** | Serviço upstream (desmilitarizado) | Chama `POST /api/v1/otp/check` para validar código informado pelo usuário |
| **Notify service** | Serviço upstream (callback) | Chama `POST /webhook/notify/{message_id}` com status de entrega WhatsApp |
| **Admin / debug** | Interno (desmilitarizado) | Consulta `GET /api/v1/otp` para listagem de logs |
| **Prometheus** | Monitoramento (desmilitarizado) | Scraping de `GET /metrics` |
| **Healthcheck** | Infraestrutura (desmilitarizado) | `GET /health`, `GET /ready`, `GET /status` |

**Fluxo típico:** O `auth` é o único consumidor real. Ele chama `POST /api/v1/otp` com
o `external_id` do usuário → o otp gera o código, envia via notify e retorna o log.
O usuário digita o código recebido no WhatsApp → o `auth` chama `POST /api/v1/otp/check`.

## 3. Estados / Máquina de Estados

### OTPLog — Ciclo de Vida do Código

```
                  ┌─────────┐
                  │generated│  (código criado, hash persistido)
                  └────┬────┘
                       │ notify.send_message() sucesso
                       ▼
                  ┌─────────┐
                  │  sent   │  (mensagem entregue ao notify)
                  └────┬────┘
                       │
            ┌──────────┼──────────┐
            ▼          ▼          ▼
       ┌─────────┐ ┌─────────┐ ┌──────────┐
       │verified │ │ expired │ │  failed  │
       └─────────┘ └─────────┘ └──────────┘
         código     TTL esgotado   max_attempts atingido
         correto    (300s def.)    ou notify falhou
```

**Estados terminais:** `verified`, `expired`, `failed` — não sofrem transição adicional.

**Transições:**
| De | Para | Condição |
|----|------|----------|
| `generated` | `sent` | `notify.send_message()` retorna sucesso |
| `generated` | `failed` | Erro permanente no notify (`NotifyPermanentError`) |
| `generated` | `generated` | Erro transiente → enfileira em `pending_notify` (status do log não muda) |
| `sent` | `verified` | `verify_code()` com código correto dentro do TTL |
| `sent` | `expired` | TTL esgotado (300s default) |
| `sent` | `failed` | `attempts >= otp_max_attempts` (3 default) |
| `sent` | `failed` | Webhook reporta `failed`/`rejected` do WhatsApp |

### PendingNotify — Fila de Retry

```
           ┌─────────┐
           │ pending │  (aguardando retry)
           └────┬────┘
                │
       ┌────────┼────────┐
       ▼                 ▼
  ┌─────────┐      ┌─────────┐
  │  done   │      │ expired │
  └─────────┘      └─────────┘
   envio OK         5 tentativas
                    ou TTL esgotado
```

**Backoff:** `[5, 10, 20, 40]` segundos. Máximo 5 tentativas. Se OTP expirou antes
do reenvio, a entrada é marcada como `expired` e o `otp_log` correspondente vai
para `failed` com `failure_reason="notify_down"`.

## 4. Entidades & Campos

### Schema `otp`

#### `otp_logs` — Registro de cada operação OTP

| Coluna | Tipo | Nullable | Default | FK / Índice | Descrição |
|--------|------|----------|---------|-------------|-----------|
| `id` | `Integer` PK | NOT NULL | autoincrement | — | PK interno ⚠️ **deveria ser UUID (CONVENTION §4)** |
| `external_id` | `UUID` | NOT NULL | — | FK → `auth.users.external_id` (RESTRICT), INDEX | UUID do usuário dono do OTP |
| `code_hash` | `String(64)` | NOT NULL | — | — | SHA256 do código (plain text nunca persistido) |
| `status` | `String(20)` | NOT NULL | `"generated"` | — | `generated` \| `sent` \| `verified` \| `expired` \| `failed` |
| `attempts` | `Integer` | NOT NULL | `0` | — | Tentativas inválidas de verificação |
| `failure_reason` | `String(20)` | NULL | — | — | `notify_down` \| `notify_permanent` \| `invalid_code` \| `expired` \| `inactive` |
| `message_id` | `Integer` | NULL | — | — | ID da mensagem no notify (para webhook callback) |
| `error_detail` | `Text` | NULL | — | — | Detalhe legível do erro |
| `verified_at` | `DateTime(tz)` | NULL | — | — | Timestamp de verificação bem-sucedida |
| `created_at` | `DateTime(tz)` | NOT NULL | `now()` | — | Timestamp de criação |

#### `pending_notify` — Fila de retry de envio

| Coluna | Tipo | Nullable | Default | FK / Índice | Descrição |
|--------|------|----------|---------|-------------|-----------|
| `id` | `Integer` PK | NOT NULL | autoincrement | — | PK interno |
| `external_id` | `UUID` | NOT NULL | — | FK → `auth.users.external_id` (RESTRICT), INDEX | UUID do usuário |
| `content` | `Text` | NOT NULL | — | — | Conteúdo da mensagem (template renderizado) |
| `otp_log_id` | `Integer` | NOT NULL | — | FK → `otp.otp_logs.id` (CASCADE), INDEX | Referência ao log original |
| `attempts` | `Integer` | NOT NULL | `1` | — | Número de tentativas de reenvio |
| `next_retry_at` | `DateTime(tz)` | NOT NULL | — | — | Próximo agendamento de retry |
| `status` | `String(20)` | NOT NULL | `"pending"` | — | `pending` \| `done` \| `expired` |
| `error_detail` | `Text` | NULL | — | — | Último erro encontrado |
| `created_at` | `DateTime(tz)` | NOT NULL | `now()` | — | Criação |
| `updated_at` | `DateTime(tz)` | NOT NULL | `now()` | — | Última atualização (auto via `onupdate`) |

#### `rate_limit` — Controle de frequência por `external_id`

| Coluna | Tipo | Nullable | Default | FK / Índice | Descrição |
|--------|------|----------|---------|-------------|-----------|
| `external_id` | `UUID` PK | NOT NULL | — | FK → `auth.users.external_id` (CASCADE) | Usuário controlado |
| `last_created_at` | `DateTime(tz)` | NOT NULL | — | — | Timestamp do último OTP gerado (janela curta) |
| `hourly_count` | `Integer` | NOT NULL | `0` | — | Contagem na janela horária atual |
| `hourly_window_start` | `DateTime(tz)` | NOT NULL | — | — | Início da janela horária corrente |
| `updated_at` | `DateTime(tz)` | NOT NULL | `now()` | — | Última atualização |

### Migrações existentes (2)

1. `0001` — Criação das tabelas `otp_logs` e `pending_notify` no schema `otp`
2. `0002` — Adição da tabela `rate_limit`

## 5. Endpoints

### 5.1. Gerar e Enviar OTP (desmilitarizado)

| Campo | Valor |
|-------|-------|
| **Método** | `POST` |
| **Rota** | `/api/v1/otp` |
| **Tipo** | **Desmilitarizado** (auth → otp) |
| **Auth** | Nenhuma |
| **Request body** | `{"external_id": "UUID"}` |
| **Response** | `201` — `OTPRead` (id, external_id, status, attempts, failure_reason, message_id, error_detail, verified_at, created_at) |
| **Erros** | `429` rate limit excedido (com `Retry-After` header); `502` notify indisponível (erro permanente) |
| **Side-effects** | Cria `otp_log` (status=generated → sent); envia mensagem via notify; pode enfileirar `pending_notify` em erro transiente |
| **Idempotência** | Não — cada chamada gera novo código |

**Regras de negócio:**
- Rate limit **antes** de qualquer trabalho: janela curta (30s default) + janela horária (5/h default)
- Se `otp_active=False`, registra log com `status=failed, failure_reason=inactive` sem enviar
- Código gerado com `secrets.randbelow` (CSPRNG), nunca persistido em plain text
- Template de mensagem: `otp/app/services/otp.md` com `{{codigo}}`, `{{ttl_minutos}}`, `{{rodape}}`
- Erro transiente no notify → enfileira em `pending_notify` para retry com backoff
- Erro permanente no notify → marca `otp_log` como `failed` sem retry

### 5.2. Validar OTP (desmilitarizado)

| Campo | Valor |
|-------|-------|
| **Método** | `POST` |
| **Rota** | `/api/v1/otp/check` |
| **Tipo** | **Desmilitarizado** (auth → otp) |
| **Auth** | Nenhuma |
| **Request body** | `{"external_id": "UUID", "code": "string (1-10 chars)"}` |
| **Response** | `200` — `{"valid": bool, "detail": string}` |
| **Erros** | Nenhum HTTP — sempre retorna 200 com `valid=false` em caso de falha |
| **Side-effects** | Incrementa `attempts`; pode invalidar OTP (`status=failed`) |

**Regras de negócio:**
- Busca OTP mais recente com `status IN (generated, sent)` para o `external_id`
- Se nenhum OTP pendente → `{"valid": false, "detail": "Nenhum OTP pendente encontrado"}`
- Se TTL esgotado (300s default) → marca `expired`, retorna `{"valid": false, "detail": "OTP expirado"}`
- Se código incorreto → incrementa `attempts`; se `attempts >= max_attempts` (3 default) → marca `failed`
- Comparação com `secrets.compare_digest` (timing-safe) contra SHA256 do código
- Se `otp_active=False` → `{"valid": false, "detail": "Serviço OTP desativado"}`

### 5.3. Listar OTPs (desmilitarizado)

| Campo | Valor |
|-------|-------|
| **Método** | `GET` |
| **Rota** | `/api/v1/otp` (também duplicado em `/api/v1/otp/logs`) |
| **Tipo** | **Desmilitarizado** |
| **Query params** | `external_id` (UUID, opcional), `status` (string, opcional), `limit` (1-200, default 50), `offset` (int, default 0) |
| **Response** | `200` — `list[OTPRead]` ordenado por `created_at DESC` |

**Nota:** `GET /api/v1/otp` e `GET /api/v1/otp/logs` são endpoints **idênticos** (código duplicado).
O `/logs` deveria ser removido ou consolidado.

### 5.4. Webhook de Callback do Notify (público)

| Campo | Valor |
|-------|-------|
| **Método** | `POST` |
| **Rota** | `/webhook/notify/{message_id}` |
| **Tipo** | **Público** (callback externo do notify) |
| **Auth** | ⚠️ **Nenhuma** — sem verificação de assinatura |
| **Request body** | `{"whatsapp_status": "sent" \| "failed" \| "rejected", ...}` |
| **Response** | `200` — `{"ok": true}` ou `{"ok": false, "detail": "mensagem desconhecida"}` |
| **Side-effects** | Atualiza `otp_log.status` conforme status do WhatsApp |

**Regras:**
- `whatsapp_status == "sent"` → `otp_log.status = "sent"`
- `whatsapp_status IN ("failed", "rejected")` → `otp_log.status = "failed"`, `failure_reason = "notify_permanent"`
- Se `message_id` não encontrado → log warning, retorna `{"ok": false}`

### 5.5. Health / Ready (desmilitarizado)

| Campo | Valor |
|-------|-------|
| **Método** | `GET` |
| **Rotas** | `/health`, `/ready` |
| **Tipo** | **Desmilitarizado** |
| **Response** | `/health`: `{"status": "ok"}` · `/ready`: testa `SELECT 1` no banco |

### 5.6. Status (desmilitarizado)

| Campo | Valor |
|-------|-------|
| **Método** | `GET` |
| **Rota** | `/status` |
| **Tipo** | **Desmilitarizado** |
| **Response** | Dashboard completo: uptime, config, conexões (db + notify), OTP stats por status, avg verificação (ms), failure breakdown, top failed external_ids, rate limit ativo, últimos 10 logs |

### 5.7. Métricas (desmilitarizado)

| Campo | Valor |
|-------|-------|
| **Método** | `GET` |
| **Rota** | `/metrics` |
| **Tipo** | **Desmilitarizado** (Prometheus format) |
| **Métricas** | `otp_http_requests_total` (counter), `otp_http_request_duration_seconds` (histogram) |

## 6. Integrações Externas

| Serviço | Tipo de integração | Propósito | Client em |
|---------|-------------------|-----------|-----------|
| `notify` | HTTP (httpx, desmilitarizado) | Enviar mensagem WhatsApp com código OTP | `integrations/notify_client.py` |
| `notify` (callback) | Webhook público (inbound) | Receber status de entrega WhatsApp | `api/webhook.py` |

**Padrão de integração:**
- Client usa `request_with_retry` do `integrations/http_client.py` (backoff exponencial)
- Erros 5xx → `NotifyTransientError` (retriável, enfileira em `pending_notify`)
- Erros 4xx → `NotifyPermanentError` (não retriável, marca `otp_log` como failed)
- URL do notify configurável via `NOTIFY_BASE_URL` (default `http://notify:8000`)
- Webhook URL registrada no notify: `{webhook_base_url}/webhook/notify`

### Background Tasks (lifespan)

| Task | Função | Intervalo | Propósito |
|------|--------|-----------|-----------|
| `queue_loop` | `services/queue.py` | 5 segundos | Processa `pending_notify` para retry de envio |
| `cleanup_loop` | `services/cleanup.py` | 3600s (1h) default | Purga logs antigos (configurável via `OTP_CLEANUP_RETENTION_DAYS`) |

**Queue loop** usa `fcntl.flock` em `/tmp/otp_queue.lock` para evitar processamento
duplicado em caso de múltiplas instâncias.

## 7. Eventos Disparados / Consumidos

### Consumidos

| Evento | Fonte | Formato |
|--------|-------|---------|
| Webhook notify callback | Serviço `notify` | `POST /webhook/notify/{message_id}` com `whatsapp_status` |

### Disparados

| Evento | Gatilho | Destino |
|--------|---------|---------|
| Mensagem WhatsApp | `POST /api/v1/otp` | Serviço `notify` → WhatsApp do usuário |
| Retry de mensagem | `queue_loop` (pending_notify) | Serviço `notify` → WhatsApp do usuário |

**Nota:** Não há event bus formal. A comunicação é HTTP síncrono (otp → notify)
e webhook assíncrono (notify → otp). O `auth` chama o `otp` de forma síncrona
e aguarda resposta.

## 8. Regras de Negócio Invariantes

1. **Código nunca persistido em plain text** — O código OTP é hasheado com SHA256
   (`_hash_code`) imediatamente após geração. O campo `code_hash` armazena apenas
   o hash. Verificação usa `secrets.compare_digest` (timing-safe).

2. **Rate limit obrigatório antes de gerar** — Toda geração de OTP passa por
   `rate_limit.check_and_record` ANTES de qualquer trabalho. Duas regras:
   - Janela curta: 1 OTP a cada `OTP_RATELIMIT_WINDOW_S` segundos (default 30)
   - Janela horária: no máximo `OTP_RATELIMIT_HOURLY_MAX` OTPs por hora (default 5)
   - UPSERT atômico na mesma transação.

3. **TTL configurável e respeitado** — OTP expira após `OTP_TTL_SECONDS` (default 300s).
   Verificação calcula `age_s = now - created_at` e rejeita se excedido.

4. **Tentativas limitadas** — Máximo `OTP_MAX_ATTEMPTS` (default 3) tentativas inválidas.
   Ao atingir o limite, `otp_log.status = "failed"` com `failure_reason = "invalid_code"`.

5. **Retry com backoff para erros transientes** — Notify com status 5xx ou timeout
   → `NotifyTransientError` → enfileira em `pending_notify`. Backoff: `[5, 10, 20, 40]s`.
   Máximo 5 tentativas. Se OTP expirar antes do reenvio, marca como `expired`.

6. **Erro permanente não é retriado** — Notify com status 4xx → `NotifyPermanentError`
   → `otp_log.status = "failed"` diretamente, sem enfileirar.

7. **OTP desativável via config** — Se `OTP_ACTIVE=False`, gera log com `failure_reason="inactive"`
   e verificação retorna `valid=false` imediatamente. Não envia mensagem.

8. **FK cross-schema via shadow table** — `external_id` referencia `auth.users.external_id`
   via shadow table declarada em `db.py` (não importa model do auth).

9. **Cleanup automático** — Logs em estado terminal (`verified`, `failed`, `expired`)
   com `created_at < now - OTP_CLEANUP_RETENTION_DAYS` (default 30 dias) são purgados.
   `rate_limit` com `last_created_at < now - 1d` também é limpo.

10. **Um OTP pendente por vez** — `verify_code` busca o OTP mais recente com
    `status IN (generated, sent)`. Se não encontrar, retorna `valid=false`.

## 9. Critérios de Aceite

1. [ ] `POST /api/v1/otp` com `external_id` válido gera código, persiste hash, envia via notify e retorna `OTPRead` com `status="sent"`.
2. [ ] `POST /api/v1/otp` respeita rate limit de janela curta (30s) — segunda chamada retorna `429` com `Retry-After`.
3. [ ] `POST /api/v1/otp` respeita rate limit horário (5/h) — sexta chamada retorna `429`.
4. [ ] `POST /api/v1/otp` com `otp_active=False` retorna log com `status="failed"`, `failure_reason="inactive"`.
5. [ ] `POST /api/v1/otp/check` com código correto dentro do TTL retorna `{"valid": true, "detail": "ok"}`.
6. [ ] `POST /api/v1/otp/check` com código incorreto retorna `{"valid": false}` e incrementa `attempts`.
7. [ ] `POST /api/v1/otp/check` com `attempts >= 3` marca OTP como `failed` com `failure_reason="invalid_code"`.
8. [ ] `POST /api/v1/otp/check` com OTP expirado (>300s) retorna `{"valid": false, "detail": "OTP expirado"}`.
9. [ ] `POST /api/v1/otp/check` com código usa `secrets.compare_digest` (timing-safe).
10. [ ] Erro transiente no notify (5xx) enfileira em `pending_notify` para retry.
11. [ ] Erro permanente no notify (4xx) marca `otp_log` como `failed` sem retry.
12. [ ] `queue_loop` processa `pending_notify` com backoff `[5, 10, 20, 40]s` e máximo 5 tentativas.
13. [ ] `POST /webhook/notify/{message_id}` atualiza `otp_log.status` conforme `whatsapp_status`.
14. [ ] `cleanup_loop` purga logs terminais com mais de 30 dias.
15. [ ] `GET /health` e `GET /ready` respondem sem autenticação.
16. [ ] `GET /status` retorna dashboard completo (uptime, config, stats, métricas).
17. [ ] `GET /metrics` retorna métricas Prometheus válidas.
18. [ ] Código OTP nunca é persistido em plain text (apenas SHA256 hash).
19. [ ] `ruff` limpo + testes verdes + `alembic upgrade head` válido.

## 10. Riscos / Open Questions

### Riscos

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| Webhook sem autenticação — spoofing de status | Média | Alto | Implementar HMAC signature verification (CONVENTION §5) |
| PK Integer em vez de UUID — previsível | Baixa | Médio | Migrar para UUID em migração futura (breaking change) |
| Race condition: dois OTPs simultâneos para mesmo `external_id` | Baixa | Baixo | Rate limit (30s) previne; verify busca apenas o mais recente |
| `queue_loop` com `fcntl.flock` não funciona em Docker sem volume compartilhado | Média | Médio | Garantir volume `/tmp` compartilhado ou migrar para advisory lock no Postgres |
| Dependência de `notify` como SPOF | Média | Alto | Retry queue mitiga parcialmente; fallback futuro: SMS direto |
| `code_hash` com SHA256 sem salt — rainbow table risk | Baixa | Baixo | OTP é efêmero (300s) + numérico (10^6 combinações) — risco aceitável |

### Open Questions

- [ ] **Autenticação do webhook** — O `POST /webhook/notify/{message_id}` é público. Deve-se implementar HMAC signature verification conforme CONVENTION §5?
- [ ] **Endpoint duplicado** — `GET /api/v1/otp` e `GET /api/v1/otp/logs` são idênticos. Remover `/logs` ou manter para compatibilidade?
- [ ] **PK UUID** — Migrar `otp_logs.id` de Integer para UUID? Breaking change para `pending_notify.otp_log_id` e auth client.
- [ ] **flock em Docker** — `fcntl.flock` em `/tmp/otp_queue.lock` funciona com Docker? Considerar advisory lock do Postgres (`pg_try_advisory_lock`).
- [ ] **CORS em prod** — Implementar `CORS_ORIGINS` para produção (COD-18 P0.2)?
- [ ] **Testes desabilitados** — Suíte legada em skip. Priorizar migração do conftest para Postgres async?

---

*Status: SPEC consolidado a partir do código-fonte, wiki, CONVENTION.md e análise estática. Aguardando review humano antes de implementação.*
