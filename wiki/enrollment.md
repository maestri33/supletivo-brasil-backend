# enrollment

## Função

Receptor de webhook do serviço `lead`: quando um Lead atinge o status `COMPLETED`, o `lead` envia um POST para este serviço, que persiste o evento de forma auditiva e idempotente. É o ponto de entrada do fluxo de matrícula — a lógica real de coleta de dados (perfil, endereço, documentos, dados educacionais, selfie) ainda não foi implementada.

## Status

**Incompleto / Stub auditivo.**

- 1 migração Alembic presente (0001 — cria `enrollment.enrollment_events`).
- 3 endpoints implementados (webhook POST + 2 de auditoria GET).
- Testes E2E presentes e cobrindo os cenários principais (persistência, idempotência, FK, 404).
- Toda a lógica de matrícula descrita no TODO está ausente: coleta de perfil, endereço, documentos, dados educacionais, selfie, status de progressão, notificação ao coordenador do polo e promoção a `student`.

## Estrutura

Localização correta: `enrollment/app/` (sem aninhamento). Conforme §3 da CONVENTION.

```
enrollment/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── db.py
│   ├── exceptions.py
│   ├── api/
│   │   └── webhooks.py
│   ├── models/
│   │   └── enrollment_event.py
│   └── schemas/
│       └── enrollment_event.py
├── alembic/
│   └── versions/2026-05-15_initial_enrollment_schema.py
├── tests/
│   ├── conftest.py
│   ├── test_health.py
│   └── test_webhooks.py
├── pyproject.toml
└── TODO
```

Ausentes (previstos pela convenção): `services/`, `integrations/`, `utils/`.

## Endpoints

### `app/api/webhooks.py` — prefixo `/api/v1`

| Método | Rota | Descrição | Tipo |
|--------|------|-----------|------|
| `POST` | `/webhook/new/{external_id}` | Recebe bifurcação do lead (`lead.completed`); persiste evento; idempotente por `(external_id, event)` | Público (webhook interno do `lead`) |
| `GET` | `/events` | Lista eventos com paginação; filtra opcionalmente por `external_id` | Desmilitarizado |
| `GET` | `/events/{event_id}` | Retorna evento por ID inteiro; 404 se não encontrado | Desmilitarizado |

### `app/main.py` — endpoints de infraestrutura

| Método | Rota | Descrição | Tipo |
|--------|------|-----------|------|
| `GET` | `/health` | Liveness básico | Desmilitarizado |
| `GET` | `/ready` | Readiness com ping ao banco | Desmilitarizado |
| `GET` | `/status` | Versão, env e uptime | Desmilitarizado |

## Dados

**Schema Postgres:** `enrollment`

### Tabela `enrollment.enrollment_events`

| Coluna | Tipo | Constraint | Descrição |
|--------|------|------------|-----------|
| `id` | `BIGINT` | PK, autoincrement | Identificador sequencial |
| `external_id` | `UUID` | NOT NULL, INDEX, FK → `auth.users.external_id` (RESTRICT/CASCADE) | Referência cross-schema ao usuário |
| `event` | `VARCHAR(64)` | NOT NULL, INDEX | Tipo do evento (ex.: `lead.completed`) |
| `promoter_external_id` | `UUID` | NULLABLE, INDEX | UUID do promotor que indicou o lead |
| `payload` | `JSONB` | NOT NULL | Corpo bruto do webhook |
| `received_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | Timestamp de recepção |
| `processed_at` | `TIMESTAMPTZ` | NULLABLE | Quando a lógica de matrícula processar (futuro) |

**Unique implícita lógica:** deduplicação por `(external_id, event)` feita em código (sem constraint UNIQUE no banco — risco de race condition).

**Shadow table cross-schema:**

```python
# db.py — shadow auth.users para resolver FK cross-schema
auth_users = Table("users", metadata,
    Column("external_id", PG_UUID(as_uuid=True), primary_key=True),
    schema="auth")
```

## Integrações

### Internas (recebe de)

- **`lead`** → envia `POST /api/v1/webhook/new/{external_id}` quando Lead.status → `COMPLETED`. Não há client httpx ativo: este serviço só recebe.

### Externas

Nenhuma implementada.

### Ausentes (previstas pelo TODO)

- **`notify`** — notificação ao coordenador do polo ao completar dados; promoção a `student` via serviço de usuários/auth.

## Pendências

### Arquivo `TODO`

Todo o fluxo de matrícula está pendente:

1. Coletar **perfil** do candidato.
2. Coletar **endereço**.
3. Coletar **documento RG** (obrigatório).
4. Coletar **dados educacionais** (último ano estudado, quando, em que escola).
5. Coletar **selfie** (mesma lógica do candidato).
6. Controlar **progressão por status** conforme dados enviados.
7. Ao completar todos os dados → status `aguardando_liberacao`.
8. Notificar **coordenador do polo** ao preenchimento completo (via `notify`).
9. Ao inserir dados da plataforma → enrollment concluído → usuário vira `student`.

### TODOs no código

- `processed_at` no model tem comment `"Quando lógica de matrícula real processar (futuro)"` — coluna existe mas nunca é preenchida.
- Nenhum `# TODO` explícito em código, mas `main.py` tem docstring `"stub auditivo"` deixando claro o estado incompleto.

### Desvios da CONVENTION

| Item | Situação |
|------|----------|
| **`httpx` ausente nas deps de produção** | `httpx` só aparece em `[dependency-groups.dev]`; quando integrações forem adicionadas, precisa ir para `[project].dependencies` |
| **`fastapi-structured-logging`** | Lib fora da stack canônica (§2 lista `structlog`). Uso não justificado em `CLAUDE.md` (arquivo ausente). `main.py` usa `fsl.setup_logging` e `fsl.get_logger` em vez de `structlog` direto; `webhooks.py` usa `structlog.get_logger()` — inconsistência entre módulos. |
| **PK da tabela é `BIGINT` sequencial**, não `UUID` | §4 da CONVENTION exige `PK = UUID`. `enrollment_events.id` é `BigInteger` autoincrement. |
| **Sem constraint UNIQUE** em `(external_id, event)` | Deduplicação feita em código; race condition possível sob carga. |
| **`services/` ausente** | Convenção exige pasta; lógica de negócio está direto na rota (`webhooks.py`). |
| **`CLAUDE.md` ausente** | §1 prevê `CLAUDE.md` para particularidades do serviço; não existe. |
| **`README.md` ausente** | §3 da CONVENTION prevê `README.md`; não existe. |
| **Sem `integrations/`** | Pasta inexistente; obrigatória quando houver clientes httpx (§12). |
| **CORS `allow_origins=["*"]`** | Permissivo demais para produção. |
