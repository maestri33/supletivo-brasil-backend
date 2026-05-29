# Auth — Módulo de Autenticação e Registro

> Serviço: `auth/` · Schema: `auth` · Convenção: `CONVENTION.md`
> Status desta SPEC: pronto para review.

---

## 1. Contexto de Negócio

O módulo `auth` é o **ponto de entrada principal da plataforma** — responsável por
registrar, autenticar e provisionar novos usuários. Quando um usuário se registra,
o `auth` é obrigado a garantir a criação atômica de: **Profile**, **Documents**,
**Address**, **Notify (contato)** e **OTP**.

**Regra dura do TODO:** "JAMAIS PODE TER DOIS USUARIOS com CPF ou PHONE ou EMAIL
iguais ou falsos". A unicidade é **delegada** aos serviços downstream (profiles para
CPF, notify para phone/email), pois a tabela `auth.users` armazena apenas `external_id`.

**Estado atual:** O módulo está **robusto e operacional**. Implementa:
- **Registro** com validação cross-service de CPF/phone + provisionamento em background
- **Check** (verificação de existência) com timing obfuscado (COD-32)
- **Recover** (recuperação de external_id por CPF/phone)
- **Login** com OTP + emissão JWT via serviço `jwt` externo
- **Atomic wipe** (limpeza total do ecossistema, two-step)
- **Audit logs** (armazenados em Redis, consulta admin-only)
- **Auth guard** (validação JWKS para proteger endpoints internos)

**Gap identificado:** O módulo é funcional mas tem pendências:
1. **Email não é coletado** no registro — apenas phone e CPF. A unicidade de email
   ficará a cargo dos serviços downstream quando o email for coletado.
2. **Validação de "falsos"** — o TODO diz "CPF ou PHONE ou EMAIL iguais ou falsos".
   A validação de CPF é apenas formato (11 dígitos, não-repetido). Não há validação
   de dígito verificador algorítmico.
3. **Blocking** de usuários existe no `roles` (integrado) mas o auth não consulta
   `is_blocked` antes de emitir OTP/JWT no login.

## 2. Atores

| Ator | Role | Ação |
|------|------|------|
| **Novo usuário** | `visitor` (sem role) | Chama `POST /register` com CPF + phone + role desejada |
| **Usuário registrado** | Qualquer role ativa | Autentica via `POST /check` → OTP → `POST /login` → JWT |
| **Admin** | `admin` (JWT) | Acessa logs, executa atomic wipe |
| **Sistema (profiles)** | Serviço downstream | Valida CPF, cria perfil mínimo |
| **Sistema (notify)** | Serviço downstream | Valida phone, cria contato, envia OTP via SMS |
| **Sistema (roles)** | Serviço downstream | Gerencia roles, valida se role é de entrada |
| **Sistema (otp)** | Serviço downstream | Gera e valida códigos OTP |
| **Sistema (jwt)** | Serviço downstream | Emite e valida tokens JWT (RS256, JWKS) |
| **Sistema (documents)** | Serviço downstream | Provisiona slot de documentos vazio |
| **Sistema (address)** | Serviço downstream | Provisiona slot de endereço vazio |

## 3. Estados / Máquina de Estados

O auth **não tem máquina de estados interna** (diferente de enrollment/lead).
O fluxo é transacional e linear:

### Fluxo de Registro
```
Request → validate_cpf → validate_phone → create_user (commit) → provision_async
Provision: roles.assign → profiles.create → notify.create → documents.ensure → address.ensure → dispatch_otp
```

### Fluxo de Autenticação
```
POST /check (CPF/phone/external_id) → lookup → OTP dispatch
POST /login (external_id + otp + role) → verify role → verify OTP → issue JWT → return token
```

### Fluxo de Recuperação
```
POST /recover (CPF/phone) → lookup → OTP dispatch (phone)
```

**Nota:** Não há estados persistidos. O "estado" é a existência do registro em `auth.users`
+ a posse de roles ativas + a validade do OTP (efêmero, via Redis no serviço `otp`).

## 4. Entidades & Campos

### Schema `auth`

#### `users` — Agregado de usuário

| Coluna | Tipo | Nullable | Default | FK / Índice | Descrição |
|--------|------|----------|---------|-------------|-----------|
| `id` | `UUID` PK | NOT NULL | `uuid4()` | — | PK interno (serial) |
| `external_id` | `UUID` | NOT NULL | `uuid4()` | **UNIQUE INDEX** | UUID público, usado como referência cross-service |
| `created_at` | `DateTime(tz)` | NOT NULL | `now()` | — | Timestamp de criação |

**Nota:** CPF, phone, email **não** residem nesta tabela. São delegados a `profiles` (CPF)
e `notify` (phone, email). A tabela `users` é propositalmente mínima — só o `external_id`.

#### `user_roles` — Roles do usuário (shadow table read-only)

| Coluna | Tipo | Nullable | Default | FK / Índice | Descrição |
|--------|------|----------|---------|-------------|-----------|
| `id` | `UUID` PK | NOT NULL | `uuid4()` | — | PK |
| `user_id` | `UUID` | NOT NULL | — | FK → `users.external_id` (CASCADE) | UUID do usuário |
| `role` | `String` | NOT NULL | — | — | Nome da role |
| `assigned_at` | `DateTime(tz)` | NOT NULL | `now()` | — | Quando foi atribuída |
| `revoked_at` | `DateTime(tz)` | NULL | — | — | Quando foi revogada (soft delete) |

**Nota:** A tabela `user_roles` existe no schema `auth` mas o **dono** das roles é o
serviço `roles`. O auth usa esta tabela como shadow table para resolver FKs locais.
A escrita é feita pelo serviço `roles` — o auth apenas lê (via integração HTTP).

#### `alembic_version` — Controle de migrações

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `version_num` | `String` | Versão atual da migração |

### Migrações existentes (7)

1. `create_auth_users_table` — Criação inicial da tabela `users`
2. `replace_users_with_identity_role_tables` — Separação de roles
3. `rename_identities_to_users` — Renomeação
4. `rename_id_external_drop_phone` — Remove phone da tabela users
5. `add_refresh_tokens_table` — Tabela de refresh tokens (legado, pode ter sido removida)
6. `add_blocking_to_role_rules` — Suporte a blocking nas regras
7. `add_forbids_role` — Suporte a role proibida

## 5. Endpoints

### 5.1. Registro (desmilitarizado)

| Campo | Valor |
|-------|-------|
| **Método** | `POST` |
| **Rota** | `/api/v1/register` |
| **Tipo** | **Desmilitarizado** (app para app) |
| **Auth** | Nenhuma |
| **Request body** | `{"role": "string", "phone": "string", "cpf": "string"}` |
| **Response** | `201` — `{"external_id": "UUID"}` |
| **Erros** | `409` CPF/phone já cadastrado; `422` CPF/phone inválido ou role não é de entrada; `502` serviço downstream indisponível |
| **Side-effects** | Cria `User` no DB (commit síncrono); provisiona roles, profiles, notify, documents, address + dispatch OTP em background |
| **Idempotência** | Não — segunda chamada com mesmo CPF/phone retorna `409` |

**Regras de negócio:**
- CPF é validado localmente (11 dígitos, não repetido) e remotamente (profiles.check_cpf)
- Phone é validado localmente (10-11 dígitos) e remotamente (notify.check_contact)
- Role é validada contra `roles.get_rules` — deve ter `from_role=None` (role de entrada)
- **Commit síncrono antes de retornar** — evita race condition com downstream que tenta FK→auth.users

### 5.2. Verificação / Check (público)

| Campo | Valor |
|-------|-------|
| **Método** | `POST` |
| **Rota** | `/api/v1/check` |
| **Tipo** | **Público** |
| **Auth** | Nenhuma |
| **Request body** | `{"cpf": "string?", "phone": "string?", "external_id": "string?"}` (pelo menos 1 campo) |
| **Response** | `200` — `{"otp_sent": true}` ou `{"otp_wait": N}` |
| **Erros** | `422` formato inválido ou nenhum campo fornecido |
| **Side-effects** | Dispatch OTP em background (sempre, mesmo se usuário não existir) |

**Regras de negócio (COD-32):**
- **Respostas uniformizadas** — nunca diferencia `found=true/false`
- **Timing obfuscado** — jitter aleatório (100-300ms) para mascarar latência de not-found
- **Rate limit** — Redis-based: 1 OTP por 30s por `external_id` (ou IP para anon)
- Quando usuário não existe, `dispatch_otp` falha silenciosamente (sem efeito externo)

### 5.3. Recuperação / Recover (público)

| Campo | Valor |
|-------|-------|
| **Método** | `POST` |
| **Rota** | `/api/v1/recover` |
| **Tipo** | **Público** |
| **Auth** | Nenhuma |
| **Request body** | `{"cpf": "string?", "phone": "string?"}` (pelo menos 1 campo) |
| **Response** | `200` — `{"found": true, "otp_sent": true}` ou `{"found": true, "otp_wait": N}` |
| **Erros** | `422` formato inválido ou nenhum campo fornecido |

**Regras de negócio:**
- Sempre retorna `found: true` (nunca expõe existência do usuário)
- External_id **nunca** é retornado na resposta — o usuário recebe OTP no phone
- Rate limit idêntico ao check

### 5.4. Login (desmilitarizado)

| Campo | Valor |
|-------|-------|
| **Método** | `POST` |
| **Rota** | `/api/v1/login` |
| **Tipo** | **Desmilitarizado** |
| **Auth** | Nenhuma (OTP é o fator de autenticação) |
| **Request body** | `{"external_id": "UUID", "otp": "string", "role": "string"}` |
| **Response** | `200` — `{"access_token": "string", "token_type": "bearer"}` |
| **Erros** | `401` OTP inválido/expirado; `403` role não pertence ao usuário |
| **Side-effects** | Valida OTP e emite JWT via `jwt` service |

**Fluxo:**
1. Busca roles ativas do usuário via `roles.get_roles`
2. Verifica se a role pedida está entre as roles ativas
3. Valida OTP via `otp.check`
4. Emite JWT com todas as roles ativas via `jwt.issue`

### 5.5. Atomic Wipe (autenticado — admin)

| Campo | Valor |
|-------|-------|
| **Método** | `POST` + `DELETE` (two-step) |
| **Rota** | `POST /api/v1/atomic` → `DELETE /api/v1/atomic/{atomic_id}` |
| **Tipo** | **Autenticado** (JWT com role `admin`) |
| **Auth** | JWT com role `admin` (validado via JWKS do serviço `jwt`) |
| **TTL** | 60 segundos entre create e execute |
| **Side-effects** | Apaga todos os dados de: auth (todas as tabelas), profiles, roles (usuários), notify, lead (leads + checkouts), Redis logs |

### 5.6. Consulta de Logs (autenticado — admin)

| Campo | Valor |
|-------|-------|
| **Método** | `GET` / `DELETE` |
| **Rota** | `/api/v1/log` |
| **Tipo** | **Autenticado** (JWT com role `admin`) |
| **Query params** | `direction` (in|out), `service`, `method`, `status`, `limit` (1-200, default 50), `offset` |
| **Response** | `200` — `{"total": N, "limit": N, "offset": N, "logs": [...]}` |

### 5.7. Health / Ready (desmilitarizado)

| Campo | Valor |
|-------|-------|
| **Método** | `GET` |
| **Rotas** | `/health`, `/ready` |
| **Tipo** | **Desmilitarizado** |
| **Response** | `{"status": "ok/ready", "version": "..."}` |

### 5.8. Métricas (desmilitarizado)

| Campo | Valor |
|-------|-------|
| **Método** | `GET` |
| **Rota** | `/metrics` |
| **Tipo** | **Desmilitarizado** (Prometheus format) |
| **Métricas** | `auth_http_requests_total` (counter), `auth_http_request_duration_seconds` (histogram) |

## 6. Integrações Externas

| Serviço | Tipo de integração | Propósito | Client em |
|---------|-------------------|-----------|-----------|
| `profiles` | HTTP (niquests, desmilitarizado) | Validar CPF, criar perfil mínimo, consultar perfil | `integrations/profiles.py` |
| `notify` | HTTP (niquests, desmilitarizado) | Validar phone, criar contato, consultar contato | `integrations/notify.py` |
| `roles` | HTTP (niquests, desmilitarizado) | Atribuir roles, consultar roles, verificar bloqueio, validar role de entrada | `integrations/roles.py` |
| `otp` | HTTP (niquests, desmilitarizado) | Gerar e validar códigos OTP | `integrations/otp.py` |
| `jwt` | HTTP (niquests, desmilitarizado) | Emitir tokens JWT, obter JWKS público | `integrations/jwt.py` |
| `documents` | HTTP (httpx, desmilitarizado) | Provisionar slot de documentos vazio (get-or-create) | `integrations/documents.py` |
| `address` | HTTP (httpx, desmilitarizado) | Provisionar slot de endereço vazio (get-or-create) | `integrations/address.py` |

**Padrão de integração:**
- Clients usam context manager (`async with Client() as c:`)
- **Best-effort** no provisionamento — falha é logada (structlog) e não impede os passos seguintes
- Exceções são tipadas (`ProfilesError`, `NotifyError`, etc.) com `status` e `detail`
- Logs nunca expõem PII (CPF, phone) — `sanitize_log_body` em todos os clients
- **Inconsistência de lib:** `profiles`, `notify`, `roles`, `otp`, `jwt` usam `niquests` (async); `documents`, `address` usam `httpx` — padronizar para `httpx` (CONVENTION §2)

## 7. Eventos Disparados / Consumidos

### Consumidos

Nenhum. O auth é o ponto de entrada — não consome eventos de outros serviços.

### Disparados

| Evento | Gatilho | Destino |
|--------|---------|---------|
| `user.registered` (implícito) | Registro bem-sucedido | Provisionamento em background: roles, profiles, notify, documents, address |
| `otp.dispatched` (implícito) | Após registro ou check/recover | Serviço `otp` → SMS via `notify` |

**Nota:** Não há eventos formais (webhooks/event bus). A comunicação é HTTP síncrono
ou background tasks do FastAPI. O padrão de eventos é mais formal em outros módulos
(enrollment, lead).

## 8. Regras de Negócio Invariantes

1. **JAMAIS dois usuários com mesmo CPF** — "JAMAIS PODE TER DOIS USUARIOS com CPF iguais" (TODO). Validado remotamente via `profiles.check_cpf` antes do registro. Invariante: se `cpf_result["found"]` → `409 Conflict`.

2. **JAMAIS dois usuários com mesmo phone** — "JAMAIS PODE TER DOIS USUARIOS com PHONE iguais" (TODO). Validado remotamente via `notify.check_contact` antes do registro. Invariante: se `phone_result["found"]` → `409 Conflict`.

3. **JAMAIS dois usuários com mesmo email** — "JAMAIS PODE TER DOIS USUARIOS com EMAIL iguais" (TODO). **Gap:** Email não é coletado no registro. A unicidade será delegada ao `notify` quando email for coletado downstream.

4. **CPF não pode ser falso** — "ou falsos" (TODO). Validação local: 11 dígitos, não-repetido. Validação remota: profiles aceita/rejeita. **Gap:** Não há validação de dígito verificador algorítmico (módulo 11).

5. **Phone não pode ser falso** — Validação local: 10-11 dígitos. Validação remota: notify aceita/rejeita. **Gap:** Não há validação de prefixo/DDD.

6. **Role de entrada obrigatória** — Registro só aceita roles com `from_role=None` no `roles` service. Tentativa de registrar com role não-entrada → `422 VALIDATION_ERROR`.

7. **Commit síncrono antes de provisionamento** — "evitar race com servicos a jusante que tentam inserir FK->auth.users antes do commit" (código). O `User` é commitado antes de retornar `201`. Background tasks rodam após o response.

8. **Provisionamento é best-effort** — Falha de qualquer integração (profiles, notify, documents, address) é logada mas **não impede** os passos seguintes nem invalida o registro. Padrão CONVENTION §12.

9. **Respostas uniformizadas em check/recover (COD-32)** — Nunca diferenciar `found=true/false`. Timing obfuscado. OTP sempre dispatchado (mesmo para not-found, falha silenciosamente).

10. **Admin-only para operações destrutivas** — Atomic wipe e logs requerem JWT com role `admin`, validado via JWKS.

## 9. Critérios de Aceite

1. [ ] `POST /register` com CPF/phone/role válidos cria `User` (commit síncrono) e retorna `external_id` em `201`.
2. [ ] `POST /register` com CPF duplicado retorna `409 CPF_EXISTS`.
3. [ ] `POST /register` com phone duplicado retorna `409 PHONE_EXISTS`.
4. [ ] `POST /register` com CPF inválido (formato) retorna `422 CPF_INVALID`.
5. [ ] `POST /register` com phone inválido (formato) retorna `422 PHONE_INVALID`.
6. [ ] `POST /register` com role não-entrada retorna `422 INVALID_ENTRY_ROLE`.
7. [ ] Após registro, provisionamento executa: roles.assign → profiles.create → notify.create → documents.ensure → address.ensure → otp.dispatch (best-effort).
8. [ ] `POST /check` com CPF existente retorna `{"otp_sent": true}` ou `{"otp_wait": N}`.
9. [ ] `POST /check` com CPF inexistente retorna **mesmo shape** (não vaza existência).
10. [ ] `POST /check` respeita rate limit de 30s por external_id/IP.
11. [ ] `POST /recover` com CPF existente retorna `{"found": true, "otp_sent": true}` e nunca expõe `external_id`.
12. [ ] `POST /login` com OTP válido + role ativa retorna JWT (`access_token`).
13. [ ] `POST /login` com OTP inválido retorna `401 OTP_INVALID`.
14. [ ] `POST /login` com role não pertencente ao usuário retorna `403 ROLE_NOT_HELD`.
15. [ ] `POST /atomic` (admin) gera token com TTL 60s.
16. [ ] `DELETE /atomic/{id}` (admin) apaga dados de todos os serviços.
17. [ ] `GET /log` (admin) retorna logs de auditoria com filtros.
18. [ ] `GET /health` e `GET /ready` respondem sem autenticação.
19. [ ] `ruff` limpo + testes verdes + `alembic upgrade head` válido.

## 10. Riscos / Open Questions

### Riscos

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| Unicidade de email não garantida | Alta | Médio | Delegar ao `notify` quando email for coletado downstream |
| Validação de CPF "falso" fraca | Média | Médio | Adicionar validação de dígito verificador (módulo 11) |
| Race condition: registro simultâneo com mesmo CPF | Baixa | Alto | Perfil remoto (`profiles`) tem constraint UNIQUE; registro retorna `409` |
| Falha de provisionamento em massa | Média | Baixo | Best-effort + logging; registro já efetivado |
| Inconsistência de lib HTTP (niquests vs httpx) | Baixa | Baixo | Padronizar para httpx (CONVENTION §2) |
| OTP bypass se serviço `otp` cair | Baixa | Alto | Login falha com `502`; fallback futuro: rate limit local |

### Open Questions

- [ ] **Validação de dígito verificador CPF** — O TODO diz "falsos". Deve-se implementar módulo 11 no `validate_cpf`? Ou a validação remota via `profiles` é suficiente?
- [ ] **Coleta de email no registro** — O TODO menciona EMAIL mas o registro não coleta. Deve-se adicionar campo `email` opcional no `RegisterRequest`?
- [ ] **Consulta de `is_blocked` no login** — O `roles` tem endpoint de blocking mas o login não consulta. Deve-se bloquear login de usuários bloqueados?
- [ ] **Padronização de HTTP client** — `niquests` (profiles, notify, roles, otp, jwt) vs `httpx` (documents, address). Migrar tudo para `httpx`?
- [ ] **Refresh token flow** — Existe migração `add_refresh_tokens_table` mas não há endpoint de refresh. Implementar ou remover?
- [ ] **Rate limit global vs per-endpoint** — slowapi está configurado como `200/minute` global. Deve-se ter limites mais agressivos para `/register` e `/check`?

---

*Status: SPEC consolidado do TODO + código existente + análise estática. Aguardando review humano antes de implementação.*
