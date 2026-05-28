# candidate

## Função
Conduz o **funil de cadastro de candidatos a promotor** (aspirantes), do registro
à conclusão, avançando por etapas sequenciais de status e **orquestrando** os
serviços donos de cada dado (auth, profiles, address, documents, asaas, roles) —
sem duplicar lógica. Ao concluir, promove o usuário para `training`.

## Status
**Funcional (Fase A+B do PLANO_ADEQUACAO, 2026-05-24)** — reescrito de Tortoise+SQLite
para a stack canônica (SQLAlchemy 2.0 async + asyncpg + Postgres schema `candidate`
+ Alembic). Funil completo: captured → personal → education → birth → address →
documents → pixkey → selfie → completed. ruff limpo, 13 testes, `alembic upgrade head`
aplicado, boot ok.

**Pendência conhecida (sem TODO órfão):** a criação do registro no serviço `training`
(passo 6 do `candidate/TODO`) só será implementada quando esse serviço existir
(é green-field, Parte B). Hoje a conclusão **promove o papel** lead→training via
`roles` e encerra o candidate em `completed`.

## Stack
Python 3.12 + uv · FastAPI · SQLAlchemy 2.0 async (`Mapped`/`mapped_column`) · asyncpg
· Alembic · Pydantic v2 + pydantic-settings · httpx.AsyncClient · structlog.

## Estrutura
`candidate/app/` (achatado): `main.py`, `config.py`, `db.py`, `exceptions.py`,
`dependencies.py`, `utils/logging.py`, `models/`, `schemas/`, `services/`,
`integrations/`, `api/{public,authenticated,demilitarized}/` + `api/router.py`.
`alembic/` (env async + revisão `0001`), `tests/`, `pyproject.toml`, `README.md`,
`.claude/`.

## Endpoints

### `api/public/auth.py` — público (exposto)
| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/api/v1/public/check` | Verifica CPF/phone/external_id e dispara OTP (auth) |
| POST | `/api/v1/public/register` | Registra no auth (role lead) + cria Candidate; notifica lead e hub |
| POST | `/api/v1/public/login` | Valida OTP e retorna JWT + status atual |
| POST | `/api/v1/public/refresh` | Renova tokens (jwt) |

### `api/authenticated/*` — autenticado (JWT role `lead` + gate por status)
| Método | Rota | Status exigido → próximo |
|--------|------|--------------------------|
| GET/POST | `/api/v1/authenticated/captured` | captured → personal (nome+email) |
| GET/POST | `/api/v1/authenticated/personal` | personal → education |
| GET/POST | `/api/v1/authenticated/educational` | education → birth |
| GET/POST | `/api/v1/authenticated/birth` | birth → address |
| GET | `/api/v1/authenticated/address/cep/{cep}` | consulta CEP (address) |
| GET/POST | `/api/v1/authenticated/address` | address → documents |
| GET | `/api/v1/authenticated/documents` | estado RG/CNH |
| PUT | `/api/v1/authenticated/documents` | salva dados RG ou CNH (documents) |
| POST | `/api/v1/authenticated/documents/images/{slot}` | upload frente/verso |
| POST | `/api/v1/authenticated/documents/submit` | valida completude → pixkey |
| GET/POST | `/api/v1/authenticated/pixkey` | pixkey → selfie (valida no asaas) |
| GET/POST | `/api/v1/authenticated/selfie` | selfie → completed (promove a training) |

### `api/demilitarized/candidates.py` — interno (sem auth, §5)
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/v1/demilitarized/candidates` | lista/filtra por hub e status |
| GET | `/api/v1/demilitarized/candidates/{external_id}` | busca por external_id |

### `main.py` — `/health`, `/ready`, `/status`

## Dados
Schema **`candidate`** no Postgres central. Tabela única **`candidates`**:
`id` (UUID PK), `external_id` (UUID unique — ref. lógica a `auth.users`, sem FK),
`status` (String), `hub_external_id` (UUID null), `created_at`/`updated_at`
(timestamptz). Os models `Checkout`/`Message` (cópia morta do lead) foram
**removidos** — candidate não tem pagamento (a chave PIX é para RECEBER comissões).

## Integrações (httpx + retry exponencial assíncrono)
| Client | Serviço | Uso |
|--------|---------|-----|
| `AuthClient` | auth | check/register(role=lead)/login |
| `JwtClient` | jwt | refresh |
| `NotifyClient` | notify | contato + envio de mensagens (§11) |
| `ProfilesClient` | profiles | dados de perfil + CPF (titular do PIX) |
| `AddressClient` | address | CEP + endereço (entity_type `lead`) |
| `AsaasClient` | asaas | `POST /pixkey` valida no DICT + confere titular (§12) |
| `DocumentsClient` | documents | RG/CNH (dados+imagens) e selfie (slot `foto`) |
| `AIClient` | ai | `/image/vision` valida heurística da selfie (§13) |
| `RolesClient` | roles | `POST /role/{id}/up/training` na conclusão |

**Notificações (§11):** o candidato é avisado a cada avanço de etapa e o hub é
avisado na conclusão (via BackgroundTasks, tolerante a falha).

## Observações / a confirmar
- **Selfie:** validação é **heurística** (ai/vision descreve a imagem; barra foto
  sem pessoa). Não é liveness/biometria — não há serviço para isso no ecossistema.
- **entity_type `lead`** no address e **CPF lido de `profiles`** (campo `cpf`) para
  o PIX — suposições documentadas; ajustar se os contratos diferirem.
- `time.sleep` bloqueante do retry corrigido para `asyncio.sleep`.
