# A1 — Auditoria de Endpoints sem Auth por Categoria (CONVENTION §5)

> **Issue:** COD-45  
> **Status:** Em andamento  
> **Data:** 2026-05-27  
> **Auditor:** SecReviewer  
> **Serviços auditados:** 22  

---

## Resumo Executivo

Dos **22 serviços** com diretório `app/api/`, apenas **7** possuem mecanismo de autenticação de usuário implementado. Os **15 restantes** expõem endpoints com apenas `Depends(get_session)` — ou nenhum `Depends` — sem verificar JWT, role, ou identidade do solicitante.

### Serviços com Auth de Usuário
| Serviço | Mecanismo |
|---------|-----------|
| lead    | `get_current_external_id` + `require_*()` status gates via JWT |
| candidate | `get_current_external_id` + `require_*()` status gates via JWT |
| fees    | `get_current_coordinator` via JWT (rota autenticada) |
| hub     | `get_current_external_id` via JWT (nas rotas autenticadas) |
| promoter| `get_current_external_id` + `get_current_promoter` via JWT |
| staff   | `get_current_external_id` via JWT |
| student | `require_role("coordinator"/"student")` via JWT |

### Serviços SEM Auth de Usuário
**CRÍTICO:** address, ai, asaas, auth, commissions, coordinator, documents, enrollment, infinitepay, jwt, notify, otp, profiles, roles, training

---

## Classificação CONVENTION §5

### 🔓 Desmilitarizados (comunicação interna entre apps)
Estes endpoints deveriam ser chamados apenas por outros serviços da plataforma, nunca expostos externamente:

| Serviço | Endpoint | Método | Problema |
|---------|----------|--------|----------|
| lead | `/api/v1/auth/check` | POST | Sem `get_current_external_id` (é public, OK) |
| lead | `/api/v1/auth/login` | POST | Endpoint público, OK |
| training | `/api/v1/materials` (CRUD) | GET/POST/PUT/DELETE | **TODO o CRUD** sem auth, só `Depends(get_session)` |
| enrollment | `/api/v1/webhook/new/{id}` | POST | Sem verificação de origem (desmilitarizado interno) |
| hub | `/api/v1/hubs`, `/api/v1/hubs/{id}` | GET | Desmilitarizado correto (read-only, público = leitura) |
| address | `/api/entity/{eid}/address` | GET/PATCH/POST | CRUD sem auth |
| ai | `/api/v1/text/chat`, `/api/v1/image` | POST | Todos endpoints sem auth |
| otp | `/api/otp` POST, `/api/otp/check` POST | POST/GET | Sem auth no OTP (deveria ser autenticado) |
| fees | `/api/v1/webhooks/asaas-payout` | POST | Webhook Asaas externo (deveria ser 🔒 público) |

### 🔐 Autenticados (requer JWT + role + status)
Endpoints que modificam dados ou leem informações sensíveis e não possuem auth:

| Serviço | Endpoint | Método | Risco |
|---------|----------|--------|-------|
| **address** | `POST /api/addresses` | POST | Qualquer um cria endereço |
| **address** | `PATCH /api/addresses/{id}` | PATCH | Qualquer um altera endereço alheio |
| **address** | `DELETE /api/addresses/{id}` | DELETE | Qualquer um deleta endereço alheio |
| **profiles** | `POST /api/profiles` | POST | Qualquer um cria perfil (CPF, nome) |
| **profiles** | `PATCH /api/profiles/{id}` | PATCH | Qualquer um altera perfil alheio |
| **profiles** | `DELETE /api/profiles/{id}` | DELETE | Qualquer um deleta perfil alheio |
| **profiles** | `GET /api/profiles` | GET | Lista todos os perfis sem auth |
| **notify** | `POST /api/v1/messages` | POST | Qualquer um envia mensagem |
| **notify** | `DELETE /api/v1/templates/{slug}` | DELETE | Qualquer um deleta template |
| **notify** | `PATCH /api/v1/contacts/{id}` | PATCH | Qualquer um altera contato |
| **notify** | `DELETE /api/v1/contacts/{id}` | DELETE | Qualquer um deleta contato |
| **roles** | `POST /api/v1/roles/{eid}/{role}` | POST | **Qualquer um adiciona role a usuário** |
| **roles** | `POST /api/v1/roles/{eid}/up/{to_role}` | POST | **Qualquer um promove usuário** |
| **roles** | `DELETE /api/v1/roles/{eid}` | DELETE | **Qualquer um remove roles** |
| **roles** | `POST /api/v1/role-rules` | POST | **Qualquer um cria regra de role** |
| **roles** | `DELETE /api/v1/role-rules/{id}` | DELETE | **Qualquer um deleta regra de role** |
| **roles** | `GET /api/v1/users` | GET | Lista todos usuários |
| **roles** | `DELETE /api/v1/users/{eid}` | DELETE | **Qualquer um deleta usuário** |
| **asaas** | `POST /api/v1/pix-keys` | POST | Qualquer um cria chave PIX |
| **asaas** | `POST /api/v1/charges` | POST | **Qualquer um cria cobrança** |
| **asaas** | `DELETE /api/v1/pix-keys/{eid}` | DELETE | Qualquer um deleta chave PIX |
| **asaas** | `DELETE /api/v1/charges/{id}` | DELETE | **Qualquer um deleta cobrança** |
| **asaas** | `POST /api/v1/payments` | POST | **Qualquer um cria pagamento** |
| **documents** | `GET/PUT/DELETE /{external_id}` | ALL | **Documentos pessoais sem auth** |
| **documents** | `POST /{external_id}/imagens/{slot}` | POST | **Upload de imagem sem auth** |
| **infinitepay** | `POST /api/checkout` | POST | **Checkout sem auth** |
| **infinitepay** | `GET /api/checkout` | GET | Lista checkouts sem auth |
| **otp** | `POST /api/otp` | POST | Solicitar OTP sem auth |

### 🌐 Públicos (webhooks externos com segurança)
| Serviço | Endpoint | Método | Proteção | Status |
|---------|----------|--------|----------|--------|
| asaas | `/security-validator` | POST | IP allowlist + HMAC + token header | ✅ OK |
| asaas | `/webhook/asaas` | POST | IP allowlist + HMAC | ✅ OK |
| infinitepay | `/api/webhook` | POST | IP allowlist + HMAC | ✅ OK |
| fees | `/api/v1/webhooks/asaas-payout` | POST | Apenas `Depends(get_session)` | ❌ SEM PROTEÇÃO |
| enrollment | `/api/v1/webhook/new/{id}` | POST | Apenas `Depends(get_session)` | ❌ SEM PROTEÇÃO |

---

## Detalhamento por Serviço

### 🔴 CRÍTICOS — Risco Imediato

#### 1. **roles** (gerenciamento de permissões)
- **Sem auth de usuário.** Nenhum endpoint verifica JWT ou role.
- Qualquer agente interno pode **promover usuários**, **adicionar/remover roles**, **criar regras de role**, **deletar usuários**.
- `POST /api/v1/roles/{external_id}/{role}` — adiciona role a qualquer usuário
- `POST /api/v1/roles/{external_id}/up/{to_role}` — promove usuário
- `DELETE /api/v1/roles/{external_id}` — remove roles
- `DELETE /api/v1/users/{external_id}` — deleta usuário

**Recomendação:** Adicionar `Depends(get_current_external_id)` + verificação de role `admin` como requisito mínimo.

#### 2. **asaas** (pagamentos)
- **Toda a API de pagamentos e cobranças sem auth de usuário.**
- `POST /api/v1/payments` — cria pagamento real
- `POST /api/v1/charges` — cria cobrança
- `POST /api/v1/pix-keys` — cria chave PIX
- `DELETE /api/v1/pix-keys/{external_id}` — deleta chave PIX
- `DELETE /api/v1/charges/{id}` — deleta cobrança
- Webhooks com IP+HMAC ✅

**Recomendação:** Todas as rotas de criação/alteração/deleção devem exigir JWT + role + algum vínculo com o usuário logado (coordinator, lead, etc).

#### 3. **notify** (envio de mensagens)
- **Toda a API de notificações sem auth de usuário.**
- `POST /api/v1/messages` — envia mensagem para qualquer destinatário
- `POST /api/v1/templates` — cria template de notificação
- `DELETE /api/v1/templates/{slug}` — deleta template
- `PATCH /api/v1/contacts/{id}` — altera contato
- `DELETE /api/v1/contacts/{id}` — deleta contato

**Recomendação:** Adicionar `Depends(get_current_external_id)` + verificar role `admin` ou `staff`.

#### 4. **infinitepay** (checkout)
- `POST /api/checkout` — checkout sem auth (qualquer um pode iniciar checkout)
- `GET /api/checkout` — lista checkouts sem auth
- Webhooks com IP+HMAC ✅

**Recomendação:** Adicionar `get_current_external_id` nas rotas de checkout.

### 🟡 MÉDIO — Risco Moderado

#### 5. **address** (endereços)
- CRUD completo de endereços sem auth: criar, listar, alterar, deletar
- Dados de endereço são dados pessoais (PII) — §4 (CONVENTION) exige cuidado
- **Recomendação:** Adicionar `Depends(get_current_external_id)` e verificar se o `external_id` da rota corresponde ao usuário logado.

#### 6. **profiles** (perfis)
- CRUD de perfis com CPF, nome, foto sem auth
- `GET /api/profiles` lista todos os perfis da plataforma
- **Recomendação:** Adicionar auth + autorização: usuário só vê/altera seu próprio perfil.

#### 7. **documents** (documentos pessoais)
- Upload/download/alteração/deleção de documentos (potencialmente fotos de RG, CPF) sem auth
- **Recomendação:** Adicionar `Depends(get_current_external_id)`.

### 🟢 BAIXO — Serviços Novos ou Internos

#### 8. **training** (materiais didáticos)
- CRUD completo sem auth
- Está em pasta `api/demilitarized/` mas tem criação/alteração/deleção — deveria ser autenticado

#### 9. **ai** (IA)
- Todos os endpoints sem auth — aceitável se estiver atrás de desmilitarizado/firewall

#### 10. **otp** (OTP)
- `GET /otp` lista OTPs sem auth — vaza hashes/status
- `GET /otp/logs` logs de OTP sem auth

#### 11. **enrollment** (matrícula)
- Webhook de entrada sem verificação de origem

#### 12. **jwt** (JWT service)
- Sem endpoints de API relevantes (só health) — baixo risco

#### 13. **commissions** — sem endpoints de API (só health) ✅
#### 14. **coordinator** — sem endpoints de API (só health) ✅

---

## Resumo Quantitativo

| Categoria | Qtd Serviços | Qtd Endpoints | Severidade |
|-----------|:---:|:---:|:---:|
| Sem auth algum (Depends(get_session) apenas) | 10 | ~90+ | 🔴 Alta |
| Com auth JWT parcial (só algumas rotas) | 2 (promoter, lead) | varia | 🟡 Média |
| Com auth JWT completo | 5 (candidate, fees, hub, staff, student) | completo | ✅ OK |
| Sem endpoints de API (só health) | 2 (commissions, coordinator) | 0 | ✅ OK |
| Webhooks externos sem proteção | 2 (fees/asas-payout, enrollment) | 2 | 🔴 Alta |

---

## Ações Imediatas Recomendadas

1. **P0 - roles**: Adicionar auth JWT + role check nas rotas de gerenciamento de permissões (MAIS CRÍTICO — sem isso, qualquer agente pode se autopromover)
2. **P0 - asaas**: Adicionar auth nas rotas de pagamento/cobrança/PIX
3. **P0 - notify**: Adicionar auth nas rotas de mensagens/templates/contatos
4. **P1 - infinitepay**: Adicionar auth nas rotas de checkout
5. **P1 - profiles**: Adicionar auth no CRUD de perfis
6. **P1 - documents**: Adicionar auth nas rotas de documentos
7. **P1 - address**: Adicionar auth nas rotas de endereços
8. **P2 - training**: Adicionar auth ou mover rotas mutáveis para autenticado
9. **P2 - otp**: Adicionar auth nas rotas GET de OTP/logs
10. **P2 - enrollment**: Adicionar verificação de origem no webhook
11. **P2 - fees**: Adicionar IP allowlist ou HMAC no webhook asaas-payout
