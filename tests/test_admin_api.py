from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_admin_login_and_health(tmp_path):
    settings = Settings(
        DATABASE_URL=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        REDIS_URL="",
        ADMIN_USERNAME="admin",
        ADMIN_PASSWORD="secret",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        health = client.get("/api/system/health")
        assert health.status_code == 200

        denied = client.get("/api/auth/me")
        assert denied.status_code == 401

        login = client.post("/api/auth/login", json={"username": "admin", "password": "secret"})
        assert login.status_code == 200
        token = login.json()["access_token"]

        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200


def test_llm_settings_mask_api_key(tmp_path):
    settings = Settings(
        DATABASE_URL=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        REDIS_URL="",
        ADMIN_USERNAME="admin",
        ADMIN_PASSWORD="secret",
        LLM_API_KEY="super-secret",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        token = client.post(
            "/api/auth/login", json={"username": "admin", "password": "secret"}
        ).json()["access_token"]
        response = client.get("/api/settings/llm", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
        payload = response.json()
        assert payload["api_key_configured"] is True
        assert "super-secret" not in str(payload)


def test_onebot_reverse_ws_receives_group_message_and_sends_action(tmp_path):
    settings = Settings(
        DATABASE_URL=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        REDIS_URL="",
        ALLOWED_GROUPS="10001",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        with client.websocket_connect("/onebot/ws") as websocket:
            websocket.send_json(
                {
                    "post_type": "message",
                    "message_type": "group",
                    "message_id": 1,
                    "group_id": 10001,
                    "user_id": 20001,
                    "message": "/ping",
                }
            )
            action = websocket.receive_json()

        assert action["action"] == "send_group_msg"
        assert action["params"]["group_id"] == 10001
        assert action["params"]["message"] == "pong"
