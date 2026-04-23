#!/usr/bin/env python3
"""Clean up partial/leaked state from verify_planner_trial_lifecycle.py.

Removes the plus-variant planner's Mongo chain (users, user_subscriptions,
stripe_customers, team_members) and every Stripe customer pinned to the
scenario-A test clock so the SEED phase can run from a blank slate.

Unlike the team-member gate verifier (which reuses a pinned clock), the
trial lifecycle driver creates a **fresh clock per run** — trials are
one-shot on a given subscription. So by default cleanup also deletes the
clock itself, but only if the clock id is supplied via the
`TRIAL_CLOCK_ID` environment variable (printed at the end of a driver run).

Usage
-----
    # Clean Mongo + Stripe customers (no clock id known):
    python testbed/cleanup_planner_trial_verify_state.py

    # Also delete the test clock the last driver run created:
    TRIAL_CLOCK_ID=clock_... python testbed/cleanup_planner_trial_verify_state.py

Safe to re-run. Only touches rows keyed on the plus-variant planner email or
the supplied clock id.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import stripe

from testbed.harness import Harness

PLANNER_EMAIL = "test_planner+trial@thespecialwedding.io"
DRIVER_NAME = "cleanup_planner_trial_verify_state"


def maybe_delete_clock(h: Harness, clock_id: str) -> None:
    """Best-effort delete the named Stripe test clock.

    Stripe permits deleting clocks whose customers have already been removed
    (cleanup_clock_customers runs before this). A clock that doesn't exist
    is treated as already-clean.
    """
    try:
        stripe.test_helpers.TestClock.delete(clock_id)
        h.log.info(f"  ✅ Deleted Stripe test clock {clock_id}")
    except stripe.error.InvalidRequestError as exc:
        # Most common case: the clock was already cleaned up by a prior run.
        h.log.info(f"  (clock {clock_id} not deletable — likely already gone: {exc})")
    except stripe.error.StripeError as exc:
        h.log.warning(f"  ⚠️ Could not delete clock {clock_id}: {exc}")


def main() -> int:
    h = Harness(driver_name=DRIVER_NAME)
    h.banner("CLEANUP — Scenario A (planner trial lifecycle)")
    h.log.info(f"  Planner email : {PLANNER_EMAIL}")

    clock_id = os.getenv("TRIAL_CLOCK_ID")
    if clock_id:
        h.log.info(
            f"  Clock id      : {clock_id} (will delete Stripe customers + clock)"
        )
    else:
        h.log.info(
            "  Clock id      : (not supplied — set TRIAL_CLOCK_ID to also drop "
            "the test clock created by the last driver run)"
        )

    # Skip the full preflight — this script must remain runnable even when
    # the backend is down. It only needs Stripe + Mongo.
    if clock_id:
        h.log.info("")
        h.log.info(f"Listing Stripe customers on clock {clock_id}…")
        deleted = h.cleanup_clock_customers(clock_id)
        if deleted == 0:
            h.log.info("  (no customers on that clock — nothing to delete)")

    h.log.info("")
    h.log.info(f"Dropping Mongo chain for {PLANNER_EMAIL}…")
    affected = h.delete_user_chain(PLANNER_EMAIL)
    if affected == 0:
        h.log.info(f"  (no Mongo user for {PLANNER_EMAIL})")

    if clock_id:
        h.log.info("")
        maybe_delete_clock(h, clock_id)

    h.log.info("")
    h.log.info(
        "Cleanup complete. Next `python testbed/verify_planner_trial_lifecycle.py` "
        "will SEED from a blank slate."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"\n❌ Cleanup aborted: {exc}\n")
        raise SystemExit(1)
