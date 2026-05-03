#!/usr/bin/env python3
"""Clean up state from verify_budget_alert_wiring.py.

Removes — using direct Mongo deletes scoped to the planner's
weddings / contracts / vendor profile (mirroring the pattern in
cleanup_vendor_contract_budget_propagation_state.py):

  - budget_alerts rows tied to the planner's wedding(s)
  - payment_records rows tied to the planner's budget categories
  - vendor_payment_milestones rows tied to the planner's contracts
  - vendor_contract_activities rows tied to the planner's contracts
  - vendor_contracts rows tied to the planner
  - vendor_assignments rows tied to the planner
  - vendor_profiles rows seeded by the verifier (matched by
    business_name + email + created_by)
  - budget_categories rows seeded by the verifier (matched by name +
    scoped to the planner's weddings)
  - the planner's user / user_subscriptions / stripe_customers /
    team_members / usage_tracking / weddings rows (via
    harness.delete_user_chain — also handles `assigned_planner_email`
    orphans)
  - the planner user itself

Direct Mongo deletes are used here because there is no admin
"wipe my test state" endpoint. The PRODUCT-state changes during
verification all go through real endpoints — this script is the
after-test scrub.

Safe to re-run.

Usage:
    python testbed/cleanup_budget_alert_wiring_state.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


from testbed.harness import Harness

# ---------------------------------------------------------------------------
# Driver constants — mirror the verifier so cleanup matches what was seeded
# ---------------------------------------------------------------------------

PLANNER_EMAIL = "test_planner+alertwire@thespecialwedding.io"
VENDOR_EMAIL = "vendor+alertwire@thespecialwedding.io"
VENDOR_BUSINESS_NAME = "Lens Co — AlertWire Verifier"
BUDGET_CATEGORY_NAME = "Photography (AlertWire Verifier)"


def cleanup(h: Harness) -> None:
    user = h.mongo["users"].find_one({"email": PLANNER_EMAIL})
    if not user:
        h.log.info("  (no planner user — nothing to clean)")
        # Even with no planner, drop any orphan vendor profile / budget
        # category / alert from a partial seed.
        _cleanup_vendor_orphans(h)
        return

    user_id = str(user["_id"])
    h.log.info(f"Cleaning state for planner {PLANNER_EMAIL} (user_id={user_id})…")

    # 1. Find every wedding owned by this planner so we can scope the
    #    contract / milestone / budget / alert cleanup tightly.
    wedding_query = {
        "$or": [
            {"assigned_planner_email": PLANNER_EMAIL},
            {"planner_id": user_id},
        ]
    }
    wedding_ids = [
        str(w["_id"]) for w in h.mongo["weddings"].find(wedding_query, {"_id": 1})
    ]

    # 2. Enumerate contracts before deleting them so milestones +
    #    activities can be scoped precisely.
    contract_filter = {"created_by": PLANNER_EMAIL}
    contract_ids = [
        str(c["_id"])
        for c in h.mongo["vendor_contracts"].find(contract_filter, {"_id": 1})
    ]
    if contract_ids:
        ms = h.mongo["vendor_payment_milestones"].delete_many(
            {"contract_id": {"$in": contract_ids}}
        )
        if ms.deleted_count:
            h.log.info(f"  ✅ vendor_payment_milestones: removed {ms.deleted_count}")

        # vendor_contract_activities — the activity log written by
        # _log_contract_activity on payment recording.
        act = h.mongo["vendor_contract_activities"].delete_many(
            {"contract_id": {"$in": contract_ids}}
        )
        if act.deleted_count:
            h.log.info(f"  ✅ vendor_contract_activities: removed {act.deleted_count}")

    # 3. vendor_contracts — by created_by.
    if contract_ids:
        cr = h.mongo["vendor_contracts"].delete_many(contract_filter)
        if cr.deleted_count:
            h.log.info(f"  ✅ vendor_contracts: removed {cr.deleted_count}")

    # 4. vendor_assignments — by created_by.
    asn = h.mongo["vendor_assignments"].delete_many({"created_by": PLANNER_EMAIL})
    if asn.deleted_count:
        h.log.info(f"  ✅ vendor_assignments: removed {asn.deleted_count}")

    # 5. vendor_profiles — verifier-seeded vendor only. Match by
    #    business_name AND email AND created_by to avoid clobbering
    #    unrelated profiles if the email is reused elsewhere.
    vp = h.mongo["vendor_profiles"].delete_many(
        {
            "$or": [
                {"business_name": VENDOR_BUSINESS_NAME},
                {"email": VENDOR_EMAIL},
            ],
            "created_by": PLANNER_EMAIL,
        }
    )
    if vp.deleted_count:
        h.log.info(f"  ✅ vendor_profiles: removed {vp.deleted_count}")

    if wedding_ids:
        # 6. budget_alerts — every alert raised by AlertWire for these
        #    weddings. This is THE collection the verifier asserts
        #    against, so it MUST be scrubbed for the next run to start
        #    with a clean over_budget count.
        ba = h.mongo["budget_alerts"].delete_many({"wedding_id": {"$in": wedding_ids}})
        if ba.deleted_count:
            h.log.info(f"  ✅ budget_alerts: removed {ba.deleted_count}")

        # 7. payment_records — direct-budget payments path (System B).
        #    The verifier doesn't write here, but a manual checkpoint
        #    via the budget UI might. Scope tightly via the planner's
        #    categories.
        wedding_category_ids = [
            str(c["_id"])
            for c in h.mongo["budget_categories"].find(
                {"wedding_id": {"$in": wedding_ids}}, {"_id": 1}
            )
        ]
        if wedding_category_ids:
            pr = h.mongo["payment_records"].delete_many(
                {"category_id": {"$in": wedding_category_ids}}
            )
            if pr.deleted_count:
                h.log.info(f"  ✅ payment_records: removed {pr.deleted_count}")

        # 8. budget_categories — verifier-seeded by name + scoped to
        #    the planner's weddings.
        bc = h.mongo["budget_categories"].delete_many(
            {
                "wedding_id": {"$in": wedding_ids},
                "name": BUDGET_CATEGORY_NAME,
            }
        )
        if bc.deleted_count:
            h.log.info(f"  ✅ budget_categories: removed {bc.deleted_count}")

    # 9. Hand the rest off to the harness's standard cleanup arc:
    #    user_subscriptions / stripe_customers / team_members /
    #    usage_tracking / weddings (by assigned_planner_email + by
    #    planner_id) / users itself.
    h.delete_user_chain(PLANNER_EMAIL)


def _cleanup_vendor_orphans(h: Harness) -> None:
    """If a partial run left vendor profile / category / alert rows
    behind without a planner user, scrub them by name match. No-op if
    nothing matches.
    """
    vp = h.mongo["vendor_profiles"].delete_many(
        {
            "$or": [
                {"business_name": VENDOR_BUSINESS_NAME},
                {"email": VENDOR_EMAIL},
            ]
        }
    )
    if vp.deleted_count:
        h.log.info(f"  ✅ vendor_profiles (orphan): removed {vp.deleted_count}")

    bc = h.mongo["budget_categories"].delete_many({"name": BUDGET_CATEGORY_NAME})
    if bc.deleted_count:
        h.log.info(f"  ✅ budget_categories (orphan): removed {bc.deleted_count}")


def main() -> int:
    h = Harness(driver_name="cleanup_budget_alert_wiring")
    h.log.info("Starting cleanup of AlertWire verification state…")
    h.log.info(f"  Mongo DB: {h.config.mongo_db}")
    h.log.info(f"  Planner:  {PLANNER_EMAIL}")
    h.log.info(f"  Vendor:   {VENDOR_BUSINESS_NAME} <{VENDOR_EMAIL}>")
    h.log.info(f"  Category: {BUDGET_CATEGORY_NAME}")
    h.log.info("")
    cleanup(h)
    h.log.info("")
    h.log.info("Cleanup complete. SEED phase can run from a blank slate.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        import logging

        logging.getLogger("cleanup_budget_alert_wiring").error(
            f"Cleanup aborted: {exc}", exc_info=True
        )
        raise SystemExit(1)
