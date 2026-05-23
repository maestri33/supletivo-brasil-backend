# jwt

Microsservico de emissao de tokens JWT — zero banco, toda config no `.env`.

**Stack:** FastAPI + PyJWT + structlog (sem ORM, sem banco)

## Como funciona a autenticacao entre os servicos

```
                        ┌─────────────┐
                        │    jwt      │  UNICO servico que TEM a chave privada
                        │  (porta 80) │  Ele ASSINA tokens.
                        │             │
                        │  private_key│  NUNCA sai daqui.
                        │  public_key │  Exposta em /.well-known/jwks.json
                        └──────┬──────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
     ┌───────▼──────┐ ┌──────▼───────┐ ┌───────▼──────┐
     │  auth        │ │  hub         │ │  qualquer    │
     │  (consumidor)│ │  (consumidor)│ │  servico     │
     │              │ │              │ │              │
     │  NAO tem     │ │  NAO tem     │ │  NAO tem     │
     │  chave       │ │  chave       │ │  chave       │
     │  privada     │ │  privada     │ │  privada     │
     └──────────────┘ └──────────────┘ └──────────────┘
```

### Fluxo A — Emitir token (quando usuario faz login)

```
1. auth (ou outro servico) recebe login do usuario
2. auth chama:  POST jwt:80/api/v1/tokens/issue
                { "external_id": "usr_123", "roles": ["admin"] }
3. jwt ASSINA o token com a chave PRIVADA RSA (so' ele tem)
4. jwt devolve access_token + refresh_token
5. auth entrega o access_token pro usuario (browser, app, etc)
```

**Quem participa:** apenas o servico consumidor (auth, hub, etc) e o jwt.
**Custo:** 1 chamada HTTP.

### Fluxo B — Validar token (a CADA requisicao do usuario)

```
1. Usuario chama servico X com o token no header:
       Authorization: Bearer eyJhbGciOiJS...

2. Servico X precisa validar. Ele faz DUAS coisas:

   a. Busca a chave PUBLICA uma vez (cacheia):
        GET jwt:80/.well-known/jwks.json
        → {"keys": [{"kid": "...", "n": "...", "e": "..."}]}

   b. Verifica a ASSINATURA localmente com a chave publica:
        - O token foi assinado pelo jwt? (assinatura bate?)
        - O token expirou? (exp > agora?)
        - O tipo e' "access"? (nao aceita refresh token)

3. Se tudo OK, confia nos dados do payload (external_id, roles, etc)
```

**Quem participa:** o servico que recebeu a requisicao + jwt (so' pra pegar a chave).
**Custo:** 0 chamadas no caso normal (chave publica cacheada). 1 chamada na primeira vez ou quando o cache expira.

### Por que assim e nao com chave compartilhada?

```
SEM jwt (ruim):                    COM jwt (nosso caso):
                           
cada servico sabe uma        so' o jwt sabe a privada
senha HMAC secreta           os outros so' sabem a PUBLICA
                           
se um servico vaza,          se um servico vaza,
TODOS os tokens sao          os tokens CONTINUAM seguros
comprometidos                (chave publica nao assina)
                           
revogar = trocar senha       revogar = so' deletar a config
em TODOS os servicos         no jwt, os outros pegam
                              a nova chave publica sozinho
```

### Resumo

| O que | Quem faz | Onde |
|---|---|---|
| Assinar token | So' o **jwt** | `POST /api/v1/tokens/issue` |
| Renovar token | So' o **jwt** | `POST /api/v1/tokens/refresh` |
| Validar token | **Qualquer servico** | Localmente (baixa chave publica do JWKS) |
| Chave publica | **Qualquer servico** | `GET /.well-known/jwks.json` |
| Chave privada | **NUNCA sai do jwt** | Banco SQLite/Postgres |

O jwt e' o **unico ponto de assinatura**. Os outros servicos so' **validam** —
e validam localmente, sem precisar chamar o jwt a cada requisicao.
Isso e' o padrao RSA assimetrico: uma chave assina, muitas chaves verificam.

## Estrutura

```
app/
├── main.py              # FastAPI: middlewares, handler de erros
├── config.py            # pydantic-settings — le tudo do .env
├── exceptions.py        # DomainError, ValidationError
├── stats.py             # Contadores em memoria (tokens emitidos, etc)
├── api/
│   ├── router.py        # Agregador de rotas
│   ├── health.py        # GET / (dashboard), /health, /ready
│   └── tokens.py        # POST /issue, /refresh; GET /.well-known/jwks.json
├── schemas/
│   └── jwt_config.py    # TokenIssueRequest, TokenResponse
├── services/
│   ├── token_service.py # Emissao/refresh/JWKS
│   ├── jwt_service.py   # Encode/decode/JWKS (baixo nivel)
│   └── key_service.py   # Geracao par RSA 2048
└── utils/
    └── logging.py       # structlog + RequestLoggingMiddleware
```

## Convencoes

- **Idioma:** codigo em ingles, docstrings/comentarios/erros em portugues
- **Services:** nunca importam `HTTPException` — levantam `app.exceptions.*`
- **API:** endpoints finos, so chamam service + `model_validate(obj, from_attributes=True)`
- **Config:** tudo que vem de fora passa por `app.config.get_settings()`
- **Imports:** stdlib → terceiros → app, sempre absolutos (`from app.`)
- **Tipos:** `str | None`, `list[X]`, `dict[str, Any]`

## Instalacao

```bash
cd /root/jwt
pip install -e .
cp .env.example .env
# Editar .env conforme necessario
```

## Executar

```bash
uvicorn app.main:app --host 0.0.0.0 --port 80
```

Swagger: http://localhost:80/docs

---

## API Reference

### Status

| Metodo | Rota | Descricao |
|---|---|---|
| `GET` | `/` | Dashboard — status completo, stats, endpoints |
| `GET` | `/health` | Liveness — processo vivo |
| `GET` | `/ready` | Readiness — pronto pra trafego |

### Tokens — `/api/v1/tokens`

| Metodo | Rota | Descricao |
|---|---|---|
| `POST` | `/api/v1/tokens/issue` | Emitir access + refresh |
| `POST` | `/api/v1/tokens/refresh` | Renovar access token |

### Chave Publica

| Metodo | Rota | Descricao |
|---|---|---|
| `GET` | `/.well-known/jwks.json` | JWKS (RFC 7517) |

---

## Exemplos rapidos

```bash
# Dashboard
curl -s http://localhost:80/

# Emitir token (zero config previa — tudo no .env)
curl -s -X POST http://localhost:80/api/v1/tokens/issue \
  -H "Content-Type: application/json" \
  -d '{"external_id":"usr_abc123","roles":["admin"]}'

# Refresh
curl -s -X POST http://localhost:80/api/v1/tokens/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"eyJhbGciOiJS..."}'

# JWKS (outros servicos validam tokens aqui)
curl -s http://localhost:80/.well-known/jwks.json
```

## Formato de erros

Todas as excecoes de dominio sao convertidas em:

```json
{"code": "not_found", "message": "Config X nao encontrada"}
```

| Excecao | HTTP |
|---|---|
| `NotFound` | 404 |
| `Conflict` | 409 |
| `ValidationError` | 422 |
| `IntegrationError` | 502 |
| `DomainError` | 400 |

## Variaveis de ambiente (.env)

| Variavel | Default | Descricao |
|---|---|---|
| `SERVICE_NAME` | `jwt` | Nome do servico |
| `ENV` | `dev` | dev / staging / prod |
| `LOG_LEVEL` | `INFO` | Nivel de log |
| `PORT` | `80` | Porta HTTP |
| `JWT_ALGORITHM` | `RS256` | Algoritmo de assinatura |
| `JWT_ACCESS_EXPIRE_MINUTES` | `30` | Duracao access token |
| `JWT_REFRESH_EXPIRE_MINUTES` | `1440` | Duracao refresh token |
| `JWT_ISSUER` | `jwt` | Claim `iss` |
| `JWT_AUDIENCE` | `` | Claim `aud` |
| `JWT_PRIVATE_KEY_FILE` | `private.pem` | Arquivo da chave privada |
| `JWT_PUBLIC_KEY_FILE` | `public.pem` | Arquivo da chave publica |
