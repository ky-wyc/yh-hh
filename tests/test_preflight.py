from __future__ import annotations

from pathlib import Path

from scripts.preflight_check import inspect_env


def write_env(path: Path, **overrides: str) -> Path:
    values = {
        "APP_SECRET_KEY": "prod-secret",
        "ADMIN_USERNAME": "admin",
        "ADMIN_PASSWORD": "prod-password",
        "POSTGRES_DB": "qqbot",
        "POSTGRES_USER": "qqbot",
        "POSTGRES_PASSWORD": "prod-postgres-password",
        "DATABASE_URL": "postgresql+asyncpg://qqbot:prod-postgres-password@postgres:5432/qqbot",
        "REDIS_URL": "redis://redis:6379/0",
        "ALLOWED_GROUPS": "10001",
        "BOT_QQ": "123456",
        "ADMIN_QQ_IDS": "123456",
        "LLM_API_KEY": "key",
        "LLM_MODEL": "model",
        "ONEBOT_REVERSE_WS_URL": "ws://bot-app:8000/onebot/ws",
    }
    values.update(overrides)
    path.write_text("\n".join(f"{key}={value}" for key, value in values.items()), encoding="utf-8")
    return path


def test_preflight_accepts_complete_env(tmp_path):
    env_path = write_env(tmp_path / ".env")

    errors, warnings = inspect_env(env_path)

    assert errors == []
    assert warnings == []


def test_preflight_rejects_default_passwords(tmp_path):
    env_path = write_env(tmp_path / ".env", ADMIN_PASSWORD="change-me")

    errors, warnings = inspect_env(env_path)

    assert any("ADMIN_PASSWORD" in error for error in errors)


def test_preflight_rejects_invalid_group_ids(tmp_path):
    env_path = write_env(tmp_path / ".env", ALLOWED_GROUPS="abc")

    errors, warnings = inspect_env(env_path)

    assert "ALLOWED_GROUPS must be comma-separated numeric QQ group ids" in errors

