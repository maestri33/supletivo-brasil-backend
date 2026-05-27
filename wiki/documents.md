# documents

## Função
Armazena e gerencia documentos de identificação dos usuários da plataforma (RG, CNH, Carteira de Trabalho, Passaporte, Certidão, Reservista, Comprovante de Residência), vinculados por `external_id` ao usuário criado em outro serviço. Expõe CRUD de dados textuais e upload/download/deleção de imagens por slot nomeado.

## Status
**Incompleto / não-conforme.** Endpoints funcionais para o fluxo básico (get-or-create, atualizar dados, upload/download/delete de imagens), mas:
- ORM é Tortoise + SQLite (padrão em `.env`) — sem Alembic, sem asyncpg, sem Postgres configurado.
- Nenhuma migração Alembic existe (`alembic/` ausente).
- Nenhum teste existe (`tests/` ausente).
- Sem autenticação em nenhum endpoint.
- Estrutura aninhada (`documents/documents/app`) viola a convenção.

## Estrutura
Aninhada: `documents/documents/app/` — o pacote real fica um nível mais fundo que o esperado pela convenção (`<servico>/app/`). A pasta raiz do serviço é `/home/maestri33/backend/documents/` e o pacote Python fica em `documents/documents/app/`.

## Endpoints

### `api/health.py`
| Método | Rota | Descrição | Tipo |
|---|---|---|---|
| GET | `/health` | Liveness check | Desmilitarizado |
| GET | `/ready` | Readiness check | Desmilitarizado |

### `api/documents.py` — prefixo `/api/v1/documentos`
| Método | Rota | Descrição | Tipo |
|---|---|---|---|
| GET | `/api/v1/documentos/{external_id}` | Retorna (ou cria) o documento do usuário | Desmilitarizado (sem auth) |
| PUT | `/api/v1/documentos/{external_id}` | Atualiza dados textuais do documento e sub-documentos | Desmilitarizado (sem auth) |
| POST | `/api/v1/documentos/{external_id}/imagens/{slot}` | Faz upload de imagem para o slot informado | Desmilitarizado (sem auth) |
| GET | `/api/v1/documentos/{external_id}/imagens/{slot}` | Retorna o arquivo de imagem de um slot | Desmilitarizado (sem auth) |
| DELETE | `/api/v1/documentos/{external_id}/imagens/{slot}` | Remove imagem de um slot | Desmilitarizado (sem auth) |

Slots válidos: `rg_front_photo`, `rg_back_photo`, `cnh_front_photo`, `cnh_back_photo`, `work_card_front_photo`, `work_card_back_photo`, `passport_front_photo`, `passport_back_photo`, `certificate_photo`, `military_photo`, `proof_of_residence_photo`, `photo`.

## Dados
ORM atual: **Tortoise-ORM** (não SQLAlchemy). Banco configurado como SQLite (`sqlite:///root/documents.db`) por padrão. Sem schema Postgres dedicado. Sem Alembic — usa `generate_schemas=True` (proibido em produção pela convenção).

### Tabelas (Tortoise models)

| Tabela | PK | Campos principais |
|---|---|---|
| `documents` | `id` (UUID) | `external_id` (UUID, unique, index); IDs `rg_id`, `cnh_id`, `work_card_id`, `passport_id`; campos inline `certificate_*` (kind, number, registry_office, book, page, entry, issue_date, photo), `military_*` (number, series, category, ra, photo), `proof_of_residence_photo`, `photo`; `created_at`, `updated_at` |
| `rg` | `id` (UUID) | `number`, `issuing_agency`, `issue_date`, `front_photo`, `back_photo` |
| `cnh` | `id` (UUID) | `number`, `category`, `date_of_birth`, `expires_on`, `national_register`, `front_photo`, `back_photo` |
| `work_cards` | `id` (UUID) | `number`, `series`, `state`, `issue_date`, `front_photo`, `back_photo` |
| `passports` | `id` (UUID) | `number`, `expires_on`, `issue_date`, `front_photo`, `back_photo` |

PKs são UUID (conforme convenção §4). `external_id` em `documents` é o UUID do usuário de outro serviço. Sem shadow tables (referência ao usuário do auth é por `external_id` UUID opaco, sem FK cross-schema).

## Integrações

### Internas
- **Webhook interno** (`settings.webhook_url`, padrão `http://10.10.10.129`): dispara via `httpx.AsyncClient` nos eventos `documento.criado`, `documento.atualizado`, `documento.imagem_uploaded`, `documento.imagem_deleted`. Falha silenciosa (log de warning, sem re-raise). Não há client nomeado em `integrations/` — a lógica está embutida em `services/document_service.py`.

### Externas
Nenhuma integração com serviços externos além do webhook interno.

## Pendências

### Arquivo `TODO` (raiz do serviço)
> "corrija isso, tá bem ruim, nome de arquivo em portugues, enfim, aqui o nome já diz, é onde vai ficar os Documentos.
> minha ideia era: ao ser criado usuário, um document é criado com seu external_id e todos documentos são criados juntos respectivamente, com campos null, só document_id relacionado ao document.
> ai tipo: cnh mesmo tem todos dados que tem lá mais espaço para fotos e assim é com todos: rg, certidao (tipo pode ser nascimento, casamento e etc, mas só uma por document), servico militar (só pra homens, mas tem que criar...)"

### TODOs no código
Nenhum comentário `# TODO` encontrado no código-fonte.

### Desvios da CONVENTION

| # | Desvio | Impacto |
|---|---|---|
| 1 | **Aninhamento** `documents/documents/app` em vez de `documents/app` | Estrutura incorreta (§3) |
| 2 | **ORM Tortoise** em vez de SQLAlchemy 2.0 async | Stack não canônica (§2) |
| 3 | **SQLite** como banco padrão; sem asyncpg | Stack não canônica; sem Postgres (§2, §4) |
| 4 | **Sem Alembic**; usa `generate_schemas=True` | Proibido em produção (§4) |
| 5 | **Sem autenticação** em qualquer endpoint | Todos os endpoints deveriam ser pelo menos desmilitarizados com controle de acesso (§5) |
| 6 | **Sem testes** | Nenhum arquivo em `tests/` |
| 7 | **Sem `integrations/`** — webhook embutido no service | Violação de organização (§12) |
| 8 | **Sem `alembic/`** | Ausência completa de migrações |
| 9 | **Nomes de arquivos em português** (`carteira_trabalho.py`) | Identificadores devem ser inglês (§7) |
| 10 | **Schemas Pydantic com `class Config`** (API v1) em vez de `model_config` | Pydantic v2 correto exige `model_config` (§8) |
| 11 | **`requires-python = ">=3.11"`** em vez de `>=3.12` | Stack canônica exige 3.12 (§2) |
| 12 | **Serviço `documents` ausente do design original** — sem `certidao` como tipo próprio, sem `servico_militar` | Funcionalidade incompleta conforme TODO |
| 13 | **Media servida diretamente** pelo FastAPI (`StaticFiles`) — sem controle de acesso às imagens | Risco de exposição de documentos sensíveis |
