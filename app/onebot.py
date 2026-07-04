from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from fastapi import WebSocket


@dataclass(slots=True)
class OneBotStatus:
    online: bool = False
    connection_mode: str = "reverse_ws"
    connected_at: datetime | None = None
    disconnected_at: datetime | None = None
    last_error: str = ""


@dataclass(slots=True)
class OneBotConnectionManager:
    status: OneBotStatus = field(default_factory=OneBotStatus)
    websocket: WebSocket | None = None
    sent_actions: list[dict[str, Any]] = field(default_factory=list)

    async def attach(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.websocket = websocket
        self.status.online = True
        self.status.connected_at = datetime.now(UTC)
        self.status.last_error = ""

    def detach(self, error: str = "") -> None:
        self.websocket = None
        self.status.online = False
        self.status.disconnected_at = datetime.now(UTC)
        self.status.last_error = error

    async def send_action(self, action: str, params: dict[str, Any]) -> str:
        echo = str(uuid.uuid4())
        payload = {"action": action, "params": params, "echo": echo}
        self.sent_actions.append(payload)
        if self.websocket is None:
            raise RuntimeError("OneBot reverse WebSocket is not connected.")
        await self.websocket.send_text(json.dumps(payload, ensure_ascii=False))
        return echo

    async def send_group_message(self, group_id: str, message: str) -> None:
        await self.send_action("send_group_msg", {"group_id": int(group_id), "message": message})

    async def send_private_message(self, user_id: str, message: str) -> None:
        await self.send_action("send_private_msg", {"user_id": int(user_id), "message": message})

    async def mute_user(self, group_id: str, user_id: str, duration: int) -> None:
        await self.send_action(
            "set_group_ban",
            {"group_id": int(group_id), "user_id": int(user_id), "duration": duration},
        )


class MemoryOneBotSender:
    def __init__(self):
        self.group_messages: list[tuple[str, str]] = []
        self.private_messages: list[tuple[str, str]] = []

    async def send_group_message(self, group_id: str, message: str) -> None:
        self.group_messages.append((group_id, message))

    async def send_private_message(self, user_id: str, message: str) -> None:
        self.private_messages.append((user_id, message))

    async def mute_user(self, group_id: str, user_id: str, duration: int) -> None:
        self.group_messages.append((group_id, f"mute:{user_id}:{duration}"))


async def websocket_event_stream(websocket: WebSocket):
    while True:
        raw = await websocket.receive_text()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if "post_type" in payload:
            yield payload
        else:
            await asyncio.sleep(0)
