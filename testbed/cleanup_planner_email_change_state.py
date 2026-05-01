#!/usr/bin/env python3
"""Cleanup paired with verify_planner_email_change.py.

Drops every Mongo + Stripe artifact the driver may have created under either
the OLD or NEW plus-variant emails, plus the couple_users row and any
activity_logs rows the driver tagged with ``metadata.driver``. Reuses the
test clock — does NOT delete it.

Safe to re-run.

Usage:
    python testbed/cleanup_planner_email_change_state.py

If the driver pinned a clock via EMAIL_CHANGE_CLOCK_ID, this script picks
the same id up from the same env var and sweeps customers off that clock.
Without the env var it falls back to deleting Stripe customers by email
match (slower but covers the case where someone deleted their .env line).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import stripe

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from testbed.harness import Harness  # noqa: E402

DRIVER_NAME = "verify_planner_email_change"

OLD_EMAIL = "test_planner+emailchange@thespecialwedding.io"
NEW_EMAIL = "test_planner+emailchange_new@thespecialwedding.io"
COUPLE_EMAIL = "test_couple+emailchange@thespecialwedding.io"
TEST_CLOCK_ID = os.getenv("EMAIL_CHANGE_CLOCK_ID")


def _delete_stripe_customers_by_email(h: Harness, email: str) -> int:
    """Fallback when no clock is pinned: delete by email match."""
    deleted = 0
    for customer in stripe.Customer.list(email=email, limit=100).auto_paging_iter():
        try:
            stripe.Customer.delete(customer.id)
            h.log.info(f"  ✅ Deleted Stripe customer {customer.id} ({customer.email})")
            deleted += 1
        except stripe.error.StripeError as exc:
            h.log.warning(f"  ⚠️ Could not delete {customer.id}: {exc}")
    return deleted


def main() -> int:
    h = Harness(driver_name=f"cleanup_{DRIVER_NAME}")

    h.banner(f"CLEANUP — {DRIVER_NAME}")
    h.log.info(f"  Mongo DB:   {h.config.mongo_db}")
    h.log.info(f"  Old email:  {OLD_EMAIL}")
    h.log.info(f"  New email:  {NEW_EMAIL}")
    h.log.info(f"  Couple:     {COUPLE_EMAIL}")
    h.log.info(
        f"  Test clock: {TEST_CLOCK_ID or '<not pinned — falling back to email sweep>'}"
    )
    h.log.info("")

    # 1. Stripe — clock-scoped sweep first, fallback by email second.
    if TEST_CLOCK_ID:
        h.log.info(f"Sweeping Stripe customers off clock {TEST_CLOCK_ID}…")
        deleted = h.cleanup_clock_customers(TEST_CLOCK_ID)
        h.log.info(f"  ({deleted} customer(s) removed from clock)")
    h.log.info("")

    h.log.info("Sweeping Stripe customers by email (catch any clockless leaks)…")
    for email in (OLD_EMAIL, NEW_EMAIL):
        n = _delete_stripe_customers_by_email(h, email)
        if n == 0:
            h.log.info(f"  (no customer for {email})")
    h.log.info("")

    # 2. Mongo user chain for both emails. delete_user_chain handles
    #    users, user_subscriptions, stripe_customers, team_members,
    #    usage_tracking, packages, weddings (by email AND planner_id).
    h.log.info("Sweeping Mongo user chain…")
    for email in (OLD_EMAIL, NEW_EMAIL):
        h.delete_user_chain(email)
    h.log.info("")

    # 3. Couple users + dashboard cache — out-of-band of user_chain.
    h.log.info("Sweeping couple_users + dashboard cache…")
    couple_result = h.mongo["couple_users"].delete_many({"email": COUPLE_EMAIL})
    if couple_result.deleted_count:
        h.log.info(f"  ✅ couple_users: removed {couple_result.deleted_count} doc(s)")

    # 4. Activity log rows the driver tagged. Tag-based cleanup is safer
    #    than email-based here because activity_logs is shared across
    #    drivers — we only want OUR rows.
    activity_result = h.mongo["activity_logs"].delete_many(
        {"metadata.driver": DRIVER_NAME}
    )
    if activity_result.deleted_count:
        h.log.info(
            f"  ✅ activity_logs (by driver tag): removed "
            f"{activity_result.deleted_count} doc(s)"
        )

    # 5. Calendar artifacts — not expected for this driver but defensive
    #    in case a future iteration starts touching them.
    for coll, field in (
        ("calendar_connections", "user_email"),
        ("calendar_connections", "owner_planner_email"),
        ("calendar_event_syncs", "owner_planner_email"),
        ("calendar_event_syncs", "target_user_email"),
        ("planner_tasks", "planner_email"),
        ("planner_tasks", "owner_planner_email"),
        ("planner_tasks", "created_by_email"),
        ("meeting_invites", "owner_planner_email"),
        ("calendar_jobs", "owner_planner_email"),
    ):
        result = h.mongo[coll].delete_many({field: {"$in": [OLD_EMAIL, NEW_EMAIL]}})
        if result.deleted_count:
            h.log.info(
                f"  ✅ {coll} (by {field}): removed {result.deleted_count} doc(s)"
            )

    h.log.info("")
    h.log.info("Cleanup complete. SEED phase can now run from a blank slate.")
    if not TEST_CLOCK_ID:
        h.log.info(
            "  💡 Pin the test clock for future runs to keep cleanup cheap: "
            "export EMAIL_CHANGE_CLOCK_ID=clock_..."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
