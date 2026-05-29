# Candidate — Módulo de Candidato a Promotor

> Serviço: `candidate/` · Schema: `candidate` · Convenção: `CONVENTION.md`
> Status desta SPEC: pronto para review.

---

## 1. Contexto de Negócio

O **candidato** é o aspirante a se tornar um promotor/parceiro da plataforma. Ele segue um funil de cadastro sequencial (mesma lógica do `lead`, mas com requisitos totalmente diferentes). O funil coleta dados pessoais, educacionais, documentos, chave PIX e selfie — ao final, o candidato é promovido para o status `training` (módulo `training`), criando um novo registro lá.

**Estado atual:** O módulo está **substantialmente implementado**. O funil completo existe com 9 etapas (captured → personal → education → birth → address → documents → pixkey → selfie → completed). Cada etapa tem endpoints autenticados GET/POST. Endpoints desmilitarizados permitem listagem/filtragem por hub/status. A integração com `asaas` (validação de chave PIX) e `ai` (validação de selfie) está implementada.

**Gaps identificados:**
- Endpoint público de registro (`POST /register/`) com phone, cpf, hub (HUB_DEFAULT em .env) — precisa confirmar se existe ou se o captured cumpre esse papel.
- Notificações ao candidato durante o funil (via `notify`) — implementação parcial.
- Transição final para `training` no status `completed` — precisa confirmar se o webhook/evento de criação no training está implementado.

## 2. Atores

| Ator | Role | Ação |
|------|------|------|
| **Candidato** | `candidate` (usuário anônimo que se registra) | Autentica e envia dados para cada etapa do funil via endpoints autenticados |
| **Promotor que indicou** | `promoter` (serviço `promoter`) | Vinculado via `promoter_external_id` na captação; recebe notificações de progresso |
| **Coordenador do polo** | `coordinator` (serviço `coordinator`/`hub`) | Acessa listagem de candidatos via endpoints desmilitarizados para acompanhar funil |
| **Sistema (auth)** | serviço `auth` | Emite JWT, fornece `external_id` do usuário |
| **Sistema (asaas)** | serviço `asaas` | Valida chave PIX do candidato (busca titular) |
| **Sistema (ai)** | serviço `ai` | Valida selfie (comparação com documento, liveness) |
| **Sistema (notify)** | serviço `notify` | Envia notificações assíncronas ao candidato e promotor |

## 3. Estados / Máquina de Estados

### Status (CandidateStatus — StrEnum)

```
CAPTURED → PERSONAL → EDUCATION → BIRTH → ADDRESS → DOCUMENTS → PIXKEY → SELFIE → COMPLETED
```

| Status | Significado | Transição para |
|--------|-------------|-----------------|
| `captured` | Candidato registrado (nome + email) | `personal` |
| `personal` | Dados pessoais (gênero, nome da mãe/pai, estado civil) | `education` |
| `education` | Dados educacionais (nível, instituição, curso, ano) | `birth` |
| `birth` | Dados de nascimento (data, local, nacionalidade) | `address` |
| `address` | Endereço (CEP primeiro, depois número/complemento) | `documents` |
| `documents` | RG ou CNH (dados + frente/verso) | `pixkey` |
| `pixkey` | Chave PIX cadastrada e validada no asaas | `selfie` |
| `selfie` | Selfie real enviada e validada (assinatura digital) | `completed` |
| `completed` | Cadastro concluído, promovido para `training` | — (terminal) |

**Regra:** A progressão é sequencial e unidirecional. Cada endpoint avança exatamente 1 status. Não é possível pular etapas nem retroceder.

### Ordem definida em código:

```python
STATUS_ORDER: tuple[CandidateStatus, ...] = (
    CandidateStatus.CAPTURED,
    CandidateStatus.PERSONAL,
    CandidateStatus.EDUCATION,
    CandidateStatus.BIRTH,
    CandidateStatus.ADDRESS,
    CandidateStatus.DOCUMENTS,
    CandidateStatus.PIXKEY,
    CandidateStatus.SELFIE,
    CandidateStatus.COMPLETED,
)
```

## 4. Entidades & Campos

### Schema `candidate`

#### `candidates` — Agregado do candidato

| Coluna | Tipo | Nullable | Default | FK / Índice | Descrição |
|--------|------|----------|---------|-------------|-----------|
| `id` | `UUID` PK | NOT NULL | `uuid4()` | — | PK do agregado |
| `external_id` | `UUID` | NOT NULL | — | UNIQUE INDEX | UUID do usuário emitido pelo auth (referência lógica, sem FK cross-schema) |
| `status` | `String(20)` | NOT NULL | `'captured'` | INDEX | Etapa atual do funil |
| `hub_external_id` | `UUID` | NULL | — | INDEX | UUID do hub ao qual o candidato pertence |
| `created_at` | `DateTime(tz)` | NOT NULL | `now()` | — | Timestamp de criação |
| `updated_at` | `DateTime(tz)` | NOT NULL | `now()` ON UPDATE | — | Timestamp de atualização |

**Nota:** Dados pessoais, endereço, documentos e educação vivem nos serviços donos (`profiles`, `address`, `documents`) — o candidato só armazena o `external_id` e o status do funil. Isso evita duplicação e mantém o princípio de cada serviço ser dono dos seus dados.

## 5. Endpoints

### Públicos (expostos ao mundo)

| Verbo | Rota | Request | Response | Auth | Descrição |
|-------|------|---------|----------|------|-----------|
| `POST` | `/api/v1/public/register` | `{phone, cpf, hub?}` | `{external_id, status}` | Nenhuma | Registro inicial do candidato (HUB_DEFAULT em .env se hub não informado) |
| `GET` | `/health` | — | `{status: "ok"}` | Nenhuma | Health check |
| `GET` | `/ready` | — | `{status: "ok"}` | Nenhuma | Readiness check |
| `GET` | `/status` | — | `{status, service, version, env, uptime}` | Nenhuma | Status detalhado |

### Autenticadas (exigem JWT com role `candidate`)

| Verbo | Rota | Request | Response | Descrição |
|-------|------|---------|----------|-----------|
| `GET` | `/api/v1/authenticated/captured` | — | `CapturedGetResponse` | Dados do candidato capturado |
| `POST` | `/api/v1/authenticated/captured` | `CapturedPostRequest` | `CapturedPostResponse` | Salva nome/email, avança para `personal` |
| `GET` | `/api/v1/authenticated/personal` | — | `PersonalGetResponse` | Dados pessoais |
| `POST` | `/api/v1/authenticated/personal` | `PersonalPostRequest` | `PersonalPostResponse` | Salva dados pessoais, avança para `education` |
| `GET` | `/api/v1/authenticated/educational` | — | `EducationalGetResponse` | Dados educacionais |
| `POST` | `/api/v1/authenticated/educational` | `EducationalPostRequest` | `EducationalPostResponse` | Salva dados educacionais, avança para `birth` |
| `GET` | `/api/v1/authenticated/birth` | — | `BirthGetResponse` | Dados de nascimento |
| `POST` | `/api/v1/authenticated/birth` | `BirthPostRequest` | `BirthPostResponse` | Salva dados de nascimento, avança para `address` |
| `GET` | `/api/v1/authenticated/address` | — | `AddressGetResponse` | Endereço do candidato |
| `GET` | `/api/v1/authenticated/address/cep/{cep}` | — | `CepCheckResponse` | Consulta CEP via address-service |
| `POST` | `/api/v1/authenticated/address` | `AddressPostRequest` | `AddressPostResponse` | Salva endereço, avança para `documents` |
| `GET` | `/api/v1/authenticated/documents` | — | `DocumentsGetResponse` | Estado dos documentos |
| `PUT` | `/api/v1/authenticated/documents` | `DocumentDataRequest` | `DocumentsResponse` | Salva dados de RG/CNH |
| `POST` | `/api/v1/authenticated/documents/images/{slot}` | `multipart/form-data` | `DocumentsResponse` | Upload imagem (rg/cnh frente/verso) |
| `GET` | `/api/v1/authenticated/pixkey` | — | `PixKeyGetResponse` | Chave PIX cadastrada |
| `POST` | `/api/v1/authenticated/pixkey` | `PixKeyPostRequest` | `PixKeyPostResponse` | Valida e cadastra chave PIX no asaas, avança para `selfie` |
| `GET` | `/api/v1/authenticated/selfie` | — | `SelfieGetResponse` | Estado da selfie |
| `POST` | `/api/v1/authenticated/selfie` | `multipart/form-data` | `SelfiePostResponse` | Envia selfie e conclui cadastro (promove para `completed`) |

### Desmilitarizadas (uso interno da plataforma, sem auth de usuário)

| Verbo | Rota | Request | Response | Descrição |
|-------|------|---------|----------|-----------|
| `GET` | `/api/v1/demilitarized/candidates` | `?hub_external_id=&status=&limit=&offset=` | `CandidateListResponse` | Lista/filtra candidatos por hub e status |
| `GET` | `/api/v1/demilitarized/candidates/{external_id}` | — | `CandidateOut` | Busca candidato por external_id |

## 6. Integrações Externas

| Serviço | Direção | Mecanismo | Descrição |
|---------|---------|-----------|-----------|
| `auth` | ← consome | HTTP interno | Valida JWT, obtém `external_id` do usuário |
| `profiles` | ↔ sincroniza | HTTP interno | Lê/escreve dados pessoais, educacionais, nascimento (profile_svc) |
| `address` | ← consome | HTTP interno | Consulta CEP, salva endereço do candidato |
| `documents` | ← consome | HTTP interno | Salva dados e imagens de RG/CNH |
| `asaas` | ↔ sincroniza | HTTP interno | Valida chave PIX (busca titular via CPF/phone/email) |
| `ai` | ← consome | HTTP interno | Valida selfie (liveness, comparação com documento) |
| `notify` | → dispara | Background task | Envia notificações de progresso do funil ao candidato e promotor |
| `training` | → dispara | Evento/webhook | Ao completar o funil, cria registro no módulo `training` |

## 7. Eventos Disparados / Consumidos

| Evento | Direção | Descrição |
|--------|---------|-----------|
| `candidate.status_advanced` | → dispara | Disparado a cada avanço de etapa do funil (via notifications.notify_status_advanced) |
| `candidate.completed` | → dispara | Disparado quando o funil é concluído (selfie validada) — deve criar registro no `training` |
| `candidate.captured` | → dispara | Disparado no registro inicial (nome + email salvos) |

**Nota:** Os eventos são disparados via `BackgroundTasks` do FastAPI (notificações assíncronas). O consumo pelo `training` precisa ser confirmado — pode ser webhook síncrono ou fila.

## 8. Regras de Negócio Invariantes

1. **Progressão sequencial obrigatória:** Cada etapa só pode ser acessada se o candidato estiver no status correspondente. Ex: endpoint `/personal` requer status `captured`.
2. **Um candidato por usuário:** `external_id` tem constraint UNIQUE — não é possível registrar o mesmo usuário duas vezes.
3. **CEP primeiro no endereço:** O endpoint de endereço primeiro consulta o CEP (via address-service) para preencher rua/bairro/cidade/estado; o candidato só informa número e complemento.
4. **CPF já puxa dados:** Ao informar o CPF na etapa de captured/profile, o sistema deve buscar dados já existentes (nome, etc.) — não duplicar lógica de coleta.
5. **PIX validado no asaas:** A chave PIX deve ser validada no asaas antes de avançar para a próxima etapa. Se a validação falhar, o candidato permanece em `pixkey`.
6. **Selfie como assinatura digital:** A selfie é validada como se fosse uma assinatura de contrato — deve passar por liveness check e comparação com o documento enviado.
7. **Hub default:** Se o hub não for informado no registro, usar `HUB_DEFAULT` do `.env`.
8. **Sem FK cross-schema:** `external_id` é referência lógica (UUID emitido pelo auth), não FK declarada — mantém testes portáveis e evita acoplamento de schema.
9. **Rate limiting:** 200 requests/minuto por IP (slowapi).
10. **Notificações a cada etapa:** Cada avanço de status dispara notificação assíncrona ao candidato e ao promotor que o indicou.

## 9. Critérios de Aceite

1. O endpoint `POST /register/` cria um candidato com status `captured`, phone, cpf e hub (ou HUB_DEFAULT).
2. Cada endpoint POST do funil avança o status em exatamente 1 etapa na ordem definida.
3. Tentar acessar uma etapa fora de ordem retorna erro (ex: tentar `/documents` quando status é `personal`).
4. A consulta de CEP preenche automaticamente rua, bairro, cidade, estado — candidato só informa número.
5. A chave PIX é validada no asaas antes de avançar; falha mantém o candidato em `pixkey`.
6. A selfie passa por validação (liveness + comparação com documento) antes de concluir o funil.
7. Ao concluir o funil (status → `completed`), um registro é criado no módulo `training`.
8. Listagem desmilitarizada filtra corretamente por `hub_external_id` e `status`.
9. Rate limiting de 200/min está ativo e funciona.
10. Notificações são disparadas a cada avanço de etapa (background task, não bloqueante).

## 10. Riscos / Open Questions

1. **Endpoint de registro público:** O TODO menciona `POST /register/` com phone, cpf, hub. O código atual tem `POST /captured` como primeira etapa. Qual é o endpoint correto para o registro inicial? O `captured` cumpre esse papel ou precisa de um endpoint separado?
2. **Integração com training:** Ao concluir o funil, como o candidato é criado no `training`? Webhook síncrono? Evento assíncrono? A implementação atual do `selfie.py` dispara algo?
3. **Validação de selfie:** O TODO diz "valida como se fosse uma assinatura de contrato". Qual é o critério exato? Liveness + comparação com documento? Ou apenas liveness?
4. **CPF pulling:** O TODO diz "cpf já puxa nome e etc". De qual serviço isso vem? `profiles`? `auth`? A lógica precisa ser confirmada.
5. **Promotor vinculado:** O `promoter_external_id` é preenchido em qual etapa? No registro? Na captação? Precisa confirmar.
6. **Imagens de documentos:** O upload de imagens (frente/verso) vai para qual storage? S3? Local? O serviço `documents` é dono disso.
