from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

from dotenv import dotenv_values


DEFAULT_VALUES = {
    "APP_SECRET_KEY": {"change-me", "change-this-secret"},
    "ADMIN_PASSWORD": {"change-me", "change-this-password"},
    "POSTGRES_PASSWORD": {"change-me", "change-this-postgres-password"},
    "ONEBOT_ACCESS_TOKEN": {"change-this-onebot-token"},
}

REQUIRED_NON_EMPTY = [
    "APP_SECRET_KEY",
    "ADMIN_USERNAME",
    "ADMIN_PASSWORD",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "DATABASE_URL",
    "REDIS_URL",
]

RECOMMENDED_NON_EMPTY = [
    "ALLOWED_GROUPS",
    "BOT_QQ",
    "ADMIN_QQ_IDS",
    "LLM_API_KEY",
    "LLM_MODEL",
    "ONEBOT_ACCESS_TOKEN",
]

REPLY_MODES = {"disabled", "command_only", "mention_only", "active"}


def _validate_identifier(values: dict, key: str, errors: list[str]) -> None:
    raw = str(values.get(key) or "").strip()
    if not raw:
        return
    if not raw.replace("_", "").isalnum():
        errors.append(f"{key} must contain only letters, numbers, and underscores")


def _validate_float_range(
    values: dict,
    key: str,
    errors: list[str],
    *,
    minimum: float,
    maximum: float,
) -> None:
    raw = str(values.get(key) or "").strip()
    if not raw:
        return
    try:
        parsed = float(raw)
    except ValueError:
        errors.append(f"{key} must be a number")
        return
    if parsed < minimum or parsed > maximum:
        errors.append(f"{key} must be between {minimum:g} and {maximum:g}")


def _validate_int_range(
    values: dict,
    key: str,
    errors: list[str],
    *,
    minimum: int,
    maximum: int,
) -> None:
    raw = str(values.get(key) or "").strip()
    if not raw:
        return
    try:
        parsed = int(raw)
    except ValueError:
        errors.append(f"{key} must be an integer")
        return
    if parsed < minimum or parsed > maximum:
        errors.append(f"{key} must be between {minimum} and {maximum}")


def _validate_reverse_ws_url(values: dict, errors: list[str]) -> None:
    raw = str(values.get("ONEBOT_REVERSE_WS_URL") or "").strip()
    if not raw:
        return
    parsed = urlparse(raw)
    if parsed.scheme not in {"ws", "wss"}:
        errors.append("ONEBOT_REVERSE_WS_URL must start with ws:// or wss://")
    if not parsed.hostname:
        errors.append("ONEBOT_REVERSE_WS_URL must include a host")


def _validate_http_url(values: dict, key: str, errors: list[str]) -> None:
    raw = str(values.get(key) or "").strip()
    if not raw:
        return
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        errors.append(f"{key} must start with http:// or https://")
    if not parsed.hostname:
        errors.append(f"{key} must include a host")


def inspect_env(path: Path) -> tuple[list[str], list[str]]:
    if not path.exists():
        return [f"env file not found: {path}"], []

    values = dotenv_values(path)
    errors: list[str] = []
    warnings: list[str] = []

    for key in REQUIRED_NON_EMPTY:
        if not str(values.get(key) or "").strip():
            errors.append(f"{key} is required")

    for key, defaults in DEFAULT_VALUES.items():
        if values.get(key) in defaults:
            errors.append(f"{key} still uses the default value")

    allowed_groups = str(values.get("ALLOWED_GROUPS") or "").strip()
    if allowed_groups and not all(part.strip().isdigit() for part in allowed_groups.split(",")):
        errors.append("ALLOWED_GROUPS must be comma-separated numeric QQ group ids")

    bot_qq = str(values.get("BOT_QQ") or "").strip()
    if bot_qq and not bot_qq.isdigit():
        errors.append("BOT_QQ must be numeric")

    admin_qq_ids = str(values.get("ADMIN_QQ_IDS") or "").strip()
    if admin_qq_ids and not all(part.strip().isdigit() for part in admin_qq_ids.split(",")):
        errors.append("ADMIN_QQ_IDS must be comma-separated numeric QQ ids")

    private_chat_whitelist = str(values.get("PRIVATE_CHAT_WHITELIST") or "").strip()
    if private_chat_whitelist and not all(part.strip().isdigit() for part in private_chat_whitelist.split(",")):
        errors.append("PRIVATE_CHAT_WHITELIST must be comma-separated numeric QQ ids")

    reply_mode = str(values.get("DEFAULT_REPLY_MODE") or "").strip()
    if reply_mode and reply_mode not in REPLY_MODES:
        errors.append("DEFAULT_REPLY_MODE must be one of: active, command_only, disabled, mention_only")

    command_prefix = str(values.get("COMMAND_PREFIX") or "").strip()
    if "COMMAND_PREFIX" in values and not command_prefix:
        errors.append("COMMAND_PREFIX must not be empty")
    if command_prefix:
        if len(command_prefix) > 8:
            errors.append("COMMAND_PREFIX must be 8 characters or fewer")
        if any(char.isspace() for char in command_prefix):
            errors.append("COMMAND_PREFIX must not contain whitespace")

    _validate_reverse_ws_url(values, errors)
    _validate_http_url(values, "LLM_BASE_URL", errors)
    _validate_http_url(values, "IMAGE_BASE_URL", errors)

    database_url = str(values.get("DATABASE_URL") or "").strip()
    postgres_user = str(values.get("POSTGRES_USER") or "").strip()
    postgres_password = str(values.get("POSTGRES_PASSWORD") or "").strip()
    postgres_db = str(values.get("POSTGRES_DB") or "").strip()
    _validate_identifier(values, "POSTGRES_USER", errors)
    _validate_identifier(values, "POSTGRES_DB", errors)
    if database_url:
        parsed = urlparse(database_url)
        is_postgres_url = bool(parsed.scheme and parsed.scheme.startswith("postgresql"))
        if parsed.scheme and not is_postgres_url:
            warnings.append("DATABASE_URL is not PostgreSQL; Docker Compose production expects PostgreSQL")
        if is_postgres_url:
            database_name = unquote(parsed.path.strip("/"))
            if postgres_user and not parsed.username:
                errors.append("DATABASE_URL username is required for PostgreSQL")
            elif postgres_user and unquote(parsed.username) != postgres_user:
                errors.append("DATABASE_URL username does not match POSTGRES_USER")
            if postgres_password and not parsed.password:
                errors.append("DATABASE_URL password is required for PostgreSQL")
            elif postgres_password and unquote(parsed.password) != postgres_password:
                errors.append("DATABASE_URL password does not match POSTGRES_PASSWORD")
            if postgres_db and not database_name:
                errors.append("DATABASE_URL database name is required for PostgreSQL")
            elif postgres_db and database_name != postgres_db:
                errors.append("DATABASE_URL database name does not match POSTGRES_DB")

    _validate_float_range(values, "LLM_TEMPERATURE", errors, minimum=0, maximum=2)
    _validate_int_range(values, "LLM_MAX_TOKENS", errors, minimum=1, maximum=32000)
    _validate_float_range(values, "LLM_TIMEOUT_SECONDS", errors, minimum=1, maximum=300)
    _validate_float_range(values, "IMAGE_TIMEOUT_SECONDS", errors, minimum=1, maximum=300)
    _validate_int_range(values, "MEMORY_SUMMARY_MESSAGE_THRESHOLD", errors, minimum=10, maximum=5000)
    image_size = str(values.get("IMAGE_SIZE") or "").strip()
    if image_size and not re.fullmatch(r"\d{2,5}x\d{2,5}", image_size):
        errors.append("IMAGE_SIZE must look like 1024x1024")
    _validate_int_range(
        values, "RATE_LIMIT_PER_USER_PER_MINUTE", errors, minimum=1, maximum=10000
    )
    _validate_int_range(
        values, "RATE_LIMIT_PER_GROUP_PER_MINUTE", errors, minimum=1, maximum=100000
    )

    for key in RECOMMENDED_NON_EMPTY:
        if not str(values.get(key) or "").strip():
            warnings.append(f"{key} is recommended for production")

    if not str(values.get("ONEBOT_REVERSE_WS_URL") or "").strip():
        warnings.append("ONEBOT_REVERSE_WS_URL is recommended for deployment documentation clarity")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate QQBot production environment file.")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures.")
    args = parser.parse_args()

    errors, warnings = inspect_env(Path(args.env_file))

    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")

    if errors or (args.strict and warnings):
        return 1

    print("Preflight check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
