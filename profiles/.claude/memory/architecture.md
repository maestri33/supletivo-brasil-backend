# Arquitetura — profiles

## Decisões

### 2026-05-24 — Adequação §15 à CONVENTION
- **`DATABASE_URL` obrigatório:** removido o default hardcoded
  `postgresql+asyncpg://v7m:v7m@...` de `config.py` (mesmo problema da Fase 1
  do `otp`). Sem `.env` o serviço não sobe — evita credencial em código.
- **`updated_at` por trigger (migração `0003`):** além do `onupdate=func.now()`
  no ORM (que só cobre escritas via SQLAlchemy), foi criada função
  `profiles.set_updated_at()` + trigger `BEFORE UPDATE` em `profiles.profiles`,
  garantindo o campo correto também em UPDATE por SQL direto.
- **`alembic/env.py` cria o schema:** `CREATE SCHEMA IF NOT EXISTS "profiles"`
  antes das migrações (espelha o `asaas`), para `alembic upgrade head` funcionar
  em Postgres limpo.
- **Makefile corrigido:** alvos vinham do template Tortoise — `migrate` usava
  `aerich` (trocado por `alembic upgrade head`) e `lint` chamava `mypy` (não é
  dependência; removido).

## Forma geral
- FastAPI com `lifespan` (startup/shutdown) e handler único de `DomainError`
  → JSON `{code, message}` com `status_code` do domínio.
- Camadas: `api/` (rota fina) → `services/` (negócio) → `models/` (ORM).
  `schemas/` (Pydantic v2) na borda; `validators/` para regras de domínio.
- Criação de perfil é **atômica e otimista**: sem SELECT prévio; confia em
  UNIQUE (`cpf`, `external_id`) e FK cross-schema, e mapeia `IntegrityError`
  para 409/422 (`_classify_integrity_error`).

## Dados
- Schema `profiles`; 3 tabelas (`profiles` raiz + `birth_info` + `educational`
  1-1 CASCADE). PK serial; `external_id` UUID é a chave cross-service.
- FK cross-schema para `auth.users` via **shadow table** read-only em `db.py`.
