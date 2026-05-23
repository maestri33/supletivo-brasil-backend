# Memória — Convenções de código

## Idioma

- Código, nomes de função e classe: **inglês**.
- Comentários, docstrings, mensagens de erro pro usuário, README e
  documentação interna: **português**.

## Nomes

- Pacotes/módulos: `snake_case`.
- Classes: `PascalCase`.
- Modelos SQLAlchemy 2: substantivo no singular (`Contact`, `Message`, não
  `Contacts`). Estilo `Mapped[...]` + `mapped_column(...)`, herdando de `Base`
  (`app/db.py`). Tabela no schema `notify` (herdado de `Base.metadata`).
  (Antes era Tortoise — migrado em 2026-05-22, ver architecture.md.)
- Schemas Pydantic: sufixo de intenção — `UserCreate`, `UserRead`,
  `UserUpdate`. Nunca usar o mesmo schema pra entrada e saída.

## Estrutura de uma feature nova

Quando o usuário pede "implementa CRUD de X":
1. `app/models/x.py` → modelo SQLAlchemy 2 (`class X(Base)`,
   `Mapped`/`mapped_column`).
2. `app/models/__init__.py` → adiciona o import (necessário para o Alembic
   autogenerate enxergar o modelo via `Base.metadata`).
3. `app/schemas/x.py` → `XCreate`, `XRead`, `XUpdate` (use
   `model_config = {"from_attributes": True}` nos *Read).
4. `app/services/x_service.py` → funções `create_x`, `get_x`, etc., recebendo
   `session: AsyncSession`. Sem FastAPI aqui, só lógica + ORM.
5. `app/api/x.py` → router; endpoints recebem `session = Depends(get_session)`.
6. `app/api/router.py` → `include_router`.
7. **Migration:** `make migrate-new msg='add x'` (Alembic autogenerate) e
   revisar o arquivo gerado em `alembic/versions/`.
8. `tests/test_x.py` → testes com `httpx.AsyncClient` + Postgres real.

## Erros

- Erros de domínio: `app/exceptions.py` (`NotFound`, `Conflict`, etc).
- Handler global em `app/main.py` converte pra HTTPException.
- **Nunca** levantar `HTTPException` direto do `services/`.

## Logging

- `structlog` configurado em `app/utils/logging.py`.
- Sempre logar com contexto: `log.info("user.created", user_id=u.id)`.
- **Nunca** logar token, senha, body completo de webhook.

## Async em todo lugar

- Endpoints, services, integrações: tudo `async def`.
- Sincronizar (`asyncio.to_thread`) só pra lib que não tem versão async.

## Clientes de API externa (`app/integrations/`)

Quando este serviço precisa consumir uma API externa:

1. Adicionar URL e credenciais em `app/config.py` (Settings).
2. Criar `app/integrations/<nome>.py` com uma classe `XxxClient`.
3. O `__init__` recebe `httpx.AsyncClient` (injeção, não cria internamente).
4. Métodos `async def`, usando `request_with_retry` do `http_client.py`.
5. Erros da API externa → `IntegrationError`.
6. Logging via structlog (`log.info("acao", key=value)`).
7. Docstrings em português, detalhando parâmetros e formato de resposta.
8. Registrar em `.claude/memory/integrations.md` com endpoints, auth e
   última verificação.

Exemplo de assinatura:

```python
class FooClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client
        self._base_url = get_settings().foo_api_base_url

    async def do_thing(self, ...) -> dict[str, Any]:
        resp = await request_with_retry(self._client, "POST", ...)
        ...
```

## Testes

- `pytest-asyncio` em modo `auto`.
- Banco de teste: **Postgres real** (não SQLite). O `conftest.py` resolve a
  fonte por: `testcontainers[postgres]` (precisa de docker) **ou**
  `TEST_DATABASE_URL`. Motivo: os modelos usam `PG_UUID`, `JSONB` e schema
  `notify` — nada disso é portável pra SQLite; o shim escondia bugs reais.
- O fixture `engine` cria schemas `auth`+`notify`, popula `auth.users` (shadow)
  e seed `default`; `_clean_between_tests` trunca tabelas mutáveis entre testes.
- Use o fixture `make_auth_user` para satisfazer a FK ao criar `Contact`.
- Só o **IO externo** é isolado (WhatsApp/DNS/SMTP/Mailcow/DeepSeek); o banco
  é sempre real.
- Rodar local: `docker run -d -p 5544:5432 -e POSTGRES_USER=test
  -e POSTGRES_PASSWORD=test -e POSTGRES_DB=test postgres:16-alpine` e
  `TEST_DATABASE_URL=postgresql+asyncpg://test:test@localhost:5544/test uv run pytest`.
