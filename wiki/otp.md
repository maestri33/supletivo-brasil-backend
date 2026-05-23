# otp

## Função

Microsserviço responsável pela geração, envio e validação de códigos OTP (One-Time Password) numéricos descartáveis. Envia o código via serviço **notify** (WhatsApp) e registra todo o ciclo de vida no banco.

## Status

**Parcial.** Endpoints implementados e funcionais; 2 migrações Alembic criadas (schema completo no Postgres). Testes existem (`tests/test_health.py`, `tests/test_otp.py`) mas a suíte legada está em skip (migração SQLite → Postgres pendente de ajuste no conftest). TODO principal não resolvido: conexão com Postgres em produção (serviço provavelmente ainda usando SQLite local).

## Estrutura

**Aninhada incorretamente:** `otp/otp/app/` — há um nível extra de diretório `otp/otp/` antes do pacote `app/`. A convenção exige `otp/app/` diretamente. Desvio registrado no CLAUDE.md do serviço como estado atual, não como intenção.

## Endpoints

### `api/health.py` — Desmilitarizado
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/health` | Liveness — retorna `{"status": "ok"}` |
| GET | `/ready` | Readiness — testa conexão com banco (`SELECT 1`) |

### `api/otp.py` — Desmilitarizado
| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/api/v1/otp` | Gera código OTP, aplica rate limit e envia via notify |
| GET | `/api/v1/otp` | Lista logs de OTP com filtros (external_id, status, paginação) |
| POST | `/api/v1/otp/check` | Valida código OTP informado pelo usuário |
| GET | `/api/v1/otp/logs` | Alias de listagem (duplicado de `GET /api/v1/otp`) |

### `api/webhook.py` — Público (callback externo)
| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/webhook/notify/{message_id}` | Recebe callback do notify com status de entrega (WhatsApp) |

> Atenção: o webhook público não possui nenhum mecanismo de autenticação/assinatura.

### `api/status.py` — Desmilitarizado
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/status` | Métricas do serviço (uptime, conexões, latência, falhas) |

## Dados

**Configurado para Postgres** (`postgresql+asyncpg://...`, schema `otp`) mas **arquivo `data/app.db` presente** — indica que o serviço ainda rodou com SQLite. O TODO `data/TODO` diz explicitamente: *"conecte com postgres"*. SQLAlchemy 2 async + asyncpg está implementado; basta garantir que o `.env` aponte para o Postgres real e rodar `alembic upgrade head`.

### Schema `otp` (2 migrações — 0001 + 0002)

**`otp.otp_logs`**
| Coluna | Tipo | Descrição |
|--------|------|-----------|
| id | Integer PK autoincrement | — |
| external_id | UUID FK → auth.users.external_id | Usuário dono do OTP |
| code_hash | String(64) | SHA256 do código |
| status | String(20) | `generated` \| `sent` \| `verified` \| `expired` \| `failed` |
| attempts | Integer default 0 | Tentativas inválidas de verificação |
| failure_reason | String(20) nullable | `notify_down` \| `notify_permanent` \| `invalid_code` \| `expired` \| `inactive` |
| message_id | Integer nullable | ID da mensagem no notify |
| error_detail | Text nullable | Detalhe do erro |
| verified_at | DateTime(tz) nullable | Quando foi validado |
| created_at | DateTime(tz) | Criação |

**`otp.pending_notify`** — fila de retry de envio
| Coluna | Tipo | Descrição |
|--------|------|-----------|
| id | Integer PK | — |
| external_id | UUID FK → auth.users | — |
| content | Text | Conteúdo da mensagem a reenviar |
| otp_log_id | Integer FK → otp.otp_logs | — |
| attempts | Integer | Número de tentativas |
| next_retry_at | DateTime(tz) | Próximo agendamento |
| status | String(20) | `pending` \| ... |
| error_detail | Text nullable | — |
| created_at / updated_at | DateTime(tz) | — |

**`otp.rate_limit`** (migração 0002) — controle por `external_id` (janela curta + horária).

## Integrações

**Internas (httpx):**
- `integrations/notify_client.py` — envia mensagem WhatsApp via serviço **notify** em `http://notify:8000` (configurável por `NOTIFY_BASE_URL`). O contato deve existir previamente no notify.
- Webhook de retorno: o notify chama `POST /webhook/notify/{message_id}` para reportar status de entrega.

**Background tasks (lifespan):**
- `services/queue.py` — `queue_loop`: processa `pending_notify` para retry de envio ao notify.
- `services/cleanup.py` — `cleanup_loop`: purga `otp_logs` antigos conforme `OTP_CLEANUP_RETENTION_DAYS`.

**Externas:** nenhuma diretamente — tudo passa pelo serviço `notify`.

## Pendências

### TODO explícito (`data/TODO`)
- **"conecte com postgres"** — o serviço tem `data/app.db` (SQLite) indicando que nunca foi conectado ao Postgres em produção. Precisa: (1) confirmar `.env` com `DATABASE_URL` apontando para o Postgres real; (2) rodar `alembic upgrade head`; (3) remover `data/app.db`.

### TODO no código
- `config.py` linha 7: `#TODO APAGAR, COLOCAR EM .env` — credenciais do banco (`database_url`) têm valor padrão hardcoded com usuário/senha reais (`v7m:v7m@postgres:5432/v7m`). Deve ser obrigatório via `.env` sem default.

### Desvios da CONVENTION
- **Aninhamento:** estrutura `otp/otp/app/` viola a regra `<servico>/app/` (§3).
- **CORS aberto:** `allow_origins=["*"]` — explicitamente marcado como temporário no código; aguarda instrução do usuário para travar.
- **Webhook sem autenticação:** `POST /webhook/notify/{message_id}` é público sem verificação de assinatura (§5 da CONVENTION exige mecanismo de verificação para webhooks externos).
- **PK de otp_logs é Integer** (autoincrement), não UUID — diverge da convenção `PK = UUID` (§4).
- **GET /api/v1/otp e GET /api/v1/otp/logs** são duplicados idênticos — código morto/redundante.
- **Testes em skip** — suíte não passa após migração SQLite → Postgres; conftest precisa ser atualizado.
- **CORS** e autenticação desmilitarizada — por ora todos os endpoints de `api/otp.py` carecem de qualquer validação de origem (aceitável na DMZ conforme CLAUDE.md, mas registrado como pendência).
