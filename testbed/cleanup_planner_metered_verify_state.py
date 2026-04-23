#!/usr/bin/env python3
"""Clean up partial/leaked state from verify_planner_metered_lifecycle.py.

Removes the Mongo chain for the metered-scenario plus-variant planner
(users, user_subscriptions, stripe_customers, team_members, plus the
weddings + usage_tracking rows the driver writes) and deletes every Stripe
customer pinned to the reusable test clock named ``planner-metered-lifecycle``.

The clock is reused across runs — cleanup does NOT delete it. Set
``METERED_CLOCK_ID`` in env (the id printed at the start of each driver
run) so this script can sweep the attached customers.

Usage
-----
    # Sweep Mongo chain only (clock id not known):
    python testbed/cleanup_planner_metered_verify_state.py

    # Sweep Mongo + Stripe customers on the pinned clock:
    METERED_CLOCK_ID=clock_... python testbed/cleanup_planner_metered_verify_state.py

Safe to re-run. Only touches rows keyed on the plus-variant email or the
supplied clock id.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from testbed.harness import Harness

PLANNER_EMAIL = "test_planner+metered@thespecialwedding.io"
DRIVER_NAME = "cleanup_planner_metered_verify_state"


def drop_wedding_and_usage_rows(h: Harness, email: str) -> None:
    """Remove weddings + usage_tracking rows owned by the user with this email.

    Must run BEFORE delete_user_chain so the user_id is still resolvable.
    Both collections are keyed by the planner's user_id (string).
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
    h.banner("CLEANUP — Scenario E (planner metered lifecycle)")
    h.log.info(f"  Planner email : {PLANNER_EMAIL}")

    clock_id = os.getenv("METERED_CLOCK_ID")
    if clock_id:
        h.log.info(
            f"  Clock id      : {clock_id} (will delete Stripe customers — "
            f"clock itself is PRESERVED for reuse)"
        )
    else:
        h.log.info(
            "  Clock id      : (not supplied — set METERED_CLOCK_ID to also "
            "sweep Stripe customers attached to the reusable clock)"
        )

    # Skip the full preflight so this script stays runnable even when the
    # backend is down. Stripe + Mongo are all we need.
    if clock_id:
        h.log.info("")
        h.log.info(f"Listing Stripe customers on clock {clock_id}…")
        deleted = h.cleanup_clock_customers(clock_id)
        if deleted == 0:
            h.log.info("  (no customers on that clock — nothing to delete)")

    h.log.info("")
    h.log.info(f"Dropping wedding + usage rows for {PLANNER_EMAIL}…")
    drop_wedding_and_usage_rows(h, PLANNER_EMAIL)

    h.log.info(f"Dropping Mongo chain for {PLANNER_EMAIL}…")
    affected = h.delete_user_chain(PLANNER_EMAIL)
    if affected == 0:
        h.log.info(f"  (no Mongo user for {PLANNER_EMAIL})")

    h.log.info("")
    h.log.info(
        "Cleanup complete. Next `python testbed/verify_planner_metered_lifecycle.py` "
        "will SEED from a blank slate against the same reusable clock."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"\n❌ Cleanup aborted: {exc}\n")
        raise SystemExit(1)
