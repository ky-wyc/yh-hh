from __future__ import annotations

import argparse

from scripts.mvp_acceptance import build_commands, first_csv_value


def args(**overrides):
    values = {
        "python": "python",
        "env_file": ".env",
        "base_url": "http://127.0.0.1:8000",
        "ws_url": "ws://127.0.0.1:8000/onebot/ws",
        "admin_username": "",
        "admin_password": "",
        "group_id": "",
        "admin_user_id": "",
        "onebot_access_token": None,
        "expect_cache_backend": "redis",
        "strict_preflight": False,
        "require_onebot_online": False,
        "require_onebot_activity": False,
        "require_mvp_core_logs": False,
        "require_admin_lite": False,
        "require_admin_lite_audit": False,
        "skip_onebot_simulation": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_first_csv_value_returns_first_non_empty_item():
    assert first_csv_value(" ,10001, 10002") == "10001"
    assert first_csv_value("") == ""


def test_acceptance_builds_core_and_admin_lite_commands():
    commands, errors = build_commands(
        args(),
        {
            "ADMIN_USERNAME": "admin",
            "ADMIN_PASSWORD": "secret",
            "ALLOWED_GROUPS": "10001,10002",
            "ADMIN_QQ_IDS": "20001",
            "ONEBOT_ACCESS_TOKEN": "token",
        },
    )

    assert errors == []
    assert commands[0] == ["python", "scripts/preflight_check.py", "--env-file", ".env"]
    assert "--expect-cache-backend" in commands[1]
    assert "mvp-core" in commands[2]
    assert commands[2][-2:] == ["--access-token", "token"]
    assert "admin-lite" in commands[3]


def test_acceptance_requires_group_for_simulation():
    commands, errors = build_commands(
        args(),
        {
            "ADMIN_USERNAME": "admin",
            "ADMIN_PASSWORD": "secret",
            "ALLOWED_GROUPS": "",
        },
    )

    assert commands
    assert "ALLOWED_GROUPS or --group-id is required for OneBot simulation" in errors


def test_acceptance_can_skip_onebot_simulation():
    commands, errors = build_commands(args(skip_onebot_simulation=True), {})

    assert errors == []
    assert len(commands) == 2


def test_acceptance_rejects_online_check_with_simulation():
    commands, errors = build_commands(
        args(require_onebot_online=True),
        {"ALLOWED_GROUPS": "10001"},
    )

    assert commands
    assert any("--require-onebot-online should be used with --skip-onebot-simulation" in error for error in errors)


def test_acceptance_rejects_admin_lite_when_simulation_is_skipped():
    commands, errors = build_commands(
        args(skip_onebot_simulation=True, require_admin_lite=True),
        {"ALLOWED_GROUPS": "10001", "ADMIN_QQ_IDS": "20001"},
    )

    assert commands
    assert any("--require-admin-lite requires simulated OneBot checks" in error for error in errors)


def test_acceptance_can_require_real_onebot_activity():
    commands, errors = build_commands(
        args(require_onebot_online=True, require_onebot_activity=True, skip_onebot_simulation=True),
        {},
    )

    assert errors == []
    assert "--require-onebot-online" in commands[1]
    assert "--require-onebot-activity" in commands[1]


def test_acceptance_can_require_real_admin_lite_audit():
    commands, errors = build_commands(
        args(require_admin_lite_audit=True, skip_onebot_simulation=True),
        {},
    )

    assert errors == []
    assert "--require-admin-lite-audit" in commands[1]


def test_acceptance_rejects_admin_lite_audit_before_simulation():
    commands, errors = build_commands(
        args(require_admin_lite_audit=True),
        {"ALLOWED_GROUPS": "10001"},
    )

    assert commands
    assert any("--require-admin-lite-audit should be used with --skip-onebot-simulation" in error for error in errors)


def test_acceptance_can_require_real_mvp_core_logs():
    commands, errors = build_commands(
        args(require_mvp_core_logs=True, skip_onebot_simulation=True),
        {},
    )

    assert errors == []
    assert "--require-mvp-core-logs" in commands[1]


def test_acceptance_rejects_mvp_core_logs_before_simulation():
    commands, errors = build_commands(
        args(require_mvp_core_logs=True),
        {"ALLOWED_GROUPS": "10001"},
    )

    assert commands
    assert any("--require-mvp-core-logs should be used with --skip-onebot-simulation" in error for error in errors)
