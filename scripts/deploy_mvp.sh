#!/usr/bin/env sh
set -eu

ENV_FILE="${ENV_FILE:-.env}"
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
ADMIN_USERNAME="${ADMIN_USERNAME:-}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-}"
PYTHON="${PYTHON:-python3}"
REQUIRE_ONEBOT_ONLINE="${REQUIRE_ONEBOT_ONLINE:-0}"
REQUIRE_ONEBOT_ACTIVITY="${REQUIRE_ONEBOT_ACTIVITY:-0}"
REQUIRE_MVP_CORE_LOGS="${REQUIRE_MVP_CORE_LOGS:-0}"
REQUIRE_ADMIN_LITE_AUDIT="${REQUIRE_ADMIN_LITE_AUDIT:-0}"
STRICT_PREFLIGHT="${STRICT_PREFLIGHT:-0}"
ONEBOT_ADAPTER="${ONEBOT_ADAPTER:-napcat}"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE. Copy .env.production.example to .env and edit it first." >&2
  exit 1
fi

env_value() {
  sed -n "s/^$1=//p" "$ENV_FILE" | tail -n 1
}

if [ -z "$ADMIN_USERNAME" ]; then
  ADMIN_USERNAME="$(env_value ADMIN_USERNAME)"
fi
ADMIN_USERNAME="${ADMIN_USERNAME:-admin}"

if [ "$STRICT_PREFLIGHT" = "1" ]; then
  "$PYTHON" scripts/preflight_check.py --env-file "$ENV_FILE" --strict
else
  "$PYTHON" scripts/preflight_check.py --env-file "$ENV_FILE"
fi

if [ "$ONEBOT_ADAPTER" = "lagrange" ]; then
  "$PYTHON" scripts/prepare_lagrange_config.py --env-file "$ENV_FILE"
fi

docker compose up -d --build

echo "Waiting for bot-app readiness..."
for i in $(seq 1 60); do
  if "$PYTHON" - <<PY
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
  ADMIN_PASSWORD="$(env_value ADMIN_PASSWORD)"
fi

"$PYTHON" scripts/smoke_check.py \
  --base-url "$BASE_URL" \
  --username "$ADMIN_USERNAME" \
  --password "$ADMIN_PASSWORD" \
  --expect-cache-backend redis

if [ "$REQUIRE_ONEBOT_ONLINE" = "1" ] || [ "$REQUIRE_ONEBOT_ACTIVITY" = "1" ] || [ "$REQUIRE_MVP_CORE_LOGS" = "1" ] || [ "$REQUIRE_ADMIN_LITE_AUDIT" = "1" ]; then
  EXTRA_SMOKE_ARGS=""
  if [ "$REQUIRE_ONEBOT_ONLINE" = "1" ] || [ "$REQUIRE_ONEBOT_ACTIVITY" = "1" ]; then
    EXTRA_SMOKE_ARGS="$EXTRA_SMOKE_ARGS --require-onebot-online"
  fi
  if [ "$REQUIRE_ONEBOT_ACTIVITY" = "1" ]; then
    EXTRA_SMOKE_ARGS="$EXTRA_SMOKE_ARGS --require-onebot-activity"
  fi
  if [ "$REQUIRE_MVP_CORE_LOGS" = "1" ]; then
    EXTRA_SMOKE_ARGS="$EXTRA_SMOKE_ARGS --require-mvp-core-logs"
  fi
  if [ "$REQUIRE_ADMIN_LITE_AUDIT" = "1" ]; then
    EXTRA_SMOKE_ARGS="$EXTRA_SMOKE_ARGS --require-admin-lite-audit"
  fi

  "$PYTHON" scripts/smoke_check.py \
    --base-url "$BASE_URL" \
    --username "$ADMIN_USERNAME" \
    --password "$ADMIN_PASSWORD" \
    --expect-cache-backend redis \
    $EXTRA_SMOKE_ARGS
fi

echo "MVP deployment smoke check passed."
