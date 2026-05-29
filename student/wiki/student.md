# student — funil do aluno

> Fonte de verdade funcional do servico `student` (CONVENTION §19).
> Apos o coordenador promover um matriculado a aluno, este servico orquestra
> todo o ciclo ate a formatura (veterano).

---

## 1. O que faz

Gerencia o ciclo de vida do aluno em 10 status sequenciais, do envio de
documentos a virada para veterano (com diploma retirado + foto + comissao do
coordenador). Cada transicao notifica o aluno via `notify`. Validacoes de
documento sao assincronas via `ai`. Sem FK cross-schema (§4) — referencias a
outros servicos sao `external_id` UUID opaco.

## 2. Funil de status

```
awaiting_documents
  ─submit─→ documents_under_review
    ─IA aprova─→ exam_released
      ─aluno agenda─→ exam_scheduled
        ─coord passed─→ awaiting_documentation_dispatch
        ─coord failed─→ exam_released  (refaz, attempt_number++)
      ─coord issue─→ awaiting_diploma_issuance | awaiting_pickup
        ─aluno pickup─→ veteran  (dispara comissao + role veterano)
```

Estados isolados:
- `pending` — pendencia identificada pelo coord (resolvida fora de fluxo)
- `awaiting_diploma_issuance` — entre dispatch e pickup (curto)

`veteran` e' terminal. Role `veterano` e' adicionada (multi-role — mantem
`student`), espelhando o padrao do promotor que e' coordenador.

## 3. Modelos (schema `student`)

| Tabela | Campos relevantes |
|---|---|
| `students` | `id`, `external_id` UNIQUE, `status`, `study_platform` JSONB |
| `student_documents` | `student_id` FK, `document_type`, `document_external_id`, `validation_status`, `validation_result` JSONB, `validated_at`. UNIQUE(student_id, document_type) |
| `student_exams` | `student_id` FK, `subject`, `scheduled_at`, `attempt_number`, `result`, `corrected_by_external_id`, `corrected_at`, `notes` |
| `student_diplomas` | `student_id` FK UNIQUE, `issued_by_external_id`, `issued_at`, `picked_up_at`, `pickup_photo_external_id`, `commission_triggered_at` |

Tipos de documento (PRD §4): `military_service` (so' homens), `certificate`,
`transcript`, `id_card` (RG), `blood_type`, `address_proof`, `birth_certificate`.
Obrigatorios para avancar: `certificate`, `transcript`, `id_card` (+
`military_service` se o aluno e' do sexo masculino).

## 4. Endpoints

| Metodo | Rota | Auth | O que faz |
|---|---|---|---|
| POST | `/api/v1/authenticated/students` | coordinator | Promove matriculado a aluno (idempotente; 409 se ja existe) |
| GET | `/api/v1/authenticated/students/me` | student | Dados do aluno autenticado |
| GET | `/api/v1/authenticated/students/me/documents` | student | Lista docs enviados |
| POST | `/api/v1/authenticated/students/me/documents` | student | Cadastra ref a um documento (1 por tipo) |
| POST | `/api/v1/authenticated/students/me/documents/submit-for-review` | student | Submete docs p/ validacao IA; status → `documents_under_review` |
| GET | `/api/v1/authenticated/students/me/exams` | student | Lista provas |
| POST | `/api/v1/authenticated/students/me/exams` | student | Agenda prova (status `exam_released` → `exam_scheduled`) |
| PATCH | `/api/v1/authenticated/students/{student_id}/exams/{exam_id}` | coordinator | Lanca resultado; passed → `awaiting_documentation_dispatch`, failed → `exam_released` |
| POST | `/api/v1/authenticated/students/{student_id}/diploma/issue` | coordinator | Emite (cert + hist); status → `awaiting_pickup` |
| POST | `/api/v1/authenticated/students/me/diploma/pickup` | student | Registra retirada com foto; status → `veteran`. Background: comissao + role veterano |
| GET | `/api/v1/authenticated/students/me/pending-items` | student | Status atual + docs reprovados |
| GET | `/health` `/ready` `/status` `/metrics` | publico | Diagnostico |

Erros: 404 `student_not_found` · 409 `student_already_exists` · 422
`required_document_missing` / `invalid_status_transition` · 403 status incompativel
com a operacao.

## 5. Integracoes externas

| Servico | Quando chama | Como degrada |
|---|---|---|
| `ai` | `submit-for-review` → BackgroundTask valida cada doc via `/api/v1/image/vision` | Doc fica `pending`, fluxo nao quebra (§14) |
| `documents` | Gera URL absoluta da imagem pra passar pro `ai` | Validacao IA cai gracioso |
| `profiles` | `submit-for-review` consulta `gender` p/ regra reservista | Sem gender → reservista vira opcional |
| `notify` | Toda mudanca de status (BackgroundTask) | Apenas loga, fluxo segue (§13) |
| `commissions` | Pickup do diploma → comissao do coord (idempotente por `student_id`) | Loga, tenta de novo na proxima reentrada |
| `roles` | Pickup → adiciona role `veterano` (multi-role) | Loga; pode ser tentado de novo manualmente |

Todas as URLs sao configuradas em `.env` (`AI_BASE_URL`, `DOCUMENTS_BASE_URL`,
etc.). Sem hardcoded. Sem import de modelo alheio. Cliente em
`app/integrations/<servico>.py`, base `BaseClient` + `request_with_retry`
(retry exponencial 3x somente em 5xx/transporte).

## 6. Quem chama este servico

- **Coordenador (UI/CLI):** `POST /students` (promocao) e PATCH/POST sob
  `/students/{id}/...` (correcao de prova, emissao de diploma).
- **App do aluno:** todos os `/students/me/...`.

Sem ser chamado por nenhum outro app via HTTP no momento (sem rotas
desmilitarizadas — pode ser adicionado depois se enrollment quiser
notificar a conclusao de matricula automaticamente).

## 7. Eventos disparados

- `student.promoted` — log estruturado na promocao.
- `student.documents_under_review` — apos submit-for-review (notify).
- `student.exam_released` — apos IA aprovar todos obrigatorios.
- `student.exam_scheduled` — apos agendamento.
- `student.exam_failed` / `awaiting_documentation_dispatch` — apos correcao.
- `student.veteran` — apos pickup. Side-effects: `commissions.trigger_graduation`
  + `roles.promote(external_id, "veterano")`.

## 8. Decisoes de projeto

1. **PK UUID, sem FK cross-schema (§4).** `student_id` e' FK intra-schema;
   `external_id` opaco.
2. **Enum completo desde o inicio.** Os 10 status existem na 0001; novas
   transicoes nao exigem migration de tipo.
3. **Tipo sanguineo como documento** (foto), nao campo. Decidido em
   2026-05-27 pra suportar validacao IA da foto do cartao.
4. **Gender via HTTP (`profiles`)** em vez de duplicar em `students` (§11).
   Falha de profiles → reservista vira opcional, nao bloqueia.
5. **BackgroundTasks pra validacao IA** (nao worker dedicado). Mais simples;
   se virar gargalo, evoluir pra worker_loop estilo `asaas`.
6. **Comissao idempotente por `student_id`.** `student_diplomas
   .commission_triggered_at` evita duplicar.
7. **Coordinator NAO e' dono dessas tabelas.** Provas, docs e diplomas vivem
   aqui (CONVENTION §6). Coordinator so' chama os endpoints de coord.

## 9. Configuracao (.env)

Ver `.env.example`. Chaves obrigatorias: `DATABASE_URL`, `JWT_BASE_URL`.
Demais `*_BASE_URL` tem default razoavel pra docker-compose.

## 10. Operacao

- Build: `docker compose -f docker-compose.dev.yml up -d --build student`
- Migrate: `docker exec backend-student-1 uv run alembic upgrade head`
- Logs: `docker logs backend-student-1`
- Health: `curl :8021/health` · `:8021/ready` · `:8021/status`
- Metrics: `:8021/metrics`
- Testes locais: `cd student && uv run pytest -q` (sqlite, sem rede)
