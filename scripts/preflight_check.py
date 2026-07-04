from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import dotenv_values


DEFAULT_VALUES = {
    "APP_SECRET_KEY": "change-me",
    "ADMIN_PASSWORD": "change-me",
    "POSTGRES_PASSWORD": "change-this-postgres-password",
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
]


def inspect_env(path: Path) -> tuple[list[str], list[str]]:
    if not path.exists():
        return [f"env file not found: {path}"], []

    values = dotenv_values(path)
    errors: list[str] = []
    warnings: list[str] = []

    for key in REQUIRED_NON_EMPTY:
        if not str(values.get(key) or "").strip():
            errors.append(f"{key} is required")

    for key, default in DEFAULT_VALUES.items():
        if values.get(key) == default:
            errors.append(f"{key} still uses the default value")

    allowed_groups = str(values.get("ALLOWED_GROUPS") or "").strip()
    if allowed_groups and not all(part.strip().isdigit() for part in allowed_groups.split(",")):
        errors.append("ALLOWED_GROUPS must be comma-separated numeric QQ group ids")

    bot_qq = str(values.get("BOT_QQ") or "").strip()
    if bot_qq and not bot_qq.isdigit():
        errors.append("BOT_QQ must be numeric")

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

