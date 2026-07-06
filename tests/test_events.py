from __future__ import annotations

from app.config import Settings
from app.events import (
    extract_text,
    normalize_group_message,
    normalize_group_notice,
    normalize_private_message,
    remove_bot_mentions,
)


def group_event(message, *, message_id: int = 1):
    return {
        "post_type": "message",
        "message_type": "group",
        "message_id": message_id,
        "group_id": 10001,
        "user_id": 20001,
        "message": message,
        "sender": {"nickname": "tester"},
    }


def group_event_with_self_id(message, *, self_id: int = 123456, user_id: int = 20001):
    return {
        "post_type": "message",
        "message_type": "group",
        "self_id": self_id,
        "message_id": 1,
        "group_id": 10001,
        "user_id": user_id,
        "message": message,
        "sender": {"nickname": "tester"},
    }


def group_event_without_message_id(message, *, message_seq: int = 1):
    return {
        "post_type": "message",
        "message_type": "group",
        "message_seq": message_seq,
        "time": 100,
        "group_id": 10001,
        "user_id": 20001,
        "message": message,
        "sender": {"nickname": "tester"},
    }


def private_event(message, *, message_id: int = 1):
    return {
        "post_type": "message",
        "message_type": "private",
        "message_id": message_id,
        "user_id": 20001,
        "message": message,
        "sender": {"nickname": "private-tester"},
    }


def test_dedup_key_uses_stable_text_digest():
    settings = Settings(DATABASE_URL="sqlite+aiosqlite:///:memory:", REDIS_URL="")
    first = normalize_group_message(group_event("/ping"), settings)
    second = normalize_group_message(group_event("/ping"), settings)
    changed_text = normalize_group_message(group_event("/help"), settings)

    assert first is not None
    assert second is not None
    assert changed_text is not None
    assert first.dedup_key == second.dedup_key
    assert first.dedup_key != changed_text.dedup_key
    assert "ping" not in first.dedup_key


def test_dedup_key_uses_message_sequence_when_message_id_is_missing():
    settings = Settings(DATABASE_URL="sqlite+aiosqlite:///:memory:", REDIS_URL="")
    first = normalize_group_message(group_event_without_message_id("/ping", message_seq=1001), settings)
    second = normalize_group_message(
        group_event_without_message_id("/ping", message_seq=1002),
        settings,
    )

    assert first is not None
    assert second is not None
    assert first.message_id == "1001"
    assert second.message_id == "1002"
    assert first.dedup_key != second.dedup_key


def test_extract_text_and_remove_bot_mentions_from_segments():
    settings = Settings(
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        REDIS_URL="",
        BOT_QQ="123456",
    )
    text = extract_text(
        [
            {"type": "at", "data": {"qq": "123456"}},
            {"type": "text", "data": {"text": " hello"}},
        ]
    )

    assert text == "[CQ:at,qq=123456] hello"
    assert remove_bot_mentions(text, settings) == "hello"


def test_at_bot_can_use_onebot_self_id_when_bot_qq_is_not_configured():
    settings = Settings(DATABASE_URL="sqlite+aiosqlite:///:memory:", REDIS_URL="", BOT_QQ="")
    event = normalize_group_message(
        group_event_with_self_id(
            [
                {"type": "at", "data": {"qq": "123456"}},
                {"type": "text", "data": {"text": " hello"}},
            ]
        ),
        settings,
    )

    assert event is not None
    assert event.self_id == "123456"
    assert event.at_bot is True
    assert remove_bot_mentions(event.text, settings, event.self_id) == "hello"


def test_normalize_group_message_ignores_empty_or_non_text_messages():
    settings = Settings(DATABASE_URL="sqlite+aiosqlite:///:memory:", REDIS_URL="")

    assert normalize_group_message(group_event("   "), settings) is None
    assert (
        normalize_group_message(
            group_event(
                [
                    {"type": "image", "data": {"file": "a.jpg"}},
                    {"type": "face", "data": {"id": "14"}},
                ]
            ),
            settings,
        )
        is None
    )


def test_normalize_group_increase_notice():
    event = normalize_group_notice(
        {
            "post_type": "notice",
            "notice_type": "group_increase",
            "sub_type": "approve",
            "group_id": 10001,
            "user_id": 20002,
            "operator_id": 30003,
        }
    )

    assert event is not None
    assert event.group_id == "10001"
    assert event.user_id == "20002"
    assert event.operator_id == "30003"


def test_normalize_private_message():
    settings = Settings(DATABASE_URL="sqlite+aiosqlite:///:memory:", REDIS_URL="")
    event = normalize_private_message(private_event("/ping"), settings)

    assert event is not None
    assert event.message_type == "private"
    assert event.group_id == ""
    assert event.user_id == "20001"
    assert event.text == "/ping"
    assert event.dedup_key.startswith("private:")
