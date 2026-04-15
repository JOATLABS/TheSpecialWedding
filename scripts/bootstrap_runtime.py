#!/usr/bin/env python3
"""Run idempotent runtime bootstrap steps before starting the API server."""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


COMMANDS: list[list[str]] = [
    ["python", "scripts/setup_admin_user.py", "--auto-create"],
    ["python", "scripts/setup_smoke_accounts.py", "--auto-create"],
    ["python", "scripts/seed_subscription_plans.py"],
    ["python", "-m", "app.scripts.migrate_subscription_fields"],
]


def main() -> int:
    for command in COMMANDS:
        print(f"[bootstrap] running: {' '.join(command)}", flush=True)
        subprocess.run(command, cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
