# Lead

- **VMID:** 137
- **Container:** lead
- **IP:** 10.10.10.137

## Descrição

Serviço de gestão de leads/captação. Inclui integrações com serviços externos e notificações.

## Stack

- **Linguagem:** Python
- **Framework:** FastAPI (app com routers, integrations, utils)

## Estrutura no Backup

```
backup/lead/app/
├── routers/
├── integrations/
├── tools/
├── notify/
├── graphify-out/
└── (scripts Python)
```
