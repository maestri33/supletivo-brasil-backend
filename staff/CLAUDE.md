# CLAUDE.md — staff (boss da operação)

Particularidades do serviço `staff` que complementam CONVENTION.md da raiz.

## Papel

Staff é o serviço administrativo da plataforma. Não tem entidades de domínio próprias (milestone 1) — atua como proxy autenticado que delega operações de domínio ao serviço dono (`hub` para polos, `coordinator` quando existir).

## Auth gate

- JWT RS256 obrigatório em toda rota autenticada.
- JWKS cacheado por 5 min (`get_jwks()` em `app/dependencies.py`).
- Roles exigidas: `admin` ou `staff` (configurável via `STAFF_ROLES`).
- `JWT_BASE_URL` aponta para o serviço `jwt` (ex.: `http://jwt:80`).

## Integrações

- **Hub:** `app/integrations/hub.py` — `HubClient` via httpx. Cria, lista, busca hubs e define coordenador. Timeout configurável (`HTTP_TIMEOUT`).
- **Comunicação com hub:** chama endpoints autenticados do hub. O staff NÃO repassa o JWT do usuário — o hub confia no staff (desmilitarizado). Se isso mudar, ajustar `HubClient._request`.

## Config

- `case_sensitive=True` no Settings. Todas as env vars em UPPER_CASE.
- `DATABASE_URL` obrigatório. `DATABASE_SCHEMA` default `staff`.
- Schema staff existe mesmo sem modelos (milestone 1) — o alembic cria o schema vazio.

## Alembic

- `alembic/env.py` configurado com `target_metadata = Base.metadata`.
- Versões em `alembic/versions/`. Migração inicial cria schema `staff` mesmo sem tabelas (placeholder para milestones 4/5).

## Testes

- JWT_BASE_URL deve ser definido para os testes (`.env` ou monkeypatch).
- Conftest usa ASGITransport sem DB no milestone 1.
- Teste de auth gate: sem token → 403, token inválido → 401.
