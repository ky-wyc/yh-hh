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
        "ONEBOT_ACCESS_TOKEN": "onebot-secret",
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


def test_preflight_rejects_production_placeholder_secrets(tmp_path):
    env_path = write_env(
        tmp_path / ".env",
        APP_SECRET_KEY="change-this-secret",
        ADMIN_PASSWORD="change-this-password",
        ONEBOT_ACCESS_TOKEN="change-this-onebot-token",
    )

    errors, warnings = inspect_env(env_path)

    assert "APP_SECRET_KEY still uses the default value" in errors
    assert "ADMIN_PASSWORD still uses the default value" in errors
    assert "ONEBOT_ACCESS_TOKEN still uses the default value" in errors


def test_preflight_warns_when_onebot_access_token_is_empty(tmp_path):
    env_path = write_env(tmp_path / ".env", ONEBOT_ACCESS_TOKEN="")

    errors, warnings = inspect_env(env_path)

    assert errors == []
    assert "ONEBOT_ACCESS_TOKEN is recommended for production" in warnings


def test_preflight_rejects_invalid_group_ids(tmp_path):
    env_path = write_env(tmp_path / ".env", ALLOWED_GROUPS="abc")

    errors, warnings = inspect_env(env_path)

    assert "ALLOWED_GROUPS must be comma-separated numeric QQ group ids" in errors


def test_preflight_rejects_invalid_admin_qq_ids(tmp_path):
    env_path = write_env(tmp_path / ".env", ADMIN_QQ_IDS="123456,not-a-number")

    errors, warnings = inspect_env(env_path)

    assert "ADMIN_QQ_IDS must be comma-separated numeric QQ ids" in errors


def test_preflight_rejects_invalid_private_chat_whitelist(tmp_path):
    env_path = write_env(tmp_path / ".env", PRIVATE_CHAT_WHITELIST="123456,not-a-number")

    errors, warnings = inspect_env(env_path)

    assert "PRIVATE_CHAT_WHITELIST must be comma-separated numeric QQ ids" in errors


def test_preflight_rejects_database_url_password_mismatch(tmp_path):
    env_path = write_env(
        tmp_path / ".env",
        POSTGRES_PASSWORD="new-password",
        DATABASE_URL="postgresql+asyncpg://qqbot:old-password@postgres:5432/qqbot",
    )

    errors, warnings = inspect_env(env_path)

    assert "DATABASE_URL password does not match POSTGRES_PASSWORD" in errors


def test_preflight_rejects_incomplete_postgres_url(tmp_path):
    env_path = write_env(
        tmp_path / ".env",
        DATABASE_URL="postgresql+asyncpg://postgres:5432",
    )

    errors, warnings = inspect_env(env_path)

    assert "DATABASE_URL username is required for PostgreSQL" in errors
    assert "DATABASE_URL password is required for PostgreSQL" in errors
    assert "DATABASE_URL database name is required for PostgreSQL" in errors


def test_preflight_rejects_postgres_identifiers_that_break_ops_scripts(tmp_path):
    env_path = write_env(
        tmp_path / ".env",
        POSTGRES_USER="qqbot-user",
        POSTGRES_DB="qqbot.prod",
        DATABASE_URL="postgresql+asyncpg://qqbot-user:prod-postgres-password@postgres:5432/qqbot.prod",
    )

    errors, warnings = inspect_env(env_path)

    assert "POSTGRES_USER must contain only letters, numbers, and underscores" in errors
    assert "POSTGRES_DB must contain only letters, numbers, and underscores" in errors


def test_preflight_rejects_invalid_runtime_settings(tmp_path):
    env_path = write_env(
        tmp_path / ".env",
        DEFAULT_REPLY_MODE="chatty",
        COMMAND_PREFIX="too long prefix",
        LLM_TEMPERATURE="9",
        LLM_MAX_TOKENS="0",
        LLM_TIMEOUT_SECONDS="fast",
        RATE_LIMIT_PER_USER_PER_MINUTE="0",
        RATE_LIMIT_PER_GROUP_PER_MINUTE="many",
    )

    errors, warnings = inspect_env(env_path)

    assert "DEFAULT_REPLY_MODE must be one of: active, command_only, disabled, mention_only" in errors
    assert "COMMAND_PREFIX must be 8 characters or fewer" in errors
    assert "COMMAND_PREFIX must not contain whitespace" in errors
    assert "LLM_TEMPERATURE must be between 0 and 2" in errors
    assert "LLM_MAX_TOKENS must be between 1 and 32000" in errors
    assert "LLM_TIMEOUT_SECONDS must be a number" in errors
    assert "RATE_LIMIT_PER_USER_PER_MINUTE must be between 1 and 10000" in errors
    assert "RATE_LIMIT_PER_GROUP_PER_MINUTE must be an integer" in errors


def test_preflight_rejects_empty_command_prefix(tmp_path):
    env_path = write_env(tmp_path / ".env", COMMAND_PREFIX="")

    errors, warnings = inspect_env(env_path)

    assert "COMMAND_PREFIX must not be empty" in errors


def test_preflight_rejects_invalid_onebot_reverse_ws_url(tmp_path):
    env_path = write_env(tmp_path / ".env", ONEBOT_REVERSE_WS_URL="http://bot-app:8000/onebot/ws")

    errors, warnings = inspect_env(env_path)

    assert "ONEBOT_REVERSE_WS_URL must start with ws:// or wss://" in errors


def test_preflight_rejects_onebot_reverse_ws_url_without_host(tmp_path):
    env_path = write_env(tmp_path / ".env", ONEBOT_REVERSE_WS_URL="ws:///onebot/ws")

    errors, warnings = inspect_env(env_path)

    assert "ONEBOT_REVERSE_WS_URL must include a host" in errors


def test_preflight_rejects_invalid_llm_base_url(tmp_path):
    env_path = write_env(tmp_path / ".env", LLM_BASE_URL="api.example.com/v1")

    errors, warnings = inspect_env(env_path)

    assert "LLM_BASE_URL must start with http:// or https://" in errors


def test_preflight_rejects_llm_base_url_without_host(tmp_path):
    env_path = write_env(tmp_path / ".env", LLM_BASE_URL="https:///v1")

    errors, warnings = inspect_env(env_path)

    assert "LLM_BASE_URL must include a host" in errors
