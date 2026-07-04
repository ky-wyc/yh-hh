#!/usr/bin/env sh
set -eu

BACKUP_DIR="${BACKUP_DIR:-./data/backups}"
mkdir -p "$BACKUP_DIR"

STAMP="$(date +%Y%m%d-%H%M%S)"
docker compose exec -T postgres pg_dump -U "${POSTGRES_USER:-qqbot}" "${POSTGRES_DB:-qqbot}" > "$BACKUP_DIR/postgres-$STAMP.sql"

echo "Backup written to $BACKUP_DIR/postgres-$STAMP.sql"

