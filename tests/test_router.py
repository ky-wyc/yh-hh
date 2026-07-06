from __future__ import annotations

import json

import httpx

from app.events import normalize_group_message
from app.llm import LLMService
from app.models import User
from app.router import MessageRouter


class FailingSender:
    async def send_group_message(self, group_id: str, message: str) -> None:
        raise RuntimeError("send failed")


def group_event(text: str, *, group_id: str = "10001", user_id: str = "20001", message_id: int = 1):
    return {
        "post_type": "message",
        "message_type": "group",
        "message_id": message_id,
        "group_id": int(group_id),
        "user_id": int(user_id),
        "message": text,
        "sender": {"nickname": "tester"},
    }


def group_segment_event(message, *, group_id: str = "10001", user_id: str = "20001", message_id: int = 1):
    return {
        "post_type": "message",
        "message_type": "group",
        "message_id": message_id,
        "group_id": int(group_id),
        "user_id": int(user_id),
        "message": message,
        "sender": {"nickname": "tester"},
    }


def group_event_with_self_id(
    text: str,
    *,
    self_id: str = "123456",
    user_id: str = "123456",
    message_id: int = 25,
):
    return {
        "post_type": "message",
        "message_type": "group",
        "self_id": int(self_id),
        "message_id": message_id,
        "group_id": 10001,
        "user_id": int(user_id),
        "message": text,
        "sender": {"nickname": "tester"},
    }


async def test_ping_replies_without_llm(settings, repo, message_router, sender):
    event = normalize_group_message(group_event("/ping"), settings)

    outcome = await message_router.handle(event, repo, sender)

    assert outcome.replied is True
    assert sender.group_messages == [("10001", "pong")]
    assert outcome.skill_name == "ping"


async def test_group_whitelist_drops_message(settings, repo, message_router, sender):
    event = normalize_group_message(group_event("/ping", group_id="99999"), settings)

    outcome = await message_router.handle(event, repo, sender)

    assert outcome.replied is False
    assert outcome.reason == "group_not_allowed"
    assert sender.group_messages == []
    assert await repo.get_groups() == []


async def test_runtime_allowed_groups_from_admin_settings(settings, repo, message_router, sender):
    message_router.settings.allowed_groups_raw = ""
    await repo.update_bot_settings({"allowed_groups": "10001"})
    allowed = normalize_group_message(group_event("/ping", group_id="10001", message_id=101), settings)
    denied = normalize_group_message(group_event("/ping", group_id="99999", message_id=102), settings)

    allowed_outcome = await message_router.handle(allowed, repo, sender)
    denied_outcome = await message_router.handle(denied, repo, sender)

    assert allowed_outcome.status == "handled"
    assert denied_outcome.status == "dropped"
    assert denied_outcome.reason == "group_not_allowed"
    assert sender.group_messages == [("10001", "pong")]


async def test_disabled_group_does_not_reply(settings, repo, message_router, sender):
    await repo.update_group("10001", enabled=False)
    event = normalize_group_message(group_event("/ping", message_id=11), settings)

    outcome = await message_router.handle(event, repo, sender)

    assert outcome.replied is False
    assert outcome.reason == "group_disabled"
    assert sender.group_messages == []


async def test_disabled_reply_mode_does_not_reply(settings, repo, message_router, sender):
    await repo.update_group("10001", reply_mode="disabled")
    event = normalize_group_message(group_event("/ping", message_id=14), settings)

    outcome = await message_router.handle(event, repo, sender)

    errors = await repo.recent_errors()
    assert outcome.replied is False
    assert outcome.reason == "reply_mode_disabled"
    assert sender.group_messages == []
    assert errors[0].drop_reason == "reply_mode_disabled"


async def test_duplicate_event_does_not_reply_twice(settings, repo, message_router, sender):
    event = normalize_group_message(group_event("/ping", message_id=10), settings)

    first = await message_router.handle(event, repo, sender)
    second = await message_router.handle(event, repo, sender)

    assert first.replied is True
    assert second.reason == "duplicate"
    assert sender.group_messages == [("10001", "pong")]


async def test_send_failure_is_logged_as_error(settings, repo, message_router):
    event = normalize_group_message(group_event("/ping", message_id=13), settings)

    outcome = await message_router.handle(event, repo, FailingSender())

    errors = await repo.recent_errors()
    assert outcome.status == "error"
    assert outcome.reason == "send_failed"
    assert errors[0].status == "error"
    assert errors[0].drop_reason == "send_failed:RuntimeError"


async def test_ai_without_api_key_has_clear_error(settings, repo, message_router, sender):
    event = normalize_group_message(group_event("/ai hello", message_id=2), settings)

    outcome = await message_router.handle(event, repo, sender)

    assert outcome.replied is True
    assert "API Key" in sender.group_messages[0][1]


async def test_mention_only_replies_to_at_bot(settings, repo, message_router, sender):
    event = normalize_group_message(
        group_segment_event(
            [
                {"type": "at", "data": {"qq": "123456"}},
                {"type": "text", "data": {"text": " hello"}},
            ],
            message_id=15,
        ),
        settings,
    )

    outcome = await message_router.handle(event, repo, sender)

    assert outcome.replied is True
    assert outcome.skill_name == "ai"
    assert "API Key" in sender.group_messages[0][1]


async def test_runtime_bot_qq_detects_cq_at(settings, repo, message_router, sender):
    message_router.settings.bot_qq = ""
    await repo.update_bot_settings({"bot_qq": "888001"})
    event = normalize_group_message(
        group_event("[CQ:at,qq=888001] hello", message_id=26),
        settings,
    )

    outcome = await message_router.handle(event, repo, sender)

    assert event.at_bot is False
    assert outcome.replied is True
    assert outcome.skill_name == "ai"
    assert "API Key" in sender.group_messages[0][1]


async def test_runtime_bot_nickname_triggers_mention_reply(settings, repo, message_router, sender):
    await repo.update_bot_settings({"bot_nicknames": "小灵"})
    event = normalize_group_message(group_event("小灵 你能做什么？", message_id=27), settings)

    outcome = await message_router.handle(event, repo, sender)

    assert event.at_bot is False
    assert outcome.replied is True
    assert outcome.skill_name == "ai"
    assert "API Key" in sender.group_messages[0][1]


async def test_command_only_does_not_reply_to_at_bot(settings, repo, message_router, sender):
    await repo.update_group("10001", reply_mode="command_only")
    event = normalize_group_message(
        group_segment_event(
            [
                {"type": "at", "data": {"qq": "123456"}},
                {"type": "text", "data": {"text": " hello"}},
            ],
            message_id=16,
        ),
        settings,
    )

    outcome = await message_router.handle(event, repo, sender)

    assert outcome.replied is False
    assert outcome.reason == "no_trigger"
    assert sender.group_messages == []


async def test_bot_self_message_is_dropped(settings, repo, message_router, sender):
    event = normalize_group_message(group_event("/ping", user_id="123456", message_id=21), settings)

    outcome = await message_router.handle(event, repo, sender)

    assert outcome.replied is False
    assert outcome.reason == "bot_self_message"
    assert sender.group_messages == []
    assert await repo.get_groups() == []


async def test_bot_self_message_is_dropped_using_onebot_self_id(repo, message_router, sender):
    message_router.settings.bot_qq = ""
    event = normalize_group_message(group_event_with_self_id("/ping"), message_router.settings)

    outcome = await message_router.handle(event, repo, sender)

    assert outcome.replied is False
    assert outcome.reason == "bot_self_message"
    assert sender.group_messages == []
    assert await repo.get_groups() == []


async def test_active_mode_replies_to_plain_question(settings, repo, message_router, sender):
    await repo.update_group("10001", reply_mode="active")
    event = normalize_group_message(group_event("今天适合做什么？", message_id=22), settings)

    outcome = await message_router.handle(event, repo, sender)

    assert outcome.replied is True
    assert outcome.skill_name == "ai"
    assert "API Key" in sender.group_messages[0][1]


async def test_active_mode_observes_plain_statement(settings, repo, message_router, sender):
    await repo.update_group("10001", reply_mode="active")
    event = normalize_group_message(group_event("今天继续推进项目", message_id=23), settings)

    outcome = await message_router.handle(event, repo, sender)

    assert outcome.replied is False
    assert outcome.reason == "no_trigger"
    assert sender.group_messages == []


async def test_ai_success_uses_openai_compatible_endpoint(settings, repo, message_router, sender):
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer test-key"
        payload = json.loads((await request.aread()).decode("utf-8"))
        assert "tester: /ai hello" in payload["messages"][1]["content"]
        assert "当前问题：hello" in payload["messages"][1]["content"]
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "hello from model"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3},
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://llm.test")
    llm = LLMService(client)
    router = MessageRouter(settings, llm, message_router.rate_limiter)
    await repo.update_llm_config(
        {
            "base_url": "https://llm.test/v1",
            "api_key": "test-key",
            "model": "test-model",
        }
    )
    event = normalize_group_message(group_event("/ai hello", message_id=12), settings)

    outcome = await router.handle(event, repo, sender)

    await client.aclose()
    assert outcome.replied is True
    assert sender.group_messages == [("10001", "hello from model")]


async def test_ai_system_prompt_uses_runtime_bot_nickname(settings, repo, message_router, sender):
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads((await request.aread()).decode("utf-8"))
        system_prompt = payload["messages"][0]["content"]
        assert "你的名字是「小灵」" in system_prompt
        assert "群友也可能用这些名字称呼你：小灵、小Q" in system_prompt
        assert "不要自称“机器人”“AI”“语言模型”" in system_prompt
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "我是小灵。"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3},
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://llm.test")
    llm = LLMService(client)
    router = MessageRouter(settings, llm, message_router.rate_limiter)
    await repo.update_bot_settings({"bot_nicknames": "小灵,小Q"})
    await repo.update_llm_config(
        {
            "base_url": "https://llm.test/v1",
            "api_key": "test-key",
            "model": "test-model",
        }
    )
    event = normalize_group_message(group_event("/ai 你是谁", message_id=29), settings)

    outcome = await router.handle(event, repo, sender)

    await client.aclose()
    assert outcome.replied is True
    assert sender.group_messages == [("10001", "我是小灵。")]


async def test_ai_only_uses_approved_memories(settings, repo, message_router, sender):
    await repo.create_memory(
        group_id="10001",
        user_id="20001",
        content="用户喜欢回答里带项目编号 A-17",
        source="admin",
        status="approved",
        created_by="admin",
    )
    await repo.create_memory(
        group_id="10001",
        user_id="20001",
        content="这条待审核记忆不能参与回答",
        source="user_command",
        status="pending",
        created_by="20001",
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads((await request.aread()).decode("utf-8"))
        user_prompt = payload["messages"][1]["content"]
        assert "已确认记忆" in user_prompt
        assert "用户喜欢回答里带项目编号 A-17" in user_prompt
        assert "这条待审核记忆不能参与回答" not in user_prompt
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "A-17 已收到。"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3},
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://llm.test")
    llm = LLMService(client)
    router = MessageRouter(settings, llm, message_router.rate_limiter)
    await repo.update_llm_config(
        {
            "base_url": "https://llm.test/v1",
            "api_key": "test-key",
            "model": "test-model",
        }
    )
    event = normalize_group_message(group_event("/ai 记得我的偏好吗", message_id=32), settings)

    outcome = await router.handle(event, repo, sender)

    await client.aclose()
    assert outcome.replied is True
    assert sender.group_messages == [("10001", "A-17 已收到。")]


async def test_dice_does_not_call_llm(settings, repo, message_router, sender):
    event = normalize_group_message(group_event("/dice 2d6", message_id=3), settings)

    outcome = await message_router.handle(event, repo, sender)

    assert outcome.replied is True
    assert outcome.skill_name == "dice"
    assert "总和" in sender.group_messages[0][1]


async def test_ordinary_user_cannot_warn(settings, repo, message_router, sender):
    event = normalize_group_message(group_event("/warn @someone noisy", message_id=4), settings)

    outcome = await message_router.handle(event, repo, sender)

    assert outcome.replied is True
    assert "权限不足" in sender.group_messages[0][1]


async def test_admin_qq_ids_can_run_admin_lite_commands(repo, message_router, sender):
    message_router.settings.admin_qq_ids_raw = "20001"
    event = normalize_group_message(
        group_event("/warn @someone noisy", message_id=20),
        message_router.settings,
    )

    outcome = await message_router.handle(event, repo, sender)

    assert outcome.replied is True
    assert sender.group_messages == [("10001", "已记录警告：@someone noisy")]
    audit_logs = await repo.recent_audit_logs()
    assert audit_logs[0].action == "warn"
    assert audit_logs[0].actor_user_id == "20001"
    assert audit_logs[0].actor_role == "super_admin"


async def test_runtime_admin_qq_ids_from_admin_settings(settings, repo, message_router, sender):
    message_router.settings.admin_qq_ids_raw = ""
    await repo.update_bot_settings({"admin_qq_ids": "20001"})
    event = normalize_group_message(
        group_event("/warn @someone noisy", message_id=28),
        settings,
    )

    outcome = await message_router.handle(event, repo, sender)

    assert outcome.replied is True
    assert sender.group_messages == [("10001", "已记录警告：@someone noisy")]
    audit_logs = await repo.recent_audit_logs()
    assert audit_logs[0].action == "warn"
    assert audit_logs[0].actor_role == "super_admin"


async def test_admin_can_add_keyword_and_keyword_hit_replies(settings, repo, message_router, sender):
    admin = User(qq_id="20001", role="group_admin")
    repo.session.add(admin)
    await repo.session.flush()

    add_event = normalize_group_message(group_event("/banword add spam 请不要发广告", message_id=5), settings)
    hit_event = normalize_group_message(group_event("this is spam", message_id=6), settings)

    add = await message_router.handle(add_event, repo, sender)
    hit = await message_router.handle(hit_event, repo, sender)

    assert add.replied is True
    assert hit.replied is True
    assert sender.group_messages[-1] == ("10001", "请不要发广告")


async def test_admin_can_update_existing_keyword_rule(settings, repo, message_router, sender):
    admin = User(qq_id="20001", role="group_admin")
    repo.session.add(admin)
    await repo.session.flush()

    first_add = normalize_group_message(
        group_event("/banword add spam 第一条回复", message_id=17), settings
    )
    second_add = normalize_group_message(
        group_event("/banword add spam 第二条回复", message_id=18), settings
    )
    hit_event = normalize_group_message(group_event("spam again", message_id=19), settings)

    await message_router.handle(first_add, repo, sender)
    await message_router.handle(second_add, repo, sender)
    hit = await message_router.handle(hit_event, repo, sender)

    assert hit.replied is True
    assert sender.group_messages[-1] == ("10001", "第二条回复")


async def test_remember_command_creates_pending_memory(settings, repo, message_router, sender):
    event = normalize_group_message(group_event("/remember 我喜欢简短回答", message_id=30), settings)

    outcome = await message_router.handle(event, repo, sender)
    memories = await repo.list_memories_for_admin()

    assert outcome.replied is True
    assert outcome.skill_name == "memory"
    assert "已记录为待审核记忆" in sender.group_messages[0][1]
    assert len(memories) == 1
    assert memories[0].content == "我喜欢简短回答"
    assert memories[0].status == "pending"
    assert memories[0].group_id == "10001"
    assert memories[0].user_id == "20001"
    assert memories[0].source == "user_command"


async def test_forget_command_deletes_own_memory(settings, repo, message_router, sender):
    memory = await repo.create_memory(
        group_id="10001",
        user_id="20001",
        content="我喜欢简短回答",
        source="user_command",
        status="approved",
        created_by="20001",
    )
    event = normalize_group_message(group_event(f"/forget {memory.id}", message_id=31), settings)

    outcome = await message_router.handle(event, repo, sender)
    memories = await repo.list_memories_for_admin()

    assert outcome.replied is True
    assert outcome.skill_name == "memory"
    assert "已删除记忆" in sender.group_messages[0][1]
    assert memories[0].status == "deleted"


async def test_configured_command_prefix_is_used_for_routing(settings, repo, message_router, sender):
    await repo.update_bot_settings({"command_prefix": "!"})
    event = normalize_group_message(group_event("!ping", message_id=7), settings)

    outcome = await message_router.handle(event, repo, sender)

    assert outcome.replied is True
    assert sender.group_messages == [("10001", "pong")]


async def test_help_uses_configured_command_prefix(settings, repo, message_router, sender):
    await repo.update_bot_settings({"command_prefix": "!"})
    event = normalize_group_message(group_event("!help", message_id=24), settings)

    outcome = await message_router.handle(event, repo, sender)

    assert outcome.replied is True
    assert "!ping" in sender.group_messages[0][1]
    assert "/ping" not in sender.group_messages[0][1]
