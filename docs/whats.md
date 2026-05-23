# Whats (WhatsApp)

- **VMID:** 149
- **Container:** whats
- **IP:** 10.10.10.149

## Descrição

Serviço de integração com WhatsApp. Contém dois componentes principais:

1. **Evolution API** — API de gestão de instâncias WhatsApp (TypeScript/Node.js)
   - Gerencia múltiplas instâncias do WhatsApp
   - Usa Prisma ORM para banco de dados
   - Estrutura Docker para deploy
   
2. **Go services** — Binários e ferramentas em Go
   - Ferramentas auxiliares compiladas

## Stack

- **Linguagem:** TypeScript (Evolution API) + Go
- **Framework:** Evolution API v2 (Node.js, Prisma, Docker)
- **DB:** Prisma ORM

## Estrutura no Backup

```
backup/whats/
├── evolution-api/
│   ├── src/
│   ├── prisma/
│   ├── manager/
│   ├── Docker/
│   ├── public/
│   └── .github/
└── go/
    └── bin/
```
