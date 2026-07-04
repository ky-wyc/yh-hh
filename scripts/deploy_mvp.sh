#!/usr/bin/env sh
set -eu

ENV_FILE="${ENV_FILE:-.env}"
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
ADMIN_USERNAME="${ADMIN_USERNAME:-admin}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-}"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE. Copy .env.production.example to .env and edit it first." >&2
  exit 1
fi

python scripts/preflight_check.py --env-file "$ENV_FILE"
python scripts/prepare_lagrange_config.py --env-file "$ENV_FILE"

docker compose up -d --build

echo "Waiting for bot-app readiness..."
for i in $(seq 1 60); do
  if python - <<PY
import urllib.request
urllib.request.urlopen("$BASE_URL/api/system/ready", timeout=3).read()
PY
  then
    break
  fi
  if [ "$i" -eq 60 ]; then
    echo "bot-app did not become ready" >&2
    docker compose ps
    docker compose logs --tail=100 bot-app
    exit 1
  fi
  sleep 2
done

if [ -z "$ADMIN_PASSWORD" ]; then
  ADMIN_PASSWORD="$(grep '^ADMIN_PASSWORD=' "$ENV_FILE" | sed 's/^ADMIN_PASSWORD=//')"
fi

python scripts/smoke_check.py \
  --base-url "$BASE_URL" \
  --username "$ADMIN_USERNAME" \
  --password "$ADMIN_PASSWORD"

echo "MVP deployment smoke check passed."
