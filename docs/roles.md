# Roles

- **VMID:** 167
- **Container:** roles
- **IP:** 10.10.10.167

## Descrição

Serviço de gestão de perfis/papéis (RBAC). Controla permissões e níveis de acesso dos usuários no sistema.

## Stack

- **Linguagem:** Python
- **Framework:** FastAPI (pyproject.toml)

## Estrutura no Backup

```
backup/roles/roles/
├── app/
│   ├── api/
│   ├── models/
│   ├── schemas/
│   ├── services/
│   ├── main.py
│   ├── config.py
│   └── db.py
├── data/
└── pyproject.toml
```
