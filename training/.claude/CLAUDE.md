# CLAUDE.md — Memória e regras do serviço `training`

> Fonte da verdade para você (Claude Code) sobre o serviço `training`. Leia
> inteiro antes de agir. A convenção geral é `../CONVENTION.md` (raiz); este
> arquivo só pode ser **mais restritivo**. PRD: `../.claude/prds/training.prd.md`.
> Plano por etapa: `../.claude/plans/training.plan.md`.

## 1. O que é
LMS de onboarding. O usuário fica no papel **`training`** (entre `candidate` e
`promoter`) e precisa concluir todas as **matérias** para virar promotor. O
`candidate` já promove o usuário para o papel `training` ao concluir o funil
(`candidate/app/services/selfie.py`).

## 2. Regras de ouro
1. **Não alucine.** Sem certeza de contrato de outro serviço? Leia o código dele
   ou pergunte. Nunca invente endpoint/campo.
2. **Faça só o que foi pedido.** Sugestões no fim da resposta, não no código.
3. **Stack canônica** (§2 da CONVENTION): FastAPI + SQLAlchemy 2.0 async +
   asyncpg + Alembic + Pydantic v2 + structlog + uv. **Porta 8000.**
4. **Postgres central, schema `training`.** Sem FK cross-schema: `external_id`
   (quando existir, M2) é referência lógica ao `auth.users`, não FK.
5. **IA é do serviço `ai`** (§12): a correção do M2 chama o `ai` via httpx
   (`integrations/ai.py`). **Proibido** client DeepSeek próprio aqui.
6. **Promoção de papel é do serviço `roles`** — não duplicar lógica de papéis.

## 3. Estrutura (espelha o `candidate`)
```
app/
├── main.py            # FastAPI, lifespan, handler de DomainError, health
├── config.py          # Settings (get_settings cacheado)
├── db.py              # engine async, Base, utcnow, get_session, close_db
├── exceptions.py      # DomainError/NotFound/Conflict/ValidationError/IntegrationError
├── models/            # Material (+ futuros: submission, trainee)
├── schemas/           # APIModel + schemas por recurso
├── services/          # material (CRUD) + media (storage local)
├── api/demilitarized/ # rotas internas sem auth
└── utils/logging.py   # structlog
alembic/  tests/  pyproject.toml  .env.example  README.md
```

## 4. Justificativas de dependência
- `python-multipart`: exigido pelo FastAPI para `UploadFile` (upload de
  vídeo/foto das matérias). Dentro da intenção da stack (§2), não é lib exótica.

## 5. Mídia
Vídeo/foto das matérias ficam no próprio serviço em `MEDIA_DIR` (volume), em
`MEDIA_DIR/<material_id>/<video|photo><ext>`. Servidos via `GET ... /video|/photo`
(`FileResponse`), **nunca** via `StaticFiles` aberto — evita o problema de
exposição apontado em `wiki/documents.md`. Validar mime e `MAX_UPLOAD_MB`.

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
- Não integrar IA direto — use o serviço `ai` (§12).
- Não manipular papéis aqui — chame `roles`.
- Não usar `Base.metadata.create_all()` em produção — mudança de modelo = migração.
- Não bloquear o fluxo por falha de IA/notificação (degrade e logue) — M2+.
- Não deixar `TODO` órfão. Comentário/doc em pt-br, log técnico em inglês.

## 8. Roadmap (PRD)
M1 Autoria de matérias **(atual)** · M2 Treinamento + correção por IA ·
M3 Conclusão + entrevista do coordenador · M4 papel `training` no `roles` ·
M5 Notificações via `notify`.

> O arquivo `../training/TODO` (spec original do dono) **só sai** quando o serviço
> estiver pronto e aprovado, e então nasce `wiki/training.md` (§15 da CONVENTION).
