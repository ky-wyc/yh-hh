from __future__ import annotations

import argparse
import sys

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description="QQBot MVP HTTP smoke check.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="change-me")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    with httpx.Client(timeout=10) as client:
        health = client.get(f"{base_url}/api/system/health")
        health.raise_for_status()
        print("health:", health.json())

        ready = client.get(f"{base_url}/api/system/ready")
        ready.raise_for_status()
        print("ready:", ready.json())

        login = client.post(
            f"{base_url}/api/auth/login",
            json={"username": args.username, "password": args.password},
        )
        login.raise_for_status()
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        for path in [
            "/api/auth/me",
            "/api/system/onebot-status",
            "/api/dashboard/overview",
            "/api/settings/llm",
            "/api/system/logs",
            "/api/system/errors",
            "/api/usage/llm",
        ]:
            response = client.get(f"{base_url}{path}", headers=headers)
            response.raise_for_status()
            print(path, "ok")

    return 0


if __name__ == "__main__":
    sys.exit(main())
