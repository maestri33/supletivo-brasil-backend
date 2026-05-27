# Supletivo — Operations Runbook

> Sprint 3-4: On-call playbook for Infra & DevOps + Observabilidade
> Cross-references: WS-INFRA (COD-13), WS-OBS (COD-17), WS-DOCS (COD-20)

---

## 1. Stack Overview

| Layer | Technology | Port | Config |
|-------|-----------|------|--------|
| API Gateway | None (direct per-service) | 8001-8022 | docker-compose.dev.yml |
| **Production** | **docker-compose.prod.yml** | **5432, 6379, 3000, 9090, 3100** | **docker-compose.prod.yml + .env** |
| Database | PostgreSQL 16 | 5433 (dev) / 5432 (prod) | postgres service |
| Cache | Redis 7 | 6379 | redis service |
| Metrics | Prometheus 2.53 | 9090 | prometheus/prometheus.yml |
| Logs | Loki 3.0 | 3100 | loki/loki-config.yml |
| Dashboards | Grafana 11.0 | 3000 | grafana/provisioning/ |
| Secrets | Infisical | 8080 | docker-compose (profile: infisical) |

**All 22 microservices** run on port 8000 internally, mapped to 8001-8022 externally.
Each has: `/health` endpoint, `/metrics` (Prometheus), structured logging (structlog).

---

## 2. Starting / Stopping

```bash
# Start everything (development)
docker compose -f docker-compose.dev.yml up -d

# Start everything (production — requires .env with secrets)
docker compose -f docker-compose.prod.yml up -d

# Start with Infisical secret manager
docker compose -f docker-compose.dev.yml --profile infisical up -d
docker compose -f docker-compose.prod.yml --profile infisical up -d

# Build and start a specific service
docker compose -f docker-compose.prod.yml build address
docker compose -f docker-compose.prod.yml up -d address

# Start specific service
docker compose -f docker-compose.dev.yml up -d address auth

# Check status
docker compose -f docker-compose.dev.yml ps

# Tail logs
docker compose -f docker-compose.dev.yml logs -f grafana prometheus

# Stop everything
docker compose -f docker-compose.dev.yml down
```

---

## 3. Health Checks

Each service exposes `GET /health`. Response format:

```json
{"status": "healthy", "service": "address", "timestamp": "2026-05-27T..."}
```

**Prometheus alert rules** (prometheus/alert-rules.yml):
- **ServiceDown**: `up == 0` for 45s → critical
- **ServiceFlapping**: `changes(up[5m]) > 3` → warning
- **HighErrorRate**: `5xx rate > 1%` over 5min → warning

**Grafana dashboard**: "Supletivo — Health & Performance" (uid: supletivo-health)
- Uptime panel (up metric × service)
- Health status table (up/down per service)
- P95 Latency panel (histogram_quantile)
- Error Rate panel (5xx / total)

---

## 4. Database Backups

| Detail | Value |
|--------|-------|
| Script | `scripts/backup-pg.sh` |
| Restore | `scripts/restore-pg.sh` |
| Schedule | Daily 3:00 AM UTC (cron) |
| Retention | 7 days |
| Output dir | `backups/` |

**Manual backup:**
```bash
DATABASE_URL="postgresql://supletivo:***@localhost:5433/supletivo" bash scripts/backup-pg.sh
```

**Restore (dry-run first):**
```bash
# List available backups
bash scripts/restore-pg.sh --list

# Dry-run (counts statements, no changes)
bash scripts/restore-pg.sh --latest

# Live restore
bash scripts/restore-pg.sh --latest --yes
```

---

## 5. Secret Management (Infisical)

```bash
# Start Infisical
docker compose -f docker-compose.dev.yml --profile infisical up -d

# Access UI
open http://localhost:8080

# First-run: create admin account
# Then create projects and add secrets per service
```

---

## 6. Observability URLs

| Service | URL | Credentials |
|---------|-----|-------------|
| Grafana | http://localhost:3000 | admin / admin |
| Prometheus | http://localhost:9090 | — |
| Infisical | http://localhost:8080 | (first-run setup) |

**Loki log query example (Grafana Explore):**
```
{job="address"} |= "error"
```

---

## 7. Service Port Map

| Port | Service | DB Schema | Depends On |
|------|---------|-----------|------------|
| 8001 | address | address | postgres, redis, auth |
| 8002 | ai | ai | postgres, redis |
| 8003 | asaas | asaas | postgres, redis |
| 8004 | auth | auth | postgres, redis |
| 8005 | candidate | candidate | postgres, redis |
| 8006 | commissions | commissions | postgres, redis |
| 8007 | coordinator | coordinator | postgres, redis |
| 8008 | documents | documents | postgres, redis |
| 8009 | enrollment | enrollment | postgres, redis |
| 8010 | fees | fees | postgres, redis |
| 8011 | hub | hub | postgres, redis |
| 8012 | infinitepay | infinitepay | postgres, redis |
| 8013 | jwt | jwt | postgres, redis |
| 8014 | lead | lead | postgres, redis |
| 8015 | notify | notify | postgres, redis |
| 8016 | otp | otp | postgres, redis |
| 8017 | profiles | profiles | postgres, redis |
| 8018 | promoter | promoter | postgres, redis |
| 8019 | roles | roles | postgres, redis |
| 8020 | staff | staff | postgres, redis |
| 8021 | student | student | postgres, redis |
| 8022 | training | training | postgres, redis |

---

## 8. CI/CD Pipeline

- **File**: `.github/workflows/ci.yml`
- **Triggers**: push/PR to main
- **Jobs**: lint (ruff) + test (pytest) + alembic check + import smoke
- **Gate**: all jobs must pass before merge

**Local CI check:**
```bash
cd services/<name>
uv sync
uv run ruff check .
uv run pytest -v
uv run alembic upgrade head
uv run python -c "import app; print('OK')"
```

---

## 9. Incident Response (Sprint 4)

### Service Down
1. Check Grafana: `http://localhost:3000/d/supletivo-health`
2. Check service logs: `docker compose logs <service>`
3. Check if DB/Redis is healthy: `docker compose ps postgres redis`
4. Restart service: `docker compose restart <service>`

### High Error Rate (>1%)
1. Identify affected service from Grafana Error Rate panel
2. Check recent logs: `docker compose logs --tail=100 <service>`
3. Check if a recent deployment caused regression
4. Rollback if needed: `git revert HEAD && docker compose up -d --build <service>`

### Disk / Backup Alert
1. Check backup dir: `ls -lh backups/`
2. Verify cron ran: `tail -20 backups/cron.log`
3. Free space: `df -h`
4. Manual backup if needed (see §4)

---

## 10. Proxmox Integration (future)

Sprint 4: Proxmox VM snapshot integration.
- VM host: TBD (human operator)
- Snapshot script: TBD
- Integration with backup-pg.sh for consistent backups
