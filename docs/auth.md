# Auth

- **VMID:** 133
- **Container:** auth
- **IP:** 10.10.10.133

## Descrição

Serviço de autenticação e autorização central. Gerencia login, tokens e permissões de usuários.

## Stack

- **Linguagem:** Python
- **Framework:** FastAPI (pyproject.toml, Makefile)
- **DB Migrations:** Alembic

## Estrutura no Backup

```
backup/auth/auth/
├── app/
│   ├── api/
│   ├── config/
│   ├── integrations/
│   ├── models/
│   ├── main.py
│   ├── config.py
│   └── db.py
├── alembic/
├── tests/
├── pyproject.toml
└── Makefile
```
