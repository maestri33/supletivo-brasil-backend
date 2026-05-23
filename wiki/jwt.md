# jwt

## Função

Emite, renova e publica tokens JWT assinados com RS256. É o único serviço autorizado a assinar tokens na plataforma; não persiste nenhum dado em banco.

## Status

**Pronto** — os 3 endpoints de negócio estão implementados e funcionais, sem banco (sem Alembic, sem models), sem testes automatizados (diretório `tests/` ausente). Operacional para uso em DMZ.

## Estrutura

**Aninhado — desvio da convenção.** O pacote está em `jwt/jwt/app/` em vez de `jwt/app/`. A CONVENTION.md proíbe explicitamente `servico/servico/app`.

```
backend/jwt/
└── jwt/                  ← aninhamento proibido
    ├── app/
    │   ├── main.py
    │   ├── config.py
    │   ├── exceptions.py
    │   ├── stats.py
    │   ├── api/           ✅ pasta (health.py, tokens.py, router.py)
    │   ├── schemas/       ✅ pasta (jwt_config.py)
    │   ├── services/      ✅ pasta (jwt_service.py, key_service.py, token_service.py)
    │   └── utils/         ✅ pasta (logging.py)
    ├── private.pem        ⚠ chave privada em disco, fora de secrets manager
    ├── public.pem
    └── pyproject.toml
```

Ausentes (esperados pela convenção): `models/`, `integrations/`, `alembic/`, `tests/`, `README.md`, `CLAUDE.md`.

## Endpoints

### `api/health.py`

| Método | Rota | Descrição | Tipo |
|--------|------|-----------|------|
| GET | `/` | Dashboard completo: uptime, stats, config, system info | desmilitarizado |
| GET | `/health` | Liveness check simples | desmilitarizado |
| GET | `/ready` | Readiness check simples | desmilitarizado |
| GET | `/status` | Resumo de runtime (alias enxuto) | desmilitarizado |

### `api/tokens.py`

| Método | Rota | Descrição | Tipo |
|--------|------|-----------|------|
| POST | `/api/v1/tokens/issue` | Emite par access+refresh a partir de `external_id` + `roles` | desmilitarizado |
| POST | `/api/v1/tokens/refresh` | Renova tokens a partir de refresh token válido | desmilitarizado |
| GET | `/.well-known/jwks.json` | Publica chave pública RSA em formato JWKS (RFC 7517) | público |

## Dados

**Sem banco de dados.** Nenhuma tabela, nenhuma migração Alembic, nenhum schema Postgres.

- Chaves RSA lidas de arquivos `.pem` em disco (`private.pem`, `public.pem`).
- Geração automática do par RSA no boot se os arquivos não existirem.
- Contadores de uso (`tokens_issued`, `tokens_refreshed`, `jwks_fetches`, `errors`) mantidos em memória — zerados no restart.
- Algoritmo padrão: RS256. Expiração: access 30 min, refresh 1440 min (configurável via `.env`).

## Integrações

**Nenhuma.** O serviço é totalmente autônomo:
- Não chama outros serviços via httpx.
- Não consome nem publica eventos.
- Dependências externas: apenas `pyjwt[crypto]` + `cryptography` para operações criptográficas locais.

## Pendências

### Arquivo TODO
Não existe arquivo `TODO` no serviço.

### TODOs no código
Nenhum `TODO`/`FIXME` encontrado no código.

### Desvios da CONVENTION.md

| # | Desvio | Gravidade |
|---|--------|-----------|
| 1 | **Aninhamento `jwt/jwt/app`** — convenção exige `jwt/app` | ❌ bloqueia |
| 2 | **Sem testes** — diretório `tests/` ausente; pytest configurado mas sem nenhum teste | ❌ bloqueia |
| 3 | **`private.pem` em disco** — chave privada RSA versionada junto ao código (consta no repo); risco de segurança | ❌ bloqueia |
| 4 | **`target-version = "py310"`** em `pyproject.toml` — convenção exige `py312` | ⚠ ajustar |
| 5 | **Sem `README.md`** — convenção exige README com descrição, como rodar e variáveis de env | ⚠ ajustar |
| 6 | **Sem `CLAUDE.md`** — particularidades do serviço não documentadas | ⚠ ajustar |
| 7 | **`requires-python = ">=3.10"`** — convenção define Python 3.12 como mínimo | ⚠ ajustar |
| 8 | **`hatchling` ausente** — convenção define `hatchling` como build backend; `pyproject.toml` usa `setuptools` implicitamente | ⚠ ajustar |
| 9 | **`httpx` não listado em dependências** — convenção exige na stack mesmo sem uso atual | ℹ observação |
| 10 | **Sem `asyncpg`/SQLAlchemy** — esperado pela stack canônica, mas justificado pois serviço não tem banco | ✅ aceitável |
