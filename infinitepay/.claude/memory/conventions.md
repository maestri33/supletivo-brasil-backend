# Convenções — infinitepay

> Convenções específicas deste serviço. As gerais estão em `CONVENTION.md`.

## Idioma (§7)
- Identificadores (variáveis, funções, classes, tabelas, colunas, rotas) em
  **inglês**.
- Docstrings e comentários em **pt-br** e **verdadeiros** (descrevem o que o
  código faz hoje). Comentário desatualizado é defeito: corrija ou apague.
- Erros de domínio voltados ao cliente: pt-br. Logs técnicos (structlog): inglês.

## Chave primária e UUID
- PK sempre `postgresql.UUID(as_uuid=False)`, gerada na app:
  `default=lambda: str(uuid4())`. Não usar autoincrement.
- Em Postgres a coluna é `uuid`; a flag `as_uuid` só muda o tipo no Python
  (usamos `str`). Os models usam `as_uuid=False`; nas migrações o tipo gerado é
  o mesmo `uuid` (a flag não muda a DDL).

## Ordenação (importante — pós-UUID)
- `created_at` **não é único**; ordenar paginação/FIFO só por ele deixa empates
  sem ordem definida (drift de paginação, FIFO não-determinístico).
- **Sempre** adicione `id` como critério de desempate, na mesma direção:
  `order_by(Model.created_at.desc(), Model.id.desc())`. Estabelecido no commit
  `93bde73`.

## Datas
- Colunas de data/hora são `DateTime(timezone=True)` (timestamptz). Default via
  `utcnow()` de `app/db.py` (aware, UTC). Nunca `datetime.utcnow()` (naive).

## Config
- Toda config vem de `app/config.py::Settings` (pydantic-settings, `@lru_cache`
  em `get_settings()`). **Nunca** ler `os.environ` fora do `config.py`.
- Não há config em banco. Defaults da loja para `POST /checkout` vêm das envs
  `INFINITEPAY_*`.

## Erros
- Exceções de domínio herdam de `DomainError` (`app/exceptions.py`):
  `Conflict`, `NotFound`, `ValidationError`, `IntegrationError`. Rota traduz
  para HTTP; mensagem ao cliente em pt-br.

## Logs
- `structlog.get_logger("infinitepay")`. Sem `print`/`logging` cru. Não logar
  segredo nem payload sensível.

## Lint
- `ruff` com `line-length = 100`, `target-version = py312`, regras
  `E,F,I,B,UP,N,ASYNC`. Ignorados conscientes: `B008` (`Depends()` é o padrão
  FastAPI), `N818` (nomes `*Error` do domínio). `ruff check` limpo antes de
  concluir qualquer alteração.

## Testes
- `pytest` + `pytest-asyncio` (`asyncio_mode="auto"`). DB de teste é
  `sqlite+aiosqlite` (conftest define `DATABASE_URL` e `DATABASE_SCHEMA=""`
  **antes** de importar `app.*`); o schema é criado via
  `Base.metadata.create_all` (não Alembic). `postgresql.UUID` compila em SQLite
  por fallback. 20 testes hoje, todos verdes.
