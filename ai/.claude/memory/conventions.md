# Convenções — Serviço AI

## Nomenclatura
- Arquivos: snake_case
- Classes: PascalCase
- Funções: snake_case
- Endpoints: plural quando coleção (/text/, /image/)

## Padrão de cliente HTTP
- Toda chamada externa usa `request_with_retry` (exceto SDKs que gerenciam seu próprio HTTP)
- Todo cliente recebe `httpx.AsyncClient` via `__init__`
- Erros de serviço externo levantam `IntegrationError`

## Logs
- structlog, nível INFO em prod
- Formato: `modulo.acao`, com kwargs descritivos
- NUNCA logar API keys ou tokens

## Schemas
- Request/Response via Pydantic `BaseModel`
- Nomes: `XxxRequest`, `XxxResponse`
- v0 (legado): schemas inline nos endpoints, sem envelope
- v1 (novo): schemas em `app/api/schemas.py`, envelope `APIResponse[T]` genérico

## Endpoints
- Rotas SEM prefixo nos routers individuais (`router = APIRouter(tags=[...])`)
- Prefixos definidos exclusivamente em `router.py` via `include_router(prefix=...)`
- Cada router incluso DUAS vezes: canonical `/api/v1/...` + alias legacy
- Novos endpoints vão em `app/api/v1.py`

## Idioma
- Código, comentários, docstrings: PT-BR com acentuação

## Configuração
- Todas as configs em `.env` (pydantic-settings)
- `.env.example` documenta cada variável com justificativa
- Defaults no `config.py` refletem produção
