# coordinator

## Função

Representa o **coordenador de polo** — o administrador local que gerencia as operações acadêmicas de um hub. Possui as mesmas capacidades de um promotor, além de funções administrativas: aprovar treinamentos, promover candidatos a alunos, gerenciar documentos, matrículas, provas e diplomas.

---

## Status

**Não criado (Parte B / Sprint futuro).** Apenas descrição de requisitos existe no `TODO`.

---

## Responsabilidades do coordenador

| Função | Serviço alvo | Endpoint |
|---|---|---|
| Aprovar conclusão de treinamento | training | Demilitarized: promover candidato a promotor |
| Promover candidato a aluno | student | Authenticated: POST /promote |
| Enviar documentos do aluno para instituição | documents | Demilitarized: upload/dispatch |
| Incluir dados de acesso à plataforma | student | Authenticated: atualizar study_platform |
| Pagar e cadastrar taxas de matrícula | enrollment, fees | Autenticado: criar cobrança |
| Aplicar prova | training | Demilitarized: liberar exame |
| Corrigir e postar resultado | training | Demilitarized: submeter resposta, IA corrige |
| Juntar documentos e enviar para instituição | documents | Demilitarized: dispatch batch |
| Postar histórico e diploma do aluno | documents, student | Demilitarized: upload diploma |
| Postar foto do aluno recebendo diploma | student | Demilitarized: trigger veteran status |

---

## Modelo de dados (planejado)

### Tabela `coordinator.coordinators`

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | UUID | PK |
| `external_id` | UUID | FK para auth.users |
| `hub_external_id` | UUID | FK lógica para hub.hubs |
| `status` | enum | `active`, `inactive`, `suspended` |
| `created_at` | timestamptz | Criação |
| `updated_at` | timestamptz | Última atualização |

---

## Endpoints (planejados)

### Autenticados (coordenador logado)

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/v1/authenticated/coordinator/me` | Dados do coordenador logado |
| GET | `/api/v1/authenticated/coordinator/hub` | Dados do polo associado |
| GET | `/api/v1/authenticated/coordinator/students` | Lista alunos do polo |
| POST | `/api/v1/authenticated/coordinator/students/{id}/documents` | Enviar documentos |
| POST | `/api/v1/authenticated/coordinator/students/{id}/exam` | Aplicar prova |
| POST | `/api/v1/authenticated/coordinator/students/{id}/diploma` | Postar diploma/foto |

### Desmilitarizados (interno)

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/v1/demilitarized/coordinators` | Lista todos os coordenadores |
| GET | `/api/v1/demilitarized/coordinators/{id}` | Detalhe do coordenador |
| PATCH | `/api/v1/demilitarized/coordinators/{id}` | Atualizar status/dados |
| POST | `/api/v1/demilitarized/coordinators` | Criar coordenador (onboarding) |

---

## Dependências

- **auth** — autenticação e JWT
- **hub** — polo ao qual o coordenador pertence
- **student** — gestão de alunos
- **training** — aprovação de treinamentos
- **documents** — gestão documental
- **enrollment** — matrículas
- **fees** — taxas
- **roles** — verificação de papel

---

## Variáveis de ambiente

| Variável | Descrição | Exemplo |
|---|---|---|
| `DATABASE_URL` | URL de conexão Postgres | `postgresql+asyncpg://...` |
| `JWT_PUBLIC_KEY_PATH` | Caminho da chave pública JWT | `../jwt/public.pem` |
