# CLAUDE.md — Memória e regras do serviço `promoter`

> Fonte da verdade para você (Claude Code) sobre o serviço `promoter`. Leia
> inteiro antes de agir. Se algo aqui conflita com o pedido atual, **pergunte** —
> não decida sozinho. A convenção geral é `../CONVENTION.md` (raiz); este arquivo
> só pode ser **mais restritivo**. Doc funcional: `wiki/promoter.md`.

---

## 1. Quem é você aqui
- Claude Code **exclusivo deste serviço**. Fala com outros serviços só por HTTP.
- Papel: manter o promoter **pequeno, claro e funcional**. Ele é um
  **orquestrador/agregador** — não duplica lógica de `lead`, `commissions`, `roles`.

## 2. Regras de ouro (não negociáveis)
1. **Não alucine.** Sem certeza de assinatura/contrato? Leia o código do serviço
   alvo ou pergunte. Nunca invente endpoint ou campo. (Ex.: `commissions` ainda
   não existe — não inventamos a API dele; ver §8.)
2. **Faça só o que foi pedido.** Sugestões no fim da resposta, não no código.
3. **Stack fixa.** FastAPI + SQLAlchemy 2.0 async + asyncpg + Alembic +
   Pydantic v2 + httpx + structlog + uv. Porta 8000.
4. **Postgres central, schema `promoter`.** Sem FK cross-schema: `external_id` é
   referência lógica ao `auth.users` (string UUID). Não leia/escreva tabela de
   outro schema — chame a API do serviço dono.

## 3. Estrutura
```
app/
├── main.py            # FastAPI, lifespan, handler de DomainError, health
├── config.py          # Settings (get_settings cacheado)
├── db.py              # engine async, Base, utcnow, get_session
├── exceptions.py      # DomainError/NotFound/Conflict/ValidationError/IntegrationError
├── dependencies.py    # JWT (role promoter) + get_current_promoter (ativo)
├── models/            # Promoter (+ PromoterStatus)
├── schemas/           # APIModel + promoter/auth/leads/commissions
├── services/          # promoter (criação/ref) · auth · leads · commissions · notifications
├── integrations/      # clients httpx: auth, jwt, roles, profiles, notify, lead, commissions
├── api/               # public/ · authenticated/ · demilitarized/ · router.py
└── utils/logging.py   # structlog
alembic/  tests/  pyproject.toml  .env.example  README.md
```

## 4. Domínio (sem funil)
O promoter **não tem funil**. Ele é criado uma vez e existe com status
`active`/`suspended`.
- **Criação** (`POST /demilitarized/promoters`, chamado pelo `coordinator`):
  `get_or_create` idempotente → se novo, promove `candidate → promoter` no `roles`
  (bloqueante: se `roles` falhar, não commita; coordinator repete) → commit →
  notifica (BackgroundTasks).
- **Validação de ref** (`GET /demilitarized/validate-ref/{ref}`): `ref == external_id`;
  retorna `valid` só se o promoter existir e estiver `active`. Consumido pelo `lead`.
- **Visão do promoter** (autenticada, role promoter ativo):
  `/me`, `/me/leads` (httpx `lead`, filtro defensivo client-side por
  `promoter_external_id`), `/me/commissions` (httpx `commissions`, degrada).

## 5. Ambiente real
- Proxmox + Docker, DMZ. Endpoints: `public/` (expostos), `authenticated/`
  (JWT role promoter), `demilitarized/` (uso interno, sem auth).

## 6. Comandos
```bash
uv sync
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
uv run pytest -q
uv run ruff check . && uv run ruff format .
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "..."
```

## 7. O que NÃO fazer
- Não duplicar domínio de `lead`/`commissions`/`roles` — só agregar/validar.
- Não captar lead aqui: a landing chama o `lead` direto; promoter só valida o ref.
- Não usar `Base.metadata.create_all()` em produção — mudança de modelo = migração.
- Não bloquear notificação/visão por falha de integração (degrade e logue) —
  exceto a promoção de papel na criação, que é intencionalmente bloqueante.
- Sem `TODO` órfão; comentário/doc em pt-br, log técnico em inglês, sem segredo em log.

## 8. Pendências abertas (documentadas)
- **`commissions` não existe** (só spec/TODO). `GET /me/commissions` degrada para
  `available=false`. Quando o serviço existir, validar a rota/parsing em
  `integrations/commissions.py` (hoje assume `GET /api/v1/demilitarized/commissions
  ?promoter_external_id=`).
- **Filtro por promoter no `lead`**: o `lead` ainda lista todos os leads; passamos
  o filtro por query e aplicamos filtro defensivo client-side. Quando o `lead`
  suportar o filtro nativo, remover o filtro client-side é opcional.
- **Quem promove o papel**: hoje a criação no promoter promove `candidate→promoter`.
  Se o `coordinator` passar a promover, a chamada continua idempotente (confirmar
  com o engenheiro antes de remover daqui).

---
**Antes de qualquer tarefa**, leia também `wiki/promoter.md` e `app/`.
