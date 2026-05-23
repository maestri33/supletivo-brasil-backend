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

Slots válidos: `rg_foto_frente`, `rg_foto_verso`, `cnh_foto_frente`, `cnh_foto_verso`, `carteira_trabalho_foto_frente`, `carteira_trabalho_foto_verso`, `passaporte_foto_frente`, `passaporte_foto_verso`, `certidao_foto`, `reservista_foto`, `comprovante_residencia_foto`, `foto`.

## Dados
ORM atual: **Tortoise-ORM** (não SQLAlchemy). Banco configurado como SQLite (`sqlite:///root/documents.db`) por padrão. Sem schema Postgres dedicado. Sem Alembic — usa `generate_schemas=True` (proibido em produção pela convenção).

### Tabelas (Tortoise models)

| Tabela | PK | Campos principais |
|---|---|---|
| `documentos` | `id` (IntField) | `external_id` (UUID, unique, index); FKs para `rg`, `cnh`, `carteira_trabalho`, `passaporte`; campos inline de certidão, reservista, comprovante_residencia, foto; `created_at`, `updated_at` |
| `rg` | `id` (IntField) | `numero`, `orgao_emissor`, `data_emissao`, `foto_frente`, `foto_verso` |
| `cnh` | `id` (IntField) | `numero`, `categoria`, `data_nascimento`, `validade`, `registro_nacional`, `foto_frente`, `foto_verso` |
| `carteiras_trabalho` | `id` (IntField) | `numero`, `serie`, `uf`, `data_emissao`, `foto_frente`, `foto_verso` |
| `passaportes` | `id` (IntField) | `numero`, `validade`, `data_emissao`, `foto_frente`, `foto_verso` |

PKs são `IntField` (não UUID como exige a convenção). `external_id` em `documentos` é o UUID do usuário de outro serviço. Sem shadow tables (não há SQLAlchemy nem FK cross-schema declarada).

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
| 5 | **PK IntField** em vez de UUID | Viola convenção de PK (§4) |
| 6 | **Sem autenticação** em qualquer endpoint | Todos os endpoints deveriam ser pelo menos desmilitarizados com controle de acesso (§5) |
| 7 | **Sem testes** | Nenhum arquivo em `tests/` |
| 8 | **Sem `integrations/`** — webhook embutido no service | Violação de organização (§12) |
| 9 | **Sem `alembic/`** | Ausência completa de migrações |
| 10 | **Nomes de arquivos em português** (`carteira_trabalho.py`) | Identificadores devem ser inglês (§7) |
| 11 | **Schemas Pydantic com `class Config`** (API v1) em vez de `model_config` | Pydantic v2 correto exige `model_config` (§8) |
| 12 | **`requires-python = ">=3.11"`** em vez de `>=3.12` | Stack canônica exige 3.12 (§2) |
| 13 | **Serviço `documents` ausente do design original** — sem `certidao` como tipo próprio, sem `servico_militar` | Funcionalidade incompleta conforme TODO |
| 14 | **Media servida diretamente** pelo FastAPI (`StaticFiles`) — sem controle de acesso às imagens | Risco de exposição de documentos sensíveis |
