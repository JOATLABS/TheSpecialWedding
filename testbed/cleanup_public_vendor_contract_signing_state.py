#!/usr/bin/env python3
"""Clean up state from verify_public_vendor_contract_signing.py.

Safe to re-run.

Usage:
    python3 testbed/cleanup_public_vendor_contract_signing_state.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from testbed.harness import Harness  # noqa: E402


PLANNER_EMAIL = "test_planner+publicvendorsign@thespecialwedding.io"
VENDOR_EMAIL = "vendor+publicvendorsign@thespecialwedding.io"
VENDOR_BUSINESS_NAME = "Elton MC QA - PublicVendorSign"


def cleanup(h: Harness) -> None:
    user = h.mongo["users"].find_one({"email": PLANNER_EMAIL})
    if not user:
        h.log.info("  (no planner user - scrubbing any orphan verifier rows)")
        _cleanup_orphans(h)
        return

    h.log.info(f"Cleaning state for planner {PLANNER_EMAIL}...")

    contract_filter = {"created_by": PLANNER_EMAIL}
    contract_ids = [
        str(c["_id"])
        for c in h.mongo["vendor_contracts"].find(contract_filter, {"_id": 1})
    ]
    if contract_ids:
        milestones = h.mongo["vendor_payment_milestones"].delete_many(
            {"contract_id": {"$in": contract_ids}}
        )
        if milestones.deleted_count:
            h.log.info(
                f"  OK vendor_payment_milestones: removed {milestones.deleted_count}"
            )

        activities = h.mongo["vendor_contract_activities"].delete_many(
            {
                "$or": [
                    {"contract_id": {"$in": contract_ids}},
                    {"root_contract_id": {"$in": contract_ids}},
                ]
            }
        )
        if activities.deleted_count:
            h.log.info(
                f"  OK vendor_contract_activities: removed {activities.deleted_count}"
            )

        contracts = h.mongo["vendor_contracts"].delete_many(contract_filter)
        if contracts.deleted_count:
            h.log.info(f"  OK vendor_contracts: removed {contracts.deleted_count}")

    assignments = h.mongo["vendor_assignments"].delete_many(
        {"created_by": PLANNER_EMAIL}
    )
    if assignments.deleted_count:
        h.log.info(f"  OK vendor_assignments: removed {assignments.deleted_count}")

    vendors = h.mongo["vendor_profiles"].delete_many(
        {
            "$or": [
                {"business_name": VENDOR_BUSINESS_NAME},
                {"email": VENDOR_EMAIL},
            ],
            "created_by": PLANNER_EMAIL,
        }
    )
    if vendors.deleted_count:
        h.log.info(f"  OK vendor_profiles: removed {vendors.deleted_count}")

    h.delete_user_chain(PLANNER_EMAIL)


def _cleanup_orphans(h: Harness) -> None:
    vendors = h.mongo["vendor_profiles"].delete_many(
        {"$or": [{"business_name": VENDOR_BUSINESS_NAME}, {"email": VENDOR_EMAIL}]}
    )
    if vendors.deleted_count:
        h.log.info(f"  OK orphan vendor_profiles: removed {vendors.deleted_count}")

    contracts = h.mongo["vendor_contracts"].delete_many({"created_by": PLANNER_EMAIL})
    if contracts.deleted_count:
        h.log.info(f"  OK orphan vendor_contracts: removed {contracts.deleted_count}")

    assignments = h.mongo["vendor_assignments"].delete_many(
        {"created_by": PLANNER_EMAIL}
    )
    if assignments.deleted_count:
        h.log.info(
            f"  OK orphan vendor_assignments: removed {assignments.deleted_count}"
        )


def main() -> int:
    h = Harness(driver_name="cleanup_public_vendor_contract_signing")
    h.log.info("Starting cleanup of public vendor contract signing verifier state...")
    h.log.info(f"  Mongo DB: {h.config.mongo_db}")
    h.log.info(f"  Planner:  {PLANNER_EMAIL}")
    h.log.info(f"  Vendor:   {VENDOR_BUSINESS_NAME} <{VENDOR_EMAIL}>")
    h.log.info("")
    cleanup(h)
    h.log.info("")
    h.log.info("Cleanup complete.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        import logging

        logging.getLogger("cleanup_public_vendor_contract_signing").error(
            f"Cleanup aborted: {exc}", exc_info=True
        )
        raise SystemExit(1)
