# Notify

- **VMID:** 157
- **Container:** notify
- **IP:** 10.10.10.157

## Descrição

Serviço de notificações multicanal:
- `notify` — app principal de disparo de notificações (email, push, etc.)

> O protótipo `ai-prep` (duplicata flat/desatualizada do serviço `ai`) foi removido — ver commit `f52302f` "chore(faxina): remove orfaos de codigo". O notify consome o serviço `ai` via HTTP (`app/integrations/ai.py` → `AIClient`).

## Stack

- **Linguagem:** Python
- **Framework:** FastAPI (pyproject.toml, Makefile)
- **DB Migrations:** scripts em `migrations/`

## Estrutura no Backup

```
backup/notify/
└── notify/
    ├── app/
    │   ├── api/
    │   ├── models/
    │   ├── schemas/
    │   ├── services/
    │   ├── integrations/
    │   ├── main.py
    │   ├── config.py
    │   └── db.py
    ├── migrations/
    ├── scripts/
    ├── tests/
    ├── docs/
    ├── media/
    ├── data/
    ├── pyproject.toml
    └── Makefile
```
