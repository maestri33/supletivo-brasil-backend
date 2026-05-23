# Relatório de Sincronização — asaas-app

**Data:** 2026-05-22
**Fonte de verdade:** `root@10.1.30.20:/opt/v7m/services/asaas/` (produção, container `v7m-asaas` healthy)
**Alvo:** `/home/maestri33/backend/asaas/asaas-app/` (estava desatualizado)
**Backup do estado anterior:** `/home/maestri33/backend/asaas/asaas-app.backup-20260522-200910.tar.gz`

O código local foi alinhado 100% ao remoto (`diff -rq` retorna vazio, exceto `data/`,
que é runtime local e foi preservado). Abaixo, o que mudou e por quê.

---

## 1. Resumo executivo

O remoto representa uma evolução grande sobre o local. Três mudanças estruturais:

1. **Banco: SQLite → Postgres + Alembic.** O app deixou de criar tabelas via
   `Base.metadata.create_all` em SQLite e passou a usar o Postgres central `v7m`
   (schema `asaas`), com migrations Alembic versionadas.
2. **Novo fluxo: Cobranças PIX de entrada (`kind=charge`).** Antes o app só fazia
   *payouts* (saída: `pixkey`, `qrcode`). Agora também cria cobranças PIX recebidas
   via Asaas `/v3/payments` (`billingType=PIX`), retornando BR Code + QR Code base64.
3. **Mecanismo de Segurança real + notificações roteadas + bootstrap por `.env`.**

Magnitude: **16 arquivos novos**, **22 arquivos modificados**, **0 removidos**.
Suíte de testes passou de 91 para **172 testes** (81 novos).

---

## 2. Arquivos NOVOS (só existiam no remoto)

### Código de aplicação
| Arquivo | Função |
|---|---|
| `app/api/charge.py` | Rotas `/api/v1/charge/*` (criar/listar/consultar/cancelar/refresh QR de cobranças PIX). |
| `app/services/charge.py` | Lógica de cobranças: cria payment no Asaas, busca QR, máquina de estados PENDING→PAID/EXPIRED/CANCELLED/REFUNDED, bridge de webhook `PAYMENT_*`. |
| `app/services/customer.py` | *Find-or-create* de pagadores (mapping `external_id` local ↔ `asaas_id`), valida CPF/CNPJ, resiliente a wipe (busca por `externalReference` no Asaas). |
| `app/services/notifications.py` | Notificação interna roteada por categoria (charge / scheduling / payout) com fallback legado. |
| `app/services/security_validator.py` | Decisão real (APPROVED/REFUSED) do Mecanismo de Segurança Asaas, validando contra Payment local (asaas_id + amount + status). |

### Banco / migrations
| Arquivo | Função |
|---|---|
| `alembic.ini` | Config do Alembic. |
| `alembic/env.py` | Env Alembic com schema `asaas`, lê URL de `app.config`. |
| `alembic/versions/2026-05-15_initial_asaas_schema.py` | Rev `0001`: tabelas `config`, `url_verify_nonce`, `webhook_event`, `pix_key`, `payment`. |
| `alembic/versions/2026-05-15_charge_support.py` | Rev `0002`: tabela `customer` + colunas `customer_external_id`, `pix_qr_image`, `due_date` em `payment`. |

### Testes (81 novos)
`tests/test_charge_service.py` (28), `tests/test_customer_service.py` (11),
`tests/test_notifications.py` (8), `tests/test_routes_charge.py` (13),
`tests/test_security_validator.py` (21).

### Infra / docs
`Dockerfile` (Python 3.12 + uv, roda `alembic upgrade head` no boot),
`README.md`, `INTEGRATION.md` (guia de integração, 406 linhas).

---

## 3. Arquivos MODIFICADOS (diferenças globais)

### `app/config.py`
- `database_url` default: `sqlite:///data/app.db` → `postgresql+psycopg2://v7m:v7m@postgres:5432/v7m`.
- Novo `database_schema = "asaas"`.
- Novo `asaas_allow_sandbox` (default `False`): aceita chaves `$aact_hmlg_` quando `True`.
- Novos campos de **bootstrap por env** (`asaas_api_key`, `asaas_external_url`,
  `asaas_wallet_id`, `asaas_internal_url[_charge|_payout|_scheduling]`).
- Novo `charge_default_due_days = 3`.
- `WEBHOOK_EVENTS` expandido com todos os `PAYMENT_*` (cobranças inbound).
- **Removido**: helpers de "eventos sintéticos" (`SYNTHETIC_EVENTS`,
  `synthetic_event_for_status`, constantes `EVT_*`) — não eram mais usados.

### `app/db.py`
- Engine SQLite (`check_same_thread`) → Postgres (`pool_pre_ping=True`).
- `Base` agora usa `MetaData(schema="asaas")`.
- `init_db()` virou no-op (schema é responsabilidade do Alembic); removida a
  criação de diretório SQLite e o `create_all`.

### `app/models/__init__.py`
- Novo modelo `Customer` (pagadores).
- `Payment` ganhou `customer_external_id`, `pix_qr_image`, `due_date` e passou a
  suportar `kind=charge` além de `pixkey`/`qrcode`.

### `app/schemas/__init__.py` (maior mudança: +208 linhas)
- Novo catálogo de erros `charge` e erro `invalid_internal_url_target` em `config`.
- Novos schemas: `CustomerInline`, `ChargeCreateRequest`, `ChargePixData`,
  `ChargeResponse`, `CustomerResponse`.
- `SetInternalUrlRequest` ganhou campo `target` (`default|scheduling|payout|charge`).
- `InternalNotification` documenta os 3 destinos e `kind=charge`.

### `app/config_store.py`
- 3 novas chaves de internal URL (`_scheduling`, `_payout`, `_charge`) + helper
  `internal_url_key(target)` e `INTERNAL_URL_TARGETS`.
- Novo `seed_from_env(db)`: pós-wipe/primeiro boot popula `asaas.config` a partir
  do `.env` (DB vence se já houver valor). Chamado no lifespan.

### `app/integrations/asaas_client.py`
- `ASAAS_BASE_URL` agora vem de Settings (suporta sandbox).
- Novos métodos: `create_customer`, `get_customer`, `list_customers`,
  `find_customer_by_external_reference`, `update_customer`, `create_payment`,
  `get_payment`, `list_payments`, `delete_payment`, `refund_payment`,
  `get_payment_pix_qr_code`.

### `app/services/payment.py`
- `_notify_internal` foi extraído para `services/notifications.py` (re-exportado
  para compat).
- `apply_webhook` agora filtra por `kind in (pixkey, qrcode)` — eventos `PAYMENT_*`
  são tratados pelo charge service, não mais aqui.

### `app/services/config_internal.py`
- Onboarding doc agora é por `target` (`doc_for_target`): cada categoria recebe
  instruções específicas. `send_onboarding(url, *, target=...)`.

### `app/services/config_key.py`
- `set_key` aceita `$aact_hmlg_` (sandbox) quando `ASAAS_ALLOW_SANDBOX=true`;
  caso contrário continua production-only.

### `app/api/config.py`
- `POST /config/internal` agora roteia por `target` e devolve `target` na resposta.
- Instruções HTML do Mecanismo de Segurança adaptam texto/host para sandbox vs prod.

### `app/api/webhook.py`
- `/security-validator` agora chama `security_validator_svc.decide(...)` (decisão
  real) em vez de aprovar tudo.
- `/webhook/` roteia `PAYMENT_*` → charge service e `TRANSFER_*` → payment service,
  e notifica via `notifications.notify_internal`.

### `app/api/router.py`
- Inclui `charge_router`.

### `app/main.py`
- Lifespan chama `cfg.seed_from_env()` no startup.
- Documentação OpenAPI reescrita para os dois fluxos (payout + charge), sandbox e
  os 3 destinos de notificação. Nova tag `charge`.

### `app/api/payment.py`
- Apenas reformatação (quebras de linha); sem mudança de comportamento.

### `.env.example` / `pyproject.toml`
- `.env.example`: passa a documentar Postgres, `ASAAS_BASE_URL`,
  `ASAAS_ALLOW_SANDBOX`, `ASAAS_APP_CHARGE_DEFAULT_DUE_DAYS`.
- `pyproject.toml`: adiciona deps `psycopg2-binary>=2.9`, `alembic>=1.14`,
  `pytest-cov>=7.1.0`.

### Testes modificados
- `tests/conftest.py`: neutraliza schema para SQLite nos testes; passa a mockar
  `AsaasClient` também em `charge` e `customer`.
- `tests/test_settings.py`: removidos testes de eventos sintéticos; adicionados
  testes de sandbox flag e charge due-days.
- `tests/test_webhook.py`: `/security-validator` agora testa REFUSED com body vazio.
- `tests/test_routes_meta.py`, `tests/test_routes_payment.py`: só reformatação.

---

## 4. Como rodar (pós-sync)

```bash
cd /home/maestri33/backend/asaas/asaas-app
uv sync                                  # instala psycopg2, alembic, etc.
export ASAAS_APP_DB_URL=postgresql+psycopg2://<user>:<pass>@<host>:<port>/<db>
uv run alembic upgrade head              # cria schema asaas (revs 0001, 0002)
uv run uvicorn app.main:app --port 8000  # sobe a API
```

---

## 6. Resultados dos testes (executados em 2026-05-22)

Ambiente de teste montado **sem mock**: Postgres 16 real (container dedicado
`asaas-e2e-pg`, porta 5546), migrations Alembic reais, app FastAPI real, e chamadas
HTTP reais ao Asaas **produção** (autorizado pelo operador).

### 6.1 Suíte de testes do projeto
- `uv run pytest -q` → **172 passed** (inclui 81 testes novos de charge/customer/
  notifications/security_validator). Esta suíte usa SQLite + AsaasClient mockado
  (decisão do projeto p/ unit/integração).

### 6.2 Migrations + schema (Postgres real)
- `alembic upgrade head` → revs `0001` + `0002` aplicadas, RC=0.
- 7 tabelas criadas em `asaas.*`: `config`, `customer`, `payment`, `pix_key`,
  `url_verify_nonce`, `webhook_event`, `alembic_version`.
- `asaas.payment` confirmado com colunas novas (`customer_external_id`,
  `pix_qr_image`, `due_date`) e índices.

### 6.3 End-to-end via HTTP, sem mock (app + Postgres reais)
| Cenário | Resultado |
|---|---|
| Lifespan `seed_from_env` no startup | OK (config vazia → tudo "absent") |
| `GET /healthz` | 200 `{"status":"up"}` |
| `GET /openapi.json` | rotas `/api/v1/charge*` registradas |
| `GET /api/v1/config/status` | lê Postgres real (3 novos `internal_url_*`) |
| `POST /api/v1/config/url` + verify | nonce persistido e consumido; `external_url` setada |
| `POST /api/v1/charge/pix` amount=0 | 422 (validação Pydantic `gt=0`) |
| `POST /api/v1/charge/pix` sem key | 400 `asaas_api_key_not_set` |
| `security_validator` sem token | 401 `invalid_token` |
| `security_validator` body vazio | REFUSED `missing_type` |
| `security_validator` TRANSFER batendo asaas_id+amount | **APPROVED** (contra `Payment` real) |
| `security_validator` valor divergente | REFUSED `value_mismatch: local=12.34 remote=999.99` |
| `security_validator` tipo BILL | REFUSED `unsupported_operation_type` |
| Webhook `PAYMENT_RECEIVED` (charge bridge) | cobrança PENDING→**PAID**, evento persistido |

### 6.4 End-to-end com Asaas PRODUÇÃO (sem mock, dados reais)
Chave `$aact_prod_*` lida do `.env` de produção (autorizado) e onboardada via
`POST /api/v1/config/key` — chamada real `get_my_account` retornou
**V7M EMPRESARIAL LTDA** (`v7maestri@gmail.com`). `confirm_key` **não** foi chamado
(não registramos webhook na conta).

Ciclo de cobrança real:
1. `POST /charge/pix` (R$5,00, payer CPF 52998224725) →
   - customer criado no Asaas (`cus_000177785121`),
   - cobrança criada (`pay_o1hvw2rgynnm6pmt`, status PENDING),
   - BR Code real (`00020101021226800014br.gov.bcb.pix…`) + QR Code PNG base64 (1124 bytes).
2. `GET /charge/{id}/status` → PENDING.
3. `DELETE /charge/{id}` → DELETE real `/v3/payments` no Asaas → **CANCELLED**
   (confirmado no Postgres).

Aprendizados reais capturados no teste:
- Asaas valida dígito de CPF (o CPF `07426367980` do README é rejeitado em produção).
- Valor mínimo de cobrança no Asaas é **R$ 5,00**.
- `find_or_create` reaproveitou o customer órfão (criado numa tentativa anterior que
  falhou no valor) via `externalReference` — resiliência confirmada na prática.

### 6.5 Lint
- `ruff check` (v0.15) aponta **4 itens** (3× E501 em `app/config.py`, 1× I001 em
  `app/main.py`). São **idênticos na fonte de verdade** (drift de versão do linter;
  `pyproject` pede `ruff>=0.6`). **Não corrigidos** para preservar coerência com o remoto.

### 6.6 Pendências / limpeza
- **Customer de teste no Asaas produção:** `cus_000177785121`
  (externalReference `e2e_sync_20260522`, "TESTE E2E SYNC (CANCELAR)"). A cobrança
  foi cancelada; o customer permanece (o client não expõe delete de customer).
  Sem impacto financeiro (notificações desabilitadas). Remover manualmente no painel
  se desejar.
- Infra de teste (container Postgres `asaas-e2e-pg` + app uvicorn) foi derrubada ao
  final; a chave de produção ficou apenas no container efêmero, agora removido.
- `data/app.db` (SQLite antigo) foi preservado localmente, mas é obsoleto (o app usa
  Postgres). Pode ser removido com segurança.
