# coordinator

## Função

Representa o **coordenador de polo** — o administrador local que gerencia as operações acadêmicas de um hub. Possui as mesmas capacidades de um promotor, além de funções administrativas: aprovar treinamentos, gerenciar documentos, taxas de matrícula, provas e diplomas.

---

## Status

**Criado e funcional.** 80 testes passando. Models, services, API endpoints e integrações implementados.

---

## Modelos de dados (schema `coordinator`)

| Tabela | Descrição | Status |
|--------|-----------|--------|
| `coordinators` | Coordenador: external_id, hub_external_id, status | ✅ |
| `training_approvals` | Aprovação de treinamento: pending → approved/rejected | ✅ |
| `enrollment_fees` | Taxa de matrícula: pending → paid | ✅ |
| `exams` | Prova: created → submitted → graded | ✅ |
| `student_documents` | Documento do aluno com flag `submitted_to_institution` | ✅ |
| `diplomas` | Diploma: pending → graduated (dispara comissão) | ✅ |

---

## API Endpoints

### Coordenadores — `/api/v1/coordinators`
| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/api/v1/coordinators` | Criar coordenador |
| GET | `/api/v1/coordinators` | Listar (filtro: hub, status) |
| GET | `/api/v1/coordinators/{id}` | Detalhe |
| PATCH | `/api/v1/coordinators/{id}` | Atualizar status |

### Aprovações de Treinamento — `/api/v1/training-approvals`
| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/api/v1/training-approvals` | Criar solicitação de aprovação |
| GET | `/api/v1/training-approvals` | Listar (filtro: coordinator, status) |
| PATCH | `/api/v1/training-approvals/{id}` | Aprovar/rejeitar → dispara promoção para promoter |

### Taxas de Matrícula — `/api/v1/enrollment-fees`
| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/api/v1/enrollment-fees` | Criar taxa |
| GET | `/api/v1/enrollment-fees` | Listar (filtro: coordinator, student, status) |
| POST | `/api/v1/enrollment-fees/{id}/pay` | Registrar pagamento |

### Provas — `/api/v1/exams`
| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/api/v1/exams` | Criar prova |
| GET | `/api/v1/exams` | Listar (filtro: coordinator, student, status) |
| POST | `/api/v1/exams/{id}/submit` | Submeter prova |
| POST | `/api/v1/exams/{id}/grade` | Corrigir e lançar nota |

### Documentos — `/api/v1/documents`
| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/api/v1/documents` | Criar registro de documento |
| GET | `/api/v1/documents` | Listar (filtro: student, coordinator, type) |
| POST | `/api/v1/documents/{id}/submit` | Enviar para instituição |

### Diplomas — `/api/v1/diplomas`
| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/api/v1/diplomas` | Criar diploma |
| GET | `/api/v1/diplomas` | Listar (filtro: student, coordinator, status) |
| POST | `/api/v1/diplomas/{id}/graduate` | Graduar aluno → dispara comissão |

---

## Integrações

| Serviço | Chamada | Quando |
|---------|---------|--------|
| **commissions** | `POST /api/v1/commissions` | Ao graduar aluno (diploma) |
| **roles** | `POST /api/v1/role/{id}/up/promoter` | Ao aprovar treinamento |

---

## Dependências

- **auth** — autenticação JWT
- **hub** — polo do coordenador
- **commissions** — comissão por graduação
- **roles** — promoção de papel (candidate → promoter)
- **training** — referência de treinamento externo
- **student** — referência de aluno externo

---

## Dados de Teste

80 testes em `coordinator/tests/` cobrindo:
- coordinator CRUD (test_coordinator_svc.py)
- training approvals (test_training_svc.py)
- enrollment fees (test_fee_svc.py)
- exams (test_exam_svc.py)
- student documents (test_document_svc.py)
- diplomas (test_diploma_svc.py)
- API endpoints (test_api.py)

---

## Variáveis de ambiente

| Variável | Descrição |
|----------|-----------|
| `DATABASE_URL` | Postgres connection (asyncpg) |
| `COMMISSIONS_SERVICE_URL` | URL do serviço de comissões |
| `ROLES_SERVICE_URL` | URL do serviço de roles |
| `COORDINATOR_COMMISSION_CENTS` | Valor padrão da comissão (centavos) |
