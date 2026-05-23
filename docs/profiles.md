# Profiles

- **VMID:** 173
- **Container:** profiles
- **IP:** 10.10.10.173

## Descrição

Serviço de gestão de perfis de usuário. Dados pessoais, preferências e configurações de conta.

## Stack

- **Linguagem:** Python
- **Framework:** FastAPI (pyproject.toml, Makefile)
- **DB Migrations:** scripts em `migrations/`

## Estrutura no Backup

```
backup/profiles/profiles/
├── app/
│   ├── api/
│   ├── models/
│   ├── schemas/
│   ├── services/
│   ├── main.py
│   ├── config.py
│   └── db.py
├── migrations/
├── tests/
├── data/
├── pyproject.toml
└── Makefile
```
