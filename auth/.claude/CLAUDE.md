# CLAUDE.md — Memória e regras do microsserviço `auth`

> Fonte da verdade para você (Claude Code) sobre o serviço `auth`. Leia inteiro
> antes de agir. Se algo aqui conflita com o pedido atual, **pergunte** — não
> decida sozinho. A convenção geral é `CONVENTION.md` (raiz); este arquivo só
> pode ser **mais restritivo**. Doc funcional completa: `wiki/auth.md`.

---

## 1. Quem é você aqui

- Claude Code **exclusivo deste serviço**. Fala com outros serviços só por HTTP.
- Papel: fonte de verdade de **identidade** da plataforma — registra usuários
  (CPF + phone), valida unicidade, emite OTP e coordena provisionamento de
  perfil, role, contato e JWT.
- **Não guarda senha** — autenticação é delegada a OTP e JWT externos.
- PK = **UUID** (`external_id`); schema `auth`.

## 2. Regras de ouro (não negociáveis)

1. **Não alucine.** Sem certeza? Consulte o código ou pergunte.
2. **Faça só o que foi pedido.** Sugestões no fim da resposta, não no código.
3. **Stack fixa (§2).** FastAPI + SQLAlchemy 2.0 async + asyncpg + Alembic +
   Pydantic v2 + httpx.AsyncClient + structlog + pydantic-settings.
4. **Config via `.env`** (pydantic-settings). `DATABASE_URL` obrigatório.
5. **Cada serviço, seu schema.** Schema `auth`. NÃO mantém tabela de roles —
   roles vivem no app `roles` (§8). NÃO usa shadow table nem FK cross-schema —
   referências a outros serviços são `external_id` UUID opaco (§4).
6. **Provisionamento atômico.** Na criação de usuário, provisiona Profile,
  Contato, Documentos e Endereço em sequência (best-effort, §12). Email é
  deferido.
7. **Toda mudança de modelo → migração Alembic.** Nada de `create_all` em prod.

## 3. Estrutura

```
auth/app/
├── main.py              # FastAPI; lifespan
├── config.py            # Settings (.env)
├── db.py                # async engine, Base, NAMING_CONVENTION
├── exceptions.py
├── api/
│   ├── router.py        # agrega routers
│   ├── register.py      # POST /api/v1/register
│   ├── check.py         # POST /api/v1/check (rate-limit via Redis)
│   ├── login.py         # POST /api/v1/login (OTP + JWT)
│   ├── recover.py       # POST /api/v1/recover
│   ├── atomic.py        # operações atômicas
│   ├── log.py           # log de eventos
│   └── deps.py          # dependências compartilhadas
├── models/              # user.py (User — roles vivem no app roles, §8)
├── integrations/        # jwt.py, notify.py, otp.py, profiles.py, roles.py,
│                        # address.py, documents.py
└── utils/               # logging.py (structlog), validation.py
```

**Pendências de convenção:** `schemas/` e `services/` não existem — validação
está inline nas rotas e lógica de negócio misturada em `api/*.py`. Refatorar
conforme §3.

## 4. Ambiente real

- **Hospedagem:** Proxmox + Docker, produção.
- **Tipos de endpoint (§5):** `register`, `check`, `login`, `recover` são
  **públicos** (superfície pública). `atomic` e `log` são **desmilitarizados**
  (consumidos por outros apps).
- **Segredos** só no `.env`, nunca no código nem no `.env.example`.
- `REDIS_URL` usado para rate-limit em `check`.

## 5. Comandos

```bash
make install                                   # uv sync
make dev / make run                            # uvicorn :8000 (--reload / prod)
make test                                      # uv run pytest -q
make lint / make fmt                           # ruff check / format
uv run alembic revision --autogenerate -m "…"  # gera migração
uv run alembic upgrade head                    # aplica
```

## 6. O que NÃO fazer

- Não usar `Base.metadata.create_all()` em produção.
- Não importar modelo de outro serviço. Sem shadow table. Use `external_id` (§4).
- Não logar PII (CPF, telefone, endereço completo).
- Não conectar no banco de outro serviço.
- Comentário/doc em **pt-br** e verdadeiro; logs técnicos em inglês.

---

**Antes de qualquer tarefa**, leia também `wiki/auth.md` e `CONVENTION.md` (raiz).
