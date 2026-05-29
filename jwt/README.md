# jwt

Serviço de tokens JWT (RS256). Gera e gerencia chaves público/privada, emite
tokens de acesso e refresh, valida tokens, expõe JWKS para outros serviços
validarem assinaturas. Stateless além das chaves em disco — sem banco de dados.
Doc completa: `../wiki/jwt.md`.

## Rodar

```bash
uv sync
cp .env.example .env      # JWT_PRIVATE_KEY_PATH, JWT_PUBLIC_KEY_PATH
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
| `JWT_PRIVATE_KEY_PATH` | | Caminho da chave privada (default `private.pem`) |
| `JWT_PUBLIC_KEY_PATH` | | Caminho da chave pública (default `public.pem`) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | | Expiração access token (default `30`) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | | Expiração refresh token (default `7`) |

## Endpoints (desmilitarizados)

- `POST /api/v1/token` — emite access + refresh tokens
- `POST /api/v1/token/refresh` — renova tokens
- `POST /api/v1/token/verify` — valida token
- `GET /.well-known/jwks.json` — chave pública para outros serviços
- **Saúde:** `/health`, `/ready`, `/status`

> As chaves são geradas automaticamente por `_ensure_keys()` se não existirem.
