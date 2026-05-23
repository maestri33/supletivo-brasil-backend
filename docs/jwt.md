# JWT

- **VMID:** 151
- **Container:** jwt
- **IP:** 10.10.10.151

## Descrição

Serviço de geração e validação de tokens JWT (JSON Web Tokens). Provê autenticação stateless para os demais microsserviços.

## Stack

- **Linguagem:** Python
- **Framework:** FastAPI (pyproject.toml)

## Estrutura no Backup

```
backup/jwt/jwt/
├── app/
│   ├── api/
│   ├── services/
│   ├── schemas/
│   ├── main.py
│   ├── config.py
│   ├── stats.py
│   └── utils.py
└── pyproject.toml
```
