# auth

Fonte de verdade de identidade da plataforma: registra usuários (CPF + phone),
valida unicidade, emite OTP e coordena provisionamento de perfil, role, contato e
JWT. Não guarda senha — autenticação delegada a OTP e JWT externos. Doc completa:
`../wiki/auth.md`.

## Rodar

```bash
uv sync
cp .env.example .env      # ajuste DATABASE_URL e *_BASE_URL
uv run alembic upgrade head
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Testes / lint

```bash
uv run pytest -q           # recover + role_logic; faltam register/login/check
uv run ruff check . && uv run ruff format --check .
```

## Variáveis (`.env`)

| Var | Obrigatória | Descrição |
|-----|:-:|-----------|
| `DATABASE_URL` | ✅ | Postgres async (`postgresql+asyncpg://...`) |
| `OTP_BASE_URL` | ✅ | URL do serviço `otp` |
| `JWT_BASE_URL` | ✅ | URL do serviço `jwt` |
| `PROFILES_BASE_URL` | | URL do serviço `profiles` |
| `ROLES_BASE_URL` | | URL do serviço `roles` |
| `NOTIFY_BASE_URL` | | URL do serviço `notify` |

## Endpoints

- **Público:** `POST /api/v1/check`, `POST /api/v1/login`, `POST /api/v1/recover`, `POST /api/v1/register`
- **Interno:** `GET /api/v1/atomic/*`, `GET /api/v1/log/*`
- **Saúde:** `/health`, `/ready`, `/status`
