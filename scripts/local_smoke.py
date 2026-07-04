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


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local QQBot MVP smoke check.")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--port", default="8765")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="change-me")
    parser.add_argument("--allowed-groups", default="10001")
    args = parser.parse_args()

    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": "sqlite+aiosqlite:///./data/smoke.db",
            "REDIS_URL": "",
            "ADMIN_USERNAME": args.username,
            "ADMIN_PASSWORD": args.password,
            "ALLOWED_GROUPS": args.allowed_groups,
            "LLM_API_KEY": "",
        }
    )

    Path("data").mkdir(exist_ok=True)
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

