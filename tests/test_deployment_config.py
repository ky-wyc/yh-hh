from __future__ import annotations

import json
from pathlib import Path

import yaml

from scripts.prepare_lagrange_config import render_config


ROOT = Path(__file__).resolve().parents[1]


def load_compose() -> dict:
    return yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))


def test_core_ports_are_bound_to_loopback_only():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert '"127.0.0.1:8000:8000"' in compose
    assert '"127.0.0.1:5432:5432"' in compose
    assert '"127.0.0.1:6379:6379"' in compose
    assert '"0.0.0.0:8000:8000"' not in compose
    assert '"8000:8000"' not in compose
    assert '"5432:5432"' not in compose
    assert '"6379:6379"' not in compose


def test_web_admin_is_the_public_entrypoint():
    compose = load_compose()

    web_admin = compose["services"]["web-admin"]
    assert "8080:80" in web_admin["ports"]
    assert web_admin["depends_on"]["bot-app"]["condition"] == "service_healthy"


def test_compose_persists_runtime_state_and_uses_reverse_ws():
    compose = load_compose()
    services = compose["services"]

    assert "./data/app:/app/data" in services["bot-app"]["volumes"]
    assert "./data/onebot:/app/data" in services["onebot"]["volumes"]
    assert "./data/postgres:/var/lib/postgresql/data" in services["postgres"]["volumes"]
    assert services["bot-app"]["environment"]["ONEBOT_REVERSE_WS_URL"] == "ws://bot-app:8000/onebot/ws"
    assert services["onebot"]["environment"]["BOT_CORE_REVERSE_WS_URL"] == "ws://bot-app:8000/onebot/ws"
    assert services["onebot"]["depends_on"]["bot-app"]["condition"] == "service_healthy"


def test_web_admin_nginx_proxies_api_to_bot_app():
    nginx = (ROOT / "web-admin/nginx.conf").read_text(encoding="utf-8")
    dockerfile = (ROOT / "web-admin/Dockerfile").read_text(encoding="utf-8")

    assert "try_files $uri $uri/ /index.html;" in nginx
    assert "location /api/" in nginx
    assert "proxy_pass http://bot-app:8000/api/;" in nginx
    assert "COPY nginx.conf /etc/nginx/conf.d/default.conf" in dockerfile


def test_bot_app_dockerfile_runs_fastapi_factory():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert 'CMD ["uvicorn", "app.main:create_app", "--factory"' in dockerfile
    assert '"--host", "0.0.0.0"' in dockerfile
    assert "EXPOSE 8000" in dockerfile


def test_ops_scripts_keep_strict_preflight_and_identifier_guards():
    deploy = (ROOT / "scripts/deploy_mvp.sh").read_text(encoding="utf-8")
    backup = (ROOT / "scripts/backup.sh").read_text(encoding="utf-8")
    restore = (ROOT / "scripts/restore_postgres.sh").read_text(encoding="utf-8")

    assert 'STRICT_PREFLIGHT="${STRICT_PREFLIGHT:-0}"' in deploy
    assert 'REQUIRE_ONEBOT_ONLINE="${REQUIRE_ONEBOT_ONLINE:-0}"' in deploy
    assert 'REQUIRE_ONEBOT_ACTIVITY="${REQUIRE_ONEBOT_ACTIVITY:-0}"' in deploy
    assert 'REQUIRE_MVP_CORE_LOGS="${REQUIRE_MVP_CORE_LOGS:-0}"' in deploy
    assert 'REQUIRE_ADMIN_LITE_AUDIT="${REQUIRE_ADMIN_LITE_AUDIT:-0}"' in deploy
    assert 'scripts/preflight_check.py --env-file "$ENV_FILE" --strict' in deploy
    assert "--require-onebot-online" in deploy
    assert "--require-onebot-activity" in deploy
    assert "--require-mvp-core-logs" in deploy
    assert "--require-admin-lite-audit" in deploy
    for script in (backup, restore):
        assert "POSTGRES_USER must contain only letters, numbers, and underscores" in script
        assert "POSTGRES_DB must contain only letters, numbers, and underscores" in script


def test_generated_lagrange_config_matches_production_env_defaults(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "BOT_QQ=123456",
                "ONEBOT_REVERSE_WS_URL=ws://bot-app:8000/onebot/ws",
                "ONEBOT_ACCESS_TOKEN=acceptance-token",
            ]
        ),
        encoding="utf-8",
    )

    config = render_config(ROOT / "deploy/lagrange/appsettings.example.json", env_path)
    reverse_ws = next(item for item in config["Implementations"] if item["Type"] == "ReverseWebSocket")

    assert config["Account"]["Uin"] == 123456
    assert reverse_ws["Host"] == "bot-app"
    assert reverse_ws["Port"] == 8000
    assert reverse_ws["Suffix"] == "/onebot/ws"
    assert reverse_ws["AccessToken"] == "acceptance-token"
    json.dumps(config)


def test_web_admin_has_auth_guard_without_router_cycle():
    router = (ROOT / "web-admin/src/router.ts").read_text(encoding="utf-8")
    api = (ROOT / "web-admin/src/api.ts").read_text(encoding="utf-8")
    app = (ROOT / "web-admin/src/App.vue").read_text(encoding="utf-8")

    assert "requiresAuth: true" in router
    assert "router.beforeEach" in router
    assert "hasToken()" in router
    assert "status === 401" in api
    assert "window.location.assign('/login')" in api
    assert "from './router'" not in api
    assert "clearToken()" in app
