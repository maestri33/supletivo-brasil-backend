# Sincronização InfinitePay — local ↔ remoto (fonte de verdade)

**Data:** 2026-05-22
**Fonte de verdade:** `root@10.1.30.20:/opt/v7m/services/infinitepay/`
**Alvos locais atualizados:** `opt-code/infinitepay/` (espelho completo) e `root-code/infinitepay/` (só pacote `app/`)

---

## 1. Resumo executivo

O código local estava desatualizado em relação ao servidor. A diferença **não** era
a troca de URL do e-mail (essa já estava aplicada localmente no pacote `app/`), e sim
uma **evolução arquitetural** que já está no remoto:

1. **Banco: SQLite → PostgreSQL** (schema `infinitepay`, FK cross-schema para `auth.users`).
2. **Migrações Alembic** (novas) substituem o `init_db()` que criava tabelas em runtime.
3. **Bootstrap de config via `.env`** (`seed_from_env()` no startup).
4. **IA: cliente OpenAI/DeepSeek direto → serviço HTTP v7m** (`ai_service_client.py`).
5. **Dependências/infra**: `psycopg2-binary`, `alembic`, `typer`, Dockerfile e README.

Após a sincronização, `opt-code/infinitepay` ficou **byte-a-byte idêntico** ao remoto
(diff vazio), e o pacote `app/` ficou idêntico nas três cópias (remoto, opt-code, root-code).

---

## 2. Método

1. Conexão SSH em `root@10.1.30.20`.
2. Snapshot do remoto via `scp -r` para `/tmp/ipay-remote/` (somente leitura no remoto).
3. Comparação recursiva `diff -rq` (excluindo `__pycache__`, `.ruff_cache`, `*.pyc`).
4. Cópia dos arquivos divergentes/novos do snapshot para os alvos locais.
5. Validação: `diff -rq` (zero), `py_compile` (sintaxe), `ruff` (lint).

---

## 3. Mapa dos diretórios

| Item | Remoto (fonte) | opt-code (antes) | root-code (antes) |
|---|---|---|---|
| pacote `app/` (ativo, `app.main:app`) | ✅ | ✅ (desatualizado) | ✅ (desatualizado) |
| pacote `infinitepay/` (legado, CLI) | ✅ | ✅ (+ `.bak`) | ❌ |
| `alembic/` + `alembic.ini` | ✅ | ❌ | ❌ |
| `tests/`, `README.md`, `SKILL.md`, `deploy/` | ✅ | ✅ | ❌ |
| `.env` real | ❌ (só `.env.example`) | ❌ | ✅ |
| `uv.lock` | ❌ | ✅ (stale) | ✅ (stale) |
| `infinitepay.old/` | ❌ | ✅ (cruft) | ❌ |

**App ativo confirmado pelo Dockerfile remoto:**
`alembic upgrade head && uvicorn app.main:app`. O pacote `infinitepay/` é legado
(o `deploy/infinitepay-api.service` aponta para ele, mas é o método antigo bare-metal).

---

## 4. Diferenças globais (o que estava desatualizado)

### 4.1 Banco de dados: SQLite → PostgreSQL
- `app/config.py`: removido `db_path` (SQLite); adicionados `database_url`
  (`postgresql+psycopg2://v7m:v7m@postgres:5432/v7m`) e `database_schema = "infinitepay"`.
- `app/db.py`: `create_engine(sqlite://…)` → `create_engine(settings.database_url, pool_pre_ping=True)`;
  **removida** a função `init_db()` (criação de schema agora é via Alembic).
- `app/models/models.py`:
  - `MetaData(schema="infinitepay")` na `Base`.
  - Tabela-sombra `auth.users` (resolve FK cross-schema no SQLAlchemy).
  - `external_id`: `String(128)` → `PG_UUID(as_uuid=True)` com FK para `auth.users.external_id`
    (`RESTRICT` em checkouts, `SET NULL` em webhook_logs/outbound_jobs).
  - Colunas de URL: `String(500)` → `Text` (URLs de checkout passam de 500 chars — ver 4.2).

### 4.2 Migrações Alembic (novas)
- `alembic/`, `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`.
- `0001_initial_infinitepay_schema` — cria `config`, `checkouts`, `webhook_logs`,
  `outbound_jobs` no schema `infinitepay`, com FKs para `auth.users`.
- `0002_widen_url_columns` — `checkout_url`/`receipt_url`/`redirect_url`/`backend_webhook`/
  `public_api_url`/`url` de `varchar(500)` → `TEXT` (InfinitePay retorna `checkout_url`
  com token `lenc` de 700+ chars; `varchar(500)` truncava).

### 4.3 Bootstrap de config via `.env`
- `app/config.py`: novos campos com `validation_alias` —
  `INFINITEPAY_HANDLE/PRICE/QUANTITY/DESCRIPTION/REDIRECT_URL/BACKEND_WEBHOOK/PUBLIC_API_URL`.
- `app/services/config_service.py`: nova função `seed_from_env()` + tabela `_ENV_BOOTSTRAP`.
  Pós-wipe/first-boot, popula `Config(id=1)` a partir do `.env`. **DB vence** se já houver
  valor (operador pode sobrescrever via `PATCH /api/v1/config`).
- `app/main.py`: o `lifespan` chama `seed_from_env()` no startup (antes chamava `init_db()`);
  `lifespan=lifespan` registrado no `FastAPI(...)`.

### 4.4 IA: OpenAI direto → serviço HTTP v7m
- `app/ai/ai_service_client.py` (**novo**): cliente `httpx` sync para
  `{ai_base_url}/api/v1/text/chat`; `chat()` retorna `ChatResult`; falhas → `AiServiceError`.
- `app/config.py`: novo `ai_base_url = "http://ai:8000"`.
- `app/ai/monitor.py` e `app/ai/receipt.py`: migrados de
  `client.chat.completions.create(...)` (OpenAI/DeepSeek direto) para `chat(...)` do
  serviço v7m. Modelos passados explicitamente (`deepseek-v4-flash`/`deepseek-v4-pro`).
  Mantêm **fallback** (receipt) e **falha silenciosa** (monitor) por design.
- Nota: `app/ai/analytics.py` e `app/ai/reporter.py` continuam usando OpenAI direto
  (`app/ai/client.py`) porque dependem de `tool_calling` com DB local — fronteira intencional.

### 4.5 Dependências / infra / docs
- `pyproject.toml` (remoto/opt-code): + `openai>=1.0`, `psycopg2-binary>=2.9`,
  `alembic>=1.14`; dev + `typer>=0.12` (testes do CLI legado);
  `[tool.pytest.ini_options]` com `--deselect tests/test_api.py::test_health_and_lock_flow`
  (schema do CLI legado desatualizado — issue #1 do roadmap).
- `Dockerfile`: copia `infinitepay/`, `alembic/`, `alembic.ini`; `CMD` roda
  `alembic upgrade head && uvicorn app.main:app`.
- `README.md`: reescrito para setup v7m (Postgres central + Compose, Tailscale funnel,
  smoke test sem cobrança, troubleshooting). 775 linhas.

---

## 5. Integração do e-mail (mudança de URL do Checkout)

**O e-mail pedia:**
| | Antiga | Nova |
|---|---|---|
| Criar link | `POST https://api.infinitepay.io/invoices/public/checkout/links` | `POST https://api.checkout.infinitepay.io/links` |
| Consulta | `POST https://api.infinitepay.io/invoices/public/checkout/payment_check` | `POST https://api.checkout.infinitepay.io/payment_check` |

**Status: já implementado no pacote ativo `app/`** (confirmado no remoto e agora local):
- `app/config.py`: `infinitepay_base_url = "https://api.checkout.infinitepay.io"` (host novo).
- `app/integrations/infinitepay_client.py`:
  - `create_checkout_link` → `POST /links` → resolve para `…/links` (URL nova). 
  - `payment_check` → `POST /payment_check` → resolve para `…/payment_check` (URL nova).
- Payloads inalterados; webhooks inalterados (conforme o e-mail).

**Pacote legado `infinitepay/` (NÃO ativo) ainda usa as URLs antigas:**
- `infinitepay/settings.py`: `infinitepay_base_url = "https://api.infinitepay.io"`.
- `infinitepay/core/infinitepay_client.py`: `POST /invoices/public/checkout/links` e
  `POST /invoices/public/checkout/payment_check`.
- **A fonte de verdade (remoto) deixou o legado intacto.** Como as URLs antigas seguem
  funcionando até 01/06/2026 e esse pacote não é o serviço ativo, mantivemos a paridade
  com o remoto (não alteramos). **Recomendação:** se o CLI legado `ipay` ainda for usado
  em produção, atualizar `infinitepay/settings.py` + `infinitepay/core/infinitepay_client.py`
  antes de 01/06/2026 — idealmente no remoto primeiro (fonte de verdade) e depois sincronizar.

---

## 6. Alterações aplicadas (exato)

### opt-code/infinitepay/ (sincronizado 1:1 com o remoto)
Copiados do snapshot remoto:
- `app/config.py`, `app/db.py`, `app/main.py`, `app/models/models.py`,
  `app/services/config_service.py`, `app/ai/monitor.py`, `app/ai/receipt.py`
- `app/ai/ai_service_client.py` (novo)
- `alembic/` (novo) + `alembic.ini` (novo)
- `Dockerfile`, `README.md`, `pyproject.toml`

Removidos (cruft local ausente na fonte de verdade):
- `infinitepay/api/main.py.bak`
- `infinitepay/api/routes/checkout.py.bak`
- `infinitepay.old/` (diretório)
- `uv.lock` (stale; remoto não versiona lock e o `pyproject` mudou — evita falha de
  `uv sync --frozen`. Regenerar com `uv lock` se quiser pinagem)

**Resultado:** `diff -rq /tmp/ipay-remote opt-code/infinitepay` → vazio (idêntico).

### root-code/infinitepay/ (propagação do pacote app/)
Copiados (mesmos arquivos do `app/` acima, incluindo `ai_service_client.py`).
- `pyproject.toml`: + `psycopg2-binary>=2.9`, + `alembic>=1.14` (mantido `openai>=2.34.0`
  pré-existente, que é maior que o `>=1.0` do remoto — ambos válidos).
- `uv.lock` removido (stale).
- `.env` **preservado** (não sobrescrito).

**Resultado:** `app/` de root-code = `app/` do remoto (idêntico).

---

## 7. Itens pré-existentes na fonte de verdade (não corrigidos de propósito)

`ruff check app alembic` acusa **14 violações idênticas no remoto e no opt-code**:
- 6× `UP007` (usar `X | None` em vez de `Optional[X]`/`Union` — nos arquivos alembic)
- 5× `E501` (linhas > 100 — `app/config.py`, campos com `validation_alias`)
- 2× `UP035` (`typing.Sequence/Union` deprecados — alembic)
- 1× `I001` (imports não ordenados — `app/models/models.py`)

**Decisão:** NÃO corrigidas localmente, para preservar a paridade byte-a-byte com a
fonte de verdade. Devem ser corrigidas **no remoto primeiro** e depois sincronizadas.

---

## 8. Implicações de runtime (importante)

- O pacote `app/` agora **exige PostgreSQL** com schema `auth` contendo a tabela
  `auth.users` (FK cross-schema). Sem isso, `alembic upgrade head` falha.
- **Não há mais SQLite.** O `root-code/.env` (`DB_PATH=/tmp/infinitepay-test.db`) ficou
  obsoleto: o novo `app/config.py` ignora `DB_PATH` e usa `database_url` (default Postgres).
  Para rodar root-code localmente é preciso definir `DATABASE_URL` para um Postgres real.
- Schema é criado por **Alembic**, não mais por `init_db()`.
- IA depende do serviço v7m em `ai_base_url` (`http://ai:8000`); se fora do ar, recibo usa
  fallback e o monitor falha em silêncio (por design).
- **InfinitePay não tem sandbox nem API key** (README §1) — qualquer chamada real é produção.

---

## 9. Teste end-to-end (status)

> Decisão do operador: rodar e2e **na stack real do servidor remoto**, com chamadas
> **reais** à API da InfinitePay.

**Ambiente real:** host `10.1.30.20`, container `v7m-infinitepay`, API na porta `8120`.
Stack v7m completa no host (auth=8133, ai=8177, postgres=5432, redis=6379).

### Resultados (stack real, sem mock)

| Check | Resultado |
|---|---|
| `GET /health` | ✅ `{"ok":true}` |
| `GET /ready` | ✅ `{"ok":true}` |
| `GET /api/v1/config/` | ✅ config real: `handle=v7m`, `price=99990`, `description="Matrícula Supletivo"`, `backend_webhook=http://lead:8000/...`, `public_api_url=https://api.v7m.org` (prova leitura Postgres + seed) |
| `alembic current` | ✅ `0002 (head)` — migrações aplicadas |
| Dados reais no DB | `checkouts=1` (paid=1), `webhook_logs=9` |
| `GET /api/v1/checkout/` (lista) | ❌ **HTTP 500** |
| `GET /api/v1/checkout/{id}/` | ❌ **HTTP 500** (mesmo bug) |
| `POST /api/v1/checkout/` | ⏸ pendente decisão (chamada real InfinitePay + exige `external_id` em `auth.users`) |

### 🐛 BUG REAL ENCONTRADO NA FONTE DE VERDADE

```
fastapi.exceptions.ResponseValidationError: 1 validation error:
 {'type':'string_type','loc':('response','items',0,'external_id'),
  'msg':'Input should be a valid string','input':UUID('77bb18ca-...')}
 app/api/checkout.py:29 in list_all
```

**Causa:** a migração SQLite→Postgres trocou `Checkout.external_id` para
`PG_UUID(as_uuid=True)` (retorna objeto `UUID` do banco), mas o schema
`CheckoutResponse.external_id` continua `str` (e `_serialize`/`get_checkout`
devolvem `c.external_id` cru). FastAPI rejeita o UUID na validação de resposta.

**Impacto:** `GET /api/v1/checkout/` e `GET /api/v1/checkout/{id}/` quebram (500)
com dados reais. `POST /checkout/` não é afetado (devolve o `external_id` de entrada,
que `normalize_external_id` retorna como `str`). Lookup interno do webhook também
funciona (comparação coage str→UUID na query).

**Correção mínima proposta** (em `app/services/checkout_service.py`, mantém o
contrato de string da API):
- `_serialize()` → `"external_id": str(c.external_id)`
- `get_checkout()` → `"external_id": str(c.external_id)` (nos dois returns)

**Resolução (decisão do operador: corrigir só no local por enquanto):**
Aplicado em `app/services/checkout_service.py` no **opt-code** e **root-code**:
```diff
  def get_checkout(...):
      ...
+         eid = str(c.external_id)
          if c.is_paid:
-             return {"external_id": c.external_id, "is_paid": True, "receipt_url": c.receipt_url}
-         return {"external_id": c.external_id, "is_paid": False, "checkout_url": c.checkout_url}
+             return {"external_id": eid, "is_paid": True, "receipt_url": c.receipt_url}
+         return {"external_id": eid, "is_paid": False, "checkout_url": c.checkout_url}
  def _serialize(c):
      return {
-         "external_id": c.external_id,
+         "external_id": str(c.external_id),
```

**⚠️ Divergência intencional vs fonte de verdade:** este é o ÚNICO arquivo em que o
opt-code difere do remoto agora (`diff -rq` confirma). O remoto **ainda tem o bug** —
quando o operador for atualizar o `/opt` do servidor, aplicar o mesmo patch lá (de
preferência fazê-lo a fonte de verdade e re-sincronizar). `ruff` limpo no arquivo.

### Validação do fix (e2e local real, sem mock)
Como o remoto não foi alterado (não dá pra validar lá sem deploy), validei localmente
contra **Postgres real** (container `postgres:16-alpine`) + app real via `TestClient`:
- Setup: schema `auth` + `auth.users`, schema `infinitepay`, `alembic upgrade head`
  (0001→0002, igual à prod), 2 checkouts reais (1 não-pago com `checkout_url` de **761
  chars** validando a migração TEXT, 1 pago).
- `GET /api/v1/checkout/` → **200**, 2 itens, `external_id` como **string** ✅
- `GET /api/v1/checkout/{unpaid}/` → **200**, `is_paid=false`, `checkout_url` ✅
- `GET /api/v1/checkout/{paid}/` → **200**, `is_paid=true`, `receipt_url` ✅
- Suíte do projeto: **19 passed, 1 deselected** (a deselecionada é o teste do CLI legado
  já marcado como desatualizado no `pyproject`).
- Postgres descartável removido ao final; `.venv`/`uv.lock`/caches de validação limpos
  (opt-code voltou a espelhar o remoto, exceto pelo fix).

### Conclusão do e2e
Stack real validada (health/ready/config/migrações/dados reais). Único defeito real
encontrado = bug UUID→str nos GETs de checkout, **corrigido e validado no local**.
Caminho de escrita (`POST /checkout/` → InfinitePay real) não exercitado por decisão do
operador (evitar artefato em produção). As URLs novas do Checkout (e-mail) já estão
ativas no pacote `app/` e foram exercitadas indiretamente pelo cliente real.
