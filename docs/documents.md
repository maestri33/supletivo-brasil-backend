# Documents

- **VMID:** 170
- **Container:** documents
- **IP:** 10.10.10.170

## Descrição

Serviço de gestão de documentos. Upload, armazenamento e geração de documentos. Inclui:
- `documents` — app principal (FastAPI)
- `media` — arquivos de mídia/documentos armazenados

## Stack

- **Linguagem:** Python
- **Framework:** FastAPI (pyproject.toml)

## Estrutura no Backup

```
backup/documents/
├── documents/
│   ├── app/
│   │   ├── api/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── main.py
│   │   ├── config.py
│   │   └── db.py
│   └── pyproject.toml
└── media/
    ├── documents/
    └── documentos/
```
