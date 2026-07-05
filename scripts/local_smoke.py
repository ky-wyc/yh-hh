from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx


def wait_ready(base_url: str, process: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("uvicorn exited before becoming ready")
        try:
            response = httpx.get(f"{base_url}/api/system/health", timeout=2)
            if response.status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    raise RuntimeError("uvicorn did not become ready")


def verify_simulated_activity(base_url: str, username: str, password: str) -> None:
    with httpx.Client(timeout=10) as client:
        login = client.post(
            f"{base_url}/api/auth/login",
            json={"username": username, "password": password},
        )
        login.raise_for_status()
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        logs = client.get(f"{base_url}/api/system/logs", headers=headers)
        logs.raise_for_status()
        messages = logs.json()
        handled_reasons = {item.get("drop_reason") for item in messages}
        for expected in {
            "command:ping",
            "command:help",
            "command:dice",
            "command:ai",
            "command:warn",
            "command:banword",
            "keyword_hit",
            "active_chat",
        }:
            if expected not in handled_reasons:
                raise RuntimeError(f"missing simulated message log: {expected}")

        usage = client.get(f"{base_url}/api/usage/llm", headers=headers)
        usage.raise_for_status()
        if not any(item.get("status") == "missing_api_key" for item in usage.json()):
            raise RuntimeError("missing simulated /ai LLM usage log")

        audit = client.get(f"{base_url}/api/audit-logs", headers=headers)
        audit.raise_for_status()
        audit_actions = {item.get("action") for item in audit.json()}
        for expected in {"warn", "banword_add"}:
            if expected not in audit_actions:
                raise RuntimeError(f"missing simulated audit log: {expected}")

        onebot_status = client.get(f"{base_url}/api/system/onebot-status", headers=headers)
        onebot_status.raise_for_status()
        status_payload = onebot_status.json()
        if not status_payload.get("last_event_at"):
            raise RuntimeError("missing OneBot last_event_at after simulated activity")
        if not status_payload.get("last_action_at"):
            raise RuntimeError("missing OneBot last_action_at after simulated activity")


def set_group_reply_mode(base_url: str, username: str, password: str, group_id: str, reply_mode: str) -> None:
    with httpx.Client(timeout=10) as client:
        login = client.post(
            f"{base_url}/api/auth/login",
            json={"username": username, "password": password},
        )
        login.raise_for_status()
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        response = client.patch(
            f"{base_url}/api/groups/{group_id}",
            headers=headers,
            json={"reply_mode": reply_mode},
        )
        response.raise_for_status()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local QQBot MVP smoke check.")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--port", default="8765")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="change-me")
    parser.add_argument("--allowed-groups", default="10001")
    parser.add_argument("--admin-user-id", default="20002")
    args = parser.parse_args()

    env = os.environ.copy()
    Path("data").mkdir(exist_ok=True)
    smoke_db = Path("data") / f"smoke-{args.port}.db"
    if smoke_db.exists():
        smoke_db.unlink()
    env.update(
        {
            "DATABASE_URL": f"sqlite+aiosqlite:///./{smoke_db.as_posix()}",
            "REDIS_URL": "",
            "ADMIN_USERNAME": args.username,
            "ADMIN_PASSWORD": args.password,
            "ALLOWED_GROUPS": args.allowed_groups,
            "ADMIN_QQ_IDS": args.admin_user_id,
            "LLM_API_KEY": "",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
        }
    )

    stdout_path = Path("data/smoke-uvicorn.out.log")
    stderr_path = Path("data/smoke-uvicorn.err.log")
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        process = subprocess.Popen(
            [
                args.python,
                "-m",
                "uvicorn",
                "app.main:create_app",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                args.port,
            ],
            stdout=stdout,
            stderr=stderr,
            env=env,
        )

        try:
            base_url = f"http://127.0.0.1:{args.port}"
            wait_ready(base_url, process)
            subprocess.run(
                [
                    args.python,
                    "scripts/smoke_check.py",
                    "--base-url",
                    base_url,
                    "--username",
                    args.username,
                    "--password",
                    args.password,
                ],
                check=True,
                env=env,
            )
            subprocess.run(
                [
                    args.python,
                    "scripts/onebot_simulate.py",
                    "--ws-url",
                    f"ws://127.0.0.1:{args.port}/onebot/ws",
                    "--group-id",
                    args.allowed_groups.split(",")[0],
                ],
                check=True,
                env=env,
            )
            subprocess.run(
                [
                    args.python,
                    "scripts/onebot_simulate.py",
                    "--ws-url",
                    f"ws://127.0.0.1:{args.port}/onebot/ws",
                    "--group-id",
                    args.allowed_groups.split(",")[0],
                    "--user-id",
                    args.admin_user_id,
                    "--scenario",
                    "admin-lite",
                ],
                check=True,
                env=env,
            )
            set_group_reply_mode(
                base_url,
                args.username,
                args.password,
                args.allowed_groups.split(",")[0],
                "active",
            )
            subprocess.run(
                [
                    args.python,
                    "scripts/onebot_simulate.py",
                    "--ws-url",
                    f"ws://127.0.0.1:{args.port}/onebot/ws",
                    "--group-id",
                    args.allowed_groups.split(",")[0],
                    "--scenario",
                    "active-question",
                ],
                check=True,
                env=env,
            )
            verify_simulated_activity(base_url, args.username, args.password)
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

    print("--- stdout ---")
    print(stdout_path.read_text(encoding="utf-8", errors="ignore")[-4000:])
    print("--- stderr ---")
    print(stderr_path.read_text(encoding="utf-8", errors="ignore")[-4000:])
    return 0


if __name__ == "__main__":
    sys.exit(main())
