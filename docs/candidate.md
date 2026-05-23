# Candidate

- **VMID:** 138
- **Container:** candidate
- **IP:** 10.10.10.138

## Descrição

Serviço de gestão de candidatos. Integra com serviços de notificação.

## Stack

- **Linguagem:** Python
- **Framework:** FastAPI (requirements.txt)
- **Estrutura:** routers, integrations, notify

## Estrutura no Backup

```
backup/candidate/candidate/
├── app/
│   ├── routers/
│   ├── integrations/
│   ├── notify/
│   ├── main.py
│   ├── config.py
│   ├── models.py
│   └── schemas.py
└── requirements.txt
```
