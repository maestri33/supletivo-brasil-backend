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

---

## Padrões validados (2026-05-28)

### Envio de mídia — WhatsApp vs Email

| Canal     | Usar URL    | Por quê                                                                                                                                                          |
|-----------|-------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| WhatsApp  | **LAN interna** (ex. `http://10.1.20.30:8002/media/image/<uuid>.jpg`) | O Evolution (em `10.1.20.200`) precisa baixar o arquivo. Se a URL pública (`api.m33.live`) estiver firewalled na rota dele, a sendMedia retorna 500 `AggregateError` ou 201 com entrega silenciosa falha. URL LAN evita essa rota. |
| Email     | **URL pública** embedada via `<img src="https://api.m33.live/...">` no HTML | O cliente de email (Gmail/Outlook) é quem baixa a imagem na hora de renderizar — precisa de URL alcançável pela internet. URL LAN não funciona pro destinatário. |

### Pré-requisitos para `POST /api/v1/messages/send`

1. **Contact existe** em `notify.contacts` apontando para um `auth.users.external_id` válido (FK obrigatório). Pra criar um contact novo precisa primeiro inserir o user:
   ```sql
   INSERT INTO auth.users DEFAULT VALUES RETURNING external_id;
   -- depois POST /api/v1/contacts com esse external_id (UUID), email e/ou phone
   ```
2. Phone no formato `DDI+DDD+numero` sem máscara, ex `5543996648750`.

### Envio de email — padrão canônico (Mailcow via SSH + sendmail)

O Mailcow vive na **VM 150** (`mail.v7m.org`, IP público `135.181.216.147`), acessível como host `mail` no tailnet **goat-gila**. A receita canônica para disparar email é injetar a mensagem direto no Postfix do container, sem SMTP AUTH — o rspamd assina DKIM automaticamente:

```bash
ssh mail 'cat > /tmp/mail.eml <<EOF
From: "Nome" <noreply@v7m.org>
To: alvo@exemplo.com
Subject: Assunto
MIME-Version: 1.0
Content-Type: text/html; charset=UTF-8

<!DOCTYPE html><html><body>
  <p>HTML body com <a href="...">link</a> e <img src="https://..."/>.</p>
</body></html>
EOF
docker exec -i mailcowdockerized-postfix-mailcow-1 sendmail -t -f noreply@v7m.org < /tmp/mail.eml'
```

**Pré-requisitos:**
- Tailscale instalado e logado no tailnet `goat-gila` (host emissor precisa enxergar o nó `mail`). Sem Tailscale: `ssh: Could not resolve hostname mail`.
- `From:` em domínio com DKIM publicado no Mailcow. **Validado:** `v7m.org`. Outros (`m33.live`, `ieadpg.com/org`, `supletivo.com.br`, `v7m.live/net/org`) requer `dig +short dkim._domainkey.<dominio> TXT` antes.
- Envelope-from (`-f`) bate com header `From:` (alinhamento SPF/DMARC).

**Verificação da entrega:**
```bash
ssh mail 'docker logs --tail 200 mailcowdockerized-postfix-mailcow-1 2>&1 | grep -iE "alvo@exemplo|<subject-unico>"'
# Padrão de sucesso: status=sent (250 ...) seguido de queue removed
ssh mail 'docker logs --tail 200 mailcowdockerized-rspamd-mailcow-1 2>&1 | grep "<QID>"'
# Score saudável: < 5.0, com DKIM_SIGNED presente
```

`status=sent` é entrega no servidor remoto, **não** garantia de inbox. Gmail pode dropar silenciosamente domínio novo. `_dmarc.v7m.org` está em `p=quarantine`, então DKIM/SPF falhando → spam direto.

### Por que NÃO usar `MAILCOW_SMTP_*` no `notify` deste host

O `SMTPClient` em `app/integrations/smtp.py` tenta conectar TCP em `mail.v7m.org:587`. Daqui (`10.1.20.30`) a rota pública para `135.181.216.0/24` está bloqueada — sintoma: `OSError(101, 'Network is unreachable')`. Opções:
1. **Preferida:** trocar o envio do notify para usar a receita SSH/sendmail acima (refatorar `SMTPClient` para shell-out via Tailscale). Mantém DKIM e reputação do v7m.org.
2. Apontar `MAILCOW_SMTP_HOST` para um relay alcançável daqui (ex: `smtp.gmail.com` com app-pass) — perde alinhamento de domínio e DKIM da v7m.
3. Liberar egress 587 do host pra `135.181.216.0/24` — autoriza o SMTPClient atual a falar com o Mailcow público.

### Configuração legada (vars `MAILCOW_*` no `/backend/.env`)

Enquanto opção 1 não acontece, as envs ainda vivem no `.env` da raiz `/backend` (NÃO em `/backend/notify/.env` — o compose usa `env_file: .env` da raiz):

```env
MAILCOW_SMTP_HOST=<host SMTP alcançável>
MAILCOW_SMTP_PORT=587
MAILCOW_SMTP_USER=<user>
MAILCOW_SMTP_PASS=<app-password>
MAILCOW_FROM_EMAIL=<from>
MAILCOW_FROM_NAME=Supletivo
MAILCOW_TIMEOUT_S=30
```

Após editar: `docker compose -f docker-compose.dev.yml up -d notify`.

### Evolution sendMedia — payload válido

`POST http://10.1.20.200/message/sendMedia/{instance}` com header `apikey: <WHATSAPP_GLOBAL_API_KEY>`:

```json
{
  "number": "5543996648750",
  "mediatype": "image",
  "mimetype": "image/jpeg",
  "caption": "Texto opcional",
  "media": "http://10.1.20.30:8002/media/image/<uuid>.jpg",
  "fileName": "<uuid>.jpg"
}
```

- `mediatype` aceita lowercase (`image|video|audio|document`) — apesar dos docs mostrarem TitleCase.
- `mimetype` e `fileName` são opcionais mas recomendados — sem eles a entrega pode falhar silenciosamente para JPGs grandes.
- Status `PENDING` no retorno é normal — significa enfileirado na rede do WhatsApp, **não erro**.
- A URL em `media` precisa ser baixável **a partir do container Evolution** — não da máquina que está chamando.

### Receita mínima — enviar imagem por WhatsApp + email no mesmo send

```bash
# 1) Garante contato com phone e email
curl -X POST http://localhost:8015/api/v1/contacts \
  -H "Content-Type: application/json" \
  -d '{"external_id":"<UUID-de-auth.users>","phone":"5543996648750","email":"alvo@gmail.com"}'

# 2) Manda mensagem — notify usa URL LAN no WhatsApp e embeda pública no email (template default)
curl -X POST http://localhost:8015/api/v1/messages/send \
  -H "Content-Type: application/json" \
  -d '{
    "external_id":"<UUID>",
    "title":"Assunto",
    "content":"Texto/HTML — links no HTML são preservados pro email",
    "media_url":"http://10.1.20.30:8002/media/image/<uuid>.jpg"
  }'
```

Se quiser URL diferente para email e WhatsApp (LAN vs pública), hoje **não há suporte direto** no payload — `media_url` é um campo só. Workaround: dois sends separados, ou enviar o HTML com `<img src="https://...">` no `content` para email + base64/URL-LAN no `media_url` para WhatsApp.
