# RBAC Matrix — CONVENTION §5

> **Fonte de verdade:** este documento mapeia cada endpoint do backend às 3 categorias
> definidas na CONVENTION §5 e documenta os gates de role/status exigidos.
>
> Atualizado: 2026-05-28 (CEO — WS-SEC COD-18)

---

## 1. Categorias de Endpoint (CONVENTION §5)

| Categoria | Pasta | Auth | Rate-Limit | Exposição |
|---|---|---|---|---|
| **Desmilitarizado** | `api/demilitarized/` | Nenhuma | Não | Interna (rede Proxmox) |
| **Autenticado** | `api/authenticated/` | JWT (RS256) + role + status | Sim | Via gateway |
| **Público** | `api/public/` | Nenhuma | Sim (Redis) | Mundo |

---

## 2. Matriz Completa por Serviço

### 2.1 address
| Endpoint | Categoria | Auth | Role Gate | Status Gate | Notas |
|---|---|---|---|---|---|
| `GET /health` | health | — | — | — | Health check |

**Gap:** Sem endpoints expostos. Serviço interno-only via `demilitarized` de outros apps.
**Ação:** Nenhuma. Correto por design (§6).

---

### 2.2 ai
| Endpoint | Categoria | Auth | Role Gate | Status Gate | Notas |
|---|---|---|---|---|---|
| `GET /health` | health | — | — | — | Health check |

**Gap:** Sem endpoints expostos. Serviço interno-only.
**Ação:** Nenhuma. Correto por design (§7 — IA só via app `ai`).

---

### 2.3 asaas
| Endpoint | Categoria | Auth | Role Gate | Status Gate | Notas |
|---|---|---|---|---|---|
| `POST /webhook` | público | Nenhuma | — | — | Webhook externo do Asaas |
| `POST /payment` | desmilitarizado | — | — | — | Criação de pagamento |
| `GET/POST /config` | desmilitarizado | — | — | — | Config de pagamento |
| `GET/POST /charge` | desmilitarizado | — | — | — | Cobranças |
| `GET/POST /pixkey` | desmilitarizado | — | — | — | Chaves PIX |

**Gap:** Webhook público precisa de verificação de assinatura HMAC.
**Status:** ✅ COD-30/COD-31 concluído — HMAC verificação + alertas implementados.

---

### 2.4 auth
| Endpoint | Categoria | Auth | Role Gate | Status Gate | Notas |
|---|---|---|---|---|---|
| `GET /health` | health | — | — | — | Health check |

**Gap:** Endpoints de registro/login não visíveis no scan (podem estar em sub-rotas).
**Ação:** Verificar se endpoints públicos de auth estão com rate-limit (COD-46 ✅).

---

### 2.5 candidate
| Endpoint | Categoria | Auth | Role Gate | Status Gate | Notas |
|---|---|---|---|---|---|
| `POST /check` | público | Nenhuma | — | — | Verifica CPF/phone |
| `POST /login` | público | Nenhuma | — | — | Login OTP |
| `POST /refresh` | público | Nenhuma | — | — | Refresh token |
| `GET /selfie` | autenticado | JWT | candidate | — | Selfie do candidato |
| `GET /birth` | autenticado | JWT | candidate | — | Dados nascimento |
| `POST /birth` | autenticado | JWT | candidate | — | Salvar nascimento |
| `GET /pixkey` | autenticado | JWT | candidate | — | Chave PIX |
| `POST /pixkey` | autenticado | JWT | candidate | — | Salvar PIX |
| `GET /educational` | autenticado | JWT | candidate | — | Dados educacionais |
| `GET /captured` | autenticado | JWT | candidate | — | Dados capturados |
| `POST /captured` | autenticado | JWT | candidate | — | Salvar capturados |
| `GET /personal` | autenticado | JWT | candidate | — | Dados pessoais |
| `POST /personal` | autenticado | JWT | candidate | — | Salvar pessoais |
| `GET /address` | autenticado | JWT | candidate | — | Endereço |
| `POST /address` | autenticado | JWT | candidate | — | Salvar endereço |
| `GET /documents` | autenticado | JWT | candidate | — | Documentos |
| `PUT /documents` | autenticado | JWT | candidate | — | Atualizar docs |
| `POST /documents/submit` | autenticado | JWT | candidate | — | Submeter para review |
| `GET /candidates` | desmilitarizado | — | — | — | Lista interna |

**Gap:** ⚠️ Endpoints `/check` e `/login` públicos — mitigação de enumeração feita (COD-32 ✅).
**Gap:** ⚠️ Verificar se `authenticated` endpoints têm gate de **status** (ex.: candidate só avança se status anterior bate).

---

### 2.6 commissions
| Endpoint | Categoria | Auth | Role Gate | Status Gate | Notas |
|---|---|---|---|---|---|
| `GET /batches` | desmilitarizado | — | — | — | Lista batches |
| `GET /batches/{id}` | desmilitarizado | — | — | — | Batch específico |
| `POST /trigger-processing` | desmilitarizado | — | — | — | Trigger processamento |
| `GET /commissions` | desmilitarizado | — | — | — | Lista comissões |
| `GET /commissions/{id}` | desmilitarizado | — | — | — | Comissão específica |
| `POST /commissions` | desmilitarizado | — | — | — | Criar comissão |
| `GET /payment-batches` | desmilitarizado | — | — | — | Batches de pagamento |
| `GET /payment-batches/{id}` | desmilitarizado | — | — | — | Batch pagamento |
| `POST /processing/trigger` | desmilitarizado | — | — | — | Trigger processamento |

**Gap:** Todos desmilitarizados — correto para serviço interno.
**Nota:** `trigger-processing` e `processing/trigger` parecem duplicados.

---

### 2.7 coordinator
| Endpoint | Categoria | Auth | Role Gate | Status Gate | Notas |
|---|---|---|---|---|---|
| `GET /health` | health | — | — | — | Health check |

**Gap:** Sem endpoints implementados. Módulo sub-implementado.

---

### 2.8 documents
| Endpoint | Categoria | Auth | Role Gate | Status Gate | Notas |
|---|---|---|---|---|---|
| `GET /health` | health | — | — | — | Health check |

**Gap:** Sem endpoints expostos. Serviço interno-only.
**Ação:** Verificar se há endpoints demilitarizados faltando para outros apps consultarem documentos.

---

### 2.9 enrollment
| Endpoint | Categoria | Auth | Role Gate | Status Gate | Notas |
|---|---|---|---|---|---|
| `GET /documents` | autenticado | JWT | ? | ? | Docs do enrollment |
| `PUT /documents/rg` | autenticado | JWT | ? | ? | Atualizar RG |
| `GET /selfie` | autenticado | JWT | ? | ? | Selfie |
| `GET /profile` | autenticado | JWT | ? | ? | Perfil |
| `POST /profile` | autenticado | JWT | ? | ? | Salvar perfil |
| `GET /education` | autenticado | JWT | ? | ? | Educação |
| `POST /education` | autenticado | JWT | ? | ? | Salvar educação |
| `GET /address` | autenticado | JWT | ? | ? | Endereço |
| `POST /address` | autenticado | JWT | ? | ? | Salvar endereço |

**Gap:** ⚠️ Role gates e status gates não verificados — precisa auditar `dependencies.py`.
**Ação:** Verificar se enrollment exige role `candidate` ou `training` e status específico.

---

### 2.10 fees
| Endpoint | Categoria | Auth | Role Gate | Status Gate | Notas |
|---|---|---|---|---|---|
| `GET /` | autenticado | JWT | ? | ? | Lista fees |
| `GET /{fee_id}` | autenticado | JWT | ? | ? | Fee específica |
| `POST /asaas-payout` | desmilitarizado | — | — | — | Webhook payout Asaas |

**Gap:** ⚠️ Verificar role gate em endpoints autenticados.

---

### 2.11 hub
| Endpoint | Categoria | Auth | Role Gate | Status Gate | Notas |
|---|---|---|---|---|---|
| `GET /health` | health | — | — | — | Health check |

**Gap:** Sem endpoints implementados. Módulo sub-implementado.

---

### 2.12 infinitepay
| Endpoint | Categoria | Auth | Role Gate | Status Gate | Notas |
|---|---|---|---|---|---|
| `GET /` (webhook) | público | Nenhuma | — | — | Webhook InfinitePay |
| `GET /` (checkout) | desmilitarizado | — | — | — | Checkout interno |

**Gap:** ✅ `/health/integration` removido/secured (COD-91).
**Gap:** ⚠️ Webhook público precisa verificação de assinatura (COD-30 ✅).

---

### 2.13 jwt
| Endpoint | Categoria | Auth | Role Gate | Status Gate | Notas |
|---|---|---|---|---|---|
| `GET /health` | health | — | — | — | Health check |

**Gap:** JWKS endpoint não visível — pode estar em rota raiz.
**Ação:** Verificar se JWKS está acessível internamente.

---

### 2.14 lead
| Endpoint | Categoria | Auth | Role Gate | Status Gate | Notas |
|---|---|---|---|---|---|
| `POST /check` | público | Nenhuma | — | — | Verifica CPF/phone |
| `POST /login` | público | Nenhuma | — | — | Login OTP |
| `POST /refresh` | público | Nenhuma | — | — | Refresh token |
| `GET /waiting` | autenticado | JWT | lead? | waiting? | Leads em espera |
| `GET /completed` | autenticado | JWT | lead? | completed? | Leads completos |
| `GET /checkout` | autenticado | JWT | lead? | — | Checkout |
| `GET /captured` | autenticado | JWT | lead? | — | Dados capturados |
| `GET /checkouts` | desmilitarizado | — | — | — | Lista checkouts |
| `POST /notify/{id}` | desmilitarizado | — | — | — | Webhook notify |
| `POST /infinitepay` | desmilitarizado | — | — | — | Webhook InfinitePay |
| `POST /asaas-charge` | desmilitarizado | — | — | — | Webhook Asaas charge |
| `GET /leads` | desmilitarizado | — | — | — | Lista leads |
| `GET /leads/{id}` | desmilitarizado | — | — | — | Lead específico |

**Gap:** ⚠️ Endpoints `/check` e `/login` públicos — mitigação de enumeração (COD-32 ✅).
**Gap:** ⚠️ Verificar role/status gates em endpoints autenticados.

---

### 2.15 notify
| Endpoint | Categoria | Auth | Role Gate | Status Gate | Notas |
|---|---|---|---|---|---|
| `GET /check` | desmilitarizado | — | — | — | Verifica contato |
| `POST /` | desmilitarizado | — | — | — | Criar notificação |
| `GET /` | desmilitarizado | — | — | — | Lista notificações |
| `GET /{id}` | desmilitarizado | — | — | — | Notificação específica |
| `GET /logs` | desmilitarizado | — | — | — | Logs de envio |
| `GET /metrics` | desmilitarizado | — | — | — | Métricas |
| `GET /templates` | desmilitarizado | — | — | — | Lista templates |
| `GET /templates/{slug}` | desmilitarizado | — | — | — | Template específica |
| `PUT /templates/{slug}` | desmilitarizado | — | — | — | Atualizar template |
| `GET /email/health` | desmilitarizado | — | — | — | Health email |
| `GET /email/status` | desmilitarizado | — | — | — | Status email |
| `GET /email/domains` | desmilitarizado | — | — | — | Domínios |
| `GET /email/domains/{d}` | desmilitarizado | — | — | — | Domínio específico |
| `GET /email/mailboxes/{d}` | desmilitarizado | — | — | — | Mailboxes |
| `GET /email/mailbox/{addr}` | desmilitarizado | — | — | — | Mailbox específica |
| `GET /email/aliases` | desmilitarizado | — | — | — | Aliases |
| `GET /email/dkim/{d}` | desmilitarizado | — | — | — | DKIM |
| `GET /email/queue` | desmilitarizado | — | — | — | Fila de email |
| `POST /email/queue/flush` | desmilitarizado | — | — | — | Flush fila |
| `GET /instructions` | desmilitarizado | — | — | — | Instruções |
| `GET /messages` | desmilitarizado | — | — | — | Mensagens |
| `GET /messages/{id}` | desmilitarizado | — | — | — | Mensagem específica |

**Gap:** Todos desmilitarizados — correto para serviço interno.
**Nota:** Endpoints de email expõem muita informação — verificar se deveriam ser demilitarizados ou autenticados com role admin.

---

### 2.16 otp
| Endpoint | Categoria | Auth | Role Gate | Status Gate | Notas |
|---|---|---|---|---|---|
| `GET /health` | health | — | — | — | Health check |

**Gap:** Endpoints de geração/validação OTP não visíveis — podem estar em rotas internas.
**Ação:** Verificar se OTP endpoints estão com rate-limit (prevenção brute-force).

---

### 2.17 profiles
| Endpoint | Categoria | Auth | Role Gate | Status Gate | Notas |
|---|---|---|---|---|---|
| `GET /health` | health | — | — | — | Health check |

**Gap:** Sem endpoints expostos. Serviço interno-only.
**Ação:** Verificar se há endpoints demilitarizados para outros apps consultarem perfis.

---

### 2.18 promoter
| Endpoint | Categoria | Auth | Role Gate | Status Gate | Notas |
|---|---|---|---|---|---|
| `POST /check` | público | Nenhuma | — | — | Verifica CPF/phone |
| `POST /login` | público | Nenhuma | — | — | Login OTP |
| `POST /refresh` | público | Nenhuma | — | — | Refresh token |
| `GET /me` | autenticado | JWT | promoter | — | Dados do promoter |
| `GET /me/leads` | autenticado | JWT | promoter | — | Leads do promoter |
| `GET /promoters` | desmilitarizado | — | — | — | Lista promoters |

**Gap:** ⚠️ Endpoints `/check` e `/login` públicos — mitigação de enumeração (COD-32 ✅).
**Gap:** ⚠️ Verificar se `GET /me` exige role `promoter` explicitamente.

---

### 2.19 roles
| Endpoint | Categoria | Auth | Role Gate | Status Gate | Notas |
|---|---|---|---|---|---|
| `GET /health` | health | — | — | — | Health check |

**Gap:** Endpoints de gestão de roles não visíveis — podem estar em rotas internas.
**Ação:** Verificar se endpoints de transição de role estão protegidos (só admin/coordinator).

---

### 2.20 staff
| Endpoint | Categoria | Auth | Role Gate | Status Gate | Notas |
|---|---|---|---|---|---|
| `GET /me` | autenticado | JWT | staff? | — | Dados do staff |
| `GET /hubs` | autenticado | JWT | staff? | — | Hubs do staff |
| `GET /health` | autenticado | JWT | staff? | — | Health interno |

**Gap:** ⚠️ Verificar se role `staff` é exigido explicitamente.

---

### 2.21 student
| Endpoint | Categoria | Auth | Role Gate | Status Gate | Notas |
|---|---|---|---|---|---|
| `GET /me/documents` | autenticado | JWT | student | — | Documentos |
| `POST /me/documents/submit` | autenticado | JWT | student | — | Submeter docs |
| `POST /` | autenticado | JWT | ? | — | Criar student |
| `GET /me` | autenticado | JWT | student | — | Dados do student |
| `GET /me/pending-items` | autenticado | JWT | student | — | Itens pendentes |
| `GET /me/exams` | autenticado | JWT | student | — | Provas |
| `PATCH /{id}/exams/{id}` | autenticado | JWT | ? | — | Atualizar prova |
| `POST /me/diploma/pickup` | autenticado | JWT | student | — | Retirar diploma |

**Gap:** ⚠️ `PATCH /{id}/exams/{id}` — verificar se exige role coordinator/admin (não student).

---

### 2.22 training
| Endpoint | Categoria | Auth | Role Gate | Status Gate | Notas |
|---|---|---|---|---|---|
| `GET /coordinator` | autenticado | JWT | coordinator? | — | Painel coordinator |
| `GET /submissions` | autenticado | JWT | ? | — | Submissões |
| `GET /materials` | autenticado | JWT | training? | — | Materiais |
| `GET /materials/{id}` | desmilitarizado | — | — | — | Material específico |
| `PUT /materials/{id}` | desmilitarizado | — | — | — | Atualizar material |
| `GET /materials/{id}/video` | desmilitarizado | — | — | — | Vídeo |
| `GET /materials/{id}/photo` | desmilitarizado | — | — | — | Foto |

**Gap:** ⚠️ `PUT /materials/{id}` desmilitarizado — qualquer serviço interno pode alterar materiais. Considerar mover para autenticado com role coordinator.

---

## 3. Resumo de Gaps

### 3.1 Gaps Críticos (bloqueiam produção)
| # | Serviço | Gap | Status |
|---|---|---|---|
| 1 | asaas | Webhook sem HMAC | ✅ COD-30/COD-31 |
| 2 | infinitepay | `/health/integration` sem auth | ✅ COD-91 |
| 3 | candidate/lead/promoter | Enumeração via `/check` | ✅ COD-32 |

### 3.2 Gaps de Role Gate (verificar)
| # | Serviço | Endpoint | Role esperado | Verificado? |
|---|---|---|---|---|
| 1 | enrollment | Todos autenticados | candidate/training | ❌ |
| 2 | fees | GET autenticados | promoter/coordinator | ❌ |
| 3 | staff | Todos autenticados | staff | ❌ |
| 4 | student | PATCH exams | coordinator | ❌ |
| 5 | training | coordinator/submissions | coordinator | ❌ |
| 6 | promoter | GET /me | promoter | ❌ |

### 3.3 Gaps de Status Gate (verificar)
| # | Serviço | Endpoint | Status esperado | Verificado? |
|---|---|---|---|---|
| 1 | candidate | documents/submit | captured? | ❌ |
| 2 | enrollment | documents/rg | ? | ❌ |
| 3 | student | documents/submit | ? | ❌ |

### 3.4 Gaps de Rate-Limit (públicos)
| # | Serviço | Endpoint | Rate-limit? |
|---|---|---|---|
| 1 | candidate | /check, /login, /refresh | ✅ COD-46 |
| 2 | lead | /check, /login, /refresh | ✅ COD-46 |
| 3 | promoter | /check, /login, /refresh | ✅ COD-46 |
| 4 | asaas | /webhook | ✅ COD-46 |
| 5 | infinitepay | /webhook | ✅ COD-46 |

### 3.5 Gaps de Design (melhorias)
| # | Serviço | Issue | Sugestão |
|---|---|---|---|
| 1 | training | PUT materials desmilitarizado | Mover para autenticado + role coordinator |
| 2 | notify | Email endpoints expõem muito | Considerar role admin para endpoints sensíveis |
| 3 | commissions | Endpoints duplicados | Consolidar trigger-processing |

---

## 4. Ações Pendentes

- [ ] Auditar `dependencies.py` de enrollment, fees, staff, student, training, promoter para confirmar role gates
- [ ] Auditar status gates em endpoints de funnel (candidate, enrollment, student)
- [ ] Verificar OTP endpoints têm rate-limit anti-brute-force
- [ ] Verificar JWT/JWKS endpoints estão acessíveis internamente
- [ ] Mover `training PUT /materials` para autenticado
- [ ] Consolidar endpoints duplicados em commissions

---

## 5. Referências

- CONVENTION §5: APIs — Três tipos de endpoint
- CONVENTION §8: Sistema de Roles
- COD-45: Auditoria de endpoints sem auth
- COD-46: Verificação de rate-limit
- COD-32: Mitigação de enumeração
- COD-30/COD-31: Webhook signature verification
- COD-91: /health/integration secured
