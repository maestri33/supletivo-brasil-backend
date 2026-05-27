# CLAUDE.md — Memória e regras deste microserviço

> Fonte da verdade para você (Claude Code) sobre o serviço `fees`. Leia inteiro
> antes de agir. Se algo aqui conflita com o pedido atual, **pergunte** — não
> decida sozinho. A convenção geral é `../CONVENTION.md` (raiz); este arquivo só
> pode ser **mais restritivo**. Doc funcional completa: `wiki/fees.md`.

---

## 1. Quem é você aqui

- Claude Code **exclusivo deste serviço**. Fala com outros serviços só por HTTP.
- Papel: manter o fees **pequeno, claro e funcional** (§14). Ele aciona o
  **caminho do dinheiro** (payouts PIX via `asaas`), então correção,
  **idempotência** e fronteiras (§6) vêm antes de esperteza.
- O fees registra **taxas de matrícula**: por aluno, dois payouts PIX por QR Code
  (à vista + agendado), executados pelo `asaas`. Status derivado; quando a parte
  à vista é paga, o acesso fica **liberável** — mas o fees só guarda o status,
  **não** libera acesso nem chama student/auth (§6).

## 2. Regras de ouro (não negociáveis)

1. **Não alucine.** Sem certeza? Leia o código (`app/config.py` p/ envs;
   `app/services/fee_service.py` p/ regras) ou pergunte.
2. **Faça só o que foi pedido.** Sugestões no fim da resposta, não no código.
3. **§12 — Asaas só via app `asaas`.** É **proibido** falar com a API Asaas
   direto. Toda chamada passa por `integrations/asaas.py`.
4. **Stack fixa (§2).** FastAPI + SQLAlchemy 2.0 async + asyncpg + Alembic +
   Pydantic v2 + httpx.AsyncClient + structlog + pydantic-settings.
5. **`external_id` é opaco.** UUID fornecido por quem chama; **sem FK
   cross-schema** (mesmo princípio do asaas). Não criar shadow table.
6. **Idempotência do money path.** Persistir a intenção (DB commit) **antes** de
   chamar o asaas; `payment_id` determinístico (`fee-<fee_id>-<kind>`) garante que
   re-submit recebe `payment_id_already_exists` e não duplica pagamento.
7. **Notificação nunca quebra o fluxo (§12).** Sempre async (BackgroundTasks),
   sempre `try/except` que só loga.
8. **Toda mudança de modelo → migração Alembic.** Nada de `create_all` em prod.

## 3. Estrutura — onde cada coisa mora

```
fees/app/
├── main.py              # FastAPI; lifespan; health/ready/status
├── config.py            # Settings (.env) — database_url obrigatório
├── db.py                # async engine, Base, NAMING_CONVENTION, utcnow
├── dependencies.py      # JWT (gate coordenador via JWKS) + get_asaas_client
├── api/authenticated/   # endpoints do coordenador (fees.py)
├── api/demilitarized/   # webhooks.py — callback de status do asaas
├── models/              # fee.py, fee_payment.py (+ _mixins.py)
├── schemas/             # Pydantic v2 (fee.py)
├── services/            # fee_service.py (negócio)
├── integrations/        # asaas.py, notify.py (+ BaseClient em __init__)
└── notify/              # handlers.py + messages/*.md
```

Rota → `api/<tipo>/<recurso>.py`; model → `models/`; schema → `schemas/`;
negócio → `services/`; cliente externo → `integrations/`. Não cabe? Pergunte.

## 4. Ambiente real

- **Hospedagem:** Proxmox + Docker; produção online.
- **Tipos de endpoint (§5):** `authenticated/fees` exigem JWT + role coordenador;
  `demilitarized/webhooks` é consumido só pelo `asaas` (sem auth).
- **Segredos** só no `.env`, nunca no código nem no `.env.example`.
- O asaas precisa apontar `internal_url_payout`/`internal_url_scheduling` para
  `POST /api/v1/webhook/asaas-payout` (config operacional do asaas).

## 5. Comandos

```bash
make install      # uv sync
make run          # uvicorn :8000 (--reload)
make test         # uv run pytest -v  (13 testes, sqlite)
make lint / fmt   # ruff check / format
make migrate      # alembic upgrade head (cria o schema fees)
```

## 6. O que NÃO fazer

- Não duplicar payout (respeitar idempotência do item 2.6).
- Não falar com a API Asaas fora de `integrations/asaas.py` (§12).
- Não conectar no banco de outro serviço; sem FK cross-schema.
- Não liberar acesso por conta própria nem chamar student/auth (§6) — só status.
- Não ordenar query paginada só por `created_at` — desempate por `id`.
- Comentário/doc em **pt-br** e verdadeiro; logs técnicos em inglês. Sem segredo
  em log.

---

**Antes de qualquer tarefa**, leia também `.claude/memory/*.md` e `wiki/fees.md`.
