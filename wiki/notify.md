# notify

## Função

Microsserviço de notificações multicanal (WhatsApp + e-mail). Recebe pedidos de envio de outros serviços, processa em background, persiste logs de auditoria e gerencia contatos, templates HTML e arquivos de mídia (áudio TTS, imagens).

---

## Status

**Parcial.** Endpoints principais implementados e 3 migrações Alembic presentes (schema inicial, templates/log, seed). Testes cobrem health, contacts, logs, templates, test-email e métricas — mas **faltam testes para messages/send, whatsapp e instructions**. A migração de IA está implementada (`integrations/ai.py`) porém não totalmente validada (ver Pendências).

---

## Estrutura

**Aninhado** — contrariando a convenção (§3 CONVENTION.md):

```
notify/          ← raiz do repositório do serviço
└── notify/      ← pacote real (aninhamento notify/notify/)
    ├── app/
    ├── alembic/
    ├── tests/
    └── ...
```

O pacote Python correto deveria ser `notify/app/`, não `notify/notify/app/`.

---

## Endpoints

### `api/health.py` — desmilitarizados
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/health` | Liveness simples |
| GET | `/ready` | Readiness com ping ao banco |
| GET | `/status` | Uptime + métricas agregadas 24h |

### `api/contacts.py` — desmilitarizados
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/v1/contacts/check` | Verifica existência por phone/email |
| POST | `/api/v1/contacts` | Cria contato |
| GET | `/api/v1/contacts` | Lista contatos (paginado) |
| GET | `/api/v1/contacts/{external_id}` | Obtém contato por UUID |
| PATCH | `/api/v1/contacts/{external_id}/email` | Atualiza e-mail do contato |
| DELETE | `/api/v1/contacts/{external_id}` | Remove contato |

### `api/messages.py` — desmilitarizados
| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/api/v1/messages/send` | Envia mensagem multicanal (background) |
| POST | `/api/v1/messages/test-email` | Disparo de e-mail de teste (sem persistir contato) |
| GET | `/api/v1/messages` | Lista mensagens (filtro por contact_id) |
| GET | `/api/v1/messages/{message_id}` | Obtém mensagem |

### `api/templates.py` — desmilitarizados
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/v1/templates` | Lista templates (filtro is_active) |
| POST | `/api/v1/templates` | Cria template (HTML direto ou via instrução IA) |
| GET | `/api/v1/templates/{slug}` | Obtém template por slug |
| PUT | `/api/v1/templates/{slug}` | Atualiza template (HTML ou instrução IA) |
| DELETE | `/api/v1/templates/{slug}` | Remove template (proibido slug `default`) |
| GET | `/api/v1/templates/email/legacy` | [Legacy] Retorna HTML do template default |

### `api/logs.py` — desmilitarizados
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/v1/logs` | Lista logs (filtro por message_id) |
| GET | `/api/v1/logs/by-external-id/{external_id}` | Timeline de logs por usuário |
| GET | `/api/v1/logs/metrics` | Métricas agregadas (janela configurável) |

### `api/whatsapp.py` — desmilitarizados
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/v1/whatsapp/profile/{external_id}` | Perfil WhatsApp do contato |
| GET | `/api/v1/whatsapp/profiles` | Lista todos os perfis WhatsApp |

### `api/instructions.py` — desmilitarizados
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/v1/instructions` | Lista arquivos `.md` em `media/instructions/` |

---

## Dados

Schema Postgres: **`notify`**. Shadow table cross-schema: `auth.users` (FK `external_id` UUID).

### `notify.contacts`
| Campo | Tipo | Constraints |
|-------|------|-------------|
| `id` | integer | PK autoincrement |
| `external_id` | uuid | UNIQUE, NOT NULL, FK → `auth.users.external_id` |
| `phone` | varchar(30) | UNIQUE, nullable, indexed |
| `email` | varchar(255) | UNIQUE, nullable, indexed |
| `created_at` | timestamptz | server_default now() |
| `updated_at` | timestamptz | server_default now(), onupdate |

### `notify.messages`
| Campo | Tipo | Constraints |
|-------|------|-------------|
| `id` | integer | PK autoincrement |
| `contact_id` | integer | NOT NULL, FK → `notify.contacts.id` CASCADE DELETE |
| `type` | varchar(20) | NOT NULL |
| `content_text` | text | nullable |
| `whatsapp_status` | varchar(20) | default `pending` |
| `email_status` | varchar(20) | default `pending` |
| `email_subject` | varchar(255) | nullable |
| `tts_audio_url` | varchar(500) | nullable |
| `created_at` / `updated_at` | timestamptz | — |

Status válidos: `pending`, `sent`, `failed`, `skipped`.

### `notify.logs`
| Campo | Tipo | Constraints |
|-------|------|-------------|
| `id` | integer | PK autoincrement |
| `message_id` | integer | nullable, FK → `notify.messages.id` CASCADE |
| `external_id` | uuid | nullable, FK → `auth.users.external_id` |
| `action` | varchar(100) | NOT NULL |
| `details` | jsonb | nullable |
| `created_at` | timestamptz | — |

### `notify.templates`
| Campo | Tipo | Constraints |
|-------|------|-------------|
| `id` | integer | PK autoincrement |
| `slug` | varchar(64) | UNIQUE, NOT NULL, indexed |
| `name` | varchar(255) | NOT NULL |
| `html` | text | NOT NULL |
| `version` | integer | default 1 |
| `is_active` | boolean | default true |
| `created_at` / `updated_at` | timestamptz | — |

---

## Integrações

### Internas (httpx)
| Serviço | Client | URL base | Uso |
|---------|--------|----------|-----|
| `ai` | `integrations/ai.py` → `AIClient` | `http://ai:8000` | Geração de texto, imagem, TTS, JSON estruturado |
| `profiles` | `integrations/profiles.py` → `ProfilesClient` | `http://profiles:8000` | Lookup de gênero do usuário para escolha de voz TTS |

### Externas
| Serviço | Client | Descrição |
|---------|--------|-----------|
| WhatsApp (Evolution GO v2) | `integrations/whatsapp.py` → `WhatsAppClient` | Envio de texto, áudio, imagem; resolve número BR |
| E-mail | `integrations/smtp.py` → `SMTPClient` | Envio SMTP genérico (STARTTLS, porta 587) + helpers opcionais de API admin Mailcow |

Todas as chamadas HTTP usam `integrations/http_client.py` com retry configurável.

---

## Pendências

### TODOs no código
- ✅ **Resolvidos (2026-05-24):** removido o `smtp.py` legado (mail merge API); o cliente Mailcow foi renomeado para `SMTPClient` em `integrations/smtp.py` (envio SMTP genérico + helpers admin Mailcow), e os dados de infra (`mailcow_smtp_host`/`mailcow_api_url`) saíram dos defaults do `config.py` para o `.env` (§12).

### Migração de IA — parcial/não validada
- `integrations/deepseek.py`, `integrations/elevenlabs.py` e `integrations/gemini.py` foram **removidos** do diretório `integrations/` (não existem mais).
- O `config.py` ainda possui todas as env vars desses três clientes removidos (`deepseek_*`, `elevenlabs_*`, `gemini_*`) — **órfãos que deveriam ser limpos**.
- `message_service.py` (linhas 587–596) ainda referencia `settings.elevenlabs_voice_male` e `settings.elevenlabs_voice_female` — **referências órfãs ao provider antigo** que podem quebrar silenciosamente se as envs não estiverem presentes.
- O `CLAUDE.md` do serviço ainda lista `deepseek.py`, `elevenlabs.py` e `gemini.py` como arquivos existentes em `app/integrations/` — memória desatualizada.
- A migração para `AIClient` não foi testada end-to-end (sem testes para `/messages/send`).

### Desvios da CONVENTION
- **Aninhamento** (`notify/notify/app`): viola §3 ("Sem aninhamento de nome").
- **PK inteira** em todas as tabelas: a convenção §4 determina `PK = UUID`. Todas as tabelas usam `Integer` autoincrement.
- **Env vars órfãs** no `config.py` para providers removidos: violação de §9 (sem ruído).
- **Sem testes** para `messages/send`, `whatsapp` e `instructions`: cobertura parcial.
- **`media/`** local com arquivos de áudio/imagem versionados no repositório: violação de §9 (dados locais não devem ser versionados).
