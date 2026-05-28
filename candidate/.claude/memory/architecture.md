# Arquitetura — candidate

## 2026-05-24 — Reescrita Fase A+B (Tortoise/SQLite → stack canônica)
- Migrado de **Tortoise ORM + SQLite** para **SQLAlchemy 2.0 async + asyncpg +
  Postgres (schema `candidate`) + Alembic**. Estrutura achatada para `app/`,
  `routers/`→`api/`, `models.py`/`schemas.py`→pastas, criados `db.py`,
  `services/`, `exceptions.py`, `utils/logging.py`, `pyproject.toml`.
- **Orquestrador, não dono de dados.** O candidate guarda apenas o estado do
  funil (tabela `candidates`); perfil/endereço/documentos/PIX/papéis vivem nos
  serviços donos e são acessados por HTTP. Removidos `Checkout` e `Message`
  (cópia morta do lead — candidate não tem pagamento).
- **Máquina de status** (sequencial, gate em `dependencies.py`):
  captured→personal→education→birth→address→documents→pixkey→selfie→completed.
  `services/candidate.advance(current→next)` só avança se estiver exatamente em
  `current` (idempotente). Corrigido o bug do fluxo antigo que pulava `address`.
- **Transação por request:** services mutam a session; o endpoint dá `commit`
  após o sucesso das integrações. Falha de integração (httpx 4xx/5xx) propaga e
  o `get_session` faz rollback.
- **PK/UUID:** `id` UUID (default uuid4) + `external_id` UUID unique (ref. lógica
  a `auth.users`, **sem FK** — mesma escolha do asaas). Colunas UUID usam
  `PG_UUID(as_uuid=False).with_variant(String(36), "sqlite")`: o sqlite dá
  afinidade NUMERIC ao tipo UUID e converteria uuid all-zeros em inteiro 0,
  quebrando a leitura nos testes — o variant força TEXT no sqlite.
- **Conclusão:** promove papel lead→training via `roles` e encerra em `completed`.
  Criar registro no serviço `training` fica pendente (serviço ainda não existe;
  não inventar API — §2).
- **Selfie:** validação heurística via `ai`/vision (descreve a imagem; barra foto
  sem pessoa). Não é liveness; falha do ai não bloqueia o funil.
