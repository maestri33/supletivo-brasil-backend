# Estratégia de variáveis de ambiente

Centralizada em **2026-05-27**.

## Onde vive cada coisa

| Tipo                                          | Local                                  |
|-----------------------------------------------|----------------------------------------|
| Secrets (API keys, passwords)                 | `/backend/.env` (raiz)                 |
| URLs internas, defaults, timeouts             | `docker-compose.dev.yml` (anchors)     |
| `DATABASE_SCHEMA` por serviço                 | inline em cada bloco `environment:`    |
| Templates                                     | `.env.example`, `.env.prod.example`    |

## Como funciona no compose

Cada microsserviço:
```yaml
foo:
  env_file: .env          # ← injeta TODOS os secrets de uma vez
  environment:
    <<: [*common-env, *postgres-url, *service-urls]   # ← config compartilhada
    DATABASE_SCHEMA: foo                                # ← schema próprio
    # ... config específica do serviço
```

Os YAML anchors estão no topo do `docker-compose.dev.yml`:
- `&common-env`: `ENV`, `LOG_LEVEL`, `REDIS_URL`, `HTTP_TIMEOUT`, `CORS_ORIGINS`
- `&postgres-url`: `DATABASE_URL` apontando para o container `postgres:5432`
- `&service-urls`: todas as URLs `http://<service>:8000` da network do compose
- `&healthcheck`: padrão `curl /health` na porta interna 8000
- `&deps-pg-redis`: depende de postgres healthy + redis started

## Arquivos `.env.local-e2e` (per-módulo)

Antes existiam `lead/.env`, `ai/.env`, etc. Eram para **testes E2E locais** (pytest rodando fora do compose, contra um Postgres dedicado na porta 5544+). Renomeados para `<modulo>/.env.local-e2e` para deixar claro que **não são carregados pelo compose**.

Se quiser rodar testes E2E locais, copie de volta:
```sh
cp lead/.env.local-e2e lead/.env
cd lead && pytest tests/
```

## Adicionar um secret novo

1. Adicionar ao `/backend/.env` (com comentário explicando uso)
2. Adicionar ao `/backend/.env.example` (sem valor real)
3. `env_file: .env` já está em todos os services — não precisa repetir
4. `docker compose -f docker-compose.dev.yml up -d --force-recreate <service>`

## Adicionar uma URL interna nova

1. Editar `x-service-urls:` no topo do `docker-compose.dev.yml`
2. Restart de todos os serviços que usam o anchor: `docker compose -f docker-compose.dev.yml up -d --force-recreate`
