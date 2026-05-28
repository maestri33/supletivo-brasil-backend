# Scripts Úteis — Supletivo

Scripts de infraestrutura e DevOps para o backend Supletivo.

| Script | Descrição | Uso |
|--------|-----------|-----|
| `backup-pg.sh` | Backup do PostgreSQL (com dump SQL + dry-run) | `./scripts/backup-pg.sh` |
| `restore-pg.sh` | Restaura backup (--list, --latest, --yes) | `./scripts/restore-pg.sh --latest` |
| `init-dbs.sh` | Cria todos os 22 schemas + roda alembic migrations | `./scripts/init-dbs.sh` |

Todos os scripts aceitam `DATABASE_URL` como variável de ambiente para sobrescrever
a connection string padrão.
