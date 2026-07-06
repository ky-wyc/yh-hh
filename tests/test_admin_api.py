from __future__ import annotations

from io import BytesIO
import json
import time

import pytest
from openpyxl import Workbook
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.config import Settings
from app.main import create_app
from app.models import now_utc


def build_xlsx_bytes() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "FAQ"
    sheet.append(["问题", "答案"])
    sheet.append(["如何部署", "使用 Docker Compose"])
    buffer = BytesIO()
    workbook.save(buffer)
    workbook.close()
    return buffer.getvalue()


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


def test_embedding_settings_can_be_managed_and_mask_api_key(tmp_path):
    settings = Settings(
        DATABASE_URL=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        REDIS_URL="",
        ADMIN_USERNAME="admin",
        ADMIN_PASSWORD="secret",
        EMBEDDING_API_KEY="embedding-secret",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        token = client.post(
            "/api/auth/login", json={"username": "admin", "password": "secret"}
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        current = client.get("/api/settings/embedding", headers=headers)
        assert current.status_code == 200
        assert current.json()["api_key_configured"] is True
        assert "embedding-secret" not in str(current.json())

        updated = client.patch(
            "/api/settings/embedding",
            json={
                "provider": "openai_compatible",
                "base_url": "https://embed.example/v1",
                "api_key": "new-secret",
                "model": "embed-model",
                "dimensions": 128,
                "timeout_seconds": 15,
            },
            headers=headers,
        )
        assert updated.status_code == 200
        payload = updated.json()
        assert payload["provider"] == "openai_compatible"
        assert payload["base_url"] == "https://embed.example/v1"
        assert payload["model"] == "embed-model"
        assert payload["dimensions"] == 128
        assert payload["api_key_configured"] is True
        assert "new-secret" not in str(payload)

        cleared = client.patch(
            "/api/settings/embedding",
            json={"api_key": ""},
            headers=headers,
        )
        assert cleared.status_code == 200
        assert cleared.json()["api_key_configured"] is False


def test_embedding_settings_local_test_does_not_require_api_key(tmp_path):
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

        response = client.post(
            "/api/settings/embedding/test",
            json={"text": "hello"},
            headers=headers,
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "success"
        assert payload["provider"] == "local"
        assert payload["actual_dimensions"] == 64


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


def test_onebot_group_increase_notice_sends_welcome_action(tmp_path):
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
        client.patch(
            "/api/groups/10001",
            json={"welcome_enabled": True, "welcome_message": "欢迎 {user_id}"},
            headers=headers,
        )

        with client.websocket_connect("/onebot/ws") as websocket:
            websocket.send_json(
                {
                    "post_type": "notice",
                    "notice_type": "group_increase",
                    "group_id": 10001,
                    "user_id": 20002,
                }
            )
            action = websocket.receive_json()

        assert action["action"] == "send_group_msg"
        assert action["params"]["group_id"] == 10001
        assert action["params"]["message"] == "欢迎 20002"


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
        assert document["index_status"] == "vectorized"

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


def test_knowledge_docs_can_be_imported_from_xlsx_for_multiple_groups(tmp_path):
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
        client.patch("/api/groups/10001", json={"name": "一群"}, headers=headers)
        client.patch("/api/groups/10002", json={"name": "二群"}, headers=headers)

        imported = client.post(
            "/api/knowledge-docs/import",
            data={
                "title": "导入 FAQ",
                "group_ids": json.dumps(["10001", "10002"]),
                "enabled": "true",
            },
            files={
                "file": (
                    "faq.xlsx",
                    build_xlsx_bytes(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
            headers=headers,
        )

        assert imported.status_code == 200
        payload = imported.json()
        assert payload["total"] == 2
        assert payload["file_type"] == "xlsx"
        assert {item["group_id"] for item in payload["documents"]} == {"10001", "10002"}
        assert all(item["title"] == "导入 FAQ" for item in payload["documents"])
        assert "如何部署 | 使用 Docker Compose" in payload["documents"][0]["content"]

        group_one_docs = client.get("/api/knowledge-docs?group_id=10001", headers=headers)
        assert group_one_docs.status_code == 200
        assert group_one_docs.json()[0]["title"] == "导入 FAQ"
        audit = client.get("/api/audit-logs", headers=headers)
        assert audit.json()[0]["action"] == "knowledge_docs_import"


def test_imported_knowledge_stays_keyword_searchable_when_embedding_fails(tmp_path):
    settings = Settings(
        DATABASE_URL=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        REDIS_URL="",
        ADMIN_USERNAME="admin",
        ADMIN_PASSWORD="secret",
        EMBEDDING_PROVIDER="openai_compatible",
        EMBEDDING_API_KEY="",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        token = client.post(
            "/api/auth/login", json={"username": "admin", "password": "secret"}
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        client.patch("/api/groups/10001", json={"name": "Docs"}, headers=headers)

        imported = client.post(
            "/api/knowledge-docs/import",
            data={
                "title": "Deploy FAQ",
                "group_ids": json.dumps(["10001"]),
                "enabled": "true",
            },
            files={
                "file": (
                    "faq.xlsx",
                    build_xlsx_bytes(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
            headers=headers,
        )

        assert imported.status_code == 200
        document = imported.json()["documents"][0]
        assert document["chunk_count"] >= 1
        assert document["index_status"] == "completed"
        assert "embedding api key is not configured" in document["index_error"]

        searched = client.post(
            "/api/knowledge-search",
            json={"group_id": "10001", "query": "Docker"},
            headers=headers,
        )
        assert searched.status_code == 200
        results = searched.json()["results"]
        assert results[0]["title"] == "Deploy FAQ"
        assert "Docker Compose" in results[0]["content"]


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
        assert payload["index_status"] == "vectorized"
        assert payload["chunk_count"] >= 1
        audit = client.get("/api/audit-logs", headers=headers)
        assert audit.json()[0]["action"] == "knowledge_doc_reindex"
        history = client.get("/api/knowledge-docs/reindex-runs?group_id=10001", headers=headers)
        assert history.status_code == 200
        assert history.json()[0]["action"] == "knowledge_doc_reindex"
        assert history.json()[0]["total"] == 1
        assert history.json()[0]["succeeded"] == 1
        assert history.json()[0]["failed"] == 0


def test_knowledge_docs_can_be_bulk_reindexed_and_retry_failed_from_admin(tmp_path):
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

        first = client.post(
            "/api/knowledge-docs",
            json={
                "group_id": "10001",
                "title": "FAQ 1",
                "content": "第一篇知识。",
                "enabled": True,
            },
            headers=headers,
        ).json()
        second = client.post(
            "/api/knowledge-docs",
            json={
                "group_id": "10001",
                "title": "FAQ 2",
                "content": "第二篇知识。",
                "enabled": True,
            },
            headers=headers,
        ).json()
        client.patch(
            f"/api/knowledge-docs/{second['id']}",
            json={"content": "第二篇知识更新。"},
            headers=headers,
        )

        bulk = client.post(
            "/api/knowledge-docs/reindex",
            json={"group_id": "10001", "only_failed": False, "limit": 10},
            headers=headers,
        )

        assert bulk.status_code == 200
        payload = bulk.json()
        assert payload["total"] == 2
        assert payload["succeeded"] == 2
        assert payload["failed"] == 0
        assert {item["id"] for item in payload["results"]} == {first["id"], second["id"]}

        failed_list = client.get(
            "/api/knowledge-docs?group_id=10001&index_status=failed",
            headers=headers,
        )
        assert failed_list.status_code == 200
        assert failed_list.json() == []

        retry_failed = client.post(
            "/api/knowledge-docs/reindex",
            json={"group_id": "10001", "only_failed": True, "limit": 10},
            headers=headers,
        )
        assert retry_failed.status_code == 200
        assert retry_failed.json()["total"] == 0

        audit = client.get("/api/audit-logs", headers=headers)
        assert audit.json()[0]["action"] == "knowledge_docs_reindex"
        history = client.get("/api/knowledge-docs/reindex-runs?group_id=10001", headers=headers)
        assert history.status_code == 200
        assert history.json()[0]["action"] == "knowledge_docs_reindex"
        assert history.json()[0]["only_failed"] is True
        assert history.json()[1]["total"] == 2
        assert history.json()[1]["succeeded"] == 2

        queued = client.post(
            "/api/knowledge-docs/reindex-queue",
            json={"group_id": "10001", "only_failed": True, "limit": 10},
            headers=headers,
        )
        assert queued.status_code == 200
        queued_task = queued.json()
        assert queued_task["task_type"] == "knowledge_reindex"
        assert queued_task["group_id"] == "10001"
        assert queued_task["payload"]["only_failed"] is True
        assert queued_task["enabled"] is True

        latest_audit = client.get("/api/audit-logs", headers=headers)
        assert latest_audit.json()[0]["action"] == "knowledge_reindex_queued"


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


def test_skill_settings_and_group_detail_can_be_managed_from_admin(tmp_path):
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

        await_group = client.patch(
            "/api/groups/10001",
            json={
                "enabled": True,
                "reply_mode": "mention_only",
                "name": "测试群",
                "welcome_enabled": True,
                "welcome_message": "欢迎 {user_id}",
                "flood_enabled": True,
                "flood_message_count": 4,
                "flood_window_seconds": 20,
                "flood_mute_seconds": 90,
                "violation_window_hours": 48,
                "escalation_enabled": True,
                "escalation_multiplier": 3,
                "escalation_max_mute_seconds": 900,
            },
            headers=headers,
        )
        global_ai = client.patch(
            "/api/skills/ai",
            json={"enabled": False, "group_id": ""},
            headers=headers,
        )
        group_dice = client.patch(
            "/api/skills/dice",
            json={"enabled": False, "group_id": "10001"},
            headers=headers,
        )
        skills = client.get("/api/skills?group_id=10001", headers=headers)
        detail = client.get("/api/groups/10001", headers=headers)

        assert await_group.status_code == 200
        assert global_ai.status_code == 200
        assert global_ai.json()["effective_enabled"] is False
        assert group_dice.status_code == 200
        assert group_dice.json()["group_enabled"] is False
        assert skills.status_code == 200
        skill_map = {item["skill_name"]: item for item in skills.json()}
        assert skill_map["ai"]["global_enabled"] is False
        assert skill_map["ai"]["effective_enabled"] is False
        assert skill_map["dice"]["group_enabled"] is False
        assert skill_map["dice"]["effective_enabled"] is False
        assert detail.status_code == 200
        assert detail.json()["name"] == "测试群"
        assert detail.json()["moderation"]["welcome_enabled"] is True
        assert detail.json()["moderation"]["welcome_message"] == "欢迎 {user_id}"
        assert detail.json()["moderation"]["flood_message_count"] == 4
        assert detail.json()["moderation"]["flood_mute_seconds"] == 90
        assert detail.json()["moderation"]["violation_window_hours"] == 48
        assert detail.json()["moderation"]["escalation_enabled"] is True
        assert detail.json()["moderation"]["escalation_multiplier"] == 3
        assert detail.json()["moderation"]["escalation_max_mute_seconds"] == 900
        assert "moderation_stats" in detail.json()
        assert "messages" in detail.json()["overview"]
        assert any(item["skill_name"] == "dice" for item in detail.json()["skills"])

        audit = client.get("/api/audit-logs", headers=headers)
        assert audit.json()[0]["action"] == "skill_setting_update"


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
        assert payload["connection_state"] == "online"
        assert payload["activity_state"] == "active"
        assert isinstance(payload["connected_seconds"], int)
        assert isinstance(payload["last_event_age_seconds"], int)
        assert isinstance(payload["last_action_age_seconds"], int)


def test_onebot_status_exposes_offline_recovery_hint(tmp_path):
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

        response = client.get("/api/system/onebot-status", headers=headers)

        assert response.status_code == 200
        payload = response.json()
        assert payload["online"] is False
        assert payload["connection_state"] == "offline"
        assert payload["activity_state"] == "offline"
        assert payload["offline_seconds"] is None
        assert "NapCat" in payload["recovery_hint"]


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


def test_audit_logs_can_be_filtered_for_moderation_history(tmp_path):
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

        client.patch("/api/settings/bot", json={"default_reply_mode": "command_only"}, headers=headers)
        client.patch("/api/groups/10001", json={"enabled": True}, headers=headers)

        all_logs = client.get("/api/audit-logs?limit=2", headers=headers)
        group_logs = client.get("/api/audit-logs?group_id=10001", headers=headers)
        action_logs = client.get("/api/audit-logs?action=group_update", headers=headers)
        target_logs = client.get(
            "/api/audit-logs?target_type=group&target_id=10001",
            headers=headers,
        )

        assert all_logs.status_code == 200
        assert len(all_logs.json()) == 2
        assert group_logs.status_code == 200
        assert all(item["group_id"] == "10001" for item in group_logs.json())
        assert action_logs.status_code == 200
        assert all(item["action"] == "group_update" for item in action_logs.json())
        assert target_logs.status_code == 200
        assert target_logs.json()[0]["target_type"] == "group"
        assert target_logs.json()[0]["target_id"] == "10001"
