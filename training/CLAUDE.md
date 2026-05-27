# CLAUDE.md — training (LMS + correção IA)

Particularidades do serviço `training` que complementam CONVENTION.md da raiz.

## Model

- **PK = UUID como String(36).** `UUIDStr = PG_UUID(as_uuid=False).with_variant(String(36), "sqlite")` — compatível com SQLite nos testes e Postgres em produção. Mesmo padrão do `candidate`.
- **Material:** título, texto, questão, resposta esperada (gabarito), video_path, photo_path opcionais.
- `_mixins.py` provê `TimestampMixin` (created_at/updated_at com server_default).

## API

- **Todas as rotas são desmilitarizadas** (uso interno da plataforma, sem auth).
- Prefixo: `/api/v1/demilitarized/*`.
- CRUD de materiais + upload/download de vídeo e foto.
- Upload valida MIME type por tipo (video/* para vídeo, image/* para foto).

## Mídia

- Armazenamento local em `MEDIA_DIR` (configurável, default `./media`).
- Servida via `FileResponse` nos endpoints GET de download — nunca via `StaticFiles` aberto.
- Estrutura: `MEDIA_DIR/<material_id>/<kind><ext>`.

## Integração com AI

- Cliente em `app/integrations/ai.py` — chama `POST /api/v1/text/` do serviço `ai`.
- Correção de resposta: endpoint `POST /api/v1/demilitarized/materials/{id}/grade` compara resposta do candidato com gabarito via IA.
- Timeout e URL base do AI via Settings (`AI_BASE_URL`, `AI_TIMEOUT`).

## Testes

- Usam SQLite em memória (compatível com UUIDStr).
- Sem dependência de Postgres — todos os 11 testes passam sem infra externa.
- Fixture `client` em `tests/conftest.py` usa `AsyncClient` + `ASGITransport`.

## Config

- `DATABASE_URL` com default SQLite para dev (`sqlite+aiosqlite:///training.db`).
- `MEDIA_DIR` default `./media`. `MAX_UPLOAD_MB` default 100.
- `AI_BASE_URL` aponta para o serviço `ai` (ex.: `http://ai:8000`).
