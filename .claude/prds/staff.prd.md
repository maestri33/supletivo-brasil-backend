# Staff — Serviço de Administração (Boss da Operação)

> Serviço: `staff/` · Schema: `staff` · Convenção: `CONVENTION.md`
> Status: Milestone 1 implementado (scaffolding + auth gate + health aggregation on-demand).
> Milestones 2-5 (health agendada, gestão de hub completa, definição de coordenador) pendentes.

---

## 1. Contexto de Negócio

A plataforma é um conjunto de microsserviços independentes (lead, candidate, hub, coordinator, etc.), mas **não existe uma camada central de operação**. Hoje não há:

- (a) Um lugar único para ver a saúde de todos os serviços.
- (b) Uma autoridade única para cadastrar polos (hubs) e definir seus coordenadores.

O módulo `staff` é o **"boss" da operação**: atua como camada administrativa que centraliza o gerenciamento de polos, a definição de coordenadores e a agregação de health checks de toda a plataforma. Todas as chamadas autenticadas exigem JWT RS256 com role `admin` ou `staff`.

**Estado atual (Milestone 1):** O serviço está **implementado** com scaffolding completo:
- Health/readiness/status próprios (`/health`, `/ready`, `/status`).
- Auth gate JWT RS256 com verificação de role via JWKS (cache 5 min).
- Endpoints autenticados de hubs delegados ao serviço `hub` via httpx (`HubClient`).
- Endpoint de health aggregation on-demand (`/api/v1/health/aggregate`).
- Rate limiting (slowapi, 200 req/min), CORS, métricas Prometheus.
- Schema `staff` criado no Postgres (placeholder, sem tabelas de domínio ainda).

**Gap:** A saúde agregada é on-demand (fan-out síncrono). Não há polling agendado nem histórico de status. A gestão de hubs depende totalmente do serviço `hub` (o staff é um proxy autenticado). Marcas (Estácio/Wyden) são strings livres sem validação de enum.

## 2. Atores

| Ator | Role | Ação |
|------|------|------|
| **Operador staff/admin** | `admin` ou `staff` (JWT) | Autentica e gerencia polos, atribui coordenadores, consulta saúde dos serviços |
| **Serviço hub** | Serviço downstream (desmilitarizado) | Recebe chamadas HTTP do staff para CRUD de hubs e definição de coordenador |
| **Serviço jwt** | Serviço de autenticação | Fornece JWKS para validação de tokens RS256 |
| **Serviços monitorados** (hub, lead, etc.) | Cada serviço com `/health` | Respondem ao health check individual quando o staff faz fan-out |

**Nota:** O coordenador do polo não interage diretamente com o staff — suas funções operacionais pertencem ao serviço `coordinator/`. O staff apenas **define** quem é o coordenador de um polo (delegando ao `hub`).

## 3. Estados / Máquina de Estados

### Hub (delegado ao serviço `hub`)

O staff **não mantém estado de hub próprio**. Ele é um proxy autenticado que delega ao serviço `hub`. Os estados de hub existem no `hub/` e são:

```
UNKNOWN → ACTIVE → INACTIVE
```

O staff apenas repassa operações (criar, listar, buscar, definir coordenador).

### Health Aggregation (on-demand)

Não há máquina de estados formal. O fluxo é:

```
Request autenticado → Fan-out paralelo (httpx, timeout 5s por serviço) → Agregado {services, all_ok}
```

Cada serviço é verificado individualmente. Falha/timeout devolve `status: "down"` para aquele serviço (tolerante a falha).

### Health Aggregation (agendada — PLANEJADO)

```
Polling periódico → Grava status no Postgres → Endpoint lê histórico/uptime
```

**Status planejados para health history:**

| Status | Significado |
|--------|-------------|
| `ok` | Serviço respondeu `/health` com sucesso |
| `down` | Serviço não respondeu ou retornou erro |
| `degraded` | Serviço respondeu mas com indicadores parciais (ex: DB fora) |

## 4. Entidades & Campos

### Schema `staff`

#### Milestone 1 (implementado) — Sem tabelas de domínio

O schema `staff` existe no Postgres como placeholder. Nenhuma tabela de domínio foi criada ainda — o staff atua como proxy que delega ao `hub`.

#### (PLANEJADO) `hubs` — Shadow table / cache de polos

Se a decisão for manter dados de hub no staff (vs. consultar sempre o `hub`):

| Coluna | Tipo | Nullable | Default | FK / Índice | Descrição |
|--------|------|----------|---------|-------------|-----------|
| `id` | `UUID` PK | NOT NULL | `uuid4()` | — | PK do registro |
| `hub_external_id` | `UUID` | NOT NULL | — | UNIQUE INDEX | UUID do polo no serviço `hub` |
| `name` | `String(120)` | NOT NULL | — | — | Nome do polo |
| `brand` | `String(40)` | NOT NULL | — | INDEX | Marca (Estácio/Wyden/outro) |
| `coordinator_external_id` | `UUID` | NULL | — | INDEX | UUID do coordenador atribuído |
| `created_at` | `DateTime(tz)` | NOT NULL | `now()` | — | Timestamp de criação |
| `updated_at` | `DateTime(tz)` | NOT NULL | `now()` ON UPDATE | — | Timestamp de atualização |

#### (PLANEJADO) `health_checks` — Histórico de health checks

| Coluna | Tipo | Nullable | Default | FK / Índice | Descrição |
|--------|------|----------|---------|-------------|-----------|
| `id` | `BIGINT` PK | NOT NULL | autoincrement | — | PK do registro |
| `service_name` | `String(64)` | NOT NULL | — | INDEX | Nome do serviço verificado |
| `status` | `String(16)` | NOT NULL | — | INDEX | `ok`, `down`, `degraded` |
| `detail` | `String(512)` | NULL | — | — | Detalhe do erro (se houver) |
| `db_status` | `String(16)` | NULL | — | — | Status do banco do serviço (se reportado) |
| `checked_at` | `DateTime(tz)` | NOT NULL | `now()` | INDEX | Timestamp da verificação |

### Schemas Pydantic (implementados)

#### `HubCreatePayload`
```python
name: str  # min_length=1, max_length=120
brand: str  # min_length=1, max_length=40
```

#### `CoordinatorSetPayload`
```python
coordinator_external_id: UUID
```

#### `HubReadResponse`
```python
id: UUID
name: str
brand: str
address_external_id: UUID | None
coordinator_external_id: UUID | None
```

#### `ServiceHealth`
```python
service: str
status: str  # "ok" | "down"
db: str | None
detail: str | None
```

#### `HealthAggregateResponse`
```python
services: list[ServiceHealth]
all_ok: bool
```

## 5. Endpoints

### 5.1. Health — Próprio do staff (público)

| Campo | Valor |
|-------|-------|
| **Método** | `GET` |
| **Rota** | `/health` |
| **Tipo** | **Público** (sem auth) |
| **Response** | `{"status": "ok", "service": "staff"}` |

### 5.2. Readiness — Próprio do staff (público)

| Campo | Valor |
|-------|-------|
| **Método** | `GET` |
| **Rota** | `/ready` |
| **Tipo** | **Público** (sem auth) |
| **Response (ok)** | `{"status": "ok", "service": "staff", "db": "ok"}` |
| **Response (fail)** | `{"status": "not_ready", "db": "unreachable"}` |
| **Side-effects** | Executa `SELECT 1` no Postgres para verificar conectividade |

### 5.3. Status — Próprio do staff (público)

| Campo | Valor |
|-------|-------|
| **Método** | `GET` |
| **Rota** | `/status` |
| **Tipo** | **Público** (sem auth) |
| **Response** | `{"status": "ok", "service": "staff", "version": "...", "environment": "...", "uptime_seconds": int}` |

### 5.4. Metrics — Prometheus (público)

| Campo | Valor |
|-------|-------|
| **Método** | `GET` |
| **Rota** | `/metrics` |
| **Tipo** | **Público** (não documentado no schema OpenAPI) |
| **Response** | Formato Prometheus text |

### 5.5. Identidade do usuário autenticado

| Campo | Valor |
|-------|-------|
| **Método** | `GET` |
| **Rota** | `/api/v1/me` |
| **Tipo** | **Autenticado** (JWT + role admin/staff) |
| **Response** | `{"external_id": "UUID"}` |
| **Erro** | `403` sem token; `401` token inválido/expirado; `403` role não autorizada |

### 5.6. Criar polo (delegado ao hub)

| Campo | Valor |
|-------|-------|
| **Método** | `POST` |
| **Rota** | `/api/v1/hubs` |
| **Tipo** | **Autenticado** (JWT + role admin/staff) |
| **Request body** | `{"name": "string (1-120)", "brand": "string (1-40)"}` |
| **Response** | `201` — dados do polo criado (retornados pelo hub) |
| **Side-effects** | Delega criação ao `HubClient.create_hub()` → `POST /hubs` no serviço hub |
| **Erro** | `502` se hub unreachable; repassa status code do hub |

### 5.7. Listar polos (delegado ao hub)

| Campo | Valor |
|-------|-------|
| **Método** | `GET` |
| **Rota** | `/api/v1/hubs` |
| **Tipo** | **Autenticado** (JWT + role admin/staff) |
| **Response** | `200` — `list[dict]` com todos os polos |

### 5.8. Buscar polo por ID (delegado ao hub)

| Campo | Valor |
|-------|-------|
| **Método** | `GET` |
| **Rota** | `/api/v1/hubs/{hub_id}` |
| **Tipo** | **Autenticado** (JWT + role admin/staff) |
| **Response** | `200` — dados do polo |
| **Erro** | `404` se polo não existe (repassado pelo hub) |

### 5.9. Definir coordenador do polo (delegado ao hub)

| Campo | Valor |
|-------|-------|
| **Método** | `PUT` |
| **Rota** | `/api/v1/hubs/{hub_id}/coordinator` |
| **Tipo** | **Autenticado** (JWT + role admin/staff) |
| **Request body** | `{"coordinator_external_id": "UUID"}` |
| **Response** | `200` — resultado da operação |
| **Side-effects** | Delega ao `HubClient.set_coordinator()` → `PUT /hubs/{id}/coordinator` no hub |

### 5.10. Health aggregation on-demand (autenticado)

| Campo | Valor |
|-------|-------|
| **Método** | `GET` |
| **Rota** | `/api/v1/health/aggregate` |
| **Tipo** | **Autenticado** (JWT + role admin/staff) |
| **Response** | `200` — `{"services": [...], "all_ok": bool}` |
| **Side-effects** | Fan-out síncrono via httpx para `/health` de cada serviço monitorado. Timeout 5s por serviço. Falha individual → `status: "down"` (não quebra o agregado) |
| **Serviços monitorados (atual)** | `hub` (via `HUB_BASE_URL`) |
| **Serviços planejados** | Todos os serviços com `/health`: address, ai, documents, infinitepay, jwt, lead, notify, otp, profiles |

### 5.11. (PLANEJADO) Health history — Histórico de uptime

| Campo | Valor |
|-------|-------|
| **Método** | `GET` |
| **Rota** | `/api/v1/health/history` |
| **Tipo** | **Autenticado** |
| **Query params** | `service` (string, opcional), `hours` (int, default 24), `limit` (1-500, default 100) |
| **Response** | `200` — lista de health checks gravados no Postgres |

## 6. Integrações Externas

| Serviço | Tipo de integração | Propósito | Status |
|---------|-------------------|-----------|--------|
| `hub` | HTTP (httpx, via `HubClient`) | CRUD de hubs, definição de coordenador | **Implementado** |
| `jwt` | HTTP (httpx) | Buscar JWKS para validação RS256 | **Implementado** |
| `hub` (health) | HTTP (httpx) | Health check individual do hub | **Implementado** |
| `address` | HTTP (httpx) | Endereço do polo (futuro) | **Planejado** |
| `coordinator` (futuro) | HTTP (httpx) | Validar coordenador, atribuir role | **Planejado** |
| `roles` | HTTP (httpx) | Confirmar role de coordenador ao atribuir | **Planejado** |
| `notify` | HTTP (httpx) | Notificar operador sobre anomalias de saúde | **Planejado** |

**Padrão de integração:** Todas as chamadas são via `httpx.AsyncClient` com timeout configurável (`HTTP_TIMEOUT`, default 10s). O `HubClient` fica em `app/integrations/hub.py`. Staff NÃO repassa o JWT do usuário ao hub — a comunicação é desmilitarizada (staff como trusted caller).

## 7. Eventos Disparados / Consumidos

### Consumidos (implementado)

Nenhum. Staff não consome webhooks de outros serviços.

### Consumidos (planejado)

| Evento | Origem | Reação |
|--------|--------|--------|
| `service.down` (health poll) | Polling interno | Grava registro em `health_checks`, notifica operador via `notify` |
| `service.recovered` (health poll) | Polling interno | Grava registro, notifica operador |

### Disparados (planejado)

| Evento | Gatilho | Destino |
|--------|---------|---------|
| `hub.created` | Criação de polo pelo staff | Log/auditoria |
| `hub.coordinator.assigned` | Definição de coordenador | Serviço `coordinator` (para ativar role) |
| `health.degraded` | Serviço cai durante polling | Serviço `notify` (alerta ao operador) |

## 8. Regras de Negócio Invariantes

1. **Staff é proxy autenticado** — O staff não possui dados de domínio (hubs, coordenadores). Ele valida o JWT + role e delega ao serviço dono (`hub`). Staff é a "porta de entrada" autenticada para operações administrativas.

2. **Role obrigatória** — Toda rota autenticada exige JWT RS256 com `roles` contendo `admin` ou `staff` (configurável via `STAFF_ROLES`). Sem token → `403`; token inválido → `401`; role insuficiente → `403`.

3. **JWKS com cache** — O JWKS é buscado do serviço `jwt` e cacheado por 5 minutos. Se o `jwt` estiver indisponível, a autenticação falha (502) — não há fallback offline.

4. **Health aggregation tolerante a falha** — O fan-out de health checks não quebra se um serviço individual falhar. Cada serviço é verificado independentemente com timeout de 5s. Falha devolve `status: "down"` para aquele serviço e o agregado continua.

5. **Rate limiting global** — 200 requisições por minuto por IP (slowapi). Aplica-se a todas as rotas.

6. **Comunicação staff→hub é desmilitarizada** — O staff não repassa o JWT do usuário ao hub. O hub confia no staff como caller interno. Se isso mudar, `HubClient._request` precisa ser ajustado.

7. **Marca é string livre** — O campo `brand` aceita qualquer string (1-40 chars). Não há enum fixo no código nem tabela de marcas. Validação é apenas Pydantic `min_length`/`max_length`.

8. **Serviços monitorados definidos em código** — `SERVICES_TO_MONITOR` é um dict no `app/services/__init__.py`. Atualmente monitora apenas `hub`. Novos serviços são adicionados manualmente.

9. **Uptime persistido no Postgres** — (Planejado) O polling agendado grava cada verificação em `health_checks` para permitir cálculo de uptime e histórico.

10. **Scheduler com proteção contra duplicação** — (Planejado) Em múltiplas réplicas, o scheduler precisa de lock (Redis ou job único) para evitar polling duplicado.

## 9. Critérios de Aceite

### Milestone 1 (implementado)

- [x] Serviço sobe com `/health`, `/ready`, `/status` próprios.
- [x] `GET /health` retorna `{"status": "ok", "service": "staff"}`.
- [x] `GET /ready` verifica conectividade com Postgres.
- [x] JWT RS256 obrigatório em todas as rotas `/api/v1/...`.
- [x] Sem token → `403`; token inválido/expirado → `401`; role insuficiente → `403`.
- [x] JWKS cacheado por 5 min via `get_jwks()`.
- [x] `GET /api/v1/me` retorna `external_id` do usuário autenticado.
- [x] `POST /api/v1/hubs` cria polo (delegado ao hub via `HubClient`).
- [x] `GET /api/v1/hubs` lista polos (delegado ao hub).
- [x] `GET /api/v1/hubs/{id}` busca polo por ID (delegado ao hub).
- [x] `PUT /api/v1/hubs/{id}/coordinator` define coordenador (delegado ao hub).
- [x] `GET /api/v1/health/aggregate` agrega saúde de todos os serviços monitorados.
- [x] Health aggregation tolerante a falha — serviço individual down não quebra o agregado.
- [x] Métricas Prometheus em `/metrics`.
- [x] Rate limiting 200 req/min por IP.
- [x] `ruff` limpo + `pytest` verde + `alembic upgrade head` válido.

### Milestones 2-5 (pendentes)

- [ ] **M2 — Health aggregation agendada:** Job periódico faz polling dos serviços e grava em `health_checks` no Postgres.
- [ ] **M2:** `GET /api/v1/health/history` retorna histórico com filtro por serviço e período.
- [ ] **M2:** Cálculo de uptime (% ok vs. total) disponível na resposta.
- [ ] **M3 — Gestão de hub completa:** Endereço do polo referenciado via `address_external_id` ou shadow table.
- [ ] **M3:** Validação de marca (enum ou tabela) — definir com dono do produto.
- [ ] **M4 — Definição de coordenador:** Atribuição de coordenador valida existência do usuário (via `profiles` ou `auth`).
- [ ] **M4:** Coordena com serviço `coordinator` para ativar role do coordenador.
- [ ] **M5 — Notificações:** Health degradation dispara notificação via `notify`.
- [ ] **M5:** Scheduler com lock para evitar duplicação em múltiplas réplicas.

## 10. Riscos / Open Questions

### Riscos

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| **Dupla propriedade de hub** — staff proxy vs. hub como dono dos dados | Alta | Alto | Staff como proxy autenticado, hub como fonte única de verdade. Fronteira clara: staff não persiste dados de hub (MVP) |
| **Fan-out de health trava se um serviço pendurar** | Média | Médio | Timeout de 5s por serviço (httpx), agregação tolerante a falha, cada serviço em task separada |
| **Registry desatualizado** — serviço novo não monitorado | Média | Médio | `SERVICES_TO_MONITOR` documentado em código; adicionar serviços conforme sobem com `/health` |
| **Scheduler in-process duplica em múltiplas réplicas** | Baixa | Médio | Lock (Redis) ou job único; decidir na fase de planejamento do M2 |
| **Hub indisponível derruba todas as operações de hub** | Média | Alto | `HubClient` retorna 502 com detalhe; operador pode tentar novamente. Circuit breaker futuro |
| **JWKS indisponível bloqueia toda autenticação** | Baixa | Alto | Cache de 5 min ameniza indisponibilidade transitória. Sem fallback offline (por segurança) |

### Open Questions

- [ ] **Fronteira staff ↔ hub ↔ coordinator:** Staff como proxy vs. hub como dono dos dados. Hoje staff delega tudo ao hub. Se hub passar a ter auth própria, como staff se autentica com hub? Token próprio ou IP whitelist?
- [ ] **Registry de serviços:** Quais serviços entram no MVP do polling agendado? Serviços com `/health` hoje: hub, address, ai, documents, infinitepay, jwt, lead, notify, otp, profiles. Todos? Subconjunto?
- [ ] **Polling agendado — intervalo e retenção:** Qual intervalo? (30s? 1min? 5min?). Quanto reter no Postgres? (7 dias? 30 dias?). Onde roda o scheduler (in-process vs. externo)?
- [ ] **Marcas (Estácio/Wyden/outro):** Enum fixo no código ou tabela no banco? Atualmente é string livre. Confirmar com dono do produto.
- [ ] **Endereço do polo:** Shadow table read-only de `address` ou apenas `external_id` + validação via `httpx`? Decisão afeta a arquitetura do hub.
- [ ] **Definir coordenador concede role via `roles/`?** O fluxo atual delega ao hub. Se hub precisar chamar `roles` para ativar coordenador, qual a sequência de chamadas?
- [ ] **Multi-réplica:** Staff roda em múltiplas réplicas? Se sim, o scheduler de health polling precisa de lock distribuído (Redis) ou externalização (Celery, cron k8s).
- [ ] **Auth entre staff e hub:** Comunicação atual é desmilitarizada. Se hub exigir auth, staff precisa de service-to-service token. Definir padrão (mTLS? service token? JWT de máquina?).
- [ ] **Rate limiting por role:** Atualmente é global (200/min por IP). Diferenciar limites para `admin` vs `staff`?

---

*Status: Milestone 1 IMPLEMENTADO. Milestones 2-5 PENDENTES — planejamento via /plan.*
