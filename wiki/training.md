# training

## Função

Serviço FastAPI do **LMS de onboarding**. O usuário passa pelo papel `training`
(entre `candidate` e `promoter`) e precisa concluir todas as **matérias** para
virar promotor. O serviço `candidate` promove o usuário para o papel `training`
ao concluir o funil inicial (`candidate/app/services/selfie.py`).

> **Escopo (§6):** o training gerencia matérias, respostas dos trainees, correção
> por IA e a transição até a entrevista com o coordenador. A promoção final de
> papel (`training → promoter`) é feita pelo serviço `roles` — o training apenas
> sinaliza a aprovação. IA é delegada ao serviço `ai`; notificações ao `notify`.

## Status

**M1 completo (green-field, criado 2026-05-27).** Stack canônica async.

- Stack: FastAPI + SQLAlchemy 2.0 **`AsyncSession`** + **asyncpg** + **Alembic** +
  **Pydantic v2** + **structlog** + pydantic-settings.
- Porta: **8000**.
- Verificação: `ruff check`/`format` limpos · `pytest` passando.
- M1 cobre autoria de matérias (CRUD + upload/download de vídeo e foto).

### Roadmap (PRD: `.claude/prds/training.prd.md`)

| Milestone | Escopo | Status |
|-----------|--------|--------|
| M1 | Autoria de matérias (CRUD + upload de mídia) | ✅ concluído |
| M2 | Trainee busca matéria, envia resposta, correção assíncrona por IA (`ai`), nota 0–10 + justificativa, aprovação (≥6), reenvio | planejado |
| M3 | Todas aprovadas → entrevista do coordenador (aprova/rejeita com motivo) | planejado |
| M4 | Papel `training` no serviço `roles` (`candidate → training → promoter`) | planejado |
| M5 | Notificações de mudança de status via `notify` | planejado |

## Estrutura

`training/app/` — achatado conforme §3 (pacote `app`).

```
training/
├── app/
│   ├── main.py              # FastAPI; lifespan; health/ready/status; handler DomainError
│   ├── config.py            # Settings (.env)
│   ├── db.py                # async engine, Base, NAMING_CONVENTION, utcnow, get_session
│   ├── exceptions.py        # DomainError + NotFound/Conflict/ValidationError
│   ├── models/
│   │   ├── _mixins.py       # TimestampMixin (created_at, updated_at)
│   │   └── material.py      # Material (id, title, text_content, question, expected_answer, video_path, photo_path)
│   ├── schemas/
│   │   └── material.py      # Pydantic v2 schemas
│   ├── services/
│   │   ├── material.py      # CRUD de matérias
│   │   └── media.py         # Upload/download de vídeo e foto (FileResponse)
│   ├── api/
│   │   ├── router.py        # Agrega routers
│   │   └── demilitarized/
│   │       └── materials.py # Rotas CRUD + upload/download
│   └── utils/
│       └── logging.py       # structlog
├── alembic/                 # env.py async + versions/
├── tests/                   # async (sqlite)
├── Dockerfile · Makefile · pyproject.toml · .env.example · README.md
└── .claude/                 # CLAUDE.md + memory/
```

## Endpoints (M1)

Todos os endpoints M1 são **desmilitarizados** (§5) — uso interno entre apps,
sem auth JWT.

### `api/demilitarized/materials.py` — `/api/v1/demilitarized/materials`

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/` | Cria matéria (texto + questão + resposta esperada). Vídeo e foto começam null |
| GET | `/` | Lista matérias (paginado) |
| GET | `/{id}` | Busca matéria por id |
| PUT | `/{id}` | Atualiza campos de texto (title, text_content, question, expected_answer) |
| POST | `/{id}/video` | Upload do vídeo da matéria (multipart) |
| POST | `/{id}/photo` | Upload da foto da matéria (multipart) |
| GET | `/{id}/video` | Download do vídeo (FileResponse) |
| GET | `/{id}/photo` | Download da foto (FileResponse) |

### Saúde — `/health` `/ready` `/status` (convenção v7m)

## Dados

**Schema Postgres:** `training`. **PK = UUID** (`postgresql.UUID(as_uuid=False)`,
gerada na app via `uuid4`). Datas/hora em **`timestamptz`** (UTC).

| Tabela | PK | Campos-chave | Unique/Index |
|--------|----|--------------|--------------|
| `materials` | `id` (UUID) | `title`, `text_content`, `question`, `expected_answer`, `video_path`, `photo_path` | — |

- `video_path` e `photo_path` são caminhos relativos dentro de `MEDIA_DIR`,
  nulos até o upload.
- Arquivos salvos em `MEDIA_DIR/<material_id>/<video|photo><ext>`. Servidos via
  `FileResponse`, **nunca** via `StaticFiles` aberto (evita exposição indevida).
- Validação de MIME type e `MAX_UPLOAD_MB` no upload.
- UUID usa variant `String(36)` em sqlite (testes) para evitar conversão NUMERIC.

### Máquina de estados (M2+, planejado)

```
candidate → training (promovido pelo candidate ao concluir funil)
         → trainee busca matéria, envia resposta
         → IA corrige (nota 0–10), ≥6 = aprovado, <6 = reenviar
         → todas aprovadas → status "aguardando entrevista"
         → coordenador aprova → promoter (via roles)
         → coordenador rejeita → motivo em texto, pode reenviar
```

## Integrações (§12)

| Serviço | Direção | Uso |
|---------|---------|-----|
| **ai** (M2) | training → ai | `POST` para correção assíncrona de respostas (DeepSeek v4 Pro). Proibido client IA direto no training |
| **roles** (M4) | training → roles | Promoção `training → promoter` após aprovação do coordenador |
| **notify** (M5) | training → notify | Notificações de mudança de status (BackgroundTasks, sempre async) |
| **candidate** | candidate → training | `candidate` promove usuário para papel `training` ao concluir funil |

## Tipos de endpoint (§5)

M1: **desmilitarizado** — CRUD de matérias e upload/download são chamados
internamente por outros apps da plataforma, sem auth.

M2+: endpoints de trainee (autenticados, JWT) e endpoints do coordenador
(autenticados + role).

## Mídia

- Upload via `UploadFile` (FastAPI), exige `python-multipart` (justificado no
  CLAUDE.md, dentro da intenção da stack §2).
- Armazenamento local em `MEDIA_DIR` (volume).
- Servido via `FileResponse` com validação de caminho — sem `StaticFiles` aberto.
- Validação de MIME type (vídeo/foto) e limite `MAX_UPLOAD_MB`.

## Variáveis de ambiente

| Variável | Obrigatória | Descrição |
|----------|-------------|-----------|
| `TRAINING_APP_DB_URL` | sim | URL do Postgres (asyncpg) |
| `DATABASE_SCHEMA` | não | Schema Postgres (default: `training`) |
| `MEDIA_DIR` | não | Diretório de mídia (default: `./media`) |
| `MAX_UPLOAD_MB` | não | Tamanho máximo de upload (default: `50`) |

## Dependências do ecossistema

- **ai**: necessário para M2 (correção de respostas). Sem o `ai`, respostas não
  são corrigidas — degrade gracefully (log e retry).
- **roles**: necessário para M4 (promoção de papel). Sem `roles`, o ciclo não
  fecha — o trainee fica em "aguardando entrevista" indefinidamente.
- **notify**: desejável para M5. Falha de notificação NÃO bloqueia o fluxo (§12).
