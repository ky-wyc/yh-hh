from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from app.config import Settings


@dataclass(slots=True)
class BotEvent:
    message_id: str
    group_id: str
    user_id: str
    self_id: str
    text: str
    raw: dict[str, Any]
    at_bot: bool
    dedup_key: str
    message_type: str = "group"
    nickname: str = ""


@dataclass(slots=True)
class GroupNoticeEvent:
    notice_type: str
    sub_type: str
    group_id: str
    user_id: str
    operator_id: str
    raw: dict[str, Any]


def extract_text(message: Any) -> str:
    if isinstance(message, str):
        return message
    if not isinstance(message, list):
        return ""
    parts: list[str] = []
    for segment in message:
        if not isinstance(segment, dict):
            continue
        segment_type = segment.get("type")
        data = segment.get("data") or {}
        if segment_type == "text":
            parts.append(str(data.get("text") or ""))
        elif segment_type == "at":
            parts.append(f"[CQ:at,qq={data.get('qq')}]")
    return "".join(parts)


def _raw_value(raw: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = raw.get(key)
        if value not in {None, ""}:
            return str(value)
    return ""


def is_at_bot(raw: dict[str, Any], text: str, settings: Settings) -> bool:
    message = raw.get("message")
    bot_qq = settings.bot_qq or _raw_value(raw, "self_id")
    if bot_qq and isinstance(message, list):
        return any(
            segment.get("type") == "at"
            and str((segment.get("data") or {}).get("qq")) == bot_qq
            for segment in message
            if isinstance(segment, dict)
        )
    if bot_qq:
        return f"[CQ:at,qq={bot_qq}]" in text
    return any(name and name in text for name in settings.bot_nicknames)


def remove_bot_mentions(text: str, settings: Settings, self_id: str = "") -> str:
    cleaned = text
    bot_qq = settings.bot_qq or self_id
    if bot_qq:
        cleaned = re.sub(rf"\[CQ:at,qq={re.escape(bot_qq)}\]", "", cleaned)
    for name in settings.bot_nicknames:
        cleaned = cleaned.replace(name, "")
    return cleaned.strip()


def normalize_group_message(raw: dict[str, Any], settings: Settings) -> BotEvent | None:
    if raw.get("post_type") != "message" or raw.get("message_type") != "group":
        return None
    group_id = str(raw.get("group_id") or "")
    user_id = str(raw.get("user_id") or "")
    self_id = _raw_value(raw, "self_id")
    message_id = _raw_value(raw, "message_id", "message_seq", "real_id", "time")
    text = extract_text(raw.get("message")).strip()
    if not group_id or not user_id or not text:
        return None
    sender = raw.get("sender") or {}
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    dedup_key = f"group:{group_id}:{message_id}:{user_id}:{text_hash}"
    return BotEvent(
        message_id=message_id,
        group_id=group_id,
        user_id=user_id,
        self_id=self_id,
        text=text,
        raw=raw,
        at_bot=is_at_bot(raw, text, settings),
        dedup_key=dedup_key,
        message_type="group",
        nickname=str(sender.get("nickname") or sender.get("card") or ""),
    )


def normalize_private_message(raw: dict[str, Any], settings: Settings) -> BotEvent | None:
    if raw.get("post_type") != "message" or raw.get("message_type") != "private":
        return None
    user_id = str(raw.get("user_id") or "")
    self_id = _raw_value(raw, "self_id")
    message_id = _raw_value(raw, "message_id", "message_seq", "real_id", "time")
    text = extract_text(raw.get("message")).strip()
    if not user_id or not text:
        return None
    sender = raw.get("sender") or {}
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    dedup_key = f"private:{message_id}:{user_id}:{text_hash}"
    return BotEvent(
        message_id=message_id,
        group_id="",
        user_id=user_id,
        self_id=self_id,
        text=text,
        raw=raw,
        at_bot=True,
        dedup_key=dedup_key,
        message_type="private",
        nickname=str(sender.get("nickname") or ""),
    )


def normalize_group_notice(raw: dict[str, Any]) -> GroupNoticeEvent | None:
    if raw.get("post_type") != "notice":
        return None
    notice_type = str(raw.get("notice_type") or "")
    group_id = str(raw.get("group_id") or "")
    user_id = str(raw.get("user_id") or "")
    if notice_type != "group_increase" or not group_id or not user_id:
        return None
    return GroupNoticeEvent(
        notice_type=notice_type,
        sub_type=str(raw.get("sub_type") or ""),
        group_id=group_id,
        user_id=user_id,
        operator_id=str(raw.get("operator_id") or ""),
        raw=raw,
    )
