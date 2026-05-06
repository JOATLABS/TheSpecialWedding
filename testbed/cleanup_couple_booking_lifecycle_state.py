#!/usr/bin/env python3
"""Clean up partial/leaked state from verify_couple_booking_lifecycle.py.

Removes the Mongo chain for the couple-booking plus-variant planner
(users, user_subscriptions, stripe_customers, team_members, weddings),
plus the calendar-side and couple-portal-side collections the lifecycle
chain doesn't sweep:

    * ``calendar_connections``       — stub connection seeded directly
    * ``planner_tasks``              — meetings created by both flows
    * ``calendar_event_syncs``       — sync rows from approve attempts
    * ``calendar_idempotency_keys``  — couple-booking idempotency rows
    * ``calendar_audit_log``         — audit entries from approve/decline
    * ``planner_notifications``      — booking-request notifications
    * ``couple_messages``            — none expected, but defensive
    * ``couple_users``               — couple-portal login row

Optionally sweeps every Stripe customer pinned to the reusable test clock
``couple-booking-lifecycle``. The clock itself is REUSED across runs and
must not be deleted by cleanup. Set ``COUPLE_BOOKING_CLOCK_ID`` in env
(printed at the start of each driver run) so this script can sweep the
attached customers.

Usage
-----
    # Mongo + couple-portal-only sweep (clock id not known):
    python testbed/cleanup_couple_booking_lifecycle_state.py

    # Mongo + Stripe customers on the pinned clock:
    COUPLE_BOOKING_CLOCK_ID=clock_... \
        python testbed/cleanup_couple_booking_lifecycle_state.py

Safe to re-run. Only touches rows keyed on the plus-variant email(s) or
the supplied clock id.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from testbed.harness import Harness

DRIVER_NAME = "cleanup_couple_booking_lifecycle_state"

# Must mirror the driver — keep in sync with
# testbed/verify_couple_booking_lifecycle.py.
PLANNER_EMAIL = "test_planner+couple_booking@thespecialwedding.io"
COUPLE_EMAIL = "test_couple+couple_booking@thespecialwedding.io"


def drop_calendar_state(h: Harness, planner_email: str, couple_email: str) -> None:
    """Sweep calendar + couple-portal state for this planner.

    Must run BEFORE ``delete_user_chain`` so the planner ``user_id`` is still
    resolvable when we need to scope ``calendar_connections`` /
    ``planner_notifications`` queries.
    """
    user = h.mongo["users"].find_one({"email": planner_email}, {"_id": 1})
    owner_id = str(user["_id"]) if user else None

    # Wedding-scoped sweeps: weddings live keyed by either
    # ``assigned_planner_email`` or ``created_by`` (different routes write
    # different fields). Match both.
    wedding_filter = {
        "$or": [
            {"assigned_planner_email": planner_email},
            {"created_by": planner_email},
        ]
    }
    wedding_docs = list(h.mongo["weddings"].find(wedding_filter, {"_id": 1}))
    wedding_ids = [str(w["_id"]) for w in wedding_docs]

    if wedding_ids:
        for coll, key in (
            ("planner_tasks", "wedding_id"),
            ("couple_users", "wedding_id"),
        ):
            result = h.mongo[coll].delete_many({key: {"$in": wedding_ids}})
            if result.deleted_count:
                h.log.info(
                    f"  ✅ {coll}: removed {result.deleted_count} doc(s) "
                    f"across {len(wedding_ids)} wedding(s)"
                )

    if owner_id:
        for coll in (
            "calendar_connections",
            "planner_tasks",
            "calendar_event_syncs",
            "planner_notifications",
        ):
            filt = (
                {"planner_id": {"$in": [owner_id, planner_email]}}
                if coll == "planner_notifications"
                else {"owner_planner_id": owner_id}
            )
            result = h.mongo[coll].delete_many(filt)
            if result.deleted_count:
                h.log.info(
                    f"  ✅ {coll}: removed {result.deleted_count} doc(s) "
                    f"for owner_id={owner_id}"
                )

    # Idempotency keys — scope_key contains the couple email.
    idem_result = h.mongo["calendar_idempotency_keys"].delete_many(
        {"scope_key": {"$regex": f"couple_meeting_book:.*{couple_email}"}}
    )
    if idem_result.deleted_count:
        h.log.info(
            f"  ✅ calendar_idempotency_keys: removed "
            f"{idem_result.deleted_count} doc(s) for {couple_email}"
        )

    # Audit log — actor or owner-email keyed.
    audit_result = h.mongo["calendar_audit_log"].delete_many(
        {
            "$or": [
                {"owner_planner_email": planner_email},
                {"actor_email": planner_email},
                {"actor_email": couple_email},
            ]
        }
    )
    if audit_result.deleted_count:
        h.log.info(
            f"  ✅ calendar_audit_log: removed {audit_result.deleted_count} "
            f"doc(s) for plus-variant scope"
        )

    # Couple-portal sweep (belt-and-braces against orphaned couple_users).
    cu_email_result = h.mongo["couple_users"].delete_many({"email": couple_email})
    if cu_email_result.deleted_count:
        h.log.info(
            f"  ✅ couple_users (by email, orphan sweep): removed "
            f"{cu_email_result.deleted_count} doc(s) for {couple_email}"
        )


def main() -> int:
    h = Harness(driver_name=DRIVER_NAME)
    h.banner("CLEANUP — Couple Booking Lifecycle (plus-variant planner + couple)")
    h.log.info(f"  Planner email : {PLANNER_EMAIL}")
    h.log.info(f"  Couple email  : {COUPLE_EMAIL}")

    clock_id = os.getenv("COUPLE_BOOKING_CLOCK_ID")
    if clock_id:
        h.log.info(
            f"  Clock id      : {clock_id} (will delete Stripe customers — "
            "clock itself is PRESERVED for reuse)"
        )
    else:
        h.log.info(
            "  Clock id      : (not supplied — set COUPLE_BOOKING_CLOCK_ID to "
            "also sweep Stripe customers attached to the reusable clock)"
        )

    if clock_id:
        h.log.info("")
        h.log.info(f"Listing Stripe customers on clock {clock_id}…")
        deleted = h.cleanup_clock_customers(clock_id)
        if deleted == 0:
            h.log.info("  (no customers on that clock — nothing to delete)")

    h.log.info("")
    h.log.info(f"Dropping calendar + couple-portal state for {PLANNER_EMAIL}…")
    drop_calendar_state(h, PLANNER_EMAIL, COUPLE_EMAIL)

    h.log.info("")
    h.log.info(f"Dropping Mongo chain for {PLANNER_EMAIL}…")
    affected = h.delete_user_chain(PLANNER_EMAIL)
    if affected == 0:
        h.log.info(f"  (no Mongo user for {PLANNER_EMAIL})")

    h.log.info("")
    h.log.info(
        "Cleanup complete. Next "
        "`python testbed/verify_couple_booking_lifecycle.py` "
        "will SEED from a blank slate against the same reusable clock."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"\n❌ Cleanup aborted: {exc}\n")
        raise SystemExit(1)
