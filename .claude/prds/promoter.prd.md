# Promoter — Módulo de Divulgação

> Serviço: `promoter/` · Schema: `promoter` · Convenção: `CONVENTION.md`
> Status: **implementado** (modelo, endpoints, integracoes, testes presentes).
> Status desta SPEC: rewrite para padrao 10-section (COD-74).

---

## 1. Contexto de Negocio

O promoter eh o divulgador da plataforma — um ex-candidato que foi aprovado no treinamento e na entrevista com o coordenador do polo. Ele recebe um link unico (`<landing>/ref=<external_id>`) e capta leads para a plataforma. Cada lead captado via seu `ref` gera uma comissao para ele.

**Fluxo de vida:**
1. Candidato completa o treinamento (servico `training`)
2. Coordenador do polo aprova na entrevista (servico `coordinator`)
3. Coordinator chama `POST /api/v1/demilitarized/promoters` para criar o promoter
4. Promoter recebe acesso autenticado (role `promoter` no JWT) e divulga seu link
5. Lead usa o link (`ref=<external_id>`), que eh validado via `GET /api/v1/demilitarized/validate-ref/{ref}`
6. Comissoes sao geradas pelo servico `commissions` e visiveis ao promoter autenticado

**Estado atual:** Servico completo — modelo, endpoints (public/demilitarized/authenticated), integracoes (lead, commissions, notify, profiles, roles, auth, jwt), testes.

## 2. Atores

| Ator | Role | Acao |
|------|------|------|
| **Promoter** | `promoter` (JWT) | Acessa seus dados, leads captados e comissoes via endpoints autenticados |
| **Coordinator** | servico `coordinator` (desmilitarizado) | Cria o promoter apos aprovar candidato na entrevista |
| **Lead** | servico `lead` (desmilitarizado) | Valida o `ref` na captação para atribuir o lead ao promoter |
| **Sistema (notify)** | servico `notify` | Envia notificacoes de criacao e mudanca de status |

**Nota:** O promoter NAO eh dono de leads nem comissoes (CONVENTION §6). Ele so tem visao read-only via `httpx`.

## 3. Estados / Maquina de Estados

### Status (PromoterStatus — StrEnum)

```
ACTIVE → SUSPENDED → ACTIVE
```

| Status | Significado | Transicao para |
|--------|-------------|-----------------|
| `active` | Promoter ativo, pode captar leads e receber comissoes | `suspended` (por coordinator/staff) |
| `suspended` | Promoter suspenso, nao capta nem recebe | `active` (reativacao por coordinator/staff) |

**Regra:** Promotor suspenso retorna `valid=False` no endpoint de validacao de `ref`.

## 4. Entidades & Campos

### Promoter (tabela `promoters`)

| Campo | Tipo | Nullable | Index | Descricao |
|-------|------|----------|-------|-----------|
| `id` | UUID (PK) | Nao | PK | UUID interno do registro |
| `external_id` | UUID | Nao | unique + idx | UUID do usuario no auth — tambem eh o `ref` |
| `status` | String(20) | Nao | idx | Estado do promoter (active/suspended) |
| `hub_external_id` | UUID | Sim | idx | UUID do hub (polo) ao qual pertence |
| `created_at` | timestamptz | Nao | — | Timestamp de criacao (via mixin) |
| `updated_at` | timestamptz | Nao | — | Timestamp de atualizacao (via mixin) |

**Design:** Modelo minimo — dados do usuario (nome, CPF, endereco, PIX) vivem nos servicos donos (`profiles`, `address`, `asaas`). O promoter so guarda `external_id`, `status` e `hub`.

## 5. Endpoints

### Publicas (§5 — sem auth)

Nenhuma. Login/register pertencem ao servico `auth`.

### Desmilitarizadas (§5 — uso interno)

| Metodo | Rota | Descricao | Resp. |
|--------|------|-----------|-------|
| `POST` | `/api/v1/demilitarized/promoters` | Cria promoter (chamado pelo coordinator) | `PromoterOut` (201) |
| `GET` | `/api/v1/demilitarized/promoters` | Lista/filtra por hub, status | `PromoterListResponse` |
| `GET` | `/api/v1/demilitarized/promoters/{external_id}` | Busca por external_id | `PromoterOut` |
| `GET` | `/api/v1/demilitarized/validate-ref/{ref}` | Valida ref de captacao (consumido pelo lead) | `RefValidation` |

### Autenticadas (§5 — JWT com role `promoter`)

| Metodo | Rota | Descricao | Resp. |
|--------|------|-----------|-------|
| `GET` | `/api/v1/authenticated/me` | Dados do proprio promoter | `PromoterOut` |
| `GET` | `/api/v1/authenticated/me/leads` | Leads captados (via httpx ao servico lead) | `LeadListResponse` |
| `GET` | `/api/v1/authenticated/me/commissions` | Comissoes (via httpx ao servico commissions) | `CommissionListResponse` |

## 6. Integracoes Externas

Nenhuma integracao com servico externo. Todas as comunicacoes sao internas via `httpx`.

## 7. Eventos Disparados / Consumidos

### Disparados (via notify)

| Evento | Quando | Destinatario |
|--------|--------|-------------|
| `promoter.created` | Novo promoter criado | Promoter (via notify) |

### Consumidos

| Evento | De | Acao |
|--------|----|------|
| Nenhum consumido como webhook | — | Criacao eh feita via chamada HTTP do coordinator |

## 8. Regras de Negocio Invariantes

1. **external_id unico:** Nao pode haver dois promoters com o mesmo `external_id` (constraint unique).
2. **Ref validation:** Promotor suspenso retorna `valid=False` na validacao de ref.
3. **Visao read-only:** Endpoints autenticados apenas leem dados de `lead` e `commissions` via httpx — nunca escrevem (CONVENTION §6).
4. **Hub default:** Se `hub_external_id` nao informado na criacao, usa `settings.hub_default` (UUID do polo default).
5. **Idempotencia:** `POST /promoters` retorna o registro existente se `external_id` ja existe (não duplica).

## 9. Criterios de Aceite

- [ ] Coordinator cria promoter via POST desmilitarizado
- [ ] Lead valida ref e recebe valid=True + hub_external_id
- [ ] Promoter ativo lista seus leads via /me/leads
- [ ] Promoter ativo lista suas comissoes via /me/commissions
- [ ] Promotor suspenso retorna valid=False na validacao de ref
- [ ] Notificacao disparada na criacao do promoter
- [ ] Ruff limpo, pytest passa, alembic upgrade head OK

## 10. Riscos / Open Questions

### Riscos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|--------------|---------|-----------|
| Duplicar dominio de lead/commission (fere §6) | baixa | alto | read-only via httpx; sem tabela de lead/comissao |
| Integracao lead/commissions fora do ar | media | medio | §12 — tratar falha, degradar visao |
| ref invalido/abuso na validacao | media | medio | validar + logar (structlog); status do promoter |

### Open Questions

- [ ] Promotor pode ter multiplos hubs? (hoje: um so — hub_external_id)
- [ ] O que exatamente suspende um promoter? (coordinator decide? automatico por inatividade?)
- [ ] Ref URL: qual o formato exato da landing? (hoje: configuravel via `settings.landing_base_url`)

---

*Rewrite do padrao antigo (Problem/Evidence/Users/...) para o padrao 10-section (COD-74).*
