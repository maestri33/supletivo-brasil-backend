# Convenções locais — fees

> Particularidades deste serviço. A geral é `../CONVENTION.md`.

- **PK = UUID** `postgresql.UUID(as_uuid=False)` gerada na app (`uuid4`) — string;
  cai para CHAR no sqlite (testes sem Postgres).
- **Datas/hora = `timestamptz`** (`DateTime(timezone=True)`), default `utcnow`
  (aware, UTC) — `asyncpg` recusa naive.
- **Sem FK cross-schema**; referências por valor. `external_id` opaco.
- **Status como `String`** (não Enum no DB) — portável e simples. Os valores
  válidos vivem em `FeeStatus` (Python) e no espelho de payout do asaas.
- **Ordenação FIFO/paginada:** sempre `order_by(created_at.desc(), id.desc())`
  (desempate por `id`; nunca só `created_at`).
- **Idioma:** identificadores em inglês; docstrings/comentários em pt-br e
  verdadeiros; mensagens de erro de domínio ao cliente em pt-br; logs em inglês.
- **Erros de domínio:** `DomainError` (+ NotFound/Conflict/ValidationError);
  handler global em `main.py` → `{"detail", "code"}`.
- **Config:** `.env` puro (pydantic-settings), `database_url` **obrigatório**
  (sem default com credenciais). Não há config operacional em DB (≠ asaas).
- **Logs:** structlog via `fastapi-structured-logging` (setup no `main.py`).
