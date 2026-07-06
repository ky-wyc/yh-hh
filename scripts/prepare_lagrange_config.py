from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

from dotenv import dotenv_values


def _int_or_zero(value: str | None) -> int:
    if not value:
        return 0
    value = value.strip()
    return int(value) if value.isdigit() else 0


def _reverse_ws_parts(url: str) -> tuple[str, int, str]:
    parsed = urlparse(url)
    if parsed.scheme not in {"ws", "wss"}:
        raise ValueError("ONEBOT_REVERSE_WS_URL must start with ws:// or wss://")
    if not parsed.hostname:
        raise ValueError("ONEBOT_REVERSE_WS_URL must include a host")
    default_port = 443 if parsed.scheme == "wss" else 80
    return parsed.hostname, parsed.port or default_port, parsed.path or "/onebot/ws"


def render_config(template_path: Path, env_path: Path) -> dict:
    env = dotenv_values(env_path)
    config = json.loads(template_path.read_text(encoding="utf-8"))

    bot_qq = str(env.get("BOT_QQ") or "").strip()
    if bot_qq:
        config.setdefault("Account", {})["Uin"] = _int_or_zero(bot_qq)

    sign_server_url = str(env.get("LAGRANGE_SIGN_SERVER_URL") or "").strip()
    if sign_server_url:
        config["SignServerUrl"] = sign_server_url

    sign_proxy_url = str(env.get("LAGRANGE_SIGN_PROXY_URL") or "").strip()
    if sign_proxy_url:
        config["SignProxyUrl"] = sign_proxy_url

    music_sign_server_url = str(env.get("LAGRANGE_MUSIC_SIGN_SERVER_URL") or "").strip()
    if music_sign_server_url:
        config["MusicSignServerUrl"] = music_sign_server_url

    ws_url = str(env.get("ONEBOT_REVERSE_WS_URL") or "ws://bot-app:8000/onebot/ws").strip()
    host, port, suffix = _reverse_ws_parts(ws_url)
    access_token = str(env.get("ONEBOT_ACCESS_TOKEN") or "").strip()

    implementations = config.setdefault("Implementations", [])
    reverse_ws = None
    for implementation in implementations:
        if implementation.get("Type") == "ReverseWebSocket":
            reverse_ws = implementation
            break
    if reverse_ws is None:
        reverse_ws = {"Type": "ReverseWebSocket"}
        implementations.append(reverse_ws)

    reverse_ws["Host"] = host
    reverse_ws["Port"] = port
    reverse_ws["Suffix"] = suffix
    reverse_ws["AccessToken"] = access_token

    return config


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Lagrange.OneBot appsettings.json.")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--template", default="deploy/lagrange/appsettings.example.json")
    parser.add_argument("--output", default="data/onebot/appsettings.json")
    args = parser.parse_args()

    env_path = Path(args.env_file)
    template_path = Path(args.template)
    output_path = Path(args.output)
    config = render_config(template_path, env_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
