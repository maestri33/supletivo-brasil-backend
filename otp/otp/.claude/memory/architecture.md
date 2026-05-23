# Memória — Arquitetura

## Forma deste serviço

- Um único processo Uvicorn na porta **8000**.
- Banco: **PostgreSQL central** (asyncpg), schema **`otp`**. Cada modelo tem
  `external_id` UUID com **FK para `auth.users.external_id`** (cross-schema).
- Tasks de fundo no lifespan: `queue_loop` (retry do notify) e `cleanup_loop`
  (purga de logs antigos).
- Comunicação externa: HTTP via `app/integrations/http_client.py`.
- Única integração ativa: **notify** (envio de mensagens).

## Princípios

1. **Service-per-database.** Acoplamento via API, nunca via SQL. Exceção
   controlada: FK read-only para `auth.users` (tabela-sombra em `app/db.py`).
2. **Camadas finas.** `api/` → `services/` → `models/`. Router injeta
   `AsyncSession` via `Depends(get_session)` e passa pro service.
3. **Configuração via env.** Sem banco pra config — tudo no `.env`.
4. **Erros explícitos.** Exceptions de domínio em `app/exceptions.py`,
   convertidas pra `JSONResponse` no handler global (`main.py`).

## Histórico de decisões

### 2026-05-15 — Migração de stack: Tortoise/SQLite → SQLAlchemy 2/Postgres
- **Decisão:** Trocar Tortoise ORM + Aerich + SQLite por **SQLAlchemy 2 (async)
  + Alembic + PostgreSQL** (schema `otp`, FK p/ `auth.users`). `external_id`
  vira `UUID`.
- **Junto vieram:** rate limit por `external_id` (`services/rate_limit.py`),
  cleanup automático (`services/cleanup.py`), colunas `attempts`/`failure_reason`
  em `otp_logs`, e métricas no `/status`.
- **Consequência:** suíte de testes legada (Tortoise/SQLite) ficou em `skip`
  aguardando reescrita; ver `MIGRACAO.md` na raiz.

### 2026-05-09 — Simplificação: config no env, remoção de boilerplate
- **Decisão:** Remover OTPConfig do banco e mover tudo pra `.env`. Remover Redis,
  RabbitMQ e workers (não usados).
- **Por quê:** Menos peças móveis, serviço mais enxuto e previsível.
- **Consequência:** Para alterar config é preciso restart do serviço.

### 2026-05-02 — Bootstrap inicial
- **Decisão (superada em 2026-05-15):** SQLite como default, Postgres opcional.
