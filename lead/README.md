# lead

**Modelo de referência de estrutura** para todos os outros serviços (§3 CONVENTION).
Gerencia o ciclo de vida do role `lead` no pipeline de captação — cadastro público
(register/OTP), checkout (PIX/cartão via `asaas` e `infinitepay`), status e
promoção. É o ponto de entrada de novos candidatos na plataforma. Doc completa:
`../wiki/lead.md`.

## Rodar

```bash
uv sync
cp .env.example .env      # ajuste DATABASE_URL e *_BASE_URL
uv run alembic upgrade head
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Testes / lint

```bash
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
```

## Variáveis (`.env`)

| Var | Obrigatória | Descrição |
|-----|:-:|-----------|
| `DATABASE_URL` | ✅ | Postgres async (`postgresql+asyncpg://...`) |
| `AUTH_BASE_URL` | ✅ | URL do serviço `auth` |
| `ASAAS_BASE_URL` | ✅ | URL do serviço `asaas` |
| `INFINITEPAY_BASE_URL` | ✅ | URL do serviço `infinitepay` |
| `NOTIFY_BASE_URL` | | URL do serviço `notify` |
| `JWT_BASE_URL` | | URL do serviço `jwt` |

## Endpoints

- **Público:** `POST /api/v1/public/check`, `/register`, `/login`, `/refresh`
- **Autenticado:** `GET/POST /api/v1/authenticated/captured`, `/waiting`, `/checkout`, `/completed`
- **Desmilitarizado:** `GET /api/v1/demilitarized/leads[/{external_id}]`, `PATCH /{external_id}`, `DELETE /{external_id}`
- **Saúde:** `/health`, `/ready`, `/status`

> **Caminho de dinheiro.** NUNCA altere fluxo de pagamento ou checkout sem
> aprovação humana explícita.
