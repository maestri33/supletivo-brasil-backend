# Documents-Service — Serviço de Documentos de Identificação

> **⚠️ SUPERSEDED — Este PRD foi consolidado em `documents.prd.md` (27/05/2025, 319 linhas).**
> **Mantido para referência histórica. Consulte `documents.prd.md` como fonte de verdade.**

> Serviço: `documents/` · Schema: `documents` · Convenção: `CONVENTION.md`
> Status desta SPEC: DRAFT original — superseded.

---

## 1. Contexto de Negócio

O microsserviço `documents` é o **repositório central de documentos de identificação** da plataforma. Cada usuário (identificado por `external_id` do auth) possui um agregado `Document` que contém referências a sub-documentos (RG, CNH, CTPS, passaporte) e campos inline (certidão, reservista, comprovante de residência, foto).

**Regra dura do TODO do dono:** "ao ser criado usuário, um document é criado com seu external_id e todos documentos são criados juntos respectivamente, com campos null, só document_id relacionado ao document". O provisionamento é **eager** — uma chamada cria o Document + todos os sub-documentos vazios de uma vez.

**Estado atual (pré-rewrite):** O serviço rodava em Tortoise+SQLite sem migrações, PK inteira, Pydantic v1, sem testes e com a regra de negócio do dono nunca implementada. Deixá-lo assim travava a padronização do backend e impedia que outros serviços confiassem nele em produção. A auditoria do próprio dono em `wiki/documents.md` catalogou 14 desvios da CONVENTION.

**Gap identificado:**
1. **Certidão** — o TODO diz "tipo pode ser nascimento, casamento e etc, mas só uma por document". A constraint de unicidade (um tipo de certidão por Document) não está implementada no banco.
2. **Serviço militar** — "só pra homens, mas tem que criar". A criação condicional por gênero não está implementada (gênero não é recebido no provisionamento).
3. **Notify** — usa webhook genérico em vez do padrão `integrations/notify.py` da CONVENTION §11/§12.
4. **Testes** — zero cobertura.
5. **Identificadores** — nomes de tabela/arquivo em português (`documentos`, `carteiras_trabalho`) quando deveriam ser em inglês.

## 2. Atores

| Ator | Role | Ação |
|------|------|------|
| **Sistema (auth)** | Serviço upstream | Provisiona documentos no registro do usuário via `GET/PUT /api/v1/documentos/{external_id}` |
| **Sistema (candidate)** | Serviço upstream | Lê documentos do candidato para validação de etapas |
| **Sistema (enrollment)** | Serviço upstream | Lê documentos para matrícula (exige certidão, RG, etc.) |
| **Sistema (training)** | Serviço upstream | Consulta documentos para compliance de treinamento |
| **Usuário final** | Indireto | Faz upload de fotos/imagens dos seus documentos via app (chamado pelo serviço de frontend/backend) |
| **Admin** | Operacional | Consulta documentos para auditoria (futuro — não implementado ainda) |

**Nota:** Todos os endpoints são **desmilitarizados** (sem JWT/auth) — uso interno da plataforma. Segurança é por restrição de rede (docker-compose interno). Não há autenticação porque o serviço só é chamado de dentro da plataforma (endpoints desmilitarizados, §5 da CONVENTION).

## 3. Estados / Máquina de Estados

O módulo **não tem máquina de estados**. O ciclo de vida é simples e linear:

```
Criação (provisionamento eager) → Document + sub-documentos vazios
  ↓
Atualização textual (PUT) → preenche campos dos sub-documentos
  ↓
Upload de imagens (POST /imagens/{slot}) → anexa fotos aos slots
  ↓
Delete de imagens (DELETE /imagens/{slot}) → remove foto do slot
```

O `get_or_create` garante que todo `external_id` válido sempre retorna um Document (cria na primeira consulta se não existir).

**Transições possíveis:**

| Estado | Significado | Transição para |
|--------|-------------|-----------------|
| `não existe` | Nenhum documento para este `external_id` | `vazio` (via provisionamento ou GET get_or_create) |
| `vazio` | Document + sub-documentos criados, todos campos null | `parcial` (via PUT textual) |
| `parcial` | Alguns campos preenchidos | `parcial` (mais PUTs) ou `completo` |
| `completo` | Todos os campos obrigatórios preenchidos | `parcial` (via alterações) |

**Nota:** Não há estados terminais nem bloqueios. O Document é sempre mutável.

## 4. Entidades & Campos

### Schema `documents`

#### Tabela `documentos` (agregado raiz)

| Coluna | Tipo | Constraints | Descrição |
|--------|------|-------------|-----------|
| `id` | UUID | PK, default gen_random_uuid() | ID interno |
| `external_id` | UUID | UNIQUE, NOT NULL, INDEX | UUID do usuário (ref. lógica ao auth.users) |
| `rg_id` | UUID | nullable | FK lógica → `rg.id` |
| `cnh_id` | UUID | nullable | FK lógica → `cnh.id` |
| `carteira_trabalho_id` | UUID | nullable | FK lógica → `carteiras_trabalho.id` |
| `passaporte_id` | UUID | nullable | FK lógica → `passaportes.id` |
| `certidao_tipo` | VARCHAR(20) | nullable | Tipo: `nascimento`, `casamento`, `obito` |
| `certidao_numero` | VARCHAR(50) | nullable | Número da certidão |
| `certidao_cartorio` | VARCHAR(100) | nullable | Cartório emissor |
| `certidao_livro` | VARCHAR(20) | nullable | Livro |
| `certidao_folha` | VARCHAR(20) | nullable | Folha |
| `certidao_termo` | VARCHAR(20) | nullable | Termo |
| `certidao_data_emissao` | DATE | nullable | Data de emissão |
| `certidao_foto` | VARCHAR(500) | nullable | Path da foto (storage local) |
| `reservista_numero` | VARCHAR(30) | nullable | Número do certificado de reservista |
| `reservista_serie` | VARCHAR(20) | nullable | Série |
| `reservista_categoria` | VARCHAR(20) | nullable | Categoria |
| `reservista_ra` | VARCHAR(20) | nullable | RA |
| `reservista_foto` | VARCHAR(500) | nullable | Path da foto |
| `comprovante_residencia_foto` | VARCHAR(500) | nullable | Path da foto |
| `foto` | VARCHAR(500) | nullable | Foto geral do usuário |
| `created_at` | TIMESTAMP | NOT NULL | Via TimestampMixin |
| `updated_at` | TIMESTAMP | NOT NULL | Via TimestampMixin |

#### Tabela `rg`

| Coluna | Tipo | Constraints | Descrição |
|--------|------|-------------|-----------|
| `id` | UUID | PK | ID interno |
| `numero` | VARCHAR(30) | nullable | Número do RG |
| `orgao_emissor` | VARCHAR(50) | nullable | Órgão emissor |
| `data_emissao` | DATE | nullable | Data de emissão |
| `foto_frente` | VARCHAR(500) | nullable | Path da foto frente |
| `foto_verso` | VARCHAR(500) | nullable | Path da foto verso |
| `created_at`, `updated_at` | TIMESTAMP | NOT NULL | Via TimestampMixin |

#### Tabela `cnh`

| Coluna | Tipo | Constraints | Descrição |
|--------|------|-------------|-----------|
| `id` | UUID | PK | ID interno |
| `numero` | VARCHAR(30) | nullable | Número da CNH |
| `categoria` | VARCHAR(5) | nullable | Categoria (A, B, AB, etc.) |
| `data_nascimento` | DATE | nullable | Data de nascimento |
| `validade` | DATE | nullable | Data de validade |
| `registro_nacional` | VARCHAR(30) | nullable | Registro nacional |
| `foto_frente` | VARCHAR(500) | nullable | Path da foto frente |
| `foto_verso` | VARCHAR(500) | nullable | Path da foto verso |
| `created_at`, `updated_at` | TIMESTAMP | NOT NULL | Via TimestampMixin |

#### Tabela `carteiras_trabalho` (CTPS)

| Coluna | Tipo | Constraints | Descrição |
|--------|------|-------------|-----------|
| `id` | UUID | PK | ID interno |
| `numero` | VARCHAR(30) | nullable | Número da CTPS |
| `serie` | VARCHAR(20) | nullable | Série |
| `uf` | VARCHAR(2) | nullable | UF de emissão |
| `data_emissao` | DATE | nullable | Data de emissão |
| `foto_frente` | VARCHAR(500) | nullable | Path da foto frente |
| `foto_verso` | VARCHAR(500) | nullable | Path da foto verso |
| `created_at`, `updated_at` | TIMESTAMP | NOT NULL | Via TimestampMixin |

#### Tabela `passaportes`

| Coluna | Tipo | Constraints | Descrição |
|--------|------|-------------|-----------|
| `id` | UUID | PK | ID interno |
| `numero` | VARCHAR(30) | nullable | Número do passaporte |
| `validade` | DATE | nullable | Data de validade |
| `data_emissao` | DATE | nullable | Data de emissão |
| `foto_frente` | VARCHAR(500) | nullable | Path da foto frente |
| `foto_verso` | VARCHAR(500) | nullable | Path da foto verso |
| `created_at`, `updated_at` | TIMESTAMP | NOT NULL | Via TimestampMixin |

### Relacionamentos

- `documentos.rg_id` → `rg.id` (lógica, sem FK cross-schema)
- `documentos.cnh_id` → `cnh.id` (lógica, sem FK cross-schema)
- `documentos.carteira_trabalho_id` → `carteiras_trabalho.id` (lógica)
- `documentos.passaporte_id` → `passaportes.id` (lógica)
- `documentos.external_id` → `auth.users.external_id` (lógica, sem FK cross-schema)

### Slots de imagem (enum `IMAGE_SLOTS`)

`rg_foto_frente`, `rg_foto_verso`, `cnh_foto_frente`, `cnh_foto_verso`, `carteira_trabalho_foto_frente`, `carteira_trabalho_foto_verso`, `passaporte_foto_frente`, `passaporte_foto_verso`, `certidao_foto`, `reservista_foto`, `comprovante_residencia_foto`, `foto` — **12 slots** no total.

## 5. Endpoints

Todos endpoints são **desmilitarizados** (uso interno da plataforma).

### 5.1. GET `/api/v1/documentos/{external_id}`

Retorna o Document completo do usuário (com todos os sub-documentos). Se não existir, cria automaticamente (get_or_create).

| Campo | Valor |
|-------|-------|
| **Método** | `GET` |
| **Tipo** | Desmilitarizado |
| **Auth** | Nenhuma |
| **Response 200** | `DocumentOut` (agregado completo com todos os sub-documentos) |
| **Idempotência** | Idempotente (get_or_create) |
| **Side-effects** | Cria Document + sub-documentos se `external_id` for novo; dispara evento `documento.criado` |

### 5.2. PUT `/api/v1/documentos/{external_id}`

Atualiza campos textuais dos sub-documentos e campos inline do Document.

| Campo | Valor |
|-------|-------|
| **Método** | `PUT` |
| **Tipo** | Desmilitarizado |
| **Request body** | `DocumentUpdate` (merge parcial — só campos não-null são atualizados) |
| **Response 200** | `DocumentOut` |
| **Response 422** | Erro de validação (ex: certidao_tipo inválido) |
| **Idempotência** | Idempotente |
| **Side-effects** | Dispara webhook `documento.atualizado` |

### 5.3. POST `/api/v1/documentos/{external_id}/imagens/{slot}`

Upload de imagem para um slot nomeado.

| Campo | Valor |
|-------|-------|
| **Método** | `POST` |
| **Content-Type** | `multipart/form-data` (campo `file`) |
| **Slots válidos** | Os 12 slots definidos em `IMAGE_SLOTS` |
| **Tipos permitidos** | `image/jpeg`, `image/png`, `image/webp` |
| **Tamanho máximo** | 10MB (configurável via `MAX_UPLOAD_MB`) |
| **Response 201** | `DocumentOut` |
| **Response 413** | Arquivo excede limite |
| **Response 422** | Slot inválido ou tipo não permitido |
| **Side-effects** | Remove arquivo anterior do mesmo slot (se existir); dispara `documento.imagem_uploaded` |

### 5.4. GET `/api/v1/documentos/{external_id}/imagens/{slot}`

Download de imagem de um slot.

| Campo | Valor |
|-------|-------|
| **Método** | `GET` |
| **Response 200** | `FileResponse` (arquivo binário) |
| **Response 404** | Slot vazio ou arquivo não encontrado |

### 5.5. DELETE `/api/v1/documentos/{external_id}/imagens/{slot}`

Remove imagem de um slot.

| Campo | Valor |
|-------|-------|
| **Método** | `DELETE` |
| **Response 200** | `DocumentOut` (atualizado) |
| **Response 422** | Slot inválido |
| **Side-effects** | Remove arquivo do storage; dispara `documento.imagem_deleted` |

### 5.6. Health

- `GET /health` — healthcheck básico (padrão CONVENTION)

## 6. Integrações Externas

| Serviço | Direção | Mecanismo | Descrição |
|---------|---------|-----------|-----------|
| **auth** | Upstream → documents | HTTP desmilitarizado | Auth provisiona documentos no registro do usuário |
| **candidate** | Upstream → documents | HTTP desmilitarizado | Candidate lê documentos do candidato |
| **enrollment** | Upstream → documents | HTTP desmilitarizado | Enrollment exige documentos para matrícula (RG obrigatório) |
| **training** | Upstream → documents | HTTP desmilitarizado | Training consulta documentos para compliance |
| **notify** | documents → notify | HTTP (`integrations/notify.py`) | **GAP:** Atual usa webhook genérico (`_fire_webhook`), deveria usar notify via padrão CONVENTION §11/§12 |
| **storage** | documents → filesystem | File I/O local | Salva imagens no storage local (migrar para S3 em produção) |

**Padrão de integração:** Todas as chamadas HTTP são via `httpx.AsyncClient` com timeout configurável. Clientes ficam em `integrations/`. Falhas de integração não quebram o fluxo — operam em modo best-effort com logging estruturado.

## 7. Eventos Disparados / Consumidos

### Eventos Disparados (via webhook)

| Evento | Trigger | Payload |
|--------|---------|---------|
| `documento.criado` | Criação do Document (get_or_create) | `{"external_id": "..."}` |
| `documento.atualizado` | PUT de campos textuais | `{"external_id": "...", "changes": {...}}` |
| `documento.imagem_uploaded` | Upload de imagem | `{"external_id": "...", "slot": "..."}` |
| `documento.imagem_deleted` | Delete de imagem | `{"external_id": "...", "slot": "..."}` |

### Eventos Consumidos

Nenhum. O módulo é reativo (chamado por outros serviços), não consome eventos.

### GAP: Integração com Notify

O padrão CONVENTION §11/§12 exige `integrations/notify.py` com httpx client para notificações assíncronas. O código atual usa um webhook genérico (`_fire_webhook`). Migrar para o padrão notify é recomendado mas não bloqueante para o MVP.

## 8. Regras de Negócio Invariantes

| # | Invariante | Fonte (TODO) | Status |
|---|-----------|--------------|--------|
| INV-1 | **Um Document por `external_id`** — a constraint UNIQUE em `external_id` garante unicidade | TODO implícito | ✅ Implementada (DB constraint) |
| INV-2 | **Provisionamento eager** — ao criar o usuário, TODOS os sub-documentos são criados (vazios) de uma vez | "ao ser criado usuário, um document é criado com seu external_id e todos documentos são criados juntos" | ⚠️ Parcial — `get_or_create` cria Document mas sub-documentos são lazy (criados no primeiro acesso via `_get_or_create_sub`) |
| INV-3 | **Certidão: apenas uma por Document** — "tipo pode ser nascimento, casamento e etc, mas só uma por document" | TODO | ❌ Não implementada — não há constraint de unicidade |
| INV-4 | **Serviço militar: só para homens** — "só pra homens, mas tem que criar" | TODO | ❌ Não implementada — gênero não é recebido no provisionamento |
| INV-5 | **Imagens: tipo e tamanho validados** — só jpeg/png/webp, máx 10MB | Código existente | ✅ Implementada |
| INV-6 | **Slots de imagem restritos** — apenas os 12 slots definidos em `IMAGE_SLOTS` | Código existente | ✅ Implementada |
| INV-7 | **PII mascarada em logs** — números de documento são mascarados antes de logar | COD-18 PII audit | ✅ Implementada (via `mask_number`) |
| INV-8 | **Identificadores em inglês** — tabelas/colunas/rotas em inglês, comentários pt-br | CONVENTION §7 | ⚠️ Parcial — nomes de tabelas em português (`documentos`, `carteiras_trabalho`) |
| INV-9 | **Merge parcial no PUT** — só campos não-null no request atualizam o registro | Implementação | ✅ Implementada |
| INV-10 | **Substituição de imagem** — upload no mesmo slot remove arquivo anterior | Implementação | ✅ Implementada |

## 9. Critérios de Aceite

| # | Critério | Testável |
|---|---------|----------|
| AC-1 | `GET /api/v1/documentos/{external_id}` retorna Document com todos os sub-documentos (vazios se nunca preenchidos) | Sim — GET retorna 200 com estrutura completa |
| AC-2 | `GET` com `external_id` inexistente cria o Document automaticamente (get_or_create) | Sim — GET + verificação no banco |
| AC-3 | `PUT` atualiza apenas campos não-null (merge parcial) | Sim — PUT parcial + GET confirma só os campos enviados mudaram |
| AC-4 | `PUT` com `certidao.tipo` inválido retorna 422 | Sim — PUT com tipo="invalido" → 422 |
| AC-5 | Upload de imagem para slot válido salva arquivo e atualiza path no banco | Sim — POST + GET download confirma |
| AC-6 | Upload de tipo não-permitido (ex: `application/pdf`) retorna 422 | Sim — POST com PDF → 422 |
| AC-7 | Upload de arquivo > 10MB retorna 413 | Sim — POST com arquivo grande → 413 |
| AC-8 | Upload para slot inválido retorna 422 | Sim — POST com slot="invalido" → 422 |
| AC-9 | Delete de imagem remove arquivo do storage e zera path no banco | Sim — DELETE + GET download → 404 |
| AC-10 | Upload substitui arquivo anterior do mesmo slot (sem lixo no storage) | Sim — upload 2x + verificação de apenas 1 arquivo no disco |
| AC-11 | Webhooks são disparados corretamente para cada operação | Sim — mock webhook endpoint + verificação de chamadas |
| AC-12 | Provisionamento eager cria Document + todos sub-documentos numa chamada | Sim — POST provisionamento + GET confirma todos presentes |
| AC-13 | Certidão: constraint de unicidade impede mais de uma por Document | Sim — tentativa de segundo insert falha |
| AC-14 | Serviço militar: condicional por gênero no provisionamento | Sim — provisionar feminino não cria reservista |
| AC-15 | `ruff check` e `ruff format` passam sem erros | Sim — execução de ruff |
| AC-16 | Migração Alembic aplica limpa em banco vazio | Sim — `alembic upgrade head` em DB fresh |
| AC-17 | Suíte `pytest` verde com cobertura de CRUD, imagens, validações | Sim — execução de pytest |

## 10. Riscos / Open Questions

### Riscos

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| Mídia sensível (documentos) exposta sem auth em endpoint desmilitarizado | Média | Alto | Endpoints são desmilitarizados — segurança depende de restrição de rede. Considerar token assinado para download de imagens (futuro) |
| `external_id` sem garantia de usuário existente gera documentos órfãos | Média | Médio | Provisionamento confiável a partir do auth + (opcional) shadow table de `auth.users` |
| `notify` indisponível perde eventos | Baixa | Baixo | Fire-and-forget — não bloqueia operação principal. Migrar para notify melhora resiliência |
| Nomes de tabela em português (`documentos`) criam fricção com outros módulos em inglês | Baixa | Baixo | Renomear é breaking change — fazer em sprint separada se necessário |
| Storage local não escala para produção | Média | Alto | Migrar para S3/object storage em produção (fora de escopo MVP) |
| Regra de gênero depende de dado externo (profiles) que pode faltar | Média | Médio | Definir fallback (não criar serviço militar quando gênero desconhecido) |
| Provisionamento eager cria muitos registros vazios | Baixa | Baixo | Aceitável (1 Document + N sub-docs por usuário); índices por `external_id` |

### Open Questions

- [ ] **Fonte do gênero** para regra INV-4 (serviço militar só pra homens): vem no payload do provisionamento, ou `documents` consulta `profiles` via integração? Definir antes de implementar INV-4.
- [ ] **Constraint de unicidade de certidão** (INV-3): aplicar como constraint no banco (ex: partial unique index) ou validar no service layer?
- [ ] **Migração de nomes de tabela**: renomear `documentos` → `documents`, `carteiras_trabalho` → `carteira_trabalho` para consistência? Breaking change.
- [ ] **Notify vs webhook**: migrar `_fire_webhook` para `integrations/notify.py` no padrão CONVENTION §11/§12 agora ou em sprint separado?
- [ ] **Dados existentes**: há dados no SQLite/Tortoise que precisam migrar, ou é greenfield?
- [ ] **Controle de acesso à mídia**: como gatear download de imagens sensíveis em endpoint desmilitarizado (restrição de rede interna? URL/token assinado?)?
- [ ] **FK cross-schema `external_id`**: declarar shadow table read-only de `auth.users` (§4) ou manter só coluna UUID indexada sem FK?

---

*Status: SUPERSEDED por `documents.prd.md` (27/05/2025). Este arquivo é referência histórica.*
*Consolidado de: PRD original (DRAFT) + código existente em `documents/app/` + TODO original do dono.*
