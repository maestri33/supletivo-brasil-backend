#!/usr/bin/env bash
# =============================================================================
# init-dbs.sh — Cria schemas PostgreSQL para todos os microsserviços
# =============================================================================
# Uso:
#   ./scripts/init-dbs.sh                          # usa .env ou defaults
#   DATABASE_URL="postgresql://user:pass@host:5432/db" ./scripts/init-dbs.sh
#
# Pré-requisitos:
#   - PostgreSQL acessível (container local ou remoto)
#   - psql instalado
# =============================================================================

set -euo pipefail

# ── Config ──────────────────────────────────────────────────────────────────

DB_URL="${DATABASE_URL:-postgresql://supletivo:supletivo_dev@localhost:5433/supletivo}"

# ── Schemas (1 por microsserviço) ───────────────────────────────────────────

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

# ── Funções ──────────────────────────────────────────────────────────────────

create_schema() {
  local schema="$1"
  echo "  🔨 $schema..."
  psql "$DB_URL" -q -c "CREATE SCHEMA IF NOT EXISTS \"${schema}\";" 2>/dev/null || {
    echo "  ⚠️  Failed to create schema '$schema' — skipping"
    return 1
  }
}

run_migrations() {
  local service="$1"
  local dir="./$service"
  if [ -f "$dir/alembic.ini" ]; then
    echo "  🔄 Running alembic migrations for $service..."
    (cd "$dir" && alembic upgrade head 2>/dev/null) || echo "  ⚠️  alembic upgrade failed for $service"
  else
    echo "  ⏭️  $service has no alembic (skipping)"
  fi
}

# ── Main ─────────────────────────────────────────────────────────────────────

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Supletivo — Database Schema Initialization"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  DB: $DB_URL"
echo "  Schemas: ${#SCHEMAS[@]}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Step 1: Create schemas
echo ""
echo "📦 Creating schemas..."
for schema in "${SCHEMAS[@]}"; do
  create_schema "$schema"
done

# Step 2: Run alembic migrations (if available)
echo ""
echo "🔄 Running alembic migrations..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

for service in "${SCHEMAS[@]}"; do
  run_migrations "$service"
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ Database initialization complete!"
echo "  ${#SCHEMAS[@]} schemas created."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
