# AI

- **VMID:** 177
- **Container:** ai
- **IP:** 10.10.10.177

## Descrição

Serviço de inteligência artificial. Provê funcionalidades de IA/ML para os demais serviços, incluindo integrações com APIs externas de IA.

## Stack

- **Linguagem:** Python
- **Framework:** FastAPI (pyproject.toml, Makefile)

## Estrutura no Backup

```
backup/ai/ai/
├── app/
│   ├── api/
│   ├── integrations/
│   ├── utils/
│   ├── main.py
│   └── config.py
├── data/
├── pyproject.toml
└── Makefile
```
