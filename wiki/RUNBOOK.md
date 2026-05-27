# RUNBOOK — Backend Supletivo

> **Status:** Sprint 2 — preenchido com dados reais do `docker-compose.dev.yml`.
> Atualizado em: 2026-05-27.
>
> **Referências:** `CONVENTION.md` · `wiki/PLANO_ADEQUACAO.md` · `wiki/<app>.md` · `docker-compose.dev.yml`

---

## 1. Inventário de Serviços

| Serviço | Porta interna | Porta host | Schema | Status | CLAUDE.md | wiki.md |
|---|---|---|---|---|---|---|
| address | 8000 | 8001 | addresses | ativo | ✅ | ✅ |
| ai | 8000 | 8002 | ai | ativo | ✅ | ✅ |
| asaas | 8000 | 8003 | asaas | ativo (F5 concluída) | ✅ | ✅ |
| auth | 8000 | 8004 | auth | ativo | ✅ | ✅ |
| candidate | 8000 | 8005 | candidate | ativo | ✅ | ✅ |
| commissions | — | — | commissions | **não criado** (Parte B) | ✅ | ✅ |
| coordinator | — | — | coordinator | **não criado** (Parte B) | ✅ | ✅ |
| documents | 8000 | 8008 | documents | ativo (⚠️ sqlite) | ✅ | ✅ |
| enrollment | 8000 | 8009 | enrollment | ativo | ✅ | ✅ |
| fees | 8000 | 8010 | fees | ativo | ✅ | ✅ |
| hub | 8000 | 8011 | hub | ativo | ✅ | ✅ |
| infinitepay | 8000 | 8012 | infinitepay | ativo (F5 concluída) | ✅ | ✅ |
| jwt | — | 8013 | jwt | ativo (lib, sem porta exposta) | ✅ | ✅ |
| lead | 8000 | 8014 | lead | ativo (modelo de referência) | ✅ | ✅ |
| notify | 8000 | 8015 | notify | ativo | ✅ | ✅ |
| otp | 8000 | 8016 | otp | ativo | ✅ | ✅ |
| profiles | 8000 | 8017 | profiles | ativo | ✅ | ✅ |
| promoter | 8000 | 8018 | promoter | ativo | ✅ | ✅ |
| roles | 8000 | 8019 | roles | ativo | ✅ | ✅ |
| staff | — | 8020 | staff | spine (Milestone 1) | ✅ | ✅ |
| student | 8000 | 8021 | student | ativo (Milestone 1) | ✅ | ✅ |
| training | 8000 | 8022 | training | ativo | ✅ | ✅ |

**CLAUDE.md:** 22/22 ✅ | **wiki.md:** 22/22 ✅

**Infraestrutura compartilhada:**
- **Postgres 16** (Alpine) — DB `supletivo`, user `supletivo`, host `postgres:5432`
- **Redis 7** (Alpine) — host `redis:6379`
- **docker-compose:** `docker-compose.dev.yml` (20 serviços + postgres + redis)
- ⚠️ **documents** usa SQLite (`sqlite:///documents.db`), não Postgres
- ⚠️ **jwt** e **staff** são serviços de biblioteca/suporte, sem porta HTTP dedicada (jwt expõe porta internamente para servir JWKS)

---

## 2. Subir / Derrubar

### 2.1 Pré-requisitos

- VM no Proxmox com Docker e `docker compose` (v2)
- `.env` configurado por serviço (ver `.env.example` de cada um)
- Postgres e Redis acessíveis via rede Docker (`postgres:5432`, `redis:6379`)

### 2.2 Subir tudo (dev)

```bash
# Na raiz do projeto
docker compose -f docker-compose.dev.yml up -d

# Verificar status (todos os 22 containers: 20 serviços + postgres + redis)
docker compose -f docker-compose.dev.yml ps

# Verificar logs de um serviço específico
docker compose -f docker-compose.dev.yml logs -f <servico>
```

### 2.3 Subir um serviço individual (Docker)

```bash
docker compose -f docker-compose.dev.yml up -d <servico>

# Exemplo: subir só o lead
docker compose -f docker-compose.dev.yml up -d lead
```

### 2.4 Subir um serviço individual (local/dev)

```bash
cd <servico>/
make install    # uv sync
make dev        # uvicorn --reload (desenvolvimento)
# ou
make run        # uvicorn (produção)
```

### 2.5 Derrubar tudo

```bash
docker compose -f docker-compose.dev.yml down

# Derrubar TUDO incluindo volumes (⚠️ perde dados do Postgres!)
docker compose -f docker-compose.dev.yml down -v
```

### 2.6 Derrubar/Reiniciar um serviço

```bash
# Parar
docker compose -f docker-compose.dev.yml stop <servico>

# Remover container (mantém volume)
docker compose -f docker-compose.dev.yml rm -f <servico>

# Reiniciar
docker compose -f docker-compose.dev.yml restart <servico>
```

### 2.7 Health check

Cada serviço expõe `/healthz` na porta interna 8000. Pelo host, use a porta mapeada:

```bash
# Pelo host (porta mapeada)
curl -fsS http://localhost:8001/healthz    # address
curl -fsS http://localhost:8002/healthz    # ai
curl -fsS http://localhost:8003/healthz    # asaas
curl -fsS http://localhost:8004/healthz    # auth
curl -fsS http://localhost:8014/healthz    # lead
# ... (ver tabela §1 para portas)

# Batch — verificar todos de uma vez
for port in $(seq 8001 8005) $(seq 8008 8022); do
  status=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$port/healthz 2>/dev/null)
  echo "port $port: $status"
done

# Infraestrutura
docker compose -f docker-compose.dev.yml exec postgres pg_isready -U supletivo -d supletivo
docker compose -f docker-compose.dev.yml exec redis redis-cli ping
```

---

## 3. Backup / Restore

### 3.1 Banco de dados (Postgres)

**Backup automatizado:** cron job `Supletivo DB Backup` roda `scripts/backup-pg.sh` diariamente às 03:00 UTC.
Retenção: 7 dias. Backups salvos em `backups/backup-YYYY-MM-DDTHH-MM-SSZ.sql.gz`.

```bash
# Backup manual (via script do projeto)
DATABASE_URL="postgresql://supletivo:***@localhost:5432/supletivo" \
  ./scripts/backup-pg.sh

# Backup de schema específico
./scripts/backup-pg.sh -s addresses,auth

# Restore (dry-run primeiro!)
./scripts/restore-pg.sh --latest          # dry run
./scripts/restore-pg.sh --yes --latest    # executar

# Credenciais reais (docker-compose.dev.yml)
#   DB: supletivo  |  User: supletivo  |  Host: postgres:5432

# Backup completo (todos os schemas) — direto no container
docker compose -f docker-compose.dev.yml exec postgres \
  pg_dump -U supletivo -d supletivo -F c -f /tmp/backup_$(date +%Y%m%d_%H%M%S).dump

# Copiar backup para o host
docker compose -f docker-compose.dev.yml cp \
  postgres:/tmp/backup_20260527_120000.dump ./backups/

# Backup de schema específico
docker compose -f docker-compose.dev.yml exec postgres \
  pg_dump -U supletivo -d supletivo -n addresses -F c -f /tmp/address_backup.dump

# Restore completo (⚠️ destrutivo — drop + recreate)
docker compose -f docker-compose.dev.yml cp ./backups/backup.dump postgres:/tmp/
docker compose -f docker-compose.dev.yml exec postgres \
  pg_restore -U supletivo -d supletivo -c --if-exists /tmp/backup.dump
```

### 3.2 Redis

```bash
# Snapshot manual (dentro do container)
docker compose -f docker-compose.dev.yml exec redis redis-cli BGSAVE

# Copiar dump para o host
docker compose -f docker-compose.dev.yml cp \
  redis:/data/dump.rdb ./backups/redis_$(date +%Y%m%d_%H%M%S).rdb
```

### 3.3 Migrações Alembic

Cada serviço gerencia suas migrações independentemente:

```bash
cd <servico>/
uv run alembic upgrade head       # aplicar pendentes
uv run alembic downgrade -1       # reverter última
uv run alembic history            # ver histórico
uv run alembic current            # versão atual
```

### 3.4 Segredos e configuração

- `.env` de cada serviço NÃO é versionado (está no `.gitignore`)
- `.env.example` serve como template
- Config operacional do `asaas` vive na tabela `asaas.config` (override via API)

---

## 4. Rotação de Segredos

### 4.1 Chaves JWT (`jwt`)

```bash
cd jwt/
# As chaves são regeneradas automaticamente por _ensure_keys() se faltarem
# Para forçar rotação manual:
rm -f private.pem public.pem
# Reiniciar o serviço — novas chaves serão geradas
docker compose restart jwt
```

**Impacto:** tokens antigos ficam inválidos; todos os usuários precisam fazer login novamente.

### 4.2 Fernet key (`infinitepay`)

```bash
# Gerar nova chave
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Atualizar no .env do infinitepay
# Reiniciar
docker compose restart infinitepay
```

**Impacto:** dados cifrados com a chave antiga não podem ser decifrados. Migrar dados antes de rotacionar.

### 4.3 Asaas API key (`asaas`)

- Sandbox vs produção controlado por `ASAAS_ALLOW_SANDBOX`
- Chave fica no `.env` e é seedada para a tabela `asaas.config` no primeiro boot
- Override via API: `POST /api/v1/config/security-key`

### 4.4 Database URL

```bash
# Atualizar em cada .env de serviço
# Reiniciar
docker compose restart <servico>
```

---

## 5. Escalar Serviço

### 5.1 Horizontal (múltiplos workers)

```bash
# Via docker-compose: ajustar replicas
docker compose up -d --scale <servico>=3

# Via Makefile (produção):
cd <servico>/
uv run uvicorn app.main:app --host 0.0.0.0 --port 80 --workers 4
```

### 5.2 Vertical (recursos do container)

No `docker-compose.yml`:

```yaml
services:
  <servico>:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 256M
```

### 5.3 Escalar Postgres

- Ajustar `max_connections` no `postgresql.conf`
- Considerar read-replica para consultas pesadas (se necessário)
- Monitorar conexões ativas: `SELECT count(*) FROM pg_stat_activity;`

### 5.4 Escalar Redis

- Redis single-threaded; escalar verticalmente (mais CPU/memória)
- Para alta disponibilidade: considerar Redis Sentinel ou Cluster

---

## 6. On-Call Playbook

> **Depende de:** WS-OBS (stack de observabilidade definida). Placeholder até lá.

### 6.1 Incidente: serviço não responde

1. Verificar containers: `docker compose -f docker-compose.dev.yml ps`
2. Verificar logs: `docker compose -f docker-compose.dev.yml logs --tail=100 <servico>`
3. Verificar saúde: `curl -fsS http://localhost:<porta_host>/healthz` (ver tabela §1)
4. Verificar Postgres: `docker compose -f docker-compose.dev.yml exec postgres pg_isready -U supletivo -d supletivo`
5. Verificar Redis: `docker compose -f docker-compose.dev.yml exec redis redis-cli ping`
6. Reiniciar se necessário: `docker compose -f docker-compose.dev.yml restart <servico>`
7. Se persistir: verificar disco (`df -h`), memória (`free -m`), CPU (`top`)

### 6.2 Incidente: migração falhou

1. Verificar versão atual: `cd <servico> && uv run alembic current`
2. Verificar log do Alembic nos logs do container
3. Se migração parcial: `uv run alembic downgrade -1` e tentar novamente
4. Se schema corrompido: restore do backup + reaplicar migrações

### 6.3 Incidente: pagamento duplicado (asaas/infinitepay)

1. Verificar idempotência: `asaas_id` é commitado antes do efeito externo
2. Consultar tabela de pagamentos para duplicatas
3. Verificar logs do worker (`asaas` tem `worker_loop` async)
4. Não reexecutar manualmente — o sistema deve se recuperar sozinho

### 6.4 Escalação

- **Nível 1:** reiniciar container, verificar logs
- **Nível 2:** verificar infraestrutura (Postgres, Redis, disco, rede)
- **Nível 3:** restore de backup, rollback de migração
- **Nível 4:** contato com time de infraestrutura / Proxmox

---

## 7. Checklist de Deploy

1. [ ] `ruff check` + `ruff format` limpos em todos os serviços tocados
2. [ ] `pytest` passando (local e CI)
3. [ ] Migrações Alembic aplicáveis (`alembic upgrade head`)
4. [ ] `.env` atualizado com novas variáveis (se houver)
5. [ ] `wiki/<app>.md` atualizado (§15)
6. [ ] PR aprovado com checklist de conformidade completa
7. [ ] Health check respondendo após deploy
8. [ ] Logs sem erros nos primeiros 5 minutos
9. [ ] Smoke test (health check): `./scripts/smoke-test.sh` — todas as 22 /health devem retornar 200
10. [ ] Smoke test (full — staging apenas): `./scripts/smoke-test.sh --full` — caminho do dinheiro end-to-end

---

## 8. Links Úteis

| Recurso | Local |
|---|---|
| Convenção de código | `CONVENTION.md` |
| Guia de contribuição | `CONTRIBUTING.md` |
| Template de PR | `.github/PULL_REQUEST_TEMPLATE.md` |
| Plano de adequação | `wiki/PLANO_ADEQUACAO.md` |
| Docs por serviço | `wiki/<app>.md` |
| Regras por serviço | `<app>/.claude/CLAUDE.md` |
| Inventário de TODOs | `find . -name TODO -not -path '*/.venv/*'` |
| TODOs inline | `grep -rn "TODO\|FIXME\|XXX" <app>/app` |
