from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time

import websockets


async def run() -> int:
    parser = argparse.ArgumentParser(description="Simulate OneBot reverse WebSocket MVP events.")
    parser.add_argument("--ws-url", default="ws://127.0.0.1:8000/onebot/ws")
    parser.add_argument("--access-token", default="")
    parser.add_argument(
        "--token-mode",
        choices=["bearer", "header", "query"],
        default="bearer",
        help="How to pass access token when --access-token is set.",
    )
    parser.add_argument("--group-id", default="10001")
    parser.add_argument("--user-id", default="20001")
    parser.add_argument(
        "--message-id-base",
        type=int,
        default=0,
        help="Base message_id for simulated events. Defaults to current time in milliseconds.",
    )
    parser.add_argument(
        "--scenario",
        choices=["ping", "mvp-core", "admin-lite", "active-question"],
        default="mvp-core",
        help="Which simulated message set to run.",
    )
    args = parser.parse_args()

    headers = {}
    args.access_token = args.access_token.strip()
    if args.access_token:
        if args.token_mode == "bearer":
            headers["Authorization"] = f"Bearer {args.access_token}"
        elif args.token_mode == "header":
            headers["X-Access-Token"] = args.access_token
        else:
            separator = "&" if "?" in args.ws_url else "?"
            args.ws_url = f"{args.ws_url}{separator}access_token={args.access_token}"

    scenarios = {
        "ping": [("/ping", "pong")],
        "mvp-core": [
            ("/ping", "pong"),
            ("/help", "可用命令"),
            ("/dice 2d6", "总和"),
            ("/ai hello", "API Key"),
        ],
        "admin-lite": [
            ("/warn @someone noisy", "已记录警告"),
            ("/banword add smoke_ad blocked smoke_ad", "已添加关键词"),
            ("this message has smoke_ad", "blocked smoke_ad"),
        ],
        "active-question": [
            ("今天适合做什么？", "API Key"),
        ],
    }
    message_id_base = args.message_id_base or int(time.time() * 1000)

    async with websockets.connect(args.ws_url, additional_headers=headers or None) as websocket:
        for index, (message, expected_text) in enumerate(scenarios[args.scenario], start=1):
            await websocket.send(
                json.dumps(
                    {
                        "post_type": "message",
                        "message_type": "group",
                        "message_id": message_id_base + index,
                        "group_id": int(args.group_id),
                        "user_id": int(args.user_id),
                        "message": message,
                    },
                    ensure_ascii=False,
                )
            )
            raw = await asyncio.wait_for(websocket.recv(), timeout=10)
            payload = json.loads(raw)
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            assert payload["action"] == "send_group_msg"
            assert expected_text in payload["params"]["message"]
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
