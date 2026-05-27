# Address — Microsserviço de Endereços (Production-Ready)

> Serviço: `address/` · Schema: `addresses` · Convenção: `CONVENTION.md`
> **Status:** Funcional (2 recursos implementados, ViaCEP + webhook prontos, testes existem).
> Pendências de produção: cobertura de testes a expandir, provisionamento auth→address, doc desatualizada.
> Status desta SPEC: pronto para review.

---

## 1. Contexto de Negócio

O microsserviço `address` é o **dono centralizado de endereços** na plataforma. Ele atende dois modelos de uso distintos:

1. **Addresses (endereço formal)** — endereço vinculado a um `auth.users` via `external_id` (UUID). Campos com validação forte (NOT NULL), tipagem por `kind` (home/billing/shipping). Usado pelo fluxo principal de cadastro de usuários e matrícula.

2. **EntityAddresses (endereço polimórfico)** — vínculo genérico `(entity_type, external_id)` como strings livres (user/hub/atendimento/parceiro). Endereço totalmente nullable, armazenado em tabela separada (`entity_address_details`). Usado para entidades que não são `auth.users` ou que precisam de endereço avulso/comprovante.

O serviço também provê:
- **Lookup ViaCEP** — consulta externa de CEP brasileiro, com degradação graciosa.
- **Webhook best-effort** — notifica consumidores externos em toda criação/alteração/deleção de `Address`.
- **Upload de comprovante** — upload de arquivo de comprovante de endereço para `entity_addresses` (disco local).

**Estado atual do código (2026-05-27):**
- 3 tabelas com PK UUID (`addresses`, `entity_address_details`, `entity_addresses`) — migração 0001 aplicada.
- Endpoints REST completos para ambos os recursos.
- Integrações ViaCEP e webhook implementadas.
- Testes existem em `address/tests/` (schemas, validators, service) — cobertura a expandir.
- `auth/app/integrations/address.py` existe como fluxo auth→address em andamento.
- `wiki/address.md` desatualizada — descreve estado antigo.

**Problema central:** O serviço é funcional mas não está apto a produção pelos critérios da CONVENTION (§4/§9/§15). Outros serviços (auth, candidate, enrollment) já dependem dele — o custo de deixar assim é dívida que se espalha por consumidores.

## 2. Atores

| Ator | Role | Ação |
|------|------|------|
| **Serviços internos** (auth, candidate, enrollment, etc.) | Consumidores HTTP na zona desmilitarizada | Chamam endpoints CRUD de address via HTTP para ler/gravar endereços de entidades |
| **Usuário final** (via auth) | `user` (autenticado) | Indiretamente — o auth provisiona endereço ao registrar; enrollment orquestra coleta de endereço |
| **Sistema (ViaCEP)** | API externa | Consulta de CEP — retornar dados normalizados de logradouro |
| **Sistema (webhook)** | Consumidor de eventos | Recebe POSTs best-effort em create/update/delete de Address |
| **Engenheiro/mantenedor** | DevOps | Mantém o serviço, roda migrações, acompanha logs |

**Nota:** Todos os endpoints de domínio são desmilitarizados (uso interno). Não há consumidores externos/públicos diretos.

## 3. Estados / Máquina de Estados

### Addresses (endereço formal)

O modelo `Address` não possui máquina de estados — é um CRUD direto. O ciclo de vida é:

```
CREATE → (existe, pode ser PATCHed) → DELETE
```

- Um endereço é criado com todos os campos obrigatórios preenchidos.
- Pode ser atualizado parcialmente via PATCH.
- Pode ser deletado (hard delete).
- O campo `kind` classifica o endereço (home/billing/shipping) — não há transição de kind, ele é definido na criação e pode ser alterado via PATCH.

### EntityAddresses (endereço polimórfico)

O modelo `EntityAddress` segue um ciclo de vida assistido:

```
GET-OR-CREATE → (opcional: update via CEP) → (opcional: upload proof) → (opcional: unlink → novo vazio)
```

| Estado | Significado | Transição para |
|--------|-------------|-----------------|
| Criado (vazio) | `EntityAddress` + `EntityAddressDetail` criados via get-or-create | Preenchido via CEP |
| Preenchido via CEP | Campos de endereço preenchidos pela ViaCEP | Proof enviado |
| Proof enviado | Comprovante de endereço uploaded | Unlink (opcional) |
| Unlinked | Endereço anterior desvinculado, novo vazio criado | Ciclo reinicia |

**Regra:** O get-or-create é idempotente por `(entity_type, external_id)`. O unlink cria um novo `EntityAddressDetail` vazio e reatribui o FK.

## 4. Entidades & Campos

### Schema `addresses`

#### `addresses` — Endereço formal (vinculado a auth.users)

| Coluna | Tipo | Nullable | Default | FK / Índice | Descrição |
|--------|------|----------|---------|-------------|-----------|
| `id` | `UUID` PK | NOT NULL | `uuid4()` | — | PK do endereço |
| `external_id` | `UUID` | NOT NULL | — | FK → `auth.users.external_id` (RESTRICT/CASCADE), INDEX | UUID do dono |
| `kind` | `String(20)` | NOT NULL | — | INDEX | Tipo: `home`, `billing`, `shipping` |
| `zipcode` | `String(8)` | NOT NULL | — | INDEX | CEP (8 dígitos, sem hífen) |
| `street` | `String(200)` | NOT NULL | — | — | Logradouro |
| `number` | `String(20)` | NULL | — | — | Número |
| `complement` | `String(100)` | NULL | — | — | Complemento |
| `neighborhood` | `String(100)` | NULL | — | — | Bairro |
| `city` | `String(100)` | NOT NULL | — | — | Cidade |
| `state` | `String(2)` | NOT NULL | — | — | UF (2 letras) |
| `country` | `String(2)` | NOT NULL | `'BR'` | — | ISO-3166-1 alpha-2 |
| `lat` | `String(30)` | NULL | — | — | Latitude (geocoding futuro) |
| `lng` | `String(30)` | NULL | — | — | Longitude (geocoding futuro) |
| `created_at` | `DateTime(tz)` | NOT NULL | `now()` | — | Timestamp de criação |
| `updated_at` | `DateTime(tz)` | NOT NULL | `now()` ON UPDATE | — | Timestamp de atualização |

#### `entity_address_details` — Endereço genérico/avulso (todos nullable)

| Coluna | Tipo | Nullable | Default | Descrição |
|--------|------|----------|---------|-----------|
| `id` | `UUID` PK | NOT NULL | `uuid4()` | PK |
| `street` | `String(200)` | NULL | — | Logradouro |
| `number` | `String(20)` | NULL | — | Número |
| `complement` | `String(100)` | NULL | — | Complemento |
| `neighborhood` | `String(100)` | NULL | — | Bairro |
| `city` | `String(100)` | NULL | — | Cidade |
| `state` | `String(2)` | NULL | — | UF |
| `zipcode` | `String(8)` | NULL | — | CEP |
| `lat` | `String(30)` | NULL | — | Latitude |
| `lng` | `String(30)` | NULL | — | Longitude |
| `created_at` | `DateTime(tz)` | NOT NULL | `now()` | Timestamp |
| `updated_at` | `DateTime(tz)` | NOT NULL | `now()` ON UPDATE | Timestamp |

#### `entity_addresses` — Vínculo polimórfico (entity_type + external_id)

| Coluna | Tipo | Nullable | Default | FK / Índice | Descrição |
|--------|------|----------|---------|-------------|-----------|
| `id` | `UUID` PK | NOT NULL | `uuid4()` | — | PK do vínculo |
| `entity_type` | `String(50)` | NOT NULL | — | UNIQUE (com external_id) | Tipo da entidade (user, hub, etc.) |
| `external_id` | `String(100)` | NOT NULL | — | UNIQUE (com entity_type) | ID externo da entidade |
| `proof_file` | `String(255)` | NULL | — | — | Path do comprovante uploaded |
| `address_id` | `UUID` | NULL | — | FK → `entity_address_details.id` (SET NULL) | FK para detalhes do endereço |
| `created_at` | `DateTime(tz)` | NOT NULL | `now()` | — | Timestamp |
| `updated_at` | `DateTime(tz)` | NOT NULL | `now()` ON UPDATE | — | Timestamp |

**Constraint:** `UNIQUE(entity_type, external_id)` — 1 vínculo por entidade.

### Schemas Pydantic

| Schema | Uso | Campos obrigatórios |
|--------|-----|---------------------|
| `AddressCreate` | POST /addresses | `external_id`, `kind`, `zipcode`, `street`, `city`, `state` |
| `AddressPatch` | PATCH /addresses/{id} | Todos opcionais |
| `AddressRead` | Response de Address | Todos do modelo |
| `ViaCepResult` | GET /addresses/cep/{zipcode} | `zipcode` (+ opcionais da ViaCEP) |
| `EntityAddressRead` | Response de EntityAddress | `id`, `entity_type`, `external_id` |
| `AddressDraftRead` | Response de EntityAddressDetail | `id` (+ todos opcionais) |

## 5. Endpoints

### 5.1. Health / Status (público)

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/health` | Health check simples — `{"status": "ok"}` |
| `GET` | `/ready` | Readiness check — testa conexão com PG |
| `GET` | `/status` | Status com versão e uptime |

### 5.2. Addresses — CRUD (desmilitarizado)

| Método | Rota | Tipo | Descrição |
|--------|------|------|-----------|
| `POST` | `/api/v1/addresses` | Desmilitarizado | Cria endereço. Valida CEP/state/kind. Retorna `201 AddressRead` |
| `GET` | `/api/v1/addresses` | Desmilitarizado | Lista endereços. Query params: `external_id`, `kind`, `limit` (1-100, default 20), `offset` |
| `GET` | `/api/v1/addresses/by-external-id/{external_id}` | Desmilitarizado | Lista endereços de um dono |
| `GET` | `/api/v1/addresses/by-external-id/{external_id}/{kind}/current` | Desmilitarizado | Endereço atual de um dono por kind |
| `GET` | `/api/v1/addresses/cep/{zipcode}` | Desmilitarizado | Lookup ViaCEP. Retorna `ViaCepResult` ou `404` |
| `GET` | `/api/v1/addresses/{address_id}` | Desmilitarizado | Obtém endereço por ID |
| `PATCH` | `/api/v1/addresses/{address_id}` | Desmilitarizado | Atualização parcial |
| `DELETE` | `/api/v1/addresses/{address_id}` | Desmilitarizado | Hard delete. Retorna `204` |

### 5.3. EntityAddresses — Vínculo polimórfico (desmilitarizado)

| Método | Rota | Tipo | Descrição |
|--------|------|------|-----------|
| `GET` | `/api/v1/entities/{entity_type}/{external_id}` | Desmilitarizado | Get-or-create do vínculo. Cria `EntityAddress` + `EntityAddressDetail` vazio se não existir |
| `POST` | `/api/v1/entities/{entity_type}/{external_id}/cep?cep=...` | Desmilitarizado | Preenche endereço via ViaCEP. Lookup + grava campos no `EntityAddressDetail` |
| `POST` | `/api/v1/entities/{entity_type}/{external_id}/proof` | Desmilitarizado | Upload de comprovante (multipart file). Salva em `uploads/` e grava path em `proof_file` |
| `POST` | `/api/v1/entities/{entity_type}/{external_id}/unlink` | Desmilitarizado | Desvincula endereço atual, cria novo `EntityAddressDetail` vazio |

### 5.4. Erros padronizados

| Status | Code | Quando |
|--------|------|--------|
| `404` | `not_found` | Recurso não encontrado (address, CEP ViaCEP) |
| `409` | `conflict` | Duplicata (entity_type + external_id) |
| `422` | `validation_error` | Campo inválido (CEP, UF, kind) |
| `502` | `integration_error` | ViaCEP indisponível |

## 6. Integrações Externas

| Serviço | Tipo | Propósito | Timeout | Degradação |
|---------|------|-----------|---------|------------|
| **ViaCEP** (`viacep.com.br`) | HTTP GET (httpx) | Lookup de CEP brasileiro — retorna logradouro, bairro, cidade, UF | 5s (configurável) | `IntegrationError` (502) se indisponível; `None` se CEP inexistente |
| **Webhook** (configurável) | HTTP POST (httpx) | Notifica consumidores em create/update/delete de Address | 5s (configurável) | Best-effort — falha é logada e ignorada |
| **auth.users** | FK referencial | `addresses.external_id` referencia `auth.users.external_id` | — | RESTRICT on delete, CASCADE on update |

**Padrão de integração:** Todas as chamadas externas são via `httpx.AsyncClient` com timeout configurável. ViaCEP usa exceção `IntegrationError` (502) para falhas de rede. Webhook é fire-and-forget com logging estruturado.

**Configuração (env vars):**

| Variável | Default | Descrição |
|----------|---------|-----------|
| `VIACEP_BASE_URL` | `https://viacep.com.br` | Base URL da ViaCEP |
| `VIACEP_TIMEOUT_SECONDS` | `5.0` | Timeout da ViaCEP |
| `WEBHOOK_URL` | `http://10.10.10.129` | URL do webhook de eventos |
| `WEBHOOK_TIMEOUT_SECONDS` | `5.0` | Timeout do webhook |
| `UPLOAD_DIR` | `uploads` | Diretório de uploads de comprovante |

## 7. Eventos Disparados / Consumidos

### Disparados (webhook best-effort)

| Evento | Gatilho | Payload | Destino |
|--------|---------|---------|---------|
| `address.created` | POST `/api/v1/addresses` | `{"event": "address.created", "payload": {...address fields...}}` | `WEBHOOK_URL` |
| `address.updated` | PATCH `/api/v1/addresses/{id}` | `{"event": "address.updated", "payload": {...address fields...}}` | `WEBHOOK_URL` |
| `address.deleted` | DELETE `/api/v1/addresses/{id}` | `{"event": "address.deleted", "payload": {"address_id": ...}}` | `WEBHOOK_URL` |

**Nota:** Os eventos são disparados pelo `services/address_service.py` após cada operação de escrita. Falhas de webhook são logadas como warning e **nunca** quebram a operação principal.

### Consumidos

Nenhum evento consumido diretamente. O serviço é puramente request-driven (endpoints HTTP). O fluxo auth→address é feito por chamada HTTP do auth ao address (não por evento).

## 8. Regras de Negócio Invariantes

1. **external_id é FK real para auth.users** — `addresses.external_id` referencia `auth.users.external_id` com RESTRICT on delete. Não é possível criar endereço para usuário inexistente.

2. **kind restrito a enum** — Valores aceitos: `home`, `billing`, `shipping`. Validação no Pydantic (`validate_kind`).

3. **state é UF brasileira (2 letras)** — Validação no Pydantic (`validate_state`). Aceita apenas siglas de estados brasileiros.

4. **country padrão BR** — Default `'BR'`, validado como ISO-3166-1 alpha-2.

5. **zipcode é 8 dígitos** — Validado e normalizado (remove hífen/ caracteres não-numéricos) pelo `validate_zipcode`.

6. **ViaCEP é lookup-only** — O endpoint `/cep/{zipcode}` apenas consulta, não grava. O preenchimento automático é feito pelo endpoint de entities (`/cep`).

7. **EntityAddress é 1:1 por (entity_type, external_id)** — UNIQUE constraint. Get-or-create é idempotente.

8. **Unlink cria vazio** — Ao desvincular, um novo `EntityAddressDetail` vazio é criado e o FK é reatribuído. O detail anterior fica órfão (SET NULL).

9. **Upload é disco local** — Comprovantes são salvos em `uploads/` (configurável). Sem S3/MinIO neste ciclo.

10. **Webhook é best-effort** — Falha de webhook nunca quebra a operação principal. Log de warning, sem retry.

11. **ViaCEP falha = 502** — Se a ViaCEP estiver indisponível (rede/HTTP), retorna `IntegrationError` (502). Se o CEP não existir, retorna `None` → `404`.

12. **Validação de texto** — Campos obrigatórios: strip + não-vazio + max length. Campos opcionais: strip + empty→None + max length.

## 9. Critérios de Aceite

1. [ ] **Addresses CRUD completo** — POST cria com `201`, GET lista com filtros/paginação, GET por ID, PATCH parcial, DELETE com `204`. Todos os endpoints retornam schemas corretos.

2. [ ] **ViaCEP lookup** — GET `/cep/{zipcode}` retorna dados normalizados. CEP inexistente → `404`. ViaCEP indisponível → `502`.

3. [ ] **EntityAddress get-or-create** — GET `/entities/{type}/{id}` cria vínculo + detail vazio se não existir, retorna existente se já existe.

4. [ ] **EntityAddress CEP update** — POST `.../cep?cep=...` preenche campos do detail via ViaCEP. CEP inválido → `404`. ViaCEP down → `502`.

5. [ ] **EntityAddress proof upload** — POST `.../proof` salva arquivo em `uploads/` e grava path em `proof_file`.

6. [ ] **EntityAddress unlink** — POST `.../unlink` desvincula endereço atual, cria novo detail vazio.

7. [ ] **Webhook disparado** — Toda escrita de Address dispara POST ao `WEBHOOK_URL`. Falha não quebra a operação.

8. [ ] **Validações Pydantic** — kind/state/zipcode/country/street/city validados nos schemas. Campos extras rejeitados (`extra: forbid`).

9. [ ] **FK referencial** — Tentativa de criar endereço com `external_id` inexistente em `auth.users` retorna erro de integridade.

10. [ ] **Testes** — Suíte `pytest` cobre: schemas, validators, address_service, entity_address_service, health endpoints. Todos verdes.

11. [ ] **Lint** — `ruff check` + `ruff format --check` limpos no serviço.

12. [ ] **Migração UUID** — `alembic upgrade head` aplica sem erro. Todas as 3 tabelas com PK UUID.

13. [ ] **Provisionamento auth→address** — Criar usuário no auth provisiona endereço automaticamente (via chamada HTTP ao address). Teste validado.

14. [ ] **Wiki atualizada** — `wiki/address.md` reflete a realidade atual do serviço.

## 10. Riscos / Open Questions

### Riscos

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| Migração PK integer→UUID quebra dados/FK | Baixa (já aplicada) | Alto | Refs cross-service usam `external_id` (UUID), não a PK. Migração 0001 já aplicada no código. |
| ViaCEP indisponível em produção | Média | Médio | `IntegrationError` (502) com mensagem clara. Não bloqueia criação manual de endereços. |
| Contrato auth→address divergente | Média | Médio | Validar `auth/app/integrations/address.py` antes de fechar. Alinhar schema de request/response. |
| Upload em disco local não persiste em deploy multi-VM | Baixa (single-VM) | Médio | Aceitável para deploy atual. S3/MinIO é milestone futuro. |
| Dependência de IA para normalização de endereço | Média | Baixo | IA é enriquecimento, nunca bloqueia create/update. Fallback gracioso. |
| Edição concorrente do worktree | Baixa | Médio | `address` está estável; evitar tocar outros serviços neste ciclo. |
| Webhook URL hardcoded em default | Baixa | Baixo | Configurável via env var. Default é IP interno — mudar em produção. |

### Open Questions

- [ ] **PK→UUID já aplicada?** Confirmar se a migração 0001 foi aplicada em banco de produção ou apenas em dev. Se greenfield, basta reaplicar.
- [ ] **Auth→address provisioning:** Qual o contrato exato? auth chama POST `/api/v1/addresses` diretamente, ou há endpoint dedicado? Confirmar `auth/app/integrations/address.py`.
- [ ] **IA (normalização):** Qual a tarefa exata? Normalizar texto livre de logradouro? Validar consistência CEP×rua×cidade? Sugerir correções? **TBD.**
- [ ] **Storage externo:** Confirmar que adiar S3/MinIO é aceitável para o deploy single-VM atual.
- [ ] **Webhook authentication:** O webhook atual não tem autenticação de origem. Precisa de HMAC/signature? **TBD.**
- [ ] **Geocoding (lat/lng):** Campos existem mas não são populados. Quando implementar? **Fora do escopo atual.**
- [ ] **Testes de integração:** Os testes atuais cobrem schemas e validators. Cobertura de endpoints (HTTP tests com httpx.AsyncClient) precisa ser expandida.
- [ ] **EntityAddress proof_path:** O path do comprovante é relativo ou absoluto? Como servir o arquivo? **TBD.**

---

*Status: DRAFT — requisitos consolidados do PRD anterior + código existente + referência do enrollment. Aguardando review humano antes de implementação.*
