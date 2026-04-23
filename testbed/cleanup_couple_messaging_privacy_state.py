#!/usr/bin/env python3
"""Clean up partial/leaked state from verify_couple_messaging_privacy.py.

Removes the Mongo chain for the couple-messaging plus-variant planner
(users, user_subscriptions, stripe_customers, team_members, weddings) and
also sweeps the couple-portal-specific collections the lifecycle chain
doesn't know about:

    * ``couple_messages``  — thread rows keyed by ``wedding_id``
    * ``couple_users``     — couple-side login row (keyed by wedding_id
                              AND/OR email — belt-and-braces in case of
                              orphans left by a half-completed prior run)

Optionally sweeps every Stripe customer pinned to the reusable test clock
named ``couple-messaging-privacy``. The clock is reused across runs —
cleanup does NOT delete it. Set ``COUPLE_PRIVACY_CLOCK_ID`` in env (the id
printed at the start of each driver run) so this script can sweep the
attached customers.

Usage
-----
    # Sweep Mongo chain + couple_users/couple_messages only (clock id not known):
    python testbed/cleanup_couple_messaging_privacy_state.py

    # Sweep Mongo + Stripe customers on the pinned clock:
    COUPLE_PRIVACY_CLOCK_ID=clock_... python testbed/cleanup_couple_messaging_privacy_state.py

Safe to re-run. Only touches rows keyed on the plus-variant email(s) or the
supplied clock id.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from testbed.harness import Harness

DRIVER_NAME = "cleanup_couple_messaging_privacy_state"

# Must mirror the driver — keep in sync with
# testbed/verify_couple_messaging_privacy.py.
PLANNER_EMAIL = "test_planner+msg_privacy@thespecialwedding.io"
COUPLE_EMAIL = "test_couple+msg_privacy@thespecialwedding.io"


def drop_couple_portal_state(h: Harness, planner_email: str, couple_email: str) -> None:
    """Sweep couple_messages + couple_users + weddings for this planner.

    Must run BEFORE ``delete_user_chain`` so the planner user_id is still
    resolvable when we need to locate wedding docs. The planner's weddings
    live in ``weddings`` keyed by either ``assigned_planner_email`` or
    ``created_by`` — we match on both because different router paths write
    different fields, and we're dropping them to keep the wedding store
    clean between runs.
    """
    # Planner-owned weddings (email-keyed — survives user_id regen).
    wedding_filter = {
        "$or": [
            {"assigned_planner_email": planner_email},
            {"created_by": planner_email},
        ]
    }
    wedding_docs = list(h.mongo["weddings"].find(wedding_filter, {"_id": 1}))
    wedding_ids = [str(w["_id"]) for w in wedding_docs]

    if wedding_ids:
        cm_result = h.mongo["couple_messages"].delete_many(
            {"wedding_id": {"$in": wedding_ids}}
        )
        if cm_result.deleted_count:
            h.log.info(
                f"  ✅ couple_messages: removed {cm_result.deleted_count} "
                f"doc(s) across {len(wedding_ids)} wedding(s)"
            )

        cu_wed_result = h.mongo["couple_users"].delete_many(
            {"wedding_id": {"$in": wedding_ids}}
        )
        if cu_wed_result.deleted_count:
            h.log.info(
                f"  ✅ couple_users (by wedding_id): removed "
                f"{cu_wed_result.deleted_count} doc(s)"
            )

        wed_result = h.mongo["weddings"].delete_many(wedding_filter)
        if wed_result.deleted_count:
            h.log.info(
                f"  ✅ weddings: removed {wed_result.deleted_count} doc(s) "
                f"for {planner_email}"
            )
    else:
        h.log.info(
            f"  (no weddings found for {planner_email} — skipping "
            f"couple_messages/weddings sweep)"
        )

    # Belt-and-braces: sweep couple_users by email too. If a prior run was
    # interrupted between couple-invite and wedding-cleanup, the couple_user
    # row can outlive its wedding doc. This catches that orphan class.
    cu_email_result = h.mongo["couple_users"].delete_many({"email": couple_email})
    if cu_email_result.deleted_count:
        h.log.info(
            f"  ✅ couple_users (by email, orphan sweep): removed "
            f"{cu_email_result.deleted_count} doc(s) for {couple_email}"
        )


def main() -> int:
    h = Harness(driver_name=DRIVER_NAME)
    h.banner("CLEANUP — Couple Messaging Privacy (plus-variant planner + couple)")
    h.log.info(f"  Planner email : {PLANNER_EMAIL}")
    h.log.info(f"  Couple email  : {COUPLE_EMAIL}")

    clock_id = os.getenv("COUPLE_PRIVACY_CLOCK_ID")
    if clock_id:
        h.log.info(
            f"  Clock id      : {clock_id} (will delete Stripe customers — "
            f"clock itself is PRESERVED for reuse)"
        )
    else:
        h.log.info(
            "  Clock id      : (not supplied — set COUPLE_PRIVACY_CLOCK_ID to "
            "also sweep Stripe customers attached to the reusable clock)"
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
    h.log.info(
        f"Dropping couple-portal state (couple_messages + couple_users + "
        f"weddings) for {PLANNER_EMAIL}…"
    )
    drop_couple_portal_state(h, PLANNER_EMAIL, COUPLE_EMAIL)

    h.log.info("")
    h.log.info(f"Dropping Mongo chain for {PLANNER_EMAIL}…")
    affected = h.delete_user_chain(PLANNER_EMAIL)
    if affected == 0:
        h.log.info(f"  (no Mongo user for {PLANNER_EMAIL})")

    h.log.info("")
    h.log.info(
        "Cleanup complete. Next `python testbed/verify_couple_messaging_privacy.py` "
        "will SEED from a blank slate against the same reusable clock."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"\n❌ Cleanup aborted: {exc}\n")
        raise SystemExit(1)
