#!/usr/bin/env sh
set -eu

ENV_FILE="${ENV_FILE:-.env}"
BACKUP_FILE="${1:-${BACKUP_FILE:-}}"
FORCE="${FORCE:-0}"

usage() {
  echo "Usage: sh scripts/restore_postgres.sh ./data/backups/postgres-YYYYmmdd-HHMMSS.sql" >&2
  echo "Set FORCE=1 to skip the interactive confirmation." >&2
}

if [ -z "$BACKUP_FILE" ]; then
  usage
  exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
  echo "Backup file not found: $BACKUP_FILE" >&2
  exit 1
fi

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
    echo "POSTGRES_USER must contain only letters, numbers, and underscores for restore." >&2
    exit 1
    ;;
esac

case "$POSTGRES_DB_VALUE" in
  *[!A-Za-z0-9_]* | "")
    echo "POSTGRES_DB must contain only letters, numbers, and underscores for restore." >&2
    exit 1
    ;;
esac

if [ "$FORCE" != "1" ]; then
  echo "This will replace PostgreSQL database '$POSTGRES_DB_VALUE' using:"
  echo "  $BACKUP_FILE"
  printf "Type RESTORE to continue: "
  read CONFIRM
  if [ "$CONFIRM" != "RESTORE" ]; then
    echo "Restore cancelled."
    exit 1
  fi
fi

echo "Stopping application services..."
docker compose stop bot-app web-admin onebot

echo "Recreating database '$POSTGRES_DB_VALUE'..."
docker compose exec -T postgres psql -U "$POSTGRES_USER_VALUE" -d postgres -v ON_ERROR_STOP=1 <<SQL
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = '$POSTGRES_DB_VALUE'
  AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS "$POSTGRES_DB_VALUE";
CREATE DATABASE "$POSTGRES_DB_VALUE" OWNER "$POSTGRES_USER_VALUE";
SQL

echo "Restoring backup..."
docker compose exec -T postgres psql -U "$POSTGRES_USER_VALUE" -d "$POSTGRES_DB_VALUE" -v ON_ERROR_STOP=1 < "$BACKUP_FILE"

echo "Starting application services..."
docker compose start bot-app web-admin onebot

echo "Restore completed from $BACKUP_FILE"
