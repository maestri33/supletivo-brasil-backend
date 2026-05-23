# OTP

- **VMID:** 156
- **Container:** otp
- **IP:** 10.10.10.156

## Descrição

Serviço de geração e validação de OTP (One-Time Password). Usado para verificação em duas etapas e recuperação de conta.

## Stack

- **Linguagem:** Python
- **Framework:** FastAPI (pyproject.toml, Makefile)
- **DB Migrations:** scripts de migração

## Estrutura no Backup

```
backup/otp/otp/
├── app/
│   ├── api/
│   ├── models/
│   ├── schemas/
│   ├── services/
│   ├── main.py
│   ├── config.py
│   └── db.py
├── migrations/
├── scripts/
├── tests/
├── data/
├── pyproject.toml
└── Makefile
```
