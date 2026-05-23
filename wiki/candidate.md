# candidate

## Função
Gerencia o funil de cadastro de candidatos a promotores (aspirantes), conduzindo-os por etapas sequenciais de status — desde a captura até a espera de aprovação — e delegando persistência de perfil, endereço e autenticação a outros microsserviços.

## Status
**Parcial / Protótipo** — o serviço implementa apenas as 4 primeiras etapas do funil (captured → personal → education → birth → waiting) descritas no TODO. Faltam as etapas 3–6 do TODO: endereço (o router `address` existe mas avança para `waiting` sem passar por `ADDRESS`), documentos (RG/CNH), chave pix/Asaas e selfie/conclusão. Não há migrações Alembic (banco via `sqlite://db.sqlite3` com `generate_schemas=True`). Não há testes. Endpoints desmilitarizados (`routers/demilitarized/`) existem como pasta vazia.

## Estrutura
Aninhada — pacote real: `candidate/candidate/app/` (deveria ser `candidate/app/` per CONVENTION §3).  
Outros desvios estruturais:
- `routers/` em vez de `api/` (CONVENTION §3 exige `api/`)
- `models.py` e `schemas.py` como arquivos únicos (devem ser pastas `models/` e `schemas/`)
- Sem `db.py`, `services/`, `exceptions.py`
- Sem `pyproject.toml` / `alembic.ini` / `README.md`

## Endpoints

### `routers/public/auth.py` — público
| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/api/v1/public/check` | Verifica CPF/phone e dispara OTP via auth-service |
| POST | `/api/v1/public/register` | Registra novo lead no auth e cria `Lead` local; notifica lead e hub |
| POST | `/api/v1/public/login` | Valida OTP e retorna JWT (role `lead`) |
| POST | `/api/v1/public/refresh` | Renova tokens via jwt-service |

### `routers/authenticated/captured.py` — autenticado (JWT + status `captured`)
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/v1/authenticated/captured` | Retorna nome/phone/email do lead capturado |
| POST | `/api/v1/authenticated/captured` | Salva nome e e-mail; avança para `personal` |

### `routers/authenticated/personal.py` — autenticado (status `personal`)
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/v1/authenticated/personal` | Retorna dados pessoais (gênero, filiação, estado civil) |
| POST | `/api/v1/authenticated/personal` | Salva dados pessoais; avança para `education` |

### `routers/authenticated/educational.py` — autenticado (status `education`)
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/v1/authenticated/educational` | Retorna dados educacionais |
| POST | `/api/v1/authenticated/educational` | Salva dados educacionais; avança para `birth` |

### `routers/authenticated/birth.py` — autenticado (status `birth`)
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/v1/authenticated/birth` | Retorna data de nascimento, naturalidade e nacionalidade |
| POST | `/api/v1/authenticated/birth` | Salva dados de nascimento; avança para `waiting` |

### `routers/authenticated/address.py` — autenticado (status `address`)
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/v1/authenticated/address` | Retorna endereço vinculado ao lead |
| GET | `/api/v1/authenticated/address/cep/{cep}` | Consulta CEP via address-service |
| POST | `/api/v1/authenticated/address` | Cria endereço e avança para `waiting` |

### `main.py` — público
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/health` | Liveness check |
| GET | `/ready` | Readiness check |

## Dados
Banco atual: **SQLite** (`db.sqlite3`, via Tortoise ORM — não SQLAlchemy). Schema sem nome próprio, sem migrações Alembic.

### Tabela `leads`
| Campo | Tipo | Obs |
|-------|------|-----|
| `id` | BigInt PK | auto |
| `external_id` | UUID unique+index | FK lógica para `auth.users` |
| `status` | CharEnum | captured/personal/education/birth/address/waiting/checkout/completed |
| `hub_external_id` | UUID null+index | referência ao hub |
| `created_at` / `updated_at` | Datetime | auto |

### Tabela `checkouts`
| Campo | Tipo | Obs |
|-------|------|-----|
| `id` | BigInt PK | |
| `external_id` | UUID unique+index | referência ao lead |
| `checkout_url` / `receipt_url` | Char(1024) null | |
| `invoice_slug` / `transaction_nsu` | Char(255) null+index | |
| `capture_method` | Char(50) null | |
| `installments` | SmallInt null | |
| `is_paid` | Bool index | |

### Tabela `messages`
| Campo | Tipo | Obs |
|-------|------|-----|
| `id` | BigInt PK | |
| `message_id` | Int null+index | ID retornado pelo notify |
| `external_id` | UUID index | referência ao lead |
| `direction` | Char(10) | out/in |
| `channel` | Char(20) null | whatsapp/email/tts |
| `content` | Text null | |
| `status` | Char(30) null+index | sent/delivered/read/failed |
| `event` | Char(50) null | message.sent/delivered/failed |
| `meta` | JSON null | dados extras de webhook |

Não há shadow tables cross-schema (não foi possível implementar — Tortoise ORM não suporta o padrão da CONVENTION).

## Integrações

### Internas (via httpx + retry exponencial)
| Client | Serviço | Operações |
|--------|---------|-----------|
| `AuthClient` | auth (`AUTH_BASE_URL`) | check CPF/phone/OTP, register (role=lead), login |
| `JwtClient` | jwt-service (`JWT_BASE_URL`) | refresh token |
| `NotifyClient` | notify (`NOTIFY_BASE_URL`) | get_contact, update_email, send_message |
| `ProfilesClient` | profiles (`PROFILES_BASE_URL`) | get, first_name, patch |
| `AddressClient` | address (`ADDRESSES_BASE_URL`) | CRUD endereço, check CEP, bind entity, upload proof |

### Externas
| Serviço | Onde | Status |
|---------|------|--------|
| InfinitePay | `INFINITEPAY_BASE_URL` em config | declarada na config, **sem client implementado** |
| Webhook enrollment | `WEBHOOK_ENROLLMENT_URL` | declarado, sem uso no código atual |
| Webhook hub | `WEBHOOK_HUB_URL` | declarado, sem uso no código atual |

**Atenção:** `request_with_retry` usa `time.sleep()` síncrono (bloqueante) no loop de retry — deve ser `asyncio.sleep()`.

## Pendências

### Arquivo TODO (candidate/candidate/TODO)
O candidato é o aspirante a promotor. Fluxo esperado (não implementado integralmente):
1. `POST /register` — phone, cpf, hub (com HUB_DEFAULT fallback) ✅ implementado
2. `POST /profile` — completar perfil (CPF puxa nome via profiles) — **parcialmente** (captured/personal/education/birth, mas sem etapa CPF→nome automático)
3. `POST /address` — endereço (CEP primeiro, sem duplicar lógica) — **parcial** (router existe mas status `address` nunca é atribuído no fluxo)
4. Documents — RG ou CNH — **não implementado**
5. Chave pix — cadastro e validação no Asaas — **não implementado** (INFINITEPAY_BASE_URL declarado mas sem client)
6. Selfie real (valida como assinatura de contrato) → se ok, conclui fase candidate, update role para `training`, cria novo registro — **não implementado**

Endpoints desmilitarizados (listar candidatos, filtrar por hub, etc.) — **não implementados** (`routers/demilitarized/__init__.py` vazio).

### Desvios da CONVENTION
| Item | Desvio | Severidade |
|------|--------|-----------|
| Aninhamento | `candidate/candidate/app/` em vez de `candidate/app/` | ❌ bloqueia |
| ORM | Tortoise ORM + SQLite em vez de SQLAlchemy 2.0 async + asyncpg + Postgres | ❌ bloqueia |
| Diretórios | `routers/` em vez de `api/`; `models.py`/`schemas.py` arquivos, não pastas | ❌ bloqueia |
| Migrações | Sem Alembic; usa `generate_schemas=True` | ❌ bloqueia produção |
| Banco | SQLite local em vez de Postgres com schema próprio | ❌ bloqueia produção |
| `time.sleep` síncrono | Bloqueante no retry assíncrono; deve ser `asyncio.sleep` | ⚠️ bug de performance |
| `fastapi-structured-logging` | Lib fora da stack canônica (deveria ser `structlog` direto) | ⚠️ justificativa ausente |
| `tortoise-orm` | Lib proibida/fora da stack; `python-dotenv` também fora (pydantic-settings lê .env nativo) | ❌ bloqueia |
| `load_dotenv()` explícito | Redundante com pydantic-settings; antipadrão da CONVENTION | ⚠️ ajustar |
| Schemas nos routers | Schemas Pydantic definidos dentro dos arquivos de router, não em `schemas/` | ⚠️ ajustar |
| Lógica de negócio no router | Sem camada `services/`; toda lógica diretamente no endpoint | ⚠️ ajustar |
| Sem testes | Nenhum teste presente | ⚠️ ajustar |
| `dependencies.py` verifica role `lead` | Serviço é `candidate`, mas valida JWT role `lead` — pode ser intencional (mesmo usuário muda de role), mas não está documentado | ⚠️ confirmar |
| `address` router não atribui status `ADDRESS` | O fluxo pula a etapa: captured→personal→education→birth→waiting, nunca passa por `address` | ❌ bug de fluxo |
