# Prompt — Próxima sessão: blindar fluxo de pagamento pra prod

## Contexto (não repete, já está validado)

Em 2026-05-28, o fluxo asaas→lead foi validado ponta-a-ponta em prod (LXC `backend-supletivo` @ 10.1.30.20, `/opt/v7m/`). Lead `77bb18ca-6505-493d-af7c-e4f59fd26058` virou `completed` após pagamento PIX de R$ 5,00 (`pay_f32b318133054b27`).

Causa raiz do "paguei e nada" anterior: API key Asaas 401. Resolvido: nova key na `asaas.config` (DB vence sobre .env, ver `project_asaas_config_hybrid_bootstrap`).

Análise completa do fluxo: ver memórias `project_asaas_key_silent_401`, `project_asaas_config_hybrid_bootstrap`, `project_env_dollar_escape`.

## Missão desta sessão

Deixar o caminho do dinheiro **prod-ready** — sem caminho silencioso que perca um pagamento. Hoje, se algo falhar no meio, cliente paga e o lead nunca completa, sem alerta.

## Lista do que está pendente (ordem de prioridade)

### 🔴 P0 — bloqueador de prod

**1. Asaas → lead sem retry (assimetria com infinitepay).**
- `asaas/app/services/notifications.py::notify_internal` faz POST direto, timeout 5s, falha = só log. Sem fila, sem retry.
- Race-condition confirmada hoje: webhook PENDING chegou antes do lead commitar o checkout → "asaas_webhook_no_checkout" → notify perdido. Só sobreviveu porque PAID veio depois e o checkout já existia.
- **Fix:** replicar pattern do `infinitepay/app/workers/outbound_queue.py` no asaas. Tabela `asaas.outbound_jobs` + worker + backoff `[60, 300, 1800, 7200, 43200, 86400]` + claim atômico.
- Escopo: novo model + migration Alembic + worker no lifespan + alterar `notify_internal` pra `enqueue` em vez de POST direto.

**2. Asaas key 401 silencioso (vai acontecer de novo).**
- Hoje o sintoma só aparece quando lead tenta criar charge — webhook entrega 200 OK e ninguém grita.
- **Fix:** adicionar check `GET /v3/customers?limit=1` no `/health` do asaas-app. Se 401 → `unhealthy`. Adicionar alerta no Grafana.

**3. IP allowlist Asaas desativada (`ASAAS_WEBHOOK_ALLOWED_CIDRS=` vazio em prod).**
- Em prod, sobra só o HMAC como defesa.
- **Fix:** setar no `.env` em prod:
  ```
  ASAAS_WEBHOOK_ALLOWED_CIDRS=52.67.135.115/32,18.231.44.29/32,18.229.238.53/32,54.233.218.242/32
  ```
  e `up -d --force-recreate asaas` (`restart` não relê env_file — armadilha).

### 🟡 P1 — qualidade pra escalar

**4. BackgroundTasks frágeis no lead.**
- `notify_lead_completed`, `notify_enrollment`, `notify_promoter_completed` rodam em FastAPI `BackgroundTasks` após o commit. Se o container morre entre commit e BG, lead fica COMPLETED mas cliente nunca recebe recibo e promoter perde a comissão.
- **Fix:** enfileirar (mesma queue) em vez de BG inline.

**5. InfinitePay end-to-end ainda não testado nesta sessão.**
- O outbound_queue já tem retry. Só validar:
  - `POST /captured payment_method=credit_card` → lead WAITING (BG cria checkout) → CHECKOUT
  - Pagamento cartão → webhook → COMPLETED
  - Conferir que `transaction_nsu`/`receipt_url` persistem (proteção anti-fora-de-ordem do código atual em `lead/api/demilitarized/webhooks.py:108`).

### 🟢 P2 — operacional / config

**6. Domínio v7m.org vs m33.live.**
- `.env` em prod tem TUDO em `api.v7m.org` (prod-real). Mas Victor disse que ambiente de teste deveria ser `m33.live`. Vars envolvidas: `LEAD_PUBLIC_BASE_URL`, `ASAAS_EXTERNAL_URL`, `INFINITEPAY_PUBLIC_API_URL`, `INFINITEPAY_REDIRECT_URL`.
- **Decisão pendente:** este deploy é prod-real ou ambiente de teste? Se for teste, trocar tudo pra `m33.live` e reconfigurar webhooks no painel Asaas/InfinitePay.

**7. Runbook: docker compose restart NÃO relê env_file.**
- `docker compose restart <svc>` mantém vars antigas. Pra mudança de `.env` pegar, precisa `docker compose up -d --force-recreate <svc>` (ou `down && up`).
- **Fix:** documentar em `backend/RUNBOOK.md`.

**8. Limpar cobranças órfãs no Asaas remoto.**
- `pay_29a87ce332c841b2` e `pay_afdc46a32ca948aa` foram apagadas do DB local nas iterações de teste hoje, mas ainda existem no painel Asaas (PENDING). Cancelar via UI ou via DELETE /v3/payments/{id}.

## Como começar a sessão

1. SSH `root@10.1.30.20`, `cd /opt/v7m`, ver `docker compose ps` (esperado: tudo healthy).
2. Confirmar lead `77bb18ca` ainda completed e key ainda válida:
   ```sql
   SELECT status FROM lead.leads WHERE external_id='77bb18ca-6505-493d-af7c-e4f59fd26058';
   SELECT LENGTH(value) FROM asaas.config WHERE key='asaas_api_key';  -- esperado 166
   ```
3. Iniciar pelo P0 #1 (outbound queue do asaas) — é o que tem maior chance de perder dinheiro em prod.

## Restrições

- **NÃO mexer no caminho do dinheiro sem testes de regressão.** (CLAUDE.md do lead, §5)
- **NÃO usar `restart`, sempre `up -d --force-recreate`** quando mudar env_file.
- **DB vence sobre .env** no asaas (`config_store`) — alterações operacionais via SQL UPDATE ou via API `/api/v1/config/*`, não no .env.
- Quando precisar enviar SQL com `$` literal via SSH: usar heredoc `<<'EOF'` (aspas simples) e pipe pro `ssh ... 'docker compose exec -T postgres psql ...'`. Heredoc bash interpolação cuidado.

## Output esperado ao final desta sessão

- `asaas.outbound_jobs` table criada + worker rodando + `notify_internal` virou `enqueue`
- `/health` do asaas detecta key 401
- IP allowlist em prod ativa
- InfinitePay end-to-end testado e funcional
- Decisão sobre domínio v7m vs m33 registrada (memória)
- Runbook atualizado
