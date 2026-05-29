# training

LMS de onboarding: trilha de **matérias** que o usuário (entre `candidate` e
`promoter`) precisa concluir para virar promotor. Este repositório implementa o
serviço; o desenho completo está em `.claude/prds/training.prd.md` (raiz do
backend) e o plano por etapa em `.claude/plans/training.plan.md`.

## Estado atual — Milestone 1 (Autoria de matérias)

Implementado:
- Criar/listar/buscar/atualizar matéria (texto + 1 questão + 1 resposta esperada).
- Upload e download de **vídeo** e **foto** da matéria, armazenados no próprio
  serviço (`MEDIA_DIR`) e servidos via `FileResponse` (sem `StaticFiles` aberto).

Ainda **não** implementado (próximos milestones — ver PRD):
- M2: trainee busca matéria, envia resposta, correção assíncrona por IA (`ai`),
  nota 0–10 + justificativa, aprovação (≥6) e reenvio.
- M3: "todas aprovadas" → entrevista do coordenador (aprova/rejeita).
- M4: papel `training` no serviço `roles` (`candidate → training → promoter`).
- M5: notificações de mudança de status via `notify`.

## Como rodar

```bash
uv sync
cp .env.example .env   # ajuste TRAINING_APP_DB_URL
uv run alembic upgrade head
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Qualidade:

```bash
uv run ruff check . && uv run ruff format .
uv run pytest -q
```

## Endpoints (M1 — todos desmilitarizados, uso interno, sem auth)

| Método | Rota | Descrição |
|---|---|---|
| POST | `/api/v1/demilitarized/materials` | Cria matéria (vídeo/foto nulos) |
| GET | `/api/v1/demilitarized/materials` | Lista matérias (paginado) |
| GET | `/api/v1/demilitarized/materials/{id}` | Busca matéria |
| PUT | `/api/v1/demilitarized/materials/{id}` | Atualiza campos de texto |
| POST | `/api/v1/demilitarized/materials/{id}/video` | Upload do vídeo |
| POST | `/api/v1/demilitarized/materials/{id}/photo` | Upload da foto |
| GET | `/api/v1/demilitarized/materials/{id}/video` | Baixa o vídeo |
| GET | `/api/v1/demilitarized/materials/{id}/photo` | Baixa a foto |
| GET | `/health` · `/ready` · `/status` | Infra |

## Variáveis de ambiente

Ver `.env.example`. Principais: `TRAINING_APP_DB_URL` (obrigatória),
`DATABASE_SCHEMA=training`, `MEDIA_DIR`, `MAX_UPLOAD_MB`.

## Dados

Schema Postgres `training`, tabela `materials` (PK UUID). Sem FK cross-schema —
quando o trainee entrar (M2), `external_id` será referência lógica ao `auth`.
