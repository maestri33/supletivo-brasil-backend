# otp

Serviço de OTP (One-Time Password) numérico descartável. Gera, envia via
`notify` (WhatsApp) e valida códigos com rate-limit e expiração. Registra todo
o ciclo de vida no banco para auditoria. Doc completa: `../wiki/otp.md`.

## Rodar

```bash
uv sync
cp .env.example .env      # ajuste DATABASE_URL e NOTIFY_BASE_URL
uv run alembic upgrade head
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Testes / lint

```bash
uv run pytest -q           # health + otp; suíte legada em skip (SQLite→PG)
uv run ruff check . && uv run ruff format --check .
```

## Variáveis (`.env`)

| Var | Obrigatória | Descrição |
|-----|:-:|-----------|
| `DATABASE_URL` | ✅ | Postgres async (`postgresql+asyncpg://...`) |
| `NOTIFY_BASE_URL` | ✅ | URL do serviço `notify` |
| `OTP_LENGTH` | | Dígitos do código (default `6`) |
| `OTP_TTL_SECONDS` | | Expiração (default `300`) |
| `MAX_ATTEMPTS` | | Tentativas máximas de verificação |

## Endpoints

- **Desmilitarizado:** `POST /api/v1/otp`, `GET /`, `POST /check`, `GET /logs`
- **Público:** `POST /webhook/notify/{message_id}` (callback do notify)
- **Saúde:** `/health`, `/ready`, `/status`
