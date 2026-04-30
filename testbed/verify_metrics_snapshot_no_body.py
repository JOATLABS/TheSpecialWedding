#!/usr/bin/env python3
"""
Metrics snapshot no-body contract - live testbed verifier.

The Cloudflare metrics cron calls POST /metrics/snapshot without a JSON body.
This driver verifies that the running backend builds and persists live platform
metrics for that exact request shape.

Usage:
    python testbed/testbed.py up
    python testbed/verify_metrics_snapshot_no_body.py
    python testbed/cleanup_metrics_snapshot_no_body_state.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from testbed.harness import Harness  # noqa: E402


DRIVER_NAME = "verify_metrics_snapshot_no_body"
STATE_FILE = (
    Path(__file__).resolve().parent / ".testbed" / "metrics_snapshot_no_body_state.json"
)


def _metrics_token() -> str:
    token = (
        os.getenv("PLATFORM_METRICS_TOKEN")
        or os.getenv("API_TOKEN")
        or os.getenv("API_KEY")
    )
    if not token:
        raise RuntimeError(
            "PLATFORM_METRICS_TOKEN, API_TOKEN, or API_KEY must be configured"
        )
    return token


def main() -> int:
    h = Harness(driver_name=DRIVER_NAME)
    h.preflight()
    admin_token = h.get_admin_token()
    metrics_token = _metrics_token()

    h.phase(
        "SNAPSHOT",
        "POST /metrics/snapshot with auth headers and no request body",
    )
    headers = {
        "Authorization": f"Bearer {metrics_token}",
        "Content-Type": "application/json",
    }
    response = requests.post(
        f"{h.config.backend_url}/metrics/snapshot",
        headers=headers,
        timeout=90,
    )
    if response.status_code != 200:
        raise AssertionError(
            "POST /metrics/snapshot expected 200, got "
            f"{response.status_code}: {response.text[:500]}"
        )

    body = response.json()
    snapshot_id = body.get("id")
    metrics = body.get("metrics") or {}
    if not snapshot_id:
        raise AssertionError(f"Snapshot response did not include id: {body!r}")
    if not metrics:
        raise AssertionError(f"Snapshot response did not include metrics: {body!r}")
    if not body.get("snapshot_time"):
        raise AssertionError(
            f"Snapshot response did not include snapshot_time: {body!r}"
        )

    h.log.info(f"  OK snapshot id: {snapshot_id}")
    h.log.info(f"  OK snapshot time: {body['snapshot_time']}")

    latest = requests.get(
        f"{h.config.backend_url}/metrics/snapshot",
        headers={"Authorization": f"Bearer {metrics_token}"},
        timeout=30,
    )
    if latest.status_code != 200:
        raise AssertionError(
            "GET /metrics/snapshot expected 200, got "
            f"{latest.status_code}: {latest.text[:500]}"
        )
    if latest.json().get("id") != snapshot_id:
        raise AssertionError("Latest metrics snapshot does not match inserted id")

    admin_response = h.api_get("/admin/platform/metrics", token=admin_token)
    if admin_response.status_code != 200:
        raise AssertionError(
            "GET /admin/platform/metrics expected 200, got "
            f"{admin_response.status_code}: {admin_response.text[:500]}"
        )

    history_response = h.api_get("/admin/platform/metrics/history", token=admin_token)
    if history_response.status_code != 200:
        raise AssertionError(
            "GET /admin/platform/metrics/history expected 200, got "
            f"{history_response.status_code}: {history_response.text[:500]}"
        )
    if not any(item.get("id") == snapshot_id for item in history_response.json()):
        raise AssertionError("Metrics history does not include inserted snapshot id")

    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps({"snapshot_id": snapshot_id, "backend_url": h.config.backend_url})
        + "\n"
    )

    h.checkpoint(
        "METRICS_SNAPSHOT_NO_BODY_VERIFIED",
        [
            "POST /metrics/snapshot with no request body returned 200.",
            "GET /metrics/snapshot returned the same snapshot id.",
            "Root-admin metrics history includes the inserted snapshot.",
            f"Cleanup state written to {STATE_FILE}.",
        ],
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        import logging

        logging.getLogger(DRIVER_NAME).error(
            f"Metrics snapshot no-body verifier aborted: {exc}", exc_info=True
        )
        raise SystemExit(1)
