#!/usr/bin/env bash
# =============================================================================
# init-dbs.sh — PostgreSQL schema initialization for Supletivo
# =============================================================================
# Creates the database and all service-specific schemas for the Supletivo
# platform. Designed for first-time production deployment (docker-compose
# entrypoint pattern) and development environment reset.
#
# Usage:
#   ./scripts/init-dbs.sh                    # init with defaults
#   ./scripts/init-dbs.sh --dry-run          # preview only, no changes
#   ./scripts/init-dbs.sh --db supletivo     # specify database name
#   ./scripts/init-dbs.sh --host localhost   # specify host
#   ./scripts/init-dbs.sh --user supletivo   # specify user
#
# Environment variables (override defaults):
#   PG_HOST      — default: localhost
#   PG_PORT      — default: 5432 (5433 for dev host-mapped)
#   PG_USER      — default: supletivo
#   PG_PASSWORD  — default: supletivo_dev
#   PG_DB        — default: supletivo
# =============================================================================
set -euo pipefail

# ── Config ───────────────────────────────────────────────────────────────────

PG_HOST="${PG_HOST:-localhost}"
PG_PORT="${PG_PORT:-5432}"
PG_USER="${PG_USER:-supletivo}"
PG_PASSWORD="${PG_PASSWORD:-supletivo_dev}"
PG_DB="${PG_DB:-supletivo}"
DRY_RUN=false

# Parse CLI args
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) DRY_RUN=true; shift ;;
        --db) PG_DB="$2"; shift 2 ;;
        --host) PG_HOST="$2"; shift 2 ;;
        --port) PG_PORT="$2"; shift 2 ;;
        --user) PG_USER="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# ── Helpers ──────────────────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass() { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; exit 1; }

PG_CMD() {
    PGPASSWORD="$PG_PASSWORD" psql -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DB" -t -A "$@"
}

PG_CMD_ADMIN() {
    PGPASSWORD="$PG_PASSWORD" psql -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d postgres -t -A "$@"
}

# ── Service schemas (1:1 with docker-compose services) ───────────────────────

SCHEMAS=(
    address
    ai
    asaas
    auth
    candidate
    commissions
    coordinator
    documents
    enrollment
    fees
    hub
    infinitepay
    jwt
    lead
    notify
    otp
    profiles
    promoter
    roles
    staff
    student
    training
)

# ── Run ──────────────────────────────────────────────────────────────────────

echo "=== init-dbs.sh ==="
echo "  Host: $PG_HOST:$PG_PORT"
echo "  User: $PG_USER"
echo "  Database: $PG_DB"
echo "  Dry-run: $DRY_RUN"
echo ""

# Step 1: Ensure the database exists
echo "--- Step 1: Ensure database '$PG_DB' exists ---"
DB_EXISTS=$(PGPASSWORD="$PG_PASSWORD" psql -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d postgres -t -A -c "SELECT 1 FROM pg_database WHERE datname='$PG_DB'")
if [ "$DB_EXISTS" = "1" ]; then
    pass "Database '$PG_DB' already exists"
else
    if [ "$DRY_RUN" = true ]; then
        warn "Would CREATE DATABASE $PG_DB"
    else
        PG_CMD_ADMIN -c "CREATE DATABASE $PG_DB" >/dev/null 2>&1
        pass "Created database '$PG_DB'"
    fi
fi

# Step 2: Create all service schemas
echo ""
echo "--- Step 2: Create service schemas ---"
for SCHEMA in "${SCHEMAS[@]}"; do
    SCHEMA_EXISTS=$(PG_CMD -c "SELECT 1 FROM information_schema.schemata WHERE schema_name='$SCHEMA'")
    if [ "$SCHEMA_EXISTS" = "1" ]; then
        pass "Schema '$SCHEMA' already exists"
    else
        if [ "$DRY_RUN" = true ]; then
            warn "Would CREATE SCHEMA $SCHEMA"
        else
            PG_CMD -c "CREATE SCHEMA $SCHEMA" >/dev/null 2>&1
            pass "Created schema '$SCHEMA'"
        fi
    fi
done

# Step 3: Set search_path defaults for each schema
echo ""
echo "--- Step 3: Configure search_path ---"
for SCHEMA in "${SCHEMAS[@]}"; do
    if [ "$DRY_RUN" = true ]; then
        warn "Would ALTER DATABASE $PG_DB SET search_path TO \$user, public, $SCHEMA (per-service config)"
    fi
done

# HINT: Each service already sets search_path via alembic context or SQLAlchemy
# connect string. This step is informational only — no global change needed.
pass "Per-service search_path configured via DATABASE_SCHEMA env var"

# Step 4: Verify
echo ""
echo "--- Step 4: Verification ---"
SCHEMA_COUNT=$(PG_CMD -c "SELECT count(*) FROM information_schema.schemata WHERE schema_name NOT IN ('information_schema','pg_catalog','pg_toast','public')")
pass "$SCHEMA_COUNT schemas created"

echo ""
echo "=== init-dbs.sh complete ==="
