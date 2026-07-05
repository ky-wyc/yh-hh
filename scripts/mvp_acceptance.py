from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values


def first_csv_value(value: str | None) -> str:
    for part in (value or "").split(","):
        part = part.strip()
        if part:
            return part
    return ""


def command_text(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def build_commands(args: argparse.Namespace, env_values: dict[str, str | None]) -> tuple[list[list[str]], list[str]]:
    errors: list[str] = []
    commands: list[list[str]] = []

    group_id = args.group_id or first_csv_value(env_values.get("ALLOWED_GROUPS"))
    admin_user_id = args.admin_user_id or first_csv_value(env_values.get("ADMIN_QQ_IDS"))
    access_token = args.onebot_access_token
    if access_token is None:
        access_token = str(env_values.get("ONEBOT_ACCESS_TOKEN") or "")

    preflight = [args.python, "scripts/preflight_check.py", "--env-file", args.env_file]
    if args.strict_preflight:
        preflight.append("--strict")
    commands.append(preflight)

    smoke = [
        args.python,
        "scripts/smoke_check.py",
        "--base-url",
        args.base_url,
        "--username",
        args.admin_username or str(env_values.get("ADMIN_USERNAME") or "admin"),
        "--password",
        args.admin_password or str(env_values.get("ADMIN_PASSWORD") or ""),
        "--expect-cache-backend",
        args.expect_cache_backend,
    ]
    if args.require_onebot_online:
        smoke.append("--require-onebot-online")
    if args.require_onebot_activity:
        smoke.append("--require-onebot-activity")
    if args.require_mvp_core_logs:
        smoke.append("--require-mvp-core-logs")
    if args.require_admin_lite_audit:
        smoke.append("--require-admin-lite-audit")
    commands.append(smoke)

    if args.require_onebot_online and not args.skip_onebot_simulation:
        errors.append(
            "--require-onebot-online should be used with --skip-onebot-simulation; "
            "run simulated OneBot checks before the real OneBot service is online."
        )
    if args.require_admin_lite and args.skip_onebot_simulation:
        errors.append(
            "--require-admin-lite requires simulated OneBot checks; "
            "remove --skip-onebot-simulation or validate admin-lite manually in the real QQ group."
        )
    if args.require_admin_lite_audit and not args.skip_onebot_simulation:
        errors.append(
            "--require-admin-lite-audit should be used with --skip-onebot-simulation after "
            "validating admin-lite manually in the real QQ group."
        )
    if args.require_mvp_core_logs and not args.skip_onebot_simulation:
        errors.append(
            "--require-mvp-core-logs should be used with --skip-onebot-simulation after "
            "validating core commands manually in the real QQ group."
        )

    if not args.skip_onebot_simulation:
        if not group_id:
            errors.append("ALLOWED_GROUPS or --group-id is required for OneBot simulation")
        else:
            mvp_core = [
                args.python,
                "scripts/onebot_simulate.py",
                "--ws-url",
                args.ws_url,
                "--group-id",
                group_id,
                "--scenario",
                "mvp-core",
            ]
            if access_token.strip():
                mvp_core.extend(["--access-token", access_token.strip()])
            commands.append(mvp_core)

            if admin_user_id:
                admin_lite = [
                    args.python,
                    "scripts/onebot_simulate.py",
                    "--ws-url",
                    args.ws_url,
                    "--group-id",
                    group_id,
                    "--user-id",
                    admin_user_id,
                    "--scenario",
                    "admin-lite",
                ]
                if access_token.strip():
                    admin_lite.extend(["--access-token", access_token.strip()])
                commands.append(admin_lite)
            elif args.require_admin_lite:
                errors.append("ADMIN_QQ_IDS or --admin-user-id is required for admin-lite acceptance")

    return commands, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Run QQBot MVP production acceptance checks.")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--ws-url", default="ws://127.0.0.1:8000/onebot/ws")
    parser.add_argument("--admin-username", default="")
    parser.add_argument("--admin-password", default="")
    parser.add_argument("--group-id", default="")
    parser.add_argument("--admin-user-id", default="")
    parser.add_argument("--onebot-access-token", default=None)
    parser.add_argument("--expect-cache-backend", choices=["memory", "redis"], default="redis")
    parser.add_argument("--strict-preflight", action="store_true")
    parser.add_argument("--require-onebot-online", action="store_true")
    parser.add_argument("--require-onebot-activity", action="store_true")
    parser.add_argument("--require-mvp-core-logs", action="store_true")
    parser.add_argument("--require-admin-lite", action="store_true")
    parser.add_argument("--require-admin-lite-audit", action="store_true")
    parser.add_argument("--skip-onebot-simulation", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    env_path = Path(args.env_file)
    if not env_path.exists():
        print(f"ERROR: env file not found: {env_path}", file=sys.stderr)
        return 1

    env_values = dotenv_values(env_path)
    commands, errors = build_commands(args, env_values)
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if errors:
        return 1

    for command in commands:
        print("+", command_text(command))
        if not args.dry_run:
            subprocess.run(command, check=True)

    print("MVP acceptance checks passed." if not args.dry_run else "MVP acceptance dry run passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
