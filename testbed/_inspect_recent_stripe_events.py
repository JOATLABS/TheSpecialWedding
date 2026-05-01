#!/usr/bin/env python3
"""Quick read-only probe for the most recent stripe_webhook_events.

Bypasses the buggy data.object filter from the email-change driver — the
backend persists events as {event_id, event_type, status, error_message,
created_at, processed_at}, so we have to query by created_at not by
subscription/customer id.

Usage:
    python testbed/_inspect_recent_stripe_events.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from testbed.harness import Harness  # noqa: E402

LIMIT = 30
WINDOW_MINUTES = 30


def main() -> int:
    h = Harness(driver_name="inspect_stripe_events")

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=WINDOW_MINUTES)
    rows = list(
        h.mongo["stripe_webhook_events"]
        .find({"created_at": {"$gte": cutoff}})
        .sort([("created_at", -1)])
        .limit(LIMIT)
    )

    h.banner(
        f"stripe_webhook_events — last {len(rows)} events (window: {WINDOW_MINUTES}m)"
    )
    if not rows:
        h.log.info(
            f"  (no webhook events recorded in the last {WINDOW_MINUTES} minutes)"
        )
        h.log.info("")
        h.log.info("  This means either:")
        h.log.info("    - stripe listen is not actually forwarding to /stripe/webhook")
        h.log.info("    - the backend is rejecting events at signature verification")
        h.log.info("      (look for 400/500 responses in the backend log)")
        h.log.info("    - STRIPE_WEBHOOK_SECRET on the backend is stale (check .env vs")
        h.log.info("      the whsec_... that stripe listen prints on startup)")
        return 0

    for row in rows:
        h.log.info(
            f"  {row.get('created_at')!s:32s} "
            f"{(row.get('status') or '?'):10s} "
            f"{(row.get('event_type') or '?'):44s} "
            f"id={row.get('event_id')}"
        )
        if row.get("error_message"):
            h.log.info(f"        error: {row['error_message']}")

    # Per-status breakdown
    h.log.info("")
    by_status: dict[str, int] = {}
    by_type: dict[str, int] = {}
    for row in rows:
        s = row.get("status") or "unknown"
        t = row.get("event_type") or "unknown"
        by_status[s] = by_status.get(s, 0) + 1
        by_type[t] = by_type.get(t, 0) + 1
    h.log.info(f"  By status: {by_status}")
    h.log.info(f"  By type:   {by_type}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
