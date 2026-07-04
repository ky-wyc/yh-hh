from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.config import Settings


@dataclass(slots=True)
class BotEvent:
    message_id: str
    group_id: str
    user_id: str
    text: str
    raw: dict[str, Any]
    at_bot: bool
    dedup_key: str
    nickname: str = ""


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


def is_at_bot(raw: dict[str, Any], text: str, settings: Settings) -> bool:
    message = raw.get("message")
    if settings.bot_qq and isinstance(message, list):
        return any(
            segment.get("type") == "at"
            and str((segment.get("data") or {}).get("qq")) == settings.bot_qq
            for segment in message
            if isinstance(segment, dict)
        )
    if settings.bot_qq:
        return f"[CQ:at,qq={settings.bot_qq}]" in text
    return any(name and name in text for name in settings.bot_nicknames)


def remove_bot_mentions(text: str, settings: Settings) -> str:
    cleaned = text
    if settings.bot_qq:
        cleaned = re.sub(rf"\[CQ:at,qq={re.escape(settings.bot_qq)}\]", "", cleaned)
    for name in settings.bot_nicknames:
        cleaned = cleaned.replace(name, "")
    return cleaned.strip()


def normalize_group_message(raw: dict[str, Any], settings: Settings) -> BotEvent | None:
    if raw.get("post_type") != "message" or raw.get("message_type") != "group":
        return None
    group_id = str(raw.get("group_id") or "")
    user_id = str(raw.get("user_id") or "")
    message_id = str(raw.get("message_id") or raw.get("time") or "")
    text = extract_text(raw.get("message")).strip()
    if not group_id or not user_id:
        return None
    sender = raw.get("sender") or {}
    dedup_key = f"group:{group_id}:{message_id or raw.get('time')}:{user_id}:{hash(text)}"
    return BotEvent(
        message_id=message_id,
        group_id=group_id,
        user_id=user_id,
        text=text,
        raw=raw,
        at_bot=is_at_bot(raw, text, settings),
        dedup_key=dedup_key,
        nickname=str(sender.get("nickname") or sender.get("card") or ""),
    )

