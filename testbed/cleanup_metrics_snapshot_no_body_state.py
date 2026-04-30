#!/usr/bin/env python3
"""Clean up state from verify_metrics_snapshot_no_body.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from bson import ObjectId

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from testbed.harness import Harness  # noqa: E402


STATE_FILE = (
    Path(__file__).resolve().parent / ".testbed" / "metrics_snapshot_no_body_state.json"
)


def _snapshot_filter(snapshot_id: str) -> dict:
    try:
        return {"_id": ObjectId(snapshot_id)}
    except Exception:
        return {"id": snapshot_id}


def main() -> int:
    h = Harness(driver_name="cleanup_metrics_snapshot_no_body_state")
    h.banner("CLEANUP - Metrics snapshot no-body verifier")

    if not STATE_FILE.exists():
        h.log.info(f"No state file at {STATE_FILE}; nothing to clean.")
        return 0

    state = json.loads(STATE_FILE.read_text())
    snapshot_id = state.get("snapshot_id")
    if not snapshot_id:
        h.log.info("State file did not include snapshot_id; nothing to clean.")
        STATE_FILE.unlink(missing_ok=True)
        return 0

    result = h.mongo["platform_metrics"].delete_many(_snapshot_filter(snapshot_id))
    h.log.info(f"Removed {result.deleted_count} platform_metrics snapshot(s).")
    STATE_FILE.unlink(missing_ok=True)
    h.log.info("Cleanup complete.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        import logging

        logging.getLogger("cleanup_metrics_snapshot_no_body_state").error(
            f"Cleanup aborted: {exc}", exc_info=True
        )
        raise SystemExit(1)
