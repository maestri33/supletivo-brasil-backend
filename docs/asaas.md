# Asaas

- **VMID:** 121
- **Container:** asaas
- **IP:** 10.10.10.121

## Descrição

Integração com gateway de pagamento Asaas. Contém 4 componentes:
- `asaas-app` — app principal de integração com Asaas (FastAPI)
- `internal-sink` — serviço auxiliar de logs/dados
- `asaas-backups` — backups de dados do Asaas
- `fastapi-mcp-demo` — demonstração/protótipo MCP com FastAPI

## Stack

- **Linguagem:** Python
- **Framework:** FastAPI (pyproject.toml, Makefile)

## Estrutura no Backup

```
backup/asaas/
├── asaas-app/         # app principal
│   ├── app/
│   │   ├── api/
│   │   ├── integrations/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── main.py
│   │   ├── config.py
│   │   └── db.py
│   ├── tests/
│   └── pyproject.toml
├── internal-sink/     # serviço auxiliar
│   └── logs/
├── asaas-backups/     # backups
└── fastapi-mcp-demo/  # protótipo MCP
```
