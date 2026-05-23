# Infinitepay

- **VMID:** 120
- **Container:** infinitepay
- **IP:** 10.10.10.120

## Descrição

Serviço de pagamentos. O código está distribuído em duas localizações:
- `/root/infinitepay` — estrutura principal do app (FastAPI)
- `/opt/infinitepay` — deployment/configuração adicional (Dockerfile, deploy scripts)

## Stack

- **Linguagem:** Python
- **Framework:** FastAPI (pyproject.toml, Makefile)
- **Infra:** Docker

## Estrutura no Backup

```
backup/infinitepay/
├── root-code/infinitepay/   # app principal de /root
│   ├── app/
│   ├── tests/
│   ├── skills/
│   ├── deploy/
│   ├── pyproject.toml
│   ├── Makefile
│   └── Dockerfile
└── opt-code/infinitepay/    # deployment de /opt
    ├── app/
    ├── tests/
    ├── pyproject.toml
    ├── Makefile
    └── Dockerfile
```
