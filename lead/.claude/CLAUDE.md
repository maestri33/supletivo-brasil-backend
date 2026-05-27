# CLAUDE.md — Memória e regras do microsserviço `lead`

> Fonte da verdade para você (Claude Code) sobre o serviço `lead`. Leia inteiro
> antes de agir. Se algo aqui conflita com o pedido atual, **pergunte** — não
> decida sozinho. A convenção geral é `CONVENTION.md` (raiz); este arquivo só
> pode ser **mais restritivo**. Doc funcional completa: `wiki/lead.md`.

---

## 1. Quem é você aqui

- Claude Code **exclusivo deste serviço**. Fala com outros serviços só por HTTP.
- Papel: gerenciar o **ciclo de vida do role lead** no pipeline de captação —
  desde o cadastro público (register/OTP) até a confirmação de pagamento
  (`COMPLETED`), transitando pelos status do fluxo. É o ponto de entrada de
  novos candidatos na plataforma.
- **Modelo de referência de estrutura** para todos os outros serviços (§3 da
  convenção). Na dúvida, espelhe a estrutura e estilo do `lead`.
- **É caminho de dinheiro?** Sim — lida com checkout e pagamento (via `asaas` e
  `infinitepay`). Toda alteração no fluxo de pagamento exige **cuidado máximo**
  e testes de regressão.
- Schema `lead`. PK = UUID.

## 2. Regras de ouro (não negociáveis)

1. **Não alucine.** Sem certeza? Consulte o código ou pergunte.
2. **Faça só o que foi pedido.** Sugestões no fim da resposta, não no código.
3. **Stack fixa (§2).** FastAPI + SQLAlchemy 2.0 async + asyncpg + Alembic +
   Pydantic v2 + httpx.AsyncClient + structlog + pydantic-settings.
4. **Cada serviço, seu schema.** Schema `lead`. FK cross-schema via shadow table
   (`Table` read-only, §4).
5. **Caminho de dinheiro.** NUNCA altere fluxo de pagamento ou checkout sem
   aprovação humana explícita. Testes de regressão obrigatórios para qualquer
   mudança em checkout/pagamento.
6. **Notificações (§11):** mudanças de status disparam notificações assíncronas
   via `notify/`. Templates em `<servico>/app/notify/messages/`.
7. **Toda mudança de modelo → migração Alembic.**

## 3. Stack

| Camada | Tecnologia |
|---|---|
| Runtime | Python 3.12 + `uv` |
| Web | FastAPI + uvicorn |
| ORM | SQLAlchemy 2.0 async (`Mapped`/`mapped_column`, `select()`) |
| Driver | asyncpg (Postgres central, schema `lead`) |
| Migrations | Alembic |
| Validação/Config | Pydantic v2 + pydantic-settings (`.env`) |
| HTTP cliente | httpx.AsyncClient (asaas, infinitepay, notify) |
| Logs | structlog |
| Testes | pytest + pytest-asyncio |

## 4. Estrutura

```
lead/app/
├── main.py           # FastAPI; lifespan; structlog
├── config.py         # Settings (.env)
├── db.py             # async engine, Base, NAMING_CONVENTION
├── dependencies.py   # Depends compartilhadas
├── api/              # rotas
├── models/           # SQLAlchemy
├── schemas/          # Pydantic v2
├── integrations/     # clients (asaas, infinitepay, notify, outros)
├── notify/           # templates de notificação por status
│   └── messages/     # arquivos .md com conteúdo das notificações
└── tools/            # utilitários
```

**Regra das pastas (§3):** rota → `api/<recurso>.py`; model → `models/`; schema
→ `schemas/`; cliente externo → `integrations/`; notificações → `notify/messages/`.

## 5. Ambiente real

- **Tipos de endpoint (§5):** `register`/`checkout` são **públicos** (superfície
  pública — cuidado redobrado). Webhooks de pagamento (asaas/infinitepay) são
  **públicos** com verificação de assinatura.
- **Caminho de dinheiro:** pagamento por PIX e cartão via `asaas` e `infinitepay`.
  Idempotência e reconciliação são críticos.
- **Segredos** só no `.env`, nunca no código.

## 6. O que NÃO fazer

- ❌ Alterar fluxo de checkout/pagamento sem aprovação humana.
- ❌ Deixar de verificar idempotência em webhooks de pagamento.
- ❌ Logar dados de pagamento completos (mascarar/omitir).
- ❌ Importar modelo de outro serviço — usar shadow table read-only.
- ❌ Commitar template de notificação sem revisar o conteúdo (vai para o cliente).
- Comentário/doc em **pt-br** e verdadeiro; logs técnicos em inglês.

---

**Antes de qualquer tarefa**, leia também `wiki/lead.md` e `CONVENTION.md` (raiz).
