# CLAUDE.md — profiles

> Fonte de verdade para você (Claude Code) **neste serviço**. Leia inteiro
> antes de mexer. Conflito com o que o usuário pediu agora → **pergunte**.
> A convenção geral está em `../CONVENTION.md` (este arquivo só pode ser
> **mais restritivo**, nunca afrouxar).

## 1. O que é
Microsserviço de **dados cadastrais** (perfil, nascimento, escolaridade),
1-para-1 com `auth.users` via `external_id`. Dono da identidade/CPF na
plataforma. Enriquecimento por CPF via CPFHub.io (best-effort).

## 2. Regras de ouro
1. **Não alucine.** Sem certeza de assinatura/versão/env var → consulte ou
   pergunte. Nunca invente import path ou método de lib.
2. **Faça só o que foi pedido.** Sugira melhorias no fim da resposta; não as
   implemente sozinho.
3. **Antes de codar, leia** os arquivos relevantes (`.claude/memory/*.md`,
   `app/`). Atualize a memória ao aprender algo novo.
4. **Stack fixa** (§2 da convenção): FastAPI + SQLAlchemy 2 async + asyncpg +
   Alembic + Pydantic v2 + structlog + httpx, via `uv`. Não troque sem confirmar.
5. **Postgres central, schema próprio `profiles`.** FK cross-schema para
   `auth.users` **só** via shadow table read-only (`app/db.py`). Nunca importe
   model de outro serviço; para o resto, chame a API dele.
6. **`DATABASE_URL` é obrigatório** (sem default no código). Nada de credencial
   hardcoded.

## 3. Estrutura
```
app/
├── main.py            # FastAPI + lifespan + handler de DomainError
├── config.py          # Settings (pydantic-settings); DATABASE_URL obrigatório
├── db.py              # engine async, Base, metadata(schema), shadow auth.users
├── exceptions.py      # DomainError → Conflict/NotFound/ValidationError
├── api/               # profiles.py (recurso) + health.py + router.py
├── models/            # profile.py, birth_info.py, educational.py
├── schemas/           # profile.py (Pydantic v2)
├── services/          # profile_service.py (regra de negócio)
├── integrations/      # cpfhub.py (externo)
├── validators/        # cpf, name, birth_date, location, educational, description
└── utils/logging.py   # structlog
alembic/               # migrações 0001 schema, 0002 índices, 0003 trigger updated_at
```
Endpoint **fino**: valida entrada → chama `service` → devolve `schema`. Regra de
negócio mora em `services/`, não na rota.

## 4. Banco
- Async sempre (`AsyncSession`/asyncpg). Schema `profiles`.
- PK atual = serial; referência cross-service = `external_id` (UUID).
- **Toda mudança de modelo → migração Alembic.** Proibido `create_all()` em prod.
- `updated_at`: mantido pelo ORM (`onupdate`) **e** por trigger no Postgres
  (migração `0003`) — cobre também UPDATE por SQL direto.

## 5. Comandos
```bash
uv sync                       # deps
make migrate                  # alembic upgrade head
make dev                      # uvicorn :80 --reload   (make run = prod)
make test                     # pytest
make lint                     # ruff check
```

## 6. O que NÃO fazer
- Não ler/escrever schema de outro serviço por SQL (exceto shadow `auth.users`).
- Não duplicar regra de identidade alheia; profiles é o dono de CPF — **auth
  delega a profiles** (não replique a validação dele aqui sem alinhar).
- Não adicionar dependência fora da stack canônica sem justificar.
- Não escrever migração manual de schema sem necessidade (use autogenerate);
  triggers/DDL específico são exceção legítima (vide `0003`).
- Não logar PII (CPF, nome) — o enriquecimento CPFHub loga só `type(exc)`.

## 7. Memória
Antes de implementar, leia `.claude/memory/{architecture,conventions,integrations}.md`.
Ao terminar, pergunte-se: "preciso registrar algo aqui?".

## 8. Ao concluir
Aplique o **Checklist §15** da convenção, deixe `ruff` limpo + `pytest` verde +
`alembic upgrade head` OK, e atualize `../wiki/profiles.md` (fonte de verdade).
