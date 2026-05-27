#!/usr/bin/env bash
# =============================================================================
# restore-pg.sh — Restore a PostgreSQL backup for Supletivo platform
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups}"

DEFAULT_DB_URL="postgresql://supletivo:supletivo_dev@localhost:5432/supletivo"
DB_URL="${DATABASE_URL:-$DEFAULT_DB_URL}"

parse_url() {
    local url="$1"
    local rest="${url#*://}"
    local user_pass="${rest%%@*}"
    local host_db="${rest#*@}"
    local host_port="${host_db%%/*}"
    local dbname="${host_db#*/}"
    PGUSER="${user_pass%%:*}"
    PGPASSWORD="${user_pass#*:}"
    PGHOST="${host_port%%:*}"
    PGPORT="${host_port#*:}"
    [ "$PGPORT" = "$PGHOST" ] && PGPORT="5432"
    export PGUSER PGPASSWORD PGHOST PGPORT
    echo "$dbname"
}

YES=false; LATEST=false; LIST=false; BACKUP_FILE=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --yes|-y) YES=true; shift ;;
        --latest|-l) LATEST=true; shift ;;
        --list) LIST=true; shift ;;
        -h|--help) echo "Usage: $0 [--yes] [--latest | <backup-file>]" ; exit 0 ;;
        *) BACKUP_FILE="$1"; shift ;;
    esac
done

if $LIST; then
    echo "Available backups in $BACKUP_DIR:"
    ls -lh "$BACKUP_DIR"/backup-*.sql.gz 2>/dev/null || echo "  (none)"
    exit 0
fi

if $LATEST; then
    BACKUP_FILE=$(ls -t "$BACKUP_DIR"/backup-*.sql.gz 2>/dev/null | head -1)
    [ -z "$BACKUP_FILE" ] && { echo "ERROR: No backups found"; exit 1; }
fi

[ -z "$BACKUP_FILE" ] && { echo "ERROR: No backup file. Use --latest or provide path."; exit 1; }
[ ! -f "$BACKUP_FILE" ] && { echo "ERROR: Not found: $BACKUP_FILE"; exit 1; }

DBNAME=$(parse_url "$DB_URL")

echo "=== PG Restore ==="
echo "  Host:     $PGHOST:$PGPORT"
echo "  Database: $DBNAME"
echo "  Backup:   $BACKUP_FILE"
echo "  Mode:     $([ "$YES" = true ] && echo 'LIVE' || echo 'DRY RUN')"

if [ "$YES" != true ]; then
    STATEMENT_COUNT=$(gunzip -c "$BACKUP_FILE" | grep -cE "CREATE SCHEMA|CREATE TABLE|COPY " || true)
    echo "  Statements: $STATEMENT_COUNT"
    echo "=== DRY RUN (no changes) ==="
    exit 0
fi

echo "WARNING: Overwriting $DBNAME. Ctrl+C within 3s to abort."
sleep 3

gunzip -c "$BACKUP_FILE" | PGPASSWORD="$PGPASSWORD" psql \
    --host="$PGHOST" --port="$PGPORT" --username="$PGUSER" \
    --dbname="$DBNAME" --echo-errors --single-transaction

echo "=== RESTORE COMPLETE ==="
