# Documents — Módulo de Documentos de Identificação

> Serviço: `documents/` · Schema: `documents` · Convenção: `CONVENTION.md`
> Status desta SPEC: pronto para review.

---

## 1. Contexto de Negócio

O módulo `documents` é o **repositório central de documentos de identificação** da
plataforma. Armazena RG, CNH, Carteira de Trabalho, Passaporte, Certidão (tipada),
Reservista (serviço militar), Comprovante de Residência e Foto — vinculados por
`external_id` ao usuário criado no serviço `auth`.

**Regra dura do TODO do dono:** "ao ser criado usuário, um document é criado com seu
external_id e todos documentos são criados juntos respectivamente, com campos null,
só document_id relacionado ao document". Ou seja: **provisionamento eager** — uma
chamada cria o Document agregado + todos os sub-documentos vazios.

**Tipos de sub-documento:**
- **Tabelas separadas** (com FK apontando por UUID): RG, CNH, Carteira de Trabalho,
  Passaporte. Cada um tem campos textuais + slots de foto (frente/verso).
- **Campos inline no Document**: Certidão (tipada: nascimento/casamento/óbito —
  **uma por Document**), Reservista (serviço militar — **criado para todos, mas
  regra de gênero pendente**), Comprovante de Residência, Foto geral.

**Estado atual:** O módulo foi **parcialmente reescrito** para a stack canônica:
- ✅ SQLAlchemy 2.0 async + asyncpg (db.py)
- ✅ PK UUID em todas as tabelas
- ✅ Pydantic v2 com `model_config`
- ✅ pydantic-settings (config.py)
- ✅ structlog (utils/logging.py)
- ✅ Estrutura correta `documents/app/` (sem aninhamento)
- ❌ Sem Alembic — `alembic/` ausente
- ❌ Sem testes — `tests/` ausente
- ❌ Sem `integrations/` — webhook embutido no service
- ❌ Nomes em português em modelos (carteira_trabalho.py)
- ❌ `requires-python = ">=3.11"` (deveria ser `>=3.12`)

**Gap de provisionamento:** O `get_or_create` atual cria o Document se não existe,
mas **não cria sub-documentos automaticamente** (RG, CNH, etc.). Os sub-documentos
são criados on-demand quando o usuário envia dados. Isso diverge da regra dura do
dono ("todos documentos são criados juntos").

## 2. Atores

| Ator | Role | Ação |
|------|------|------|
| **Sistema (auth)** | Serviço upstream | Chama provisionamento eager no registro do usuário |
| **Sistema (candidate/enrollment)** | Serviço upstream | Lê e escreve dados de documentos do candidato |
| **Sistema (training)** | Serviço upstream | Consulta documentos para validar elegibilidade |
| **App do usuário** | Consumidor indireto | Faz upload de fotos e preenche dados (via serviços upstream) |
| **Admin** | Operador | Consulta/gerencia documentos (futuro — sem endpoint admin hoje) |

**Nota:** Todos os endpoints são **desmilitarizados** (uso interno, sem autenticação).
O serviço não é exposto à internet.

## 3. Estados / Máquina de Estados

O `documents` **não tem máquina de estados**. O ciclo de vida é:

```
Provisionamento (auth.register)
  → Document criado + sub-documentos vazios (todos NULL)
    → Preenchimento gradual (PUT textual + POST imagem por slot)
      → Estado "completo" quando todos os campos obrigatórios preenchidos
        (validação é responsabilidade do serviço que consome — ex.: candidate)
```

**Fluxo de provisionamento (target):**
```
POST /api/v1/documentos/{external_id}/provision  (desmilitarizado)
  → Cria Document (se não existe)
  → Cria RG (vazio)
  → Cria CNH (vazio)
  → Cria CarteiraTrabalho (vazio)
  → Cria Passaporte (vazio)
  → Campos inline (certidão, reservista, etc.) ficam NULL
  → Retorna DocumentOut com todos os sub-documentos
```

**Fluxo atual (get-or-create):**
```
GET /api/v1/documentos/{external_id}
  → Se Document não existe, cria (sem sub-documentos)
  → Retorna DocumentOut
```

## 4. Entidades & Campos

### Schema `documents`

#### `documentos` — Agregado principal

| Coluna | Tipo | Nullable | Default | FK / Índice | Descrição |
|--------|------|----------|---------|-------------|-----------|
| `id` | `UUID` PK | NOT NULL | `uuid4()` | — | PK interno |
| `external_id` | `UUID` | NOT NULL | `uuid4()` | **UNIQUE INDEX** | UUID do usuário (auth) — referência lógica sem FK |
| `rg_id` | `UUID` | NULL | — | — | FK lógica → `rg.id` |
| `cnh_id` | `UUID` | NULL | — | — | FK lógica → `cnh.id` |
| `carteira_trabalho_id` | `UUID` | NULL | — | — | FK lógica → `carteiras_trabalho.id` |
| `passaporte_id` | `UUID` | NULL | — | — | FK lógica → `passaportes.id` |
| `certidao_tipo` | `String(20)` | NULL | — | — | Tipo: nascimento, casamento, obito |
| `certidao_numero` | `String(50)` | NULL | — | — | Número da certidão |
| `certidao_cartorio` | `String(100)` | NULL | — | — | Cartório emissor |
| `certidao_livro` | `String(20)` | NULL | — | — | Livro |
| `certidao_folha` | `String(20)` | NULL | — | — | Folha |
| `certidao_termo` | `String(20)` | NULL | — | — | Termo |
| `certidao_data_emissao` | `Date` | NULL | — | — | Data de emissão |
| `certidao_foto` | `String(500)` | NULL | — | — | Path da foto (media) |
| `reservista_numero` | `String(30)` | NULL | — | — | Número do certificado |
| `reservista_serie` | `String(20)` | NULL | — | — | Série |
| `reservista_categoria` | `String(20)` | NULL | — | — | Categoria |
| `reservista_ra` | `String(20)` | NULL | — | — | RA (Região de Alistamento) |
| `reservista_foto` | `String(500)` | NULL | — | — | Path da foto |
| `comprovante_residencia_foto` | `String(500)` | NULL | — | — | Path do comprovante |
| `foto` | `String(500)` | NULL | — | — | Foto geral do usuário |
| `created_at` | `DateTime(tz)` | NOT NULL | `now()` | — | Timestamp de criação |
| `updated_at` | `DateTime(tz)` | NOT NULL | `now()` | — | Timestamp de atualização |

#### `rg` — Registro Geral

| Coluna | Tipo | Nullable | Default | Descrição |
|--------|------|----------|---------|-----------|
| `id` | `UUID` PK | NOT NULL | `uuid4()` | PK |
| `numero` | `String(30)` | NULL | — | Número do RG |
| `orgao_emissor` | `String(50)` | NULL | — | Órgão emissor |
| `data_emissao` | `Date` | NULL | — | Data de emissão |
| `foto_frente` | `String(500)` | NULL | — | Path da foto frente |
| `foto_verso` | `String(500)` | NULL | — | Path do foto verso |
| `created_at` | `DateTime(tz)` | NOT NULL | `now()` | — |
| `updated_at` | `DateTime(tz)` | NOT NULL | `now()` | — |

#### `cnh` — Carteira Nacional de Habilitação

| Coluna | Tipo | Nullable | Default | Descrição |
|--------|------|----------|---------|-----------|
| `id` | `UUID` PK | NOT NULL | `uuid4()` | PK |
| `numero` | `String(30)` | NULL | — | Número da CNH |
| `categoria` | `String(5)` | NULL | — | Categoria (A, B, AB, etc.) |
| `data_nascimento` | `Date` | NULL | — | Data de nascimento |
| `validade` | `Date` | NULL | — | Data de validade |
| `registro_nacional` | `String(30)` | NULL | — | Registro nacional (RENACH) |
| `foto_frente` | `String(500)` | NULL | — | Path da foto frente |
| `foto_verso` | `String(500)` | NULL | — | Path do foto verso |
| `created_at` | `DateTime(tz)` | NOT NULL | `now()` | — |
| `updated_at` | `DateTime(tz)` | NOT NULL | `now()` | — |

#### `carteiras_trabalho` — Carteira de Trabalho (CTPS)

| Coluna | Tipo | Nullable | Default | Descrição |
|--------|------|----------|---------|-----------|
| `id` | `UUID` PK | NOT NULL | `uuid4()` | PK |
| `numero` | `String(30)` | NULL | — | Número da CTPS |
| `serie` | `String(20)` | NULL | — | Série |
| `uf` | `String(2)` | NULL | — | UF de emissão |
| `data_emissao` | `Date` | NULL | — | Data de emissão |
| `foto_frente` | `String(500)` | NULL | — | Path da foto frente |
| `foto_verso` | `String(500)` | NULL | — | Path do foto verso |
| `created_at` | `DateTime(tz)` | NOT NULL | `now()` | — |
| `updated_at` | `DateTime(tz)` | NOT NULL | `now()` | — |

#### `passaportes` — Passaporte

| Coluna | Tipo | Nullable | Default | Descrição |
|--------|------|----------|---------|-----------|
| `id` | `UUID` PK | NOT NULL | `uuid4()` | PK |
| `numero` | `String(30)` | NULL | — | Número do passaporte |
| `validade` | `Date` | NULL | — | Data de validade |
| `data_emissao` | `Date` | NULL | — | Data de emissão |
| `foto_frente` | `String(500)` | NULL | — | Path da foto frente |
| `foto_verso` | `String(500)` | NULL | — | Path do foto verso |
| `created_at` | `DateTime(tz)` | NOT NULL | `now()` | — |
| `updated_at` | `DateTime(tz)` | NOT NULL | `now()` | — |

**Nota sobre FKs:** As referências de `documentos` para as tabelas filhas são
**FKs lógicas** (UUID sem constraint de FK declarada no banco). Segue o padrão
de referência cross-service por `external_id` (CONVENTION §4). Shadow table
read-only de `auth.users` é opcional — ver Open Questions.

### Slots de imagem válidos

| Slot | Tipo | Tabela alvo |
|------|------|-------------|
| `rg_foto_frente` | Sub-documento | `rg.foto_frente` |
| `rg_foto_verso` | Sub-documento | `rg.foto_verso` |
| `cnh_foto_frente` | Sub-documento | `cnh.foto_frente` |
| `cnh_foto_verso` | Sub-documento | `cnh.foto_verso` |
| `carteira_trabalho_foto_frente` | Sub-documento | `carteiras_trabalho.foto_frente` |
| `carteira_trabalho_foto_verso` | Sub-documento | `carteiras_trabalho.foto_verso` |
| `passaporte_foto_frente` | Sub-documento | `passaportes.foto_frente` |
| `passaporte_foto_verso` | Sub-documento | `passaportes.foto_verso` |
| `certidao_foto` | Inline | `documentos.certidao_foto` |
| `reservista_foto` | Inline | `documentos.reservista_foto` |
| `comprovante_residencia_foto` | Inline | `documentos.comprovante_residencia_foto` |
| `foto` | Inline | `documentos.foto` |

## 5. Endpoints

### 5.1. Provisionamento (desmilitarizado) — **NOVO (target)**

| Campo | Valor |
|-------|-------|
| **Método** | `POST` |
| **Rota** | `/api/v1/documentos/{external_id}/provision` |
| **Tipo** | **Desmilitarizado** (app para app) |
| **Auth** | Nenhuma |
| **Request body** | `{"gender": "M\|F\|null"}` (opcional — para regra do reservista) |
| **Response** | `201` — `DocumentOut` com todos os sub-documentos criados |
| **Erros** | `409` Document já existe para este external_id |
| **Side-effects** | Cria Document + RG + CNH + CarteiraTrabalho + Passaporte (vazios); campos inline NULL |
| **Idempotência** | Segunda chamada → `409` (ou `200` se optarmos por idempotência — ver Open Questions) |

**Regras de negócio:**
- Cria **todos** os sub-documentos numa transação única (atomicidade)
- Se `gender` for "F" ou null, **mesmo assim cria** o registro de reservista
  (campos NULL) — a regra de gênero é de validação, não de existência
  (conforme TODO: "serviço militar só pra homens, mas tem que criar")
- `external_id` é referência lógica ao `auth.users` — sem FK cross-schema

### 5.2. Consulta (desmilitarizado)

| Campo | Valor |
|-------|-------|
| **Método** | `GET` |
| **Rota** | `/api/v1/documentos/{external_id}` |
| **Tipo** | **Desmilitarizado** |
| **Auth** | Nenhuma |
| **Response** | `200` — `DocumentOut` (com sub-documentos carregados via joinedload) |
| **Erros** | `404` Document não encontrado (quando provisionamento obrigatório) |
| **Comportamento atual** | **get-or-create** — cria Document se não existe (sem sub-documentos) |

**Nota:** O comportamento get-or-create atual diverge do provisionamento eager.
Após implementar o endpoint de provisionamento, este GET deveria retornar `404`
se o Document não foi provisionado (o `auth` é responsável por chamar o provision).

### 5.3. Atualização textual (desmilitarizado)

| Campo | Valor |
|-------|-------|
| **Método** | `PUT` |
| **Rota** | `/api/v1/documentos/{external_id}` |
| **Tipo** | **Desmilitarizado** |
| **Auth** | Nenhuma |
| **Request body** | `DocumentUpdate` (campos parciais por sub-documento) |
| **Response** | `200` — `DocumentOut` atualizado |
| **Erros** | `422` certidao_tipo inválido; `404` Document não encontrado |

**Regras de negócio:**
- Atualização é **parcial** — só os campos enviados são alterados
- Certidão tipo deve ser um de: `nascimento`, `casamento`, `obito`
- Sub-documentos são criados on-demand se não existem (via `_get_or_create_sub`)
- PII (números) é mascarado nos logs (utils/pii.py)

### 5.4. Upload de imagem (desmilitarizado)

| Campo | Valor |
|-------|-------|
| **Método** | `POST` |
| **Rota** | `/api/v1/documentos/{external_id}/imagens/{slot}` |
| **Tipo** | **Desmilitarizado** |
| **Auth** | Nenhuma |
| **Content-Type** | `multipart/form-data` |
| **Validações** | Slot válido (12 opções); MIME type ∈ {image/jpeg, image/png, image/webp}; tamanho ≤ `max_upload_mb` (default 10MB) |
| **Response** | `201` — `DocumentOut` atualizado |
| **Erros** | `422` slot inválido; `422` tipo não permitido; `413` arquivo grande demais |
| **Side-effects** | Salva arquivo em `{media_root}/documentos/{external_id}/{slot}.{ext}`; atualiza path no DB; deleta arquivo anterior se existia |

### 5.5. Download de imagem (desmilitarizado)

| Campo | Valor |
|-------|-------|
| **Método** | `GET` |
| **Rota** | `/api/v1/documentos/{external_id}/imagens/{slot}` |
| **Tipo** | **Desmilitarizado** |
| **Auth** | Nenhuma |
| **Response** | `200` — `FileResponse` com o arquivo de imagem |
| **Erros** | `404` slot vazio ou arquivo não encontrado; `422` slot inválido |

### 5.6. Delete de imagem (desmilitarizado)

| Campo | Valor |
|-------|-------|
| **Método** | `DELETE` |
| **Rota** | `/api/v1/documentos/{external_id}/imagens/{slot}` |
| **Tipo** | **Desmilitarizado** |
| **Auth** | Nenhuma |
| **Response** | `200` — `DocumentOut` atualizado |
| **Erros** | `422` slot inválido |
| **Side-effects** | Remove arquivo do disco; seta coluna para NULL no DB |

### 5.7. Health / Ready (desmilitarizado)

| Campo | Valor |
|-------|-------|
| **Método** | `GET` |
| **Rotas** | `/health`, `/ready` |
| **Tipo** | **Desmilitarizado** |
| **Response** | `{"status": "ok/ready", "version": "..."}` |

## 6. Integrações Externas

| Serviço | Tipo de integração | Propósito | Client em |
|---------|-------------------|-----------|-----------|
| `notify` | HTTP (httpx, desmilitarizado) | Disparar notificações assíncronas (fire-and-forget) | `integrations/notify.py` (**a criar**) |

**Atualmente:** O webhook está embutido em `services/document_service.py` como
`_fire_webhook()` usando httpx direto para `settings.webhook_url`. Deve ser
extraído para `integrations/notify.py` seguindo o padrão dos outros serviços.

**Padrão de integração (CONVENTION §12):**
- Client httpx com context manager
- **Fire-and-forget** — falha é logada (structlog), nunca impede o fluxo principal
- Timeout de 5s
- Logs nunca expõem PII

## 7. Eventos Disparados / Consumidos

### Consumidos

Nenhum. O documents não consome eventos de outros serviços.

### Disparados (via webhook → notify)

| Evento | Gatilho | Destino |
|--------|---------|---------|
| `documento.criado` | Criação do Document (get_or_create ou provision) | `notify` (webhook) |
| `documento.atualizado` | Atualização textual via PUT | `notify` (webhook) |
| `documento.imagem_uploaded` | Upload de imagem via POST | `notify` (webhook) |
| `documento.imagem_deleted` | Delete de imagem via DELETE | `notify` (webhook) |

**Padrão:** Fire-and-forget via httpx.AsyncClient. Falha é logged como warning,
nunca re-raises. O fluxo principal (criação/atualização) é sempre commitado
independentemente da disponibilidade do notify.

## 8. Regras de Negócio Invariantes

1. **MUITO IMPORTANTE → provisionamento eager** — "ao ser criado usuário, um document
   é criado com seu external_id e todos documentos são criados juntos respectivamente"
   (TODO). Invariante: após `POST /provision`, existem 1 Document + 4 sub-documentos
   (RG, CNH, CarteiraTrabalho, Passaporte) com campos NULL.

2. **MUITO IMPORTANTE → certidão única por Document** — "certidao tipo pode ser
   nascimento, casamento e etc, mas só uma por document" (TODO). Invariante:
   `documentos` tem no máximo 1 certidão (campos inline, não tabela separada).
   Tipo ∈ {nascimento, casamento, obito}.

3. **MUITO IMPORTANTE → reservista criado para todos** — "serviço militar só pra
   homens, mas tem que criar" (TODO). Invariante: reservista é criado (campos NULL)
   independentemente do gênero. A **validação** de gênero é responsabilidade do
   serviço que consome (ex.: candidate ao marcar como "completo").

4. **JAMAIS servir imagem sem validação** — Upload aceita apenas {image/jpeg,
   image/png, image/webp} com tamanho ≤ max_upload_mb. Invariante: se MIME ∉
   permitidos ou tamanho > limite → 422/413, arquivo não é salvo.

5. **JAMAIS deletar arquivo sem atualizar DB** — Delete de imagem remove o arquivo
   do disco E seta a coluna para NULL numa mesma operação. Invariante: se o DB
   diz NULL, o arquivo não existe no disco (e vice-versa após sync).

6. **MUITO IMPORTANTE → PII mascarado em logs** — Números de documentos (RG, CNH,
   CTPS, passaporte, certidão, reservista) são mascarados via `mask_number()` antes
   de escrever no structlog. Invariante: nenhum log contém número de documento
   completo.

7. **MUITO IMPORTANTE → external_id sem duplicata** — `external_id` tem constraint
   UNIQUE na tabela `documentos`. Invariante: não existem dois Documents para o
   mesmo usuário.

## 9. Critérios de Aceite

1. [ ] `POST /provision/{external_id}` cria Document + 4 sub-documentos (RG, CNH,
   CarteiraTrabalho, Passaporte) com campos NULL numa transação única.
2. [ ] `POST /provision` para external_id já existente retorna `409`.
3. [ ] `GET /{external_id}` retorna Document com todos os sub-documentos (joinedload).
4. [ ] `PUT /{external_id}` atualiza campos parciais de qualquer sub-documento.
5. [ ] `PUT /{external_id}` com certidao_tipo inválido retorna `422`.
6. [ ] `POST /{external_id}/imagens/{slot}` com MIME válido salva arquivo e atualiza DB.
7. [ ] `POST /{external_id}/imagens/{slot}` com MIME inválido retorna `422` sem salvar.
8. [ ] `POST /{external_id}/imagens/{slot}` com arquivo > max_upload_mb retorna `413`.
9. [ ] `GET /{external_id}/imagens/{slot}` retorna o arquivo via FileResponse.
10. [ ] `DELETE /{external_id}/imagens/{slot}` remove arquivo do disco e seta coluna NULL.
11. [ ] Webhook é extraído para `integrations/notify.py` com fire-and-forget.
12. [ ] Migrações Alembic válidas (`alembic upgrade head` sem erro).
13. [ ] Testes verdes: provisionamento, CRUD textual, imagens, validações.
14. [ ] `ruff check` e `ruff format` limpos.
15. [ ] `wiki/documents.md` reescrita refletindo o serviço novo.

## 10. Riscos / Open Questions

### Riscos

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| Mídia sensível (documentos) exposta sem auth | Média | Alto | Endpoint desmilitarizado = rede interna; considerar restrição de IP ou token assinado (Open Question) |
| `external_id` sem garantia de usuário existente | Média | Médio | Provisionamento é chamado pelo `auth` após commit do User; shadow table opcional |
| Provisionamento eager cria muitos registros vazios | Baixa | Baixo | Aceitável (1 Document + 4 sub-docs por usuário); índices por `external_id` |
| Arquivo no disco sem referência no DB (lixo) | Média | Baixo | Job de limpeza periódica (futuro); delete sempre limpa arquivo+coluna juntos |
| Regra de gênero do reservista depende de dado externo | Média | Médio | Criar reservista para todos (campos NULL); validação de gênero fica no consumidor |

### Open Questions

- [ ] **Shadow table de `auth.users`** — Declarar `Table("users", ...)` no schema
  `auth` para resolver FK cross-schema? Ou manter apenas coluna UUID indexada sem
  FK declarada (comportamento atual)?
- [ ] **Endpoint de provisionamento vs get-or-create** — O GET atual cria o Document
  se não existe. Após implementar `/provision`, o GET deve retornar `404` se não
  provisionado? Ou manter get-or-create como fallback?
- [ ] **Idempotência do provisionamento** — `POST /provision` deve retornar `409` se
  já existe, ou `200` com o Document existente (idempotente)?
- [ ] **Controle de acesso à mídia** — Como restringir download de imagens sensíveis
  num endpoint desmilitarizado? Restrição de rede interna? URL/token assinado?
- [ ] **Validação de gênero para reservista** — O gênero vem no payload do
  provisionamento, ou `documents` consulta o `profiles` via integração? Ou a
  validação é responsabilidade exclusiva do consumidor (candidate)?
- [ ] **Quais notificações via notify** — Definir catálogo mínimo de eventos
  notificados. Os 4 atuais (criado, atualizado, imagem_uploaded, imagem_deleted)
  são suficientes?
- [ ] **Renomeação de modelos para inglês** — `carteira_trabalho.py` → `work_permit.py`?
  Ou manter nomes em português por serem termos de domínio brasileiro?
- [ ] **Dados existentes no SQLite** — Há dados no SQLite atual que precisam migrar,
  ou é greenfield?
- [ ] **`requires-python`** — Atualmente `>=3.11`. Deve ser `>=3.12` conforme
  CONVENTION §2.

---

*CONSOLIDADO a partir de: `documents-service.prd.md`, `wiki/documents.md`,
`documents/TODO`, código-fonte atual (`documents/app/`), CONVENTION.md.*
*Status: PRONTO PARA REVIEW.*
