# RUNBOOK — Backend Supletivo

> **Status:** esqueleto (Sprint 0). Conteúdo será preenchido conforme a infra
> (docker-compose, CI/CD) amadurece. Atualizado em: 2026-05-27.
>
> **Referências:** `CONVENTION.md` · `wiki/PLANO_ADEQUACAO.md` · `wiki/<app>.md`

---

## 1. Inventário de Serviços

| Serviço | Porta | Schema | Status | CLAUDE.md | wiki.md |
|---|---|---|---|---|---|---|
| address | 80 | addresses | ativo | ✅ | ✅ |
| ai | 80 | ai | ativo | ✅ | ✅ |
| asaas | 80 | asaas | ativo (F5 concluída) | ✅ | ✅ |
| auth | 80 | auth | ativo | ✅ | ✅ |
| candidate | 80 | candidate | ativo | ✅ | ✅ |
| commissions | — | commissions | **não criado** (Parte B) | ❌ | ✅ |
| coordinator | — | coordinator | **não criado** (Parte B) | ❌ | ✅ |
| documents | 80 | documents | ativo | ❌ | ✅ |
| enrollment | 80 | enrollment | ativo | ❌ | ✅ |
| fees | 80 | fees | ativo | ✅ | ✅ |
| hub | — | hub | **não criado** (Parte B) | ❌ | ✅ |
| infinitepay | 80 | infinitepay | ativo (F5 concluída) | ✅ | ✅ |
| jwt | — | jwt | ativo | ❌ | ✅ |
| lead | 80 | lead | ativo (modelo de referência) | ❌ | ✅ |
| notify | 80 | notify | ativo | ✅ | ✅ |
| otp | 80 | otp | ativo | ✅ | ✅ |
| profiles | 80 | profiles | ativo | ✅ | ✅ |
| promoter | 80 | promoter | ativo | ✅ | ✅ |
| roles | 80 | roles | ativo | ❌ | ✅ |
| staff | — | staff | **não criado** (Parte B) | ❌ | ❌ |
| student | — | student | **não criado** (Parte B) | ❌ | ❌ |
| training | 80 | training | ativo | ✅ | ❌ |

**CLAUDE.md:** 12/22 (faltam 10) | **wiki.md:** 20/22 (faltam staff, student, training)

**Infraestrutura compartilhada:**
- Postgres central (todas as services usam schemas distintos no mesmo DB)
- Redis (OTP, locks, cache efêmero)

---

## 2. Subir / Derrubar

### 2.1 Pré-requisitos

- VM no Proxmox com Docker instalado
- `docker compose` (v2) disponível
- `.env` configurado na raiz (ver `.env.example` de cada serviço)
- Postgres e Redis acessíveis

### 2.2 Subir tudo

```bash
# Na raiz do projeto (onde está o docker-compose.yml)
docker compose up -d

# Verificar status
docker compose ps

# Verificar logs de um serviço específico
docker compose logs -f <servico>
```

### 2.3 Subir um serviço individual

```bash
cd <servico>/
make install    # uv sync
make dev        # uvicorn com reload (desenvolvimento)
# ou
make run        # uvicorn produção (workers=2)
```

### 2.4 Derrubar tudo

```bash
docker compose down
```

### 2.5 Derrubar um serviço

```bash
docker compose stop <servico>
docker compose rm -f <servico>
```

### 2.6 Health check

Cada serviço expõe `/healthz`:

```bash
curl -fsS http://localhost:<porta>/healthz
```

---

## 3. Backup / Restore

### 3.1 Banco de dados (Postgres)

```bash
# Backup completo (todos os schemas)
pg_dump -h <host> -U <user> -d <dbname> -F c -f backup_$(date +%Y%m%d_%H%M%S).dump

# Backup de schema específico
pg_dump -h <host> -U <user> -d <dbname> -n <schema> -F c -f <schema>_backup.dump

# Restore
pg_restore -h <host> -U <user> -d <dbname> -c --if-exists backup.dump
```

### 3.2 Redis

```bash
# Snapshot manual
redis-cli BGSAVE

# Backup do dump.rdb
cp /var/lib/redis/dump.rdb /backups/redis_$(date +%Y%m%d_%H%M%S).rdb
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

1. Verificar container: `docker compose ps`
2. Verificar logs: `docker compose logs --tail=100 <servico>`
3. Verificar saúde: `curl -fsS http://localhost:<porta>/healthz`
4. Verificar Postgres: `pg_isready -h <host> -U <user>`
5. Verificar Redis: `redis-cli ping`
6. Reiniciar se necessário: `docker compose restart <servico>`
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
