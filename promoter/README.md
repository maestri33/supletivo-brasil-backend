# promoter

Serviço do **promotor** — o ex-candidato que passou pelo treinamento e foi
aprovado na entrevista com o **coordenador do polo**. O promotor divulga um link
de captação (`<landing>/ref=<external_id>`) e acompanha seus leads e comissões.

Microsserviço FastAPI (porta 8000), schema Postgres próprio `promoter`. Espelha a
estrutura do app-modelo `candidate`. Convenção geral: `../CONVENTION.md`.

## O que faz

| Área | Endpoint | Quem chama |
|---|---|---|
| Pública | `POST /api/v1/public/check` · `POST /login` · `POST /refresh` | app do promotor |
| Autenticada (JWT role `promoter`) | `GET /api/v1/authenticated/me` · `/me/leads` · `/me/commissions` | app do promotor |
| Desmilitarizada | `POST /api/v1/demilitarized/promoters` | `coordinator` (cria o promotor) |
| Desmilitarizada | `GET /api/v1/demilitarized/promoters[/{id}]` | `hub`, `coordinator` |
| Desmilitarizada | `GET /api/v1/demilitarized/validate-ref/{ref}` | `lead` (valida o ref na captação) |

### Fronteiras (CONVENTION §6)
- **Captação**: a landing chama o **`lead` direto** com `ref=<external_id>`. O
  promoter **só valida** o ref (`validate-ref`). A atribuição do lead vive no `lead`
  (`promoter_external_id`).
- **Leads / comissões**: read-only, **agregados via httpx** de `lead` e
  `commissions`. O promoter não duplica esses domínios.
- **Criação**: o `coordinator` aprova a entrevista e chama `POST /promoters`. A
  criação promove o papel `candidate → promoter` no `roles` (bloqueante e
  idempotente por `external_id`).

### Pendência documentada (sem TODO órfão)
O serviço **`commissions` ainda não existe** (só spec/TODO). Não inventamos seu
contrato (§2). `GET /me/commissions` **degrada** para `available=false` + lista
vazia enquanto `commissions` não responder (§12). Quando existir, o client em
`app/integrations/commissions.py` passa a funcionar sem mudança de chamada.

## Rodar

```bash
uv sync
cp .env.example .env   # ajuste PROMOTER_APP_DB_URL
uv run alembic upgrade head
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
uv run pytest -q
uv run ruff check . && uv run ruff format .
```

## Variáveis de ambiente
Ver `.env.example`. Destaques: `PROMOTER_APP_DB_URL` (obrigatório),
`LEAD_BASE_URL`, `COMMISSIONS_BASE_URL`, `ROLES_BASE_URL`, `LANDING_BASE_URL`.
