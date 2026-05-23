# Address

- **VMID:** 172
- **Container:** address
- **IP:** 10.10.10.172

## Descrição

Serviço de gestão de endereços. Cadastro, validação e busca de endereços (CEP, logradouros).

## Stack

- **Linguagem:** Python
- **Framework:** FastAPI (pyproject.toml)

## Estrutura no Backup

```
backup/address/address/
├── app/
│   ├── api/
│   ├── models/
│   ├── schemas/
│   ├── services/
│   ├── main.py
│   ├── config.py
│   └── db.py
├── uploads/
└── pyproject.toml
```
