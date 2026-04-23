#!/usr/bin/env python3
"""Clean up partial/leaked state from verify_planner_active_lifecycle.py.

Removes the Mongo chain for every plus-variant planner that the active
lifecycle driver creates (primary, downgrade, upgrade, past-due) plus the
wedding + usage-tracking rows those planners own, and deletes every Stripe
customer pinned to the reusable test clock named ``planner-active-lifecycle``.

Unlike the trial driver (which creates a fresh clock per run), the active
lifecycle driver **reuses the same test clock** across runs so that the
clock's frozen_time keeps drifting forward — this mirrors the team-member
gate pattern. Therefore cleanup does NOT delete the clock itself. Only its
customers are removed. Supply ``ACTIVE_CLOCK_ID`` via the environment (the
id printed at the start of each driver run) to let this script find the
customers; without it, only the Mongo chains are swept.

Usage
-----
    # Sweep Mongo chains only (no clock id known):
    python testbed/cleanup_planner_active_verify_state.py

    # Sweep Mongo + Stripe customers on the pinned clock:
    ACTIVE_CLOCK_ID=clock_... python testbed/cleanup_planner_active_verify_state.py

Safe to re-run. Only touches rows keyed on the plus-variant emails or the
supplied clock id.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from testbed.harness import Harness

# Mirror of the constants in verify_planner_active_lifecycle.py. If the driver
# adds another plus-variant email, add it here too — cleanup is always paired.
PLANNER_EMAILS = (
    "test_planner+active@thespecialwedding.io",
    "test_planner+downgrade@thespecialwedding.io",
    "test_planner+upgrade@thespecialwedding.io",
    "test_planner+pastdue@thespecialwedding.io",
)

DRIVER_NAME = "cleanup_planner_active_verify_state"


def drop_wedding_and_usage_rows(h: Harness, email: str) -> None:
    """Remove weddings + usage_tracking rows owned by the user with this email.

    Called BEFORE delete_user_chain so we can still resolve user_id. Both
    collections are keyed by the planner's user_id (string). Safe when the
    user doesn't exist — no-ops out.
    """
    user = h.mongo["users"].find_one({"email": email})
    if not user:
        return

    user_id = str(user["_id"])

    wed_result = h.mongo["weddings"].delete_many({"user_id": user_id})
    if wed_result.deleted_count:
        h.log.info(
            f"  ✅ weddings: removed {wed_result.deleted_count} doc(s) for {email}"
        )

    usage_result = h.mongo["usage_tracking"].delete_many({"user_id": user_id})
    if usage_result.deleted_count:
        h.log.info(
            f"  ✅ usage_tracking: removed {usage_result.deleted_count} doc(s) for {email}"
        )


def main() -> int:
    h = Harness(driver_name=DRIVER_NAME)
    h.banner("CLEANUP — Scenarios B/C/D (planner active lifecycle)")
    for email in PLANNER_EMAILS:
        h.log.info(f"  Planner email : {email}")

    clock_id = os.getenv("ACTIVE_CLOCK_ID")
    if clock_id:
        h.log.info(
            f"  Clock id      : {clock_id} (will delete Stripe customers — "
            f"clock itself is PRESERVED for reuse)"
        )
    else:
        h.log.info(
            "  Clock id      : (not supplied — set ACTIVE_CLOCK_ID to also "
            "sweep Stripe customers attached to the reusable clock)"
        )

    # Skip the full preflight so this script stays runnable with the backend
    # down. Mongo + Stripe are all we need.
    if clock_id:
        h.log.info("")
        h.log.info(f"Listing Stripe customers on clock {clock_id}…")
        deleted = h.cleanup_clock_customers(clock_id)
        if deleted == 0:
            h.log.info("  (no customers on that clock — nothing to delete)")

    for email in PLANNER_EMAILS:
        h.log.info("")
        h.log.info(f"Dropping wedding + usage rows for {email}…")
        drop_wedding_and_usage_rows(h, email)

        h.log.info(f"Dropping Mongo chain for {email}…")
        affected = h.delete_user_chain(email)
        if affected == 0:
            h.log.info(f"  (no Mongo user for {email})")

    h.log.info("")
    h.log.info(
        "Cleanup complete. Next `python testbed/verify_planner_active_lifecycle.py` "
        "will SEED from a blank slate against the same reusable clock."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"\n❌ Cleanup aborted: {exc}\n")
        raise SystemExit(1)
