# Memória — Integrações com outros serviços

## Integrações ativas

### notify
- **Tipo:** HTTP
- **Base URL (env `NOTIFY_BASE_URL`):** o host **sem** `/api/v1` — ex.
  `http://notify.local` ou `http://notify:8000`. O `notify_client._url()`
  **prefixa `/api/v1` no código**, então NÃO inclua `/api/v1` na env var
  (mudança de 2026-05-15; antes a env var carregava o `/api/v1`).
- **Endpoints usados:**
  - `POST /api/v1/messages/send` — envia mensagem formatada. Body inclui
    `external_id`, `title`, `content`, `webhook_url`.
- **Webhook de volta:** notify chama `POST {WEBHOOK_BASE_URL}/webhook/notify/{message_id}`
  com `{"whatsapp_status": ...}`; tratado em `app/api/webhook.py`.
- **Auth:** nenhuma (DMZ).
- **Retry:** `send_message` usa `max_attempts=1` (sem retry no client); falha
  transitória vira `NotifyTransientError` → enfileirada em `pending_notify` e
  reprocessada pelo `queue_loop` (backoff 5/10/20/40s, até 5 tentativas).
- **Pré-requisito:** o contato (`external_id`) deve existir previamente no notify.
- **Última verificação:** 2026-05-22 (E2E local; notify real não exercitado —
  ver "Não testado" em `MIGRACAO.md`).
