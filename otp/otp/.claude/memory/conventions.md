# Memória — Convenções de código

## Idioma

- Código, nomes de função e classe: **inglês**.
- Comentários, docstrings, mensagens de erro pro usuário, README e
  documentação interna: **português**.

## Nomes

- Pacotes/módulos: `snake_case`.
- Classes: `PascalCase`.
- Modelos SQLAlchemy: substantivo no singular (`User`, `Order`, não `Users`);
  use `Mapped[...]` + `mapped_column(...)`. `__tablename__` em snake_case.
- Schemas Pydantic: sufixo de intenção — `XCreate`, `XRead`, `XUpdate`.
  Nunca usar o mesmo schema pra entrada e saída. `OTPRead` usa
  `model_config = ConfigDict(from_attributes=True)`.

## Estrutura de uma feature nova

Quando o usuário pede "implementa CRUD de X":
1. `app/models/x.py` → modelo SQLAlchemy (`Base`, `Mapped`, `mapped_column`).
   Se referencia usuário, FK p/ `auth.users.external_id` (UUID).
2. `app/models/__init__.py` → adiciona o import (Alembic enxerga via
   `Base.metadata`).
3. `app/schemas/x.py` → `XCreate`, `XRead`, `XUpdate`.
4. `app/services/x.py` → funções recebem `session: AsyncSession` + lógica/ORM.
   Sem FastAPI aqui.
5. `app/api/x.py` → router; injeta `session = Depends(get_session)`; chama service.
6. `app/api/router.py` → `include_router`.
7. `uv run alembic revision --autogenerate -m "add x"` + `alembic upgrade head`.
8. `tests/test_x.py` → testes com `httpx.AsyncClient` (ver nota de Testes).

## Erros

- Erros de domínio: `app/exceptions.py` (`NotFound`, `Conflict`,
  `RateLimitExceeded`, etc).
- Handler global em `app/main.py` converte pra `JSONResponse`
  (`{code, message}`; rate limit adiciona `retry_after_s` + header `Retry-After`).
- **Nunca** levantar `HTTPException` direto do `services/`.

## Logging

- `structlog` configurado em `app/utils/logging.py`.
- Sempre logar com contexto: `log.info("otp.generated", id=otp_log.id)`.
- **Nunca** logar token, senha, código OTP em texto plano ou body de webhook.

## Async em todo lugar

- Endpoints, services, integrações: tudo `async def`.
- Sessão SQLAlchemy async; `await session.commit()` explícito nos services.

## Testes

- `pytest-asyncio` em modo `auto`.
- **Atenção:** a suíte atual (`tests/test_otp.py`, `test_health.py`) é legada
  (Tortoise/SQLite) e está **toda em skip** via `conftest.py`. Precisa reescrita
  com Postgres real (`testcontainers-postgres`/`pg_tmp`) — ver `MIGRACAO.md`.
- E2E real (sem mock): subir Postgres com schemas `auth`+`otp`, rodar
  `alembic upgrade head`, exercitar via HTTP. Procedimento na seção 6 do
  `MIGRACAO.md`.
