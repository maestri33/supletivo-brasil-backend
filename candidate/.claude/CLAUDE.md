# CLAUDE.md — Memória e regras do serviço `candidate`

> Fonte da verdade para você (Claude Code) sobre o serviço `candidate`. Leia
> inteiro antes de agir. Se algo aqui conflita com o pedido atual, **pergunte** —
> não decida sozinho. A convenção geral é `../CONVENTION.md` (raiz); este arquivo
> só pode ser **mais restritivo**. Doc funcional: `wiki/candidate.md`.

---

## 1. Quem é você aqui
- Claude Code **exclusivo deste serviço**. Fala com outros serviços só por HTTP.
- Papel: manter o candidate **pequeno, claro e funcional**. Ele é um
  **orquestrador** do funil — não duplica lógica que pertence a outro serviço.

## 2. Regras de ouro (não negociáveis)
1. **Não alucine.** Sem certeza de assinatura/contrato? Leia o código do serviço
   alvo ou pergunte. Nunca invente endpoint ou campo.
2. **Faça só o que foi pedido.** Sugestões no fim da resposta, não no código.
3. **Antes de codar, leia** `.claude/memory/*.md` e os arquivos de `app/`.
4. **Stack fixa (§3).** FastAPI + SQLAlchemy 2.0 async + asyncpg + Alembic +
   Pydantic v2 + httpx + structlog + uv. Não troque sem confirmar.
5. **Porta 8000.**
6. **Postgres central, schema `candidate`.** Sem FK cross-schema: `external_id` é
   referência lógica ao `auth.users` (string UUID), não FK. Não leia/escreva
   tabela de schema de outro serviço — chame a API dele.

## 3. Estrutura
```
app/
├── main.py            # FastAPI, lifespan, handler de DomainError, health
├── config.py          # Settings (get_settings cacheado)
├── db.py              # engine async, Base, utcnow, get_session
├── exceptions.py      # DomainError/NotFound/Conflict/ValidationError/IntegrationError
├── dependencies.py    # JWT (role lead) + gate por status (require_<etapa>)
├── models/            # Candidate (+ CandidateStatus, STATUS_ORDER)
├── schemas/           # APIModel + schemas por recurso
├── services/          # 1 módulo por etapa + candidate (transições) + notifications
├── integrations/      # clients httpx: auth, jwt, notify, profiles, address,
│                      #   asaas, documents, ai, roles  (+ request_with_retry)
├── api/               # public/ · authenticated/ · demilitarized/ · router.py
└── utils/logging.py   # structlog
alembic/  tests/  pyproject.toml  .env.example  README.md
```
Regra das pastas: rota → `api/<area>/<recurso>.py` (+ `router.py`); model →
`models/`; schema → `schemas/`; negócio → `services/`; cliente externo →
`integrations/`. Não cabe? Pergunte.

## 4. Funil (máquina de status)
`captured → personal → education → birth → address → documents → pixkey → selfie → completed`
- Cada POST de etapa: valida → chama o serviço dono → `advance(current→next)` →
  `commit` → notifica (BackgroundTasks).
- O gate `require_<etapa>` (dependencies.py) bloqueia fora de ordem (403).
- Conclusão (selfie): promove papel lead→training no `roles`; status `completed`.

## 5. Ambiente real
- Proxmox + Docker, DMZ. Segurança ainda não é prioridade (sem rate-limit etc.).
- Endpoints: `public/` (expostos), `authenticated/` (JWT role lead),
  `demilitarized/` (uso interno da plataforma, sem auth).

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
- Não duplicar lógica de outro serviço (perfil, endereço, documentos, PIX, papéis
  vivem nos seus donos — candidate só orquestra).
- Não integrar com Asaas direto — use o serviço `asaas` (§12 da CONVENTION).
- Não usar `Base.metadata.create_all()` em produção — mudança de modelo = migração.
- Não bloquear o funil por falha de notificação/IA (degrade e logue).
- Não deixar `TODO` órfão; comentário/doc em pt-br, log técnico em inglês, sem segredo em log.

## 8. Pendência aberta
Criar registro no serviço `training` na conclusão — só quando o `training` existir
(green-field). Hoje a conclusão promove o papel via `roles`. Não inventar a API do
training (§2).

---
**Antes de qualquer tarefa**, leia também `.claude/memory/*.md` e `wiki/candidate.md`.
