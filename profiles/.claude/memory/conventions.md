# Convenções — profiles

> Especializa `../CONVENTION.md`. Só registra o que é específico daqui.

## Código
- Identificadores em inglês; docstrings/comentários em pt-br e **verdadeiros**.
- `import` sempre no topo do módulo (sem import dentro de função).
- Endpoint fino: `api/` valida → chama `services/` → devolve `schemas/`.
- Erros de domínio via `app.exceptions` (`Conflict` 409, `NotFound` 404,
  `ValidationError` 422), nunca `HTTPException` cru no service.
- Logs via `structlog` (`app.utils.logging.get_logger`). **Nunca logar PII**
  (CPF/nome) — no enriquecimento CPFHub loga-se só `type(exc).__name__`.

## Banco / migrações
- 1 arquivo por entidade em `models/`. Toda mudança de modelo → migração Alembic
  (`make migrate-new msg='...'`); aplicar com `make migrate`.
- Migração com revision string curta (`0001`, `0002`, `0003`) e
  `down_revision` encadeado. DDL específico (trigger) é `op.execute(...)` com
  `downgrade` simétrico (`DROP ... IF EXISTS`).
- Naming convention de constraints copiada em `db.py` — os mappers de erro em
  `profile_service._classify_integrity_error` dependem desses nomes
  (`profiles_cpf_key`, `profiles_external_id_key`, `profiles_external_id_fkey`).

## Identidade / CPF
- profiles é o **dono** de CPF na plataforma; `auth` delega a profiles.
  Mantemos `validators/cpf.py` aqui — não é duplicação a ser removida.

## Qualidade
- `ruff check` + `ruff format` limpos antes de concluir.
- Teste para todo comportamento novo (`tests/`, pytest-asyncio `asyncio_mode=auto`).
