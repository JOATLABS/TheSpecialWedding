#!/usr/bin/env python3
"""Cleanup for verify_guest_help_sms_inbox_lifecycle.py.

Safe to re-run. Removes only the plus-variant planner users, their Stripe
customers, the guest-help SMS support tickets, and planner notifications seeded
by the driver.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from testbed.harness import Harness
from testbed.verify_guest_help_sms_inbox_lifecycle import (
    COUPLE_NAMES,
    GUEST_PHONE,
    PLANNER_A_EMAIL,
    PLANNER_B_EMAIL,
)

DRIVER_NAME = "cleanup_guest_help_sms_inbox_state"


def _delete_stripe_customers_by_email(h: Harness, email: str) -> int:
    deleted = 0
    for customer in h.stripe.Customer.list(email=email, limit=100).auto_paging_iter():
        try:
            h.stripe.Customer.delete(customer.id)
            h.log.info(f"  ✅ Deleted Stripe customer {customer.id} ({customer.email})")
            deleted += 1
        except h.stripe.error.StripeError as exc:
            h.log.warning(f"  ⚠️ Could not delete Stripe customer {customer.id}: {exc}")
    return deleted


def main() -> int:
    h = Harness(driver_name=DRIVER_NAME)
    h.banner("CLEANUP — Guest Help SMS Inbox")

    planner_emails = [PLANNER_A_EMAIL, PLANNER_B_EMAIL]
    wedding_docs = list(
        h.mongo["weddings"].find(
            {
                "$or": [
                    {"assigned_planner_email": {"$in": planner_emails}},
                    {"created_by": {"$in": planner_emails}},
                    {"couple_names": COUPLE_NAMES},
                ]
            },
            {"_id": 1},
        )
    )
    wedding_ids = [str(doc["_id"]) for doc in wedding_docs]

    ticket_filter: dict[str, Any] = {
        "$or": [
            {"assigned_to": {"$in": planner_emails}},
            {"phone": GUEST_PHONE},
            {"origin": "public_help_form"},
        ]
    }
    if wedding_ids:
        ticket_filter["$or"].append({"wedding_id": {"$in": wedding_ids}})

    ticket_ids = [
        str(doc["_id"])
        for doc in h.mongo["support_tickets"].find(ticket_filter, {"_id": 1})
    ]
    ticket_result = h.mongo["support_tickets"].delete_many(ticket_filter)
    h.log.info(f"  support_tickets removed: {ticket_result.deleted_count}")

    notification_filter: dict[str, Any] = {
        "$or": [
            {"planner_id": {"$in": planner_emails}},
            {"metadata.ticket_id": {"$in": ticket_ids or ["__none__"]}},
            {"metadata.origin": "public_help_form"},
        ]
    }
    notification_result = h.mongo["planner_notifications"].delete_many(
        notification_filter
    )
    h.log.info(f"  planner_notifications removed: {notification_result.deleted_count}")

    for email in planner_emails:
        deleted = _delete_stripe_customers_by_email(h, email)
        h.log.info(f"  Stripe customers removed for {email}: {deleted}")
        h.delete_user_chain(email)

    h.log.info("Cleanup complete.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"\n❌ Cleanup aborted: {exc}\n")
        raise SystemExit(1)
