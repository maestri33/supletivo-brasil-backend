# Convenções — asaas

> Específicas deste serviço. As gerais estão em `CONVENTION.md`.

## Idioma (§7)
- Identificadores em **inglês**; docstrings/comentários em **pt-br** e
  **verdadeiros**. Erros de domínio ao cliente em pt-br; logs técnicos
  (structlog) em inglês.

## Chave primária e UUID
- PK `postgresql.UUID(as_uuid=False)`, gerada na app (`default=lambda:
  str(uuid4())`) em customer/payment/pix_key/webhook_event.
- `config` e `url_verify_nonce` mantêm **PK String** (a chave natural é
  `key`/`nonce`).
- Em Postgres a coluna UUID é `uuid`; `as_uuid` só muda o tipo no Python.

## Ordenação (importante — pós-UUID)
- `created_at`/`validated_at` **não são únicos**; ordenar paginação/FIFO só por
  eles deixa empates indefinidos (drift de paginação; FIFO não-determinístico no
  money-path).
- **Sempre** desempate por `id`, na mesma direção:
  `order_by(Model.created_at.desc(), Model.id.desc())`. Vale também para o
  `tick()` do worker (`created_at.asc(), id.asc()`). Commit `93bde73`;
  regressão em `tests/test_list_ordering.py`.

## Datas
- `DateTime(timezone=True)` (timestamptz); default via `utcnow()` de `app/db.py`
  (aware, UTC). Nunca `datetime.utcnow()` naive.

## Config
- Operacional (API key, URLs, wallet, token) vive na tabela `asaas.config` via
  `config_store` (`cfg.set_/get`). O `.env` só faz bootstrap (`_seed_from_env`).
- Settings de processo (`config.py`) só para o que não muda em runtime
  (`ASAAS_BASE_URL`, `ASAAS_ALLOW_SANDBOX`, TTLs). Nunca `os.environ` fora de
  `config.py`.

## Erros & idempotência
- Erros de domínio com código estável (ex.: `invalid_amount`, `not_found`,
  `payment_id_already_exists`) — ver tabela no `README.md`.
- **Payout idempotente:** `asaas_id` commitado antes de confirmar o efeito
  externo; reprocessar não duplica (BLOQUEIO §15).

## Logs
- `structlog`. Sem `print`/`logging` cru. Não logar segredo (API key, token) nem
  payload sensível.

## Lint & testes
- `ruff` (`line-length=100`, `py312`). `ruff check app tests` limpo antes de
  concluir.
- `pytest` + `pytest-asyncio` (`asyncio_mode="auto"`). DB de teste
  `sqlite+aiosqlite`; conftest define `ASAAS_APP_DB_URL` e `DATABASE_SCHEMA=""`
  **antes** de importar `app.*`, zera `schema` nas tabelas e recria
  (drop+create) por teste. Worker vira no-op; `AsaasClient` é stubbado via
  `fake_asaas`. 190 testes verdes.
