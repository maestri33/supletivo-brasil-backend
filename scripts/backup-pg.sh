#!/usr/bin/env bash
# =============================================================================
# backup-pg.sh — Automated PostgreSQL backup for Supletivo platform
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H-%M-%SZ")

DEFAULT_DB_URL="postgresql://supletivo:supletivo_dev@localhost:5433/supletivo"
DB_URL="${DATABASE_URL:-$DEFAULT_DB_URL}"

PARSE_URL() {
    local url="$1"
    local rest="${url#*://}"
    local user_pass="${rest%%@*}"
    local host_db="${rest#*@}"
    local host_part="${host_db%%/*}"
    local dbname="${host_db#*/}"
    local user="${user_pass%%:*}"
    local pass="${user_pass#*:}"
    [ "$user" = "$pass" ] && pass=""
    [ -z "$host_part" ] && host_part="localhost:5432"
    local host="${host_part%%:*}"
    local port="${host_part#*:}"
    [ "$port" = "$host" ] && port="5432"
    PGHOST="$host"
    PGPORT="$port"
    PGUSER="$user"
    PGPASSWORD="$pass"
    export PGHOST PGPORT PGUSER PGPASSWORD
    DBNAME="$dbname"
}

SCHEMA_FILTER=""
SCHEMAS="all"
while getopts "s:h" opt; do
    case "$opt" in
        s) SCHEMAS="$OPTARG"
           IFS=',' read -ra SA <<< "$SCHEMAS"
           for s in "${SA[@]}"; do SCHEMA_FILTER="$SCHEMA_FILTER -n $s"; done ;;
        h) echo "Usage: $0 [-s schema1,schema2]" ; exit 0 ;;
    esac
done

PARSE_URL "$DB_URL"
mkdir -p "$BACKUP_DIR"
BACKUP_FILE="$BACKUP_DIR/backup-${TIMESTAMP}.sql.gz"

echo "=== PG Backup ==="
echo "  Host:     $PGHOST:$PGPORT"
echo "  Database: $DBNAME"
echo "  Schemas:  $SCHEMAS"
echo "  Output:   $BACKUP_FILE"

PGPASSWORD="$PGPASSWORD" pg_dump \
    --host="$PGHOST" --port="$PGPORT" --username="$PGUSER" \
    --dbname="$DBNAME" --no-owner --no-acl --compress=0 \
    $SCHEMA_FILTER 2>&1 | gzip > "$BACKUP_FILE"

BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "  Size:     $BACKUP_SIZE"
echo "  Done:     $BACKUP_FILE"

DELETED=$(find "$BACKUP_DIR" -name "backup-*.sql.gz" -mtime +"$RETENTION_DAYS" -delete -print | wc -l)
echo "  Cleanup:  removed $DELETED backup(s) older than ${RETENTION_DAYS}d"
echo "=== OK ==="
