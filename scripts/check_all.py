from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run(command: list[str], cwd: Path | None = None) -> None:
    print("+", " ".join(command))
    subprocess.run(command, cwd=cwd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run QQBot MVP verification checks.")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--pnpm", default="pnpm")
    parser.add_argument("--with-smoke", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    web_admin = root / "web-admin"

    run([args.python, "-m", "compileall", "app", "scripts"], cwd=root)
    run([args.python, "-m", "ruff", "check", "."], cwd=root)
    run([args.python, "-m", "pytest"], cwd=root)
    run([args.pnpm, "run", "build"], cwd=web_admin)

    if args.with_smoke:
        run(
            [
                args.python,
                "scripts/local_smoke.py",
                "--python",
                args.python,
                "--port",
                "8769",
                "--allowed-groups",
                "10001",
            ],
            cwd=root,
        )

    print("All MVP checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

