# Convenções — candidate

## Identificadores
- `external_id` é sempre tratado como **string** no código (URLs, JSON, JWT). As
  queries e inserts normalizam com `str(...)` — a coluna é `as_uuid=False`.

## Status do funil
- `CandidateStatus` é um `enum.StrEnum`; a coluna `status` é `String`. Comparar e
  atribuir via membros (`CandidateStatus.X`) ou `.value` — ambos funcionam.
- Avanço só por `services.candidate.advance(candidate, current, next)`
  (idempotente). Não setar `status` na mão nos endpoints.

## Camadas
- **api/**: valida entrada, chama service, devolve schema. Sem regra de negócio.
  Erros de serviço upstream → `with upstream_errors():` (preserva status+detail).
- **services/**: regra de negócio + chamadas HTTP. Levanta exceções de domínio
  (`exceptions.py`); não importa `HTTPException`.
- **integrations/**: 1 client por serviço; `request_with_retry` (backoff
  `asyncio.sleep`, retry só em 5xx/transporte; 4xx vira `HTTPStatusError`).

## Erros
- `DomainError` e subclasses (NotFound 404, Conflict 409, ValidationError 422,
  IntegrationError 502) → convertidas em JSON pelo handler em `main.py`.

## Notificações (§11)
- Sempre via `BackgroundTasks` + `services/notifications.py`; toleram falha
  (logam, não quebram o request). Candidato a cada avanço; hub na conclusão.

## Testes
- `tests/conftest.py`: sqlite+aiosqlite (`CANDIDATE_APP_DB_URL` setado antes de
  importar `app`), `DATABASE_SCHEMA=""`, tabelas recriadas por teste.
- JWT é dispensado por `app.dependency_overrides[get_current_external_id]`
  (fixture `login_as`). Integrações são stubadas pela fixture `mocks` (substitui
  os client classes nos módulos de service por `AsyncMock`).

## Estilo
- pt-br em comentário/doc; inglês em log técnico; sem segredo em log.
- ruff: `line-length=100`, regras `E,F,I,B,UP,N,ASYNC`. Rodar `ruff format` + `ruff check`.
