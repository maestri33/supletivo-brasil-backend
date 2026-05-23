# Backup de Código — Infraestrutura

**Data:** 2026-05-22
**Host:** dev (Proxmox VE)
**Container de backup:** VMID 1000, IP 10.10.10.100

## Resumo

Este diretório contém uma cópia do código-fonte de todos os microsserviços encontrados nos LXCs do ambiente, excluindo dependências (node_modules, venv, .npm, etc.).

Foram varridos **24 containers** (excluídos 1010/net e 200/m33-live).
- **17 apps com código** copiado e documentado
- **7 containers sem código** (provisionados mas sem deploy)

---

## Índice de Aplicações

### Serviços Core

| App | VMID | IP | Stack | Doc |
|-----|------|-----|-------|-----|
| Auth | 133 | 10.10.10.133 | Python/FastAPI | [auth.md](docs/auth.md) |
| JWT | 151 | 10.10.10.151 | Python/FastAPI | [jwt.md](docs/jwt.md) |
| OTP | 156 | 10.10.10.156 | Python/FastAPI | [otp.md](docs/otp.md) |
| Roles | 167 | 10.10.10.167 | Python/FastAPI | [roles.md](docs/roles.md) |
| Profiles | 173 | 10.10.10.173 | Python/FastAPI | [profiles.md](docs/profiles.md) |
| Address | 172 | 10.10.10.172 | Python/FastAPI | [address.md](docs/address.md) |

### Serviços de Negócio

| App | VMID | IP | Stack | Doc |
|-----|------|-----|-------|-----|
| Infinitepay | 120 | 10.10.10.120 | Python/FastAPI + Docker | [infinitepay.md](docs/infinitepay.md) |
| Asaas | 121 | 10.10.10.121 | Python/FastAPI | [asaas.md](docs/asaas.md) |
| Lead | 137 | 10.10.10.137 | Python/FastAPI | [lead.md](docs/lead.md) |
| Candidate | 138 | 10.10.10.138 | Python/FastAPI | [candidate.md](docs/candidate.md) |
| Enrollment | 139 | 10.10.10.139 | Python/FastAPI | [enrollment.md](docs/enrollment.md) |
| Documents | 170 | 10.10.10.170 | Python/FastAPI | [documents.md](docs/documents.md) |
| Notify | 157 | 10.10.10.157 | Python/FastAPI | [notify.md](docs/notify.md) |
| Mail | 150 | 10.10.10.150 | Python/Flask | [mail.md](docs/mail.md) |
| AI | 177 | 10.10.10.177 | Python/FastAPI | [ai.md](docs/ai.md) |

### Frontend / Especial

| App | VMID | IP | Stack | Doc |
|-----|------|-----|-------|-----|
| Staff Dashboard | 143 | 10.10.10.143 | React (Node.js) | [staff.md](docs/staff.md) |
| WhatsApp (Evolution API) | 149 | 10.10.10.149 | TypeScript + Go | [whats.md](docs/whats.md) |

### Containers sem Código

| App | VMID | IP | Doc |
|-----|------|-----|-----|
| Student | 140 | 10.10.10.140 | [student.md](docs/student.md) |
| Promoter | 141 | 10.10.10.141 | [promoter.md](docs/promoter.md) |
| Hub | 142 | 10.10.10.142 | [hub.md](docs/hub.md) |
| Coordinator | 147 | 10.10.10.147 | [coordinator.md](docs/coordinator.md) |
| Fees | 164 | 10.10.10.164 | [fees.md](docs/fees.md) |
| Commissions | 165 | 10.10.10.165 | [commissions.md](docs/commissions.md) |
| Training | 176 | 10.10.10.176 | [training.md](docs/training.md) |

---

## Estatísticas

- **Total de containers varridos:** 24
- **Apps com código:** 17 (71%)
- **Containers sem código:** 7 (29%)
- **Stack predominante:** Python + FastAPI (15 de 17 apps)
- **Outliers:** React/Node.js (1), TypeScript + Go (1), Flask (1)

## Observações

1. A maioria dos apps segue o mesmo padrão estrutural: FastAPI com `app/api`, `app/models`, `app/schemas`, `app/services`
2. Containers sem código (student, promoter, hub, coordinator, fees, commissions, training) podem ser:
   - Provisionados mas ainda não deployados
   - Consumers de filas/mensageria (sem código próprio)
   - Serviços que usam imagens Docker internas não persistidas no filesystem
3. O container `whats` (149) é o mais complexo, com ~66k arquivos entre Evolution API e binários Go
4. O container `infinitepay` (120) tem código duplicado em `/root` e `/opt` — possivelmente dev/prod ou migração em andamento
