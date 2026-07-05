from __future__ import annotations

import pytest

from app.onebot import OneBotConnectionManager


class FailingWebSocket:
    async def accept(self) -> None:
        return None

    async def send_text(self, text: str) -> None:
        raise RuntimeError("connection closed")


class DummyWebSocket:
    async def accept(self) -> None:
        return None

    async def send_text(self, text: str) -> None:
        return None


@pytest.mark.asyncio
async def test_onebot_send_failure_updates_connection_status():
    manager = OneBotConnectionManager()
    await manager.attach(FailingWebSocket())

    with pytest.raises(RuntimeError):
        await manager.send_group_message("10001", "pong")

    assert manager.status.online is False
    assert manager.status.disconnected_at is not None
    assert manager.status.last_error == "send_action_failed:RuntimeError"


@pytest.mark.asyncio
async def test_onebot_send_without_connection_records_error():
    manager = OneBotConnectionManager()

    with pytest.raises(RuntimeError):
        await manager.send_group_message("10001", "pong")

    assert manager.status.online is False
    assert manager.status.last_error == "OneBot reverse WebSocket is not connected."


@pytest.mark.asyncio
async def test_old_onebot_disconnect_does_not_mark_new_connection_offline():
    manager = OneBotConnectionManager()
    old_socket = DummyWebSocket()
    new_socket = DummyWebSocket()

    await manager.attach(old_socket)
    await manager.attach(new_socket)
    manager.detach("old disconnected", websocket=old_socket)

    assert manager.websocket is new_socket
    assert manager.status.online is True
    assert manager.status.last_error == ""


@pytest.mark.asyncio
async def test_current_onebot_disconnect_marks_offline():
    manager = OneBotConnectionManager()
    websocket = DummyWebSocket()

    await manager.attach(websocket)
    manager.detach("closed", websocket=websocket)

    assert manager.websocket is None
    assert manager.status.online is False
    assert manager.status.disconnected_at is not None
    assert manager.status.last_error == "closed"


@pytest.mark.asyncio
async def test_onebot_sent_action_history_is_bounded():
    manager = OneBotConnectionManager(max_sent_actions=3)
    websocket = DummyWebSocket()
    await manager.attach(websocket)

    for index in range(5):
        await manager.send_group_message("10001", f"message {index}")

    assert len(manager.sent_actions) == 3
    assert [item["params"]["message"] for item in manager.sent_actions] == [
        "message 2",
        "message 3",
        "message 4",
    ]


@pytest.mark.asyncio
async def test_onebot_status_tracks_event_and_action_timestamps():
    manager = OneBotConnectionManager()
    websocket = DummyWebSocket()
    await manager.attach(websocket)

    manager.record_event()
    await manager.send_group_message("10001", "pong")

    assert manager.status.last_event_at is not None
    assert manager.status.last_action_at is not None
