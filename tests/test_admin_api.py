from __future__ import annotations

import time

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.config import Settings
from app.main import create_app
from app.models import now_utc


def test_database_timestamp_defaults_are_timezone_naive_utc():
    assert now_utc().tzinfo is None


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

        ready = client.get("/api/system/ready")
        assert ready.status_code == 200
        assert ready.json()["database"] == "ok"

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


def test_llm_settings_can_clear_api_key(tmp_path):
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
        headers = {"Authorization": f"Bearer {token}"}

        response = client.patch(
            "/api/settings/llm",
            json={"api_key": ""},
            headers=headers,
        )

        assert response.status_code == 200
        assert response.json()["api_key_configured"] is False


def test_llm_usage_log_is_queryable(tmp_path):
    settings = Settings(
        DATABASE_URL=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        REDIS_URL="",
        ADMIN_USERNAME="admin",
        ADMIN_PASSWORD="secret",
        LLM_API_KEY="",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        token = client.post(
            "/api/auth/login", json={"username": "admin", "password": "secret"}
        ).json()["access_token"]
        test_response = client.post(
            "/api/settings/llm/test",
            json={"prompt": "hello"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert test_response.status_code == 200

        usage = client.get("/api/usage/llm", headers={"Authorization": f"Bearer {token}"})

        assert usage.status_code == 200
        assert usage.json()[0]["status"] == "missing_api_key"


def test_message_logs_include_onebot_message_id(tmp_path):
    settings = Settings(
        DATABASE_URL=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        REDIS_URL="",
        ADMIN_USERNAME="admin",
        ADMIN_PASSWORD="secret",
        ALLOWED_GROUPS="10001",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        token = client.post(
            "/api/auth/login", json={"username": "admin", "password": "secret"}
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        with client.websocket_connect("/onebot/ws") as websocket:
            websocket.send_json(
                {
                    "post_type": "message",
                    "message_type": "group",
                    "message_id": 991,
                    "group_id": 10001,
                    "user_id": 20001,
                    "message": "/ping",
                }
            )
            websocket.receive_json()
            logs = None
            for _ in range(20):
                logs = client.get("/api/system/logs", headers=headers)
                if logs.json():
                    break
                time.sleep(0.05)

        assert logs is not None
        assert logs.status_code == 200
        assert logs.json()[0]["message_id"] == "991"


def test_bot_settings_can_update_default_reply_mode(tmp_path):
    settings = Settings(
        DATABASE_URL=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        REDIS_URL="",
        ADMIN_USERNAME="admin",
        ADMIN_PASSWORD="secret",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        token = client.post(
            "/api/auth/login", json={"username": "admin", "password": "secret"}
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        response = client.patch(
            "/api/settings/bot",
            json={"default_reply_mode": "command_only", "command_prefix": "!"},
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["default_reply_mode"] == "command_only"
        assert response.json()["command_prefix"] == "!"
        assert "allowed_groups" in response.json()


def test_bot_settings_can_update_runtime_operation_fields(tmp_path):
    settings = Settings(
        DATABASE_URL=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        REDIS_URL="",
        ADMIN_USERNAME="admin",
        ADMIN_PASSWORD="secret",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        token = client.post(
            "/api/auth/login", json={"username": "admin", "password": "secret"}
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        response = client.patch(
            "/api/settings/bot",
            json={
                "bot_qq": "123456",
                "bot_nicknames": "小Q,助手",
                "admin_qq_ids": "20001, 20002",
                "allowed_groups": "10001, 10002",
                "rate_limit_per_user_per_minute": 20,
                "rate_limit_per_group_per_minute": 120,
            },
            headers=headers,
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["bot_qq"] == "123456"
        assert payload["bot_nicknames"] == "小Q,助手"
        assert payload["admin_qq_ids"] == "20001,20002"
        assert payload["allowed_groups"] == "10001,10002"
        assert payload["rate_limit_per_user_per_minute"] == 20
        assert payload["rate_limit_per_group_per_minute"] == 120


def test_bot_settings_reject_invalid_values(tmp_path):
    settings = Settings(
        DATABASE_URL=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        REDIS_URL="",
        ADMIN_USERNAME="admin",
        ADMIN_PASSWORD="secret",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        token = client.post(
            "/api/auth/login", json={"username": "admin", "password": "secret"}
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        invalid_mode = client.patch(
            "/api/settings/bot",
            json={"default_reply_mode": "chatty"},
            headers=headers,
        )
        invalid_prefix = client.patch(
            "/api/settings/bot",
            json={"command_prefix": ""},
            headers=headers,
        )
        invalid_admin_ids = client.patch(
            "/api/settings/bot",
            json={"admin_qq_ids": "abc"},
            headers=headers,
        )
        invalid_rate_limit = client.patch(
            "/api/settings/bot",
            json={"rate_limit_per_user_per_minute": 0},
            headers=headers,
        )

        assert invalid_mode.status_code == 422
        assert invalid_prefix.status_code == 422
        assert invalid_admin_ids.status_code == 422
        assert invalid_rate_limit.status_code == 422


def test_keyword_rules_can_be_managed_from_admin(tmp_path):
    settings = Settings(
        DATABASE_URL=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        REDIS_URL="",
        ADMIN_USERNAME="admin",
        ADMIN_PASSWORD="secret",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        token = client.post(
            "/api/auth/login", json={"username": "admin", "password": "secret"}
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        created = client.post(
            "/api/keyword-rules",
            json={
                "group_id": "10001",
                "keyword": "spam",
                "response": "请不要发广告",
                "enabled": True,
            },
            headers=headers,
        )
        assert created.status_code == 200
        rule = created.json()
        assert rule["group_id"] == "10001"
        assert rule["keyword"] == "spam"
        assert rule["response"] == "请不要发广告"
        assert rule["enabled"] is True

        patched = client.patch(
            f"/api/keyword-rules/{rule['id']}",
            json={"response": "广告已拦截", "enabled": False},
            headers=headers,
        )
        assert patched.status_code == 200
        assert patched.json()["response"] == "广告已拦截"
        assert patched.json()["enabled"] is False

        listed = client.get("/api/keyword-rules?group_id=10001", headers=headers)
        assert listed.status_code == 200
        assert listed.json()[0]["keyword"] == "spam"

        deleted = client.delete(f"/api/keyword-rules/{rule['id']}", headers=headers)
        assert deleted.status_code == 200
        assert deleted.json()["deleted"] is True

        assert client.get("/api/keyword-rules", headers=headers).json() == []
        audit = client.get("/api/audit-logs", headers=headers)
        assert audit.json()[0]["action"] == "keyword_rule_delete"


def test_keyword_rules_reject_invalid_payloads(tmp_path):
    settings = Settings(
        DATABASE_URL=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        REDIS_URL="",
        ADMIN_USERNAME="admin",
        ADMIN_PASSWORD="secret",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        token = client.post(
            "/api/auth/login", json={"username": "admin", "password": "secret"}
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        invalid_group = client.post(
            "/api/keyword-rules",
            json={"group_id": "abc", "keyword": "spam", "response": "blocked"},
            headers=headers,
        )
        empty_keyword = client.post(
            "/api/keyword-rules",
            json={"group_id": "", "keyword": "  ", "response": "blocked"},
            headers=headers,
        )

        assert invalid_group.status_code == 422
        assert empty_keyword.status_code == 422


def test_memories_can_be_managed_from_admin(tmp_path):
    settings = Settings(
        DATABASE_URL=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        REDIS_URL="",
        ADMIN_USERNAME="admin",
        ADMIN_PASSWORD="secret",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        token = client.post(
            "/api/auth/login", json={"username": "admin", "password": "secret"}
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        created = client.post(
            "/api/memories",
            json={
                "group_id": "10001",
                "user_id": "20001",
                "content": "用户喜欢简短回答",
                "source": "admin",
                "confidence": 0.9,
                "status": "approved",
            },
            headers=headers,
        )
        assert created.status_code == 200
        memory = created.json()
        assert memory["content"] == "用户喜欢简短回答"
        assert memory["status"] == "approved"

        patched = client.patch(
            f"/api/memories/{memory['id']}",
            json={"content": "用户喜欢直接、简短的回答", "status": "pending"},
            headers=headers,
        )
        assert patched.status_code == 200
        assert patched.json()["content"] == "用户喜欢直接、简短的回答"
        assert patched.json()["status"] == "pending"

        listed = client.get("/api/memories?status=pending", headers=headers)
        assert listed.status_code == 200
        assert listed.json()[0]["id"] == memory["id"]

        deleted = client.delete(f"/api/memories/{memory['id']}", headers=headers)
        assert deleted.status_code == 200
        assert deleted.json()["deleted"] is True
        assert client.get("/api/memories?status=deleted", headers=headers).json()[0]["id"] == memory["id"]


def test_knowledge_docs_can_be_created_chunked_and_searched_from_admin(tmp_path):
    settings = Settings(
        DATABASE_URL=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        REDIS_URL="",
        ADMIN_USERNAME="admin",
        ADMIN_PASSWORD="secret",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        token = client.post(
            "/api/auth/login", json={"username": "admin", "password": "secret"}
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        created = client.post(
            "/api/knowledge-docs",
            json={
                "group_id": "10001",
                "title": "群规",
                "content": "禁止广告。提问请带上下文。管理员可以处理违规。",
                "enabled": True,
            },
            headers=headers,
        )
        assert created.status_code == 200
        document = created.json()
        assert document["title"] == "群规"
        assert document["chunk_count"] >= 1
        assert document["index_status"] == "completed"

        listed = client.get("/api/knowledge-docs?group_id=10001", headers=headers)
        assert listed.status_code == 200
        assert listed.json()[0]["id"] == document["id"]

        searched = client.post(
            "/api/knowledge-search",
            json={"group_id": "10001", "query": "广告"},
            headers=headers,
        )
        assert searched.status_code == 200
        results = searched.json()["results"]
        assert results[0]["title"] == "群规"
        assert "禁止广告" in results[0]["content"]
        assert results[0]["source"] == f"群规#{results[0]['chunk_index'] + 1}"


def test_knowledge_doc_can_be_reindexed_from_admin(tmp_path):
    settings = Settings(
        DATABASE_URL=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        REDIS_URL="",
        ADMIN_USERNAME="admin",
        ADMIN_PASSWORD="secret",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        token = client.post(
            "/api/auth/login", json={"username": "admin", "password": "secret"}
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        created = client.post(
            "/api/knowledge-docs",
            json={
                "group_id": "10001",
                "title": "FAQ",
                "content": "部署问题请查看运维说明。",
                "enabled": True,
            },
            headers=headers,
        ).json()

        reindexed = client.post(f"/api/knowledge-docs/{created['id']}/reindex", headers=headers)

        assert reindexed.status_code == 200
        payload = reindexed.json()
        assert payload["index_status"] == "completed"
        assert payload["chunk_count"] >= 1
        audit = client.get("/api/audit-logs", headers=headers)
        assert audit.json()[0]["action"] == "knowledge_doc_reindex"


def test_scheduled_tasks_can_be_managed_from_admin(tmp_path):
    settings = Settings(
        DATABASE_URL=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        REDIS_URL="",
        ADMIN_USERNAME="admin",
        ADMIN_PASSWORD="secret",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        token = client.post(
            "/api/auth/login", json={"username": "admin", "password": "secret"}
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        created = client.post(
            "/api/scheduled-tasks",
            json={
                "name": "测试提醒",
                "task_type": "reminder_once",
                "schedule_type": "once",
                "group_id": "10001",
                "payload": {"message": "记得测试"},
                "next_run_at": "2026-07-06T12:00:00",
                "enabled": True,
            },
            headers=headers,
        )
        assert created.status_code == 200
        task = created.json()
        assert task["name"] == "测试提醒"
        assert task["task_type"] == "reminder_once"
        assert task["enabled"] is True

        patched = client.patch(
            f"/api/scheduled-tasks/{task['id']}",
            json={"enabled": False},
            headers=headers,
        )
        assert patched.status_code == 200
        assert patched.json()["enabled"] is False

        listed = client.get("/api/scheduled-tasks", headers=headers)
        assert listed.status_code == 200
        assert listed.json()[0]["id"] == task["id"]

        deleted = client.delete(f"/api/scheduled-tasks/{task['id']}", headers=headers)
        assert deleted.status_code == 200
        assert deleted.json()["deleted"] is True


def test_group_update_rejects_invalid_reply_mode(tmp_path):
    settings = Settings(
        DATABASE_URL=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        REDIS_URL="",
        ADMIN_USERNAME="admin",
        ADMIN_PASSWORD="secret",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        token = client.post(
            "/api/auth/login", json={"username": "admin", "password": "secret"}
        ).json()["access_token"]
        response = client.patch(
            "/api/groups/10001",
            json={"reply_mode": "chatty"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 422


def test_group_update_rejects_invalid_group_id(tmp_path):
    settings = Settings(
        DATABASE_URL=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        REDIS_URL="",
        ADMIN_USERNAME="admin",
        ADMIN_PASSWORD="secret",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        token = client.post(
            "/api/auth/login", json={"username": "admin", "password": "secret"}
        ).json()["access_token"]
        response = client.patch(
            "/api/groups/not-a-group",
            json={"enabled": True},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 422


def test_group_update_can_create_group_configuration(tmp_path):
    settings = Settings(
        DATABASE_URL=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        REDIS_URL="",
        ADMIN_USERNAME="admin",
        ADMIN_PASSWORD="secret",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        token = client.post(
            "/api/auth/login", json={"username": "admin", "password": "secret"}
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        update = client.patch(
            "/api/groups/10001",
            json={"enabled": False, "reply_mode": "command_only", "name": "测试群"},
            headers=headers,
        )
        groups = client.get("/api/groups", headers=headers)
        audit = client.get("/api/audit-logs", headers=headers)

        assert update.status_code == 200
        assert update.json()["enabled"] is False
        assert update.json()["reply_mode"] == "command_only"
        assert groups.json() == [
            {
                "qq_group_id": "10001",
                "name": "测试群",
                "enabled": False,
                "reply_mode": "command_only",
            }
        ]
        assert audit.json()[0]["action"] == "group_update"


def test_llm_settings_reject_invalid_ranges(tmp_path):
    settings = Settings(
        DATABASE_URL=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        REDIS_URL="",
        ADMIN_USERNAME="admin",
        ADMIN_PASSWORD="secret",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        token = client.post(
            "/api/auth/login", json={"username": "admin", "password": "secret"}
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        temperature = client.patch(
            "/api/settings/llm",
            json={"temperature": 9},
            headers=headers,
        )
        timeout = client.patch(
            "/api/settings/llm",
            json={"timeout_seconds": 0},
            headers=headers,
        )

        assert temperature.status_code == 422
        assert timeout.status_code == 422


def test_llm_settings_reject_invalid_base_url(tmp_path):
    settings = Settings(
        DATABASE_URL=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        REDIS_URL="",
        ADMIN_USERNAME="admin",
        ADMIN_PASSWORD="secret",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        token = client.post(
            "/api/auth/login", json={"username": "admin", "password": "secret"}
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        no_scheme = client.patch(
            "/api/settings/llm",
            json={"base_url": "api.example.com/v1"},
            headers=headers,
        )
        no_host = client.patch(
            "/api/settings/llm",
            json={"base_url": "https:///v1"},
            headers=headers,
        )

        assert no_scheme.status_code == 422
        assert no_host.status_code == 422


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


def test_onebot_status_exposes_last_event_and_action_times(tmp_path):
    settings = Settings(
        DATABASE_URL=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        REDIS_URL="",
        ADMIN_USERNAME="admin",
        ADMIN_PASSWORD="secret",
        ALLOWED_GROUPS="10001",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        token = client.post(
            "/api/auth/login", json={"username": "admin", "password": "secret"}
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        with client.websocket_connect("/onebot/ws") as websocket:
            websocket.send_json(
                {
                    "post_type": "message",
                    "message_type": "group",
                    "message_id": 991,
                    "group_id": 10001,
                    "user_id": 20001,
                    "message": "/ping",
                }
            )
            websocket.receive_json()
            status = None
            for _ in range(20):
                status = client.get("/api/system/onebot-status", headers=headers)
                if status.json().get("last_action_at"):
                    break
                time.sleep(0.05)

        assert status is not None
        assert status.status_code == 200
        payload = status.json()
        assert payload["last_event_at"]
        assert payload["last_action_at"]


def test_onebot_reverse_ws_accepts_access_token_query(tmp_path):
    settings = Settings(
        DATABASE_URL=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        REDIS_URL="",
        ALLOWED_GROUPS="10001",
        ONEBOT_ACCESS_TOKEN="secret-token",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        with client.websocket_connect("/onebot/ws?access_token=secret-token") as websocket:
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

        assert action["params"]["message"] == "pong"


def test_onebot_reverse_ws_accepts_access_token_headers(tmp_path):
    settings = Settings(
        DATABASE_URL=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        REDIS_URL="",
        ALLOWED_GROUPS="10001",
        ONEBOT_ACCESS_TOKEN="secret-token",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        for headers in [
            {"Authorization": "Bearer secret-token"},
            {"X-Access-Token": "secret-token"},
        ]:
            with client.websocket_connect("/onebot/ws", headers=headers) as websocket:
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

            assert action["params"]["message"] == "pong"


def test_onebot_reverse_ws_rejects_invalid_access_token(tmp_path):
    settings = Settings(
        DATABASE_URL=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        REDIS_URL="",
        ALLOWED_GROUPS="10001",
        ONEBOT_ACCESS_TOKEN="secret-token",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/onebot/ws?access_token=wrong"):
                raise AssertionError("websocket should not connect")

        assert exc_info.value.code == 1008


def test_audit_logs_are_queryable(tmp_path):
    settings = Settings(
        DATABASE_URL=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        REDIS_URL="",
        ADMIN_USERNAME="admin",
        ADMIN_PASSWORD="secret",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        token = client.post(
            "/api/auth/login", json={"username": "admin", "password": "secret"}
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        update = client.patch(
            "/api/settings/bot",
            json={"default_reply_mode": "command_only"},
            headers=headers,
        )
        assert update.status_code == 200

        response = client.get("/api/audit-logs", headers=headers)

        assert response.status_code == 200
        assert response.json()[0]["action"] == "bot_settings_update"
