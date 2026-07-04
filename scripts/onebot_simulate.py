from __future__ import annotations

import argparse
import asyncio
import json
import sys

import websockets


async def run() -> int:
    parser = argparse.ArgumentParser(description="Simulate OneBot reverse WebSocket /ping event.")
    parser.add_argument("--ws-url", default="ws://127.0.0.1:8000/onebot/ws")
    parser.add_argument("--access-token", default="")
    parser.add_argument("--group-id", default="10001")
    parser.add_argument("--user-id", default="20001")
    args = parser.parse_args()

    headers = {}
    if args.access_token:
        headers["Authorization"] = f"Bearer {args.access_token}"

    async with websockets.connect(args.ws_url, additional_headers=headers or None) as websocket:
        await websocket.send(
            json.dumps(
                {
                    "post_type": "message",
                    "message_type": "group",
                    "message_id": 1,
                    "group_id": int(args.group_id),
                    "user_id": int(args.user_id),
                    "message": "/ping",
                },
                ensure_ascii=False,
            )
        )
        raw = await asyncio.wait_for(websocket.recv(), timeout=10)
        payload = json.loads(raw)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        assert payload["action"] == "send_group_msg"
        assert payload["params"]["message"] == "pong"
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))

