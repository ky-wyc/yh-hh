from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx


REQUIRED_ADMIN_LITE_AUDIT_ACTIONS = {"warn", "banword_add"}
REQUIRED_MVP_CORE_LOG_REASONS = {"command:ping", "command:help", "command:dice", "command:ai"}


def missing_audit_actions(records: list[dict], required_actions: set[str]) -> set[str]:
    existing_actions = {str(item.get("action") or "") for item in records}
    return required_actions - existing_actions


def missing_message_reasons(records: list[dict], required_reasons: set[str]) -> set[str]:
    existing_reasons = {str(item.get("drop_reason") or "") for item in records}
    return required_reasons - existing_reasons


def write_report(path: str, report: dict) -> None:
    if not path:
        return
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="QQBot MVP HTTP smoke check.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="change-me")
    parser.add_argument("--expect-cache-backend", choices=["memory", "redis"], default="")
    parser.add_argument("--require-onebot-online", action="store_true")
    parser.add_argument("--require-onebot-activity", action="store_true")
    parser.add_argument("--require-mvp-core-logs", action="store_true")
    parser.add_argument("--require-admin-lite-audit", action="store_true")
    parser.add_argument("--report-file", default="", help="Write a JSON evidence report to this path.")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    report = {
        "base_url": base_url,
        "requirements": {
            "expect_cache_backend": args.expect_cache_backend,
            "require_onebot_online": args.require_onebot_online,
            "require_onebot_activity": args.require_onebot_activity,
            "require_mvp_core_logs": args.require_mvp_core_logs,
            "require_admin_lite_audit": args.require_admin_lite_audit,
        },
        "checks": {},
        "missing": {},
    }
    with httpx.Client(timeout=10) as client:
        health = client.get(f"{base_url}/api/system/health")
        health.raise_for_status()
        health_payload = health.json()
        report["checks"]["health"] = health_payload
        print("health:", health_payload)

        ready = client.get(f"{base_url}/api/system/ready")
        ready.raise_for_status()
        ready_payload = ready.json()
        report["checks"]["ready"] = ready_payload
        print("ready:", ready_payload)
        if args.expect_cache_backend:
            cache_backend = (ready_payload.get("cache") or {}).get("backend")
            if cache_backend != args.expect_cache_backend:
                report["status"] = "failed"
                report["missing"]["cache_backend"] = {
                    "expected": args.expect_cache_backend,
                    "actual": cache_backend,
                }
                write_report(args.report_file, report)
                print(
                    f"ERROR: expected cache backend {args.expect_cache_backend}, got {cache_backend}",
                    file=sys.stderr,
                )
                return 1

        login = client.post(
            f"{base_url}/api/auth/login",
            json={"username": args.username, "password": args.password},
        )
        login.raise_for_status()
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        onebot = client.get(f"{base_url}/api/system/onebot-status", headers=headers)
        onebot.raise_for_status()
        onebot_payload = onebot.json()
        report["checks"]["onebot_status"] = onebot_payload
        print("/api/system/onebot-status", "ok", onebot_payload)
        if args.require_onebot_online and not onebot_payload.get("online"):
            report["status"] = "failed"
            report["missing"]["onebot_online"] = True
            write_report(args.report_file, report)
            print("ERROR: OneBot is not online", file=sys.stderr)
            return 1
        if args.require_onebot_activity:
            if not onebot_payload.get("last_event_at"):
                report["status"] = "failed"
                report["missing"]["onebot_last_event_at"] = True
                write_report(args.report_file, report)
                print("ERROR: OneBot has no recorded inbound event activity", file=sys.stderr)
                return 1
            if not onebot_payload.get("last_action_at"):
                report["status"] = "failed"
                report["missing"]["onebot_last_action_at"] = True
                write_report(args.report_file, report)
                print("ERROR: OneBot has no recorded outbound action activity", file=sys.stderr)
                return 1

        audit_payload: list[dict] | None = None
        logs_payload: list[dict] | None = None
        endpoint_statuses: dict[str, str] = {}
        for path in [
            "/api/auth/me",
            "/api/dashboard/overview",
            "/api/groups",
            "/api/settings/bot",
            "/api/settings/llm",
            "/api/system/logs",
            "/api/system/errors",
            "/api/usage/llm",
            "/api/audit-logs",
        ]:
            response = client.get(f"{base_url}{path}", headers=headers)
            response.raise_for_status()
            print(path, "ok")
            endpoint_statuses[path] = "ok"
            if path == "/api/system/logs":
                logs_payload = response.json()
            if path == "/api/audit-logs":
                audit_payload = response.json()
        report["checks"]["endpoints"] = endpoint_statuses

        if args.require_mvp_core_logs:
            missing_reasons = missing_message_reasons(logs_payload or [], REQUIRED_MVP_CORE_LOG_REASONS)
            report["checks"]["mvp_core_log_reasons"] = sorted(REQUIRED_MVP_CORE_LOG_REASONS - missing_reasons)
            if missing_reasons:
                report["status"] = "failed"
                report["missing"]["mvp_core_log_reasons"] = sorted(missing_reasons)
                write_report(args.report_file, report)
                print(
                    "ERROR: missing MVP core message log reasons: " + ", ".join(sorted(missing_reasons)),
                    file=sys.stderr,
                )
                return 1

        if args.require_admin_lite_audit:
            missing_actions = missing_audit_actions(audit_payload or [], REQUIRED_ADMIN_LITE_AUDIT_ACTIONS)
            report["checks"]["admin_lite_audit_actions"] = sorted(
                REQUIRED_ADMIN_LITE_AUDIT_ACTIONS - missing_actions
            )
            if missing_actions:
                report["status"] = "failed"
                report["missing"]["admin_lite_audit_actions"] = sorted(missing_actions)
                write_report(args.report_file, report)
                print(
                    "ERROR: missing admin-lite audit actions: " + ", ".join(sorted(missing_actions)),
                    file=sys.stderr,
                )
                return 1

    report["status"] = "passed"
    write_report(args.report_file, report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
