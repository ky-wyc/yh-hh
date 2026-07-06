from __future__ import annotations

import argparse
import json
import os
import stat
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def safe_identifier(value: str) -> bool:
    return bool(value) and all(char.isalnum() or char == "_" for char in value)


def private_permission_status(path: Path) -> str:
    if os.name == "nt" or not path.exists():
        return "not_checked"
    mode = stat.S_IMODE(path.stat().st_mode)
    return "ok" if mode & 0o077 == 0 else "too_open"


def latest_backup(backup_dir: Path) -> Path | None:
    if not backup_dir.exists():
        return None
    backups = sorted(backup_dir.glob("postgres-*.sql"), key=lambda item: item.stat().st_mtime)
    return backups[-1] if backups else None


def looks_like_sql_dump(path: Path) -> bool:
    if not path.exists() or path.stat().st_size <= 0:
        return False
    sample = path.read_text(encoding="utf-8", errors="ignore")[:10000]
    markers = ("PostgreSQL database dump", "CREATE TABLE", "COPY ", "INSERT INTO", "SELECT pg_catalog")
    return any(marker in sample for marker in markers)


def check(name: str, ok: bool, message: str, *, required: bool = True) -> dict[str, Any]:
    if ok:
        status = "passed"
    elif required:
        status = "failed"
    else:
        status = "warning"
    return {"name": name, "status": status, "required": required, "message": message}


def build_report(project_dir: Path, env_file: Path, backup_file: Path | None = None) -> dict[str, Any]:
    env = load_env(env_file)
    backup_dir = project_dir / "data" / "backups"
    selected_backup = backup_file or latest_backup(backup_dir)
    postgres_user = env.get("POSTGRES_USER") or "qqbot"
    postgres_db = env.get("POSTGRES_DB") or "qqbot"
    napcat_config = project_dir / "data" / "napcat" / "config"
    napcat_qq = project_dir / "data" / "napcat" / "qq"

    checks = [
        check("env_file_exists", env_file.exists(), f"env file: {env_file}"),
        check(
            "env_file_permissions",
            private_permission_status(env_file) in {"ok", "not_checked"},
            f"permission status: {private_permission_status(env_file)}",
            required=False,
        ),
        check(
            "postgres_user_identifier",
            safe_identifier(postgres_user),
            "POSTGRES_USER must contain only letters, numbers, and underscores",
        ),
        check(
            "postgres_db_identifier",
            safe_identifier(postgres_db),
            "POSTGRES_DB must contain only letters, numbers, and underscores",
        ),
        check("backup_dir_exists", backup_dir.exists(), f"backup dir: {backup_dir}"),
        check(
            "backup_file_selected",
            selected_backup is not None,
            f"selected backup: {selected_backup or 'none'}",
        ),
    ]

    if selected_backup is not None:
        checks.extend(
            [
                check("backup_file_exists", selected_backup.exists(), f"backup file: {selected_backup}"),
                check(
                    "backup_file_non_empty",
                    selected_backup.exists() and selected_backup.stat().st_size > 0,
                    "backup file must be non-empty",
                ),
                check(
                    "backup_file_looks_like_sql",
                    looks_like_sql_dump(selected_backup),
                    "backup file should look like a PostgreSQL SQL dump",
                ),
                check(
                    "backup_file_permissions",
                    private_permission_status(selected_backup) in {"ok", "not_checked"},
                    f"permission status: {private_permission_status(selected_backup)}",
                    required=False,
                ),
            ]
        )

    checks.extend(
        [
            check(
                "napcat_config_dir_exists",
                napcat_config.exists(),
                f"NapCat config dir: {napcat_config}",
                required=False,
            ),
            check(
                "napcat_qq_dir_exists",
                napcat_qq.exists(),
                f"NapCat QQ state dir: {napcat_qq}",
                required=False,
            ),
        ]
    )

    failed = [item for item in checks if item["status"] == "failed"]
    warnings = [item for item in checks if item["status"] == "warning"]
    backup_arg = str(selected_backup) if selected_backup is not None else "./data/backups/postgres-YYYYmmdd-HHMMSS.sql"
    return {
        "status": "failed" if failed else "passed",
        "generated_at": datetime.now(UTC).isoformat(),
        "restore_executed": False,
        "project_dir": str(project_dir),
        "env_file": str(env_file),
        "backup_file": str(selected_backup) if selected_backup is not None else "",
        "checks": checks,
        "failed_count": len(failed),
        "warning_count": len(warnings),
        "restore_command": f"FORCE=1 sh scripts/restore_postgres.sh {backup_arg}",
        "post_restore_smoke_command": (
            'python scripts/smoke_check.py --base-url http://127.0.0.1:8000 '
            '--username "$ADMIN_USERNAME" --password "$ADMIN_PASSWORD" --expect-cache-backend redis'
        ),
        "notes": [
            "This drill report does not stop services, recreate databases, or restore data.",
            "Keep .env, data/napcat, and SQL backups private because they contain sensitive runtime state.",
        ],
    }


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if os.name != "nt":
        path.chmod(0o600)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a non-destructive backup/restore drill report.")
    parser.add_argument("--project-dir", default=".")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--backup-file", default="")
    parser.add_argument("--report-file", default="data/backup-restore-drill.json")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    env_file = Path(args.env_file)
    if not env_file.is_absolute():
        env_file = project_dir / env_file
    backup_file = Path(args.backup_file) if args.backup_file else None
    if backup_file is not None and not backup_file.is_absolute():
        backup_file = project_dir / backup_file
    report_file = Path(args.report_file)
    if not report_file.is_absolute():
        report_file = project_dir / report_file

    report = build_report(project_dir, env_file, backup_file)
    write_report(report_file, report)
    print(f"Backup/restore drill report written to {report_file}")
    print(f"status={report['status']} failed={report['failed_count']} warnings={report['warning_count']}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
