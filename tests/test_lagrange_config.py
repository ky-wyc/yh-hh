from __future__ import annotations

from pathlib import Path

from scripts.prepare_lagrange_config import render_config


def test_render_lagrange_config_from_env(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "BOT_QQ=123456",
                "ONEBOT_REVERSE_WS_URL=ws://bot-app:8000/onebot/ws",
                "ONEBOT_ACCESS_TOKEN=secret",
                "LAGRANGE_SIGN_SERVER_URL=https://sign.example/api/sign/30366",
                "LAGRANGE_SIGN_PROXY_URL=http://proxy.example:8080",
                "LAGRANGE_MUSIC_SIGN_SERVER_URL=https://music-sign.example",
            ]
        ),
        encoding="utf-8",
    )
    template = Path("deploy/lagrange/appsettings.example.json")

    config = render_config(template, env_path)

    assert config["Account"]["Uin"] == 123456
    reverse_ws = config["Implementations"][0]
    assert reverse_ws["Host"] == "bot-app"
    assert reverse_ws["Port"] == 8000
    assert reverse_ws["Suffix"] == "/onebot/ws"
    assert reverse_ws["AccessToken"] == "secret"
    assert config["SignServerUrl"] == "https://sign.example/api/sign/30366"
    assert config["SignProxyUrl"] == "http://proxy.example:8080"
    assert config["MusicSignServerUrl"] == "https://music-sign.example"
