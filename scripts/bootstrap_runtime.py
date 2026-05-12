#!/usr/bin/env python3
"""Run idempotent runtime bootstrap steps before starting the API server."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


COMMANDS: list[list[str]] = [
    ["python", "scripts/setup_admin_user.py", "--auto-create"],
    ["python", "scripts/setup_smoke_accounts.py", "--auto-create"],
    ["python", "scripts/seed_subscription_plans.py"],
    ["python", "-m", "app.scripts.migrate_subscription_fields"],
]


def bootstrap_env() -> dict[str, str]:
    env = os.environ.copy()
    root = str(ROOT)
    existing_pythonpath = env.get("PYTHONPATH")
    pythonpath_entries = [root]
    if existing_pythonpath:
        pythonpath_entries.extend(
            entry
            for entry in existing_pythonpath.split(os.pathsep)
            if entry and entry != root
        )
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_entries)
    return env


def main() -> int:
    env = bootstrap_env()
    for command in COMMANDS:
        print(f"[bootstrap] running: {' '.join(command)}", flush=True)
        subprocess.run(command, cwd=ROOT, check=True, env=env)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
