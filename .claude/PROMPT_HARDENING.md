# Prompt — Continuar o hardening do caminho de dinheiro (sessão nova)

> Cole como primeira mensagem numa sessão nova. Pode abrir dentro de `lead/`
> (o foco começa lá), mas vários alvos tocam outros serviços — confirme escopo
> comigo antes de editar fora do `lead`.

---

Continue o "ataque" aos bugs e fragilidades do backend, com foco em **segurança e
robustez do caminho de dinheiro**. Sou solo founder e **não sou programador** —
explique o "porquê" de cada coisa em pt-br e **confirme comigo antes de mexer em
fluxo de pagamento/checkout** (regra de ouro do `CLAUDE.md`).

## Estado atual (verifique contra git/working-tree antes de agir)
- Branch: **`fix/lead-review-2026-05-28`**, commit **`dc623d0`** (revisão e2e do lead).
- Suíte do `lead`: **191 passed** (`cd lead && uv run pytest -q`).
- Ambiente dev de pé: ~31 containers (`docker ps`). Lead em `localhost:8014`.
- ⚠️ **DEV usa Asaas/InfinitePay/CPFHub de PRODUÇÃO REAL** (memória
  `project-dev-usa-pagamento-prod-real`). Testar checkout cria cobrança/valida CPF
  REAL. Pare no QR/link, não pague, a menos que eu peça.
- Lead de teste já existente: `615b03d8-bec5-431e-aad1-a4c8e5d9f622` (CPF do founder).

## O padrão de bug que se repete (a tese do ataque)
Vários pontos do caminho de dinheiro são **fire-and-forget + fail-silent**: disparam
um BG task / webhook, capturam exceção, só logam, e seguem. Quando o serviço-alvo
está fora, **o evento se perde sem retry nem fila** → dinheiro confirmado mas estado
inconsistente, em silêncio. Já corrigimos 2 sintomas; faltam outros.

## Alvos priorizados (do mais crítico ao menos)
1. **Handoff `lead.completed` fail-silent** (`lead/app/tools/webhooks.py:19-66`):
   quando o lead vira COMPLETED, `notify_enrollment` e `notify_promoter_completed`
   são `background_tasks` que só logam erro. Se `enrollment` estiver fora, **o cliente
   paga, o lead fica COMPLETED, mas a matrícula NUNCA é criada**. Proponha outbox/fila
   ou retry idempotente (o `infinitepay` já tem `outbound_queue` como referência).
2. **Aplicar em PROD o fix do `NOTIFY_CALLBACK_URL`** (memória
   `project-notify-callback-url-mismatch`): em dev corrigi pra
   `http://lead:8000/api/v1/webhook/notify`; o compose de prod (`/opt/v7m/`)
   provavelmente ainda aponta pra `/api/v1/contact/_callback` (404 → status pending eterno).
3. **Validar o callback ao vivo em dev**: gerar um checkout e confirmar que
   `lead.messages.status` sai de `pending` pra `sent` (o fix foi aplicado mas não
   validado ao vivo).
4. **Asaas webhook PENDING race** (memória `project-asaas-webhook-before-checkout-race`):
   sem fila no asaas, o PENDING pode chegar antes do checkout commitar e se perder.
   Avaliar simetria com o `outbound_queue` do infinitepay.
5. **Migration 0004 (`qrcode_url_to_asaas`)** não rodou no dev: QRs PIX antigos têm
   URL relativa legada. Rodar com `ASAAS_PUBLIC_BASE_URL` setada (ver o próprio arquivo
   da migration em `lead/alembic/versions/`).

## Como trabalhar
- Leia `lead/.claude/CLAUDE.md`, `CONVENTION.md` e as memórias relevantes antes.
- Caminho de dinheiro: **proponha o fix + testes de regressão e espere meu OK** antes de aplicar.
- Cada fix com teste. Mantenha a suíte verde.
- Atenção ao custo da sessão: agrupe tool calls, evite re-rodar e2e caro sem necessidade.
