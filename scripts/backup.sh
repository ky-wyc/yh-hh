#!/usr/bin/env sh
set -eu

ENV_FILE="${ENV_FILE:-.env}"
BACKUP_DIR="${BACKUP_DIR:-./data/backups}"
mkdir -p "$BACKUP_DIR"

env_value() {
  if [ -f "$ENV_FILE" ]; then
    sed -n "s/^$1=//p" "$ENV_FILE" | tail -n 1
  fi
}

POSTGRES_USER_VALUE="${POSTGRES_USER:-$(env_value POSTGRES_USER)}"
POSTGRES_DB_VALUE="${POSTGRES_DB:-$(env_value POSTGRES_DB)}"
POSTGRES_USER_VALUE="${POSTGRES_USER_VALUE:-qqbot}"
POSTGRES_DB_VALUE="${POSTGRES_DB_VALUE:-qqbot}"

case "$POSTGRES_USER_VALUE" in
  *[!A-Za-z0-9_]* | "")
    echo "POSTGRES_USER must contain only letters, numbers, and underscores for backup." >&2
    exit 1
    ;;
esac

case "$POSTGRES_DB_VALUE" in
  *[!A-Za-z0-9_]* | "")
    echo "POSTGRES_DB must contain only letters, numbers, and underscores for backup." >&2
    exit 1
    ;;
esac

STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_FILE="$BACKUP_DIR/postgres-$STAMP.sql"
docker compose exec -T postgres pg_dump -U "$POSTGRES_USER_VALUE" "$POSTGRES_DB_VALUE" > "$BACKUP_FILE"

if [ ! -s "$BACKUP_FILE" ]; then
  echo "Backup file is empty: $BACKUP_FILE" >&2
  exit 1
fi

chmod 600 "$BACKUP_FILE" 2>/dev/null || true

echo "Backup written to $BACKUP_FILE"
