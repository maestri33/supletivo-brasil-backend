# otp

Microsserviço de geração e validação de OTP (one-time password).

Stack: **FastAPI + Tortoise ORM + Uvicorn + uv**.

## Endpoints

| Método | Rota              | Descrição                        |
| ------ | ----------------- | -------------------------------- |
| POST   | `/api/v1/otp`     | Gerar e enviar OTP via notify    |
| GET    | `/api/v1/otp`     | Listar OTPs (filtros opcionais)  |
| POST   | `/api/v1/otp/check` | Validar código OTP             |
| GET    | `/api/v1/otp/logs` | Listar logs (idêntico ao GET /) |
| GET    | `/health`         | Liveness                         |
| GET    | `/ready`          | Readiness (verifica banco)       |

## Fluxo

1. **Geração:** `POST /api/v1/otp` com `external_id` → gera código numérico → salva hash SHA256 no banco → renderiza template `otp.md` → envia via **notify** → retorna status `sent`.
2. **Validação:** `POST /api/v1/otp/check` com `external_id` + `code` → busca OTP pendente mais recente → verifica TTL → compara hash em tempo constante → retorna `valid: true/false`.
3. **Listagem:** `GET /api/v1/otp` ou `/api/v1/otp/logs` com filtros por `external_id` e `status`.

## Configuração

Toda configuração é feita via `.env`:

| Variável         | Default        | Descrição                    |
| ---------------- | -------------- | ---------------------------- |
| `OTP_FOOTER`     | Equipe OTP     | Rodapé da mensagem           |
| `OTP_TTL_S`      | 300            | Tempo de vida do código (s)  |
| `OTP_NUM_DIGITS` | 6              | Quantidade de dígitos        |
| `OTP_MAX_ATTEMPTS` | 3            | Tentativas máximas (futuro)  |
| `OTP_ACTIVE`     | true           | Ativar/desativar serviço     |

## Integração

Envia mensagens via **notify** (`10.10.10.157/api/v1`). O contacto deve existir previamente no notify.

## Comandos

```bash
make install     # uv sync
make dev         # uvicorn --reload na porta 80
make run         # uvicorn 2 workers
make test        # pytest
make lint        # ruff + mypy
make fmt         # ruff format
make migrate     # aerich migrate && upgrade
```

## Banco

SQLite em `./data/app.db`. Para trocar pra Postgres, mude `DATABASE_URL` no `.env`.
