# roles — Adequação à convenção + regras no `.env`

## Problem
O serviço `roles` (motor de transição de papéis do pipeline v7m) está fora do padrão da `CONVENTION.md` e não cumpre seu `TODO`: as 7 regras de transição estão **hardcoded** em `main.py`, o serviço usa `logging` cru em vez de `structlog`, expõe endpoints duplicados e **não tem testes**. O custo de deixar assim: regra de negócio enterrada no código (não versionável por config), serviço inconsistente com os demais (asaas/infinitepay já adequados) e sem rede de segurança para mexer no caminho de papéis — que é base de auth, candidate e todo o pipeline.

## Evidence
- `roles/TODO`: *"Se houver como mudarmos as funcoes fixas para .env ao invés de DB eu fico grato"*.
- Auditoria em `wiki/roles.md` (parcialmente desatualizada — ver abaixo).
- `grep`/inspeção do estado atual (2026-05-25):
  - `app/main.py:24-31` — array `SEEDS` com 7 regras hardcoded, semeadas no startup (`_seed_if_empty`).
  - `app/main.py:3,20` — `import logging` + `logging.getLogger("roles")` (não `structlog`).
  - `app/api/users.py` — `GET /api/v1/users` e `DELETE /api/v1/users/{id}` duplicam exatamente `app/api/role.py`.
  - Sem diretório `tests/`.
  - `pyproject.toml` sem `structlog`.
- **Correções ao wiki/roles.md (estava stale):** estrutura **já achatada** (`roles/app`, não `roles/roles/app`); `pyproject` **já async** (sqlalchemy[asyncio] + asyncpg + alembic + hatchling); arquivos `data/*.db` **gitignored e não versionados** (`git ls-files` vazio) — não são violação de repo, só clutter local.

## Users
- **Primary**: a plataforma v7m — consumidores internos do serviço via HTTP, hoje `auth` (register, /atomic, integrations/roles) e `candidate` (promote/get_roles). O operador/dev (Victor) que mantém o catálogo de regras.
- **Not for**: usuários finais. Todos os endpoints são desmilitarizados (internos, sem JWT).

## Hypothesis
Acreditamos que **adequar `roles` à convenção e tornar as regras de transição configuração de `.env`** vai **padronizar o serviço, versionar a regra de negócio em config e dar cobertura de testes** para **a plataforma v7m e quem mantém o catálogo de papéis**.
Saberemos que acertamos quando: as regras vierem do `.env` (zero hardcode em `main.py`), o serviço usar só `structlog`, não houver endpoint duplicado, a suíte de testes cobrir os fluxos de papel e `ruff`/§15 fecharem — **sem quebrar os consumidores `auth`/`candidate`**.

## Success Metrics
| Metric | Target | How measured |
|---|---|---|
| Regras hardcoded em `main.py` | 0 (vêm do `.env`) | grep `SEEDS`/regras em `app/` |
| Uso de `logging` cru | 0 | grep `import logging`/`getLogger` em `app/` |
| Endpoints duplicados | 0 | rotas distintas em `app/api/` |
| Cobertura comportamental | fluxos assign / promote(up) / blocked / list / delete verdes | `pytest -q` |
| `ruff check` + `ruff format` | limpos | CI local |
| Contratos consumidos por `auth`/`candidate` | preservados (GET de regras e de papéis seguem respondendo) | testes + grep cross-service |

## Scope
**MVP** — Deixar `roles` aderente à convenção mantendo os contratos de leitura que `auth`/`candidate` consomem:
1. `structlog` substitui `logging` cru (config canônica, JSON em prod).
2. Regras de transição passam a viver no `.env` (fonte de verdade em runtime); `main.py` deixa de ter `SEEDS` hardcoded.
3. Endpoints de **escrita** de regras (`POST/PATCH/DELETE /api/v1/config/roles`) saem (não dá pra editar `.env` em runtime); **leitura** (`GET /api/v1/config/roles[/{id}]`) **permanece**, agora servindo as regras derivadas do `.env` — preserva `auth/register.py` e `auth/integrations/roles.py`.
4. `users.py` removido; `/api/v1/role` vira o canônico para list/delete.
5. Suíte de testes (§15) cobrindo os fluxos de papel.
6. `wiki/roles.md` reescrito (estado real) + `.claude/` do serviço; limpeza dos `data/*.db` locais.

**Out of scope**
- **Notificações `notify` (§11)** — adiado; registrar como débito no wiki. (Evita acoplar `roles` ao `notify`, que está quebrado.)
- **Mudanças em `auth`** (`atomic.py` apontar de `/api/v1/users` → `/api/v1/role`; remover método `get_rule` do client se necessário; ajustar `auth/tests`) — pertencem a um **PR coordenado no `auth`**, não a este escopo (1 app = 1 PR).
- **Reescrita do `/atomic`** e dedup de identidade — já listados como débito separado no `PLANO_ADEQUACAO` (Fase 4).
- `httpx` no `roles` — só seria necessário com a integração `notify` (fora de escopo).

## Delivery Milestones
<!-- Business outcomes, not engineering tasks. /plan turns each into a plan. -->

| # | Milestone | Outcome | Status | Plan |
|---|---|---|---|---|
| 1 | Logging canônico | `roles` emite logs `structlog` (JSON em prod); zero `logging` cru | pending | — |
| 2 | Regras no `.env` | Catálogo de transições vem do `.env`; `main.py` sem `SEEDS`; `GET /config/roles` segue respondendo (derivado do `.env`) | pending | — |
| 3 | Remoção de duplicação | `users.py` removido; escrita de regras removida; só rotas canônicas restam | pending | — |
| 4 | Rede de segurança | Suíte `pytest` cobre assign / promote / blocked / list / delete; `ruff` limpo | pending | — |
| 5 | Documentação §15 | `wiki/roles.md` reflete o estado real; `.claude/` do serviço criado; `data/*.db` locais limpos | pending | — |

## Open Questions
- [ ] **Formato das regras no `.env`**: uma var com JSON (ex.: `ROLE_RULES=[{...}]`) vs múltiplas vars? Validar legibilidade x parsing.
- [ ] **Lista de papéis válidos**: também vai pro `.env` (validação de nomes) ou deriva das próprias regras?
- [ ] **Compatibilidade com `auth`**: manter `GET /config/roles` read-only resolve `register.py`. Confirmar que `auth/integrations/roles.py:get_rule` (`GET /config/roles/{id}`) basta como leitura; e agendar o ajuste de `auth/atomic.py` (`/users` → `/role`) no PR do `auth`.
- [ ] **`requires_role`/`forbids_role`/`blocking`** continuam expressos no `.env`? (hoje só `requires_role` aparece nos seeds; `forbids_role`/`blocking` existem no schema).

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Remover escrita de `/config/roles` e `/users` quebra `auth` | Alta | Alto | Manter contratos **GET** (`/config/roles`, `/role`); ajustes de escrita/`/atomic` no `auth` em PR coordenado |
| Perda da edição de regras em runtime (eram CRUD no DB) | Média | Médio | Era o pedido explícito do `TODO` (`.env` como fonte); mudança de regra passa a ser deploy/config |
| Testes exigem Postgres | Baixa | Baixo | Espelhar conftest async sqlite (`aiosqlite`) usado por asaas/infinitepay |
| `.env` com JSON malformado derruba o boot | Média | Médio | Validar/parsear via `pydantic-settings` com erro claro no startup |

---
*Status: DRAFT — requirements only. Implementation planning pending via /plan.*
