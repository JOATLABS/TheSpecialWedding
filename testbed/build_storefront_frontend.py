#!/usr/bin/env python3
"""Build and bind the production Next storefront to its exact source tree."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess

try:
    from testbed.storefront_build_evidence import frontend_source_evidence
except ModuleNotFoundError:  # Direct ``python testbed/<script>.py`` execution.
    from storefront_build_evidence import frontend_source_evidence  # type: ignore[no-redef]


REPO_ROOT = Path(__file__).resolve().parent.parent
RECEIPT_PATH = REPO_ROOT / ".next" / "storefront-testbed-build-receipt.json"


def main() -> int:
    before = frontend_source_evidence(REPO_ROOT)
    environment = dict(os.environ)
    node22 = Path("/opt/homebrew/opt/node@22/bin")
    if node22.is_dir():
        environment["PATH"] = f"{node22}:{environment.get('PATH', '')}"
    subprocess.run(
        ["npm", "run", "build"],
        cwd=REPO_ROOT,
        env=environment,
        check=True,
    )
    after = frontend_source_evidence(REPO_ROOT)
    if after["frontend_source_sha256"] != before["frontend_source_sha256"]:
        raise RuntimeError(
            "Frontend source changed while the production build was running"
        )
    build_id_path = REPO_ROOT / ".next" / "BUILD_ID"
    build_id = build_id_path.read_text(encoding="utf-8").strip()
    if not build_id:
        raise RuntimeError("Next production build did not produce a BUILD_ID")
    node_version = subprocess.check_output(
        ["node", "--version"], cwd=REPO_ROOT, env=environment, text=True
    ).strip()
    receipt = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "build_id": build_id,
        "node_version": node_version,
        **after,
    }
    RECEIPT_PATH.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(RECEIPT_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
