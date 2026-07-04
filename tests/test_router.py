from __future__ import annotations

from app.events import normalize_group_message
from app.models import User


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


async def test_duplicate_event_does_not_reply_twice(settings, repo, message_router, sender):
    event = normalize_group_message(group_event("/ping", message_id=10), settings)

    first = await message_router.handle(event, repo, sender)
    second = await message_router.handle(event, repo, sender)

    assert first.replied is True
    assert second.reason == "duplicate"
    assert sender.group_messages == [("10001", "pong")]


async def test_ai_without_api_key_has_clear_error(settings, repo, message_router, sender):
    event = normalize_group_message(group_event("/ai hello", message_id=2), settings)

    outcome = await message_router.handle(event, repo, sender)

    assert outcome.replied is True
    assert "API Key" in sender.group_messages[0][1]


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

