"""
Migration: Remove budget_category_id from vendor_contracts (P2.2).

Field removed: `vendor_contracts.budget_category_id`

Reason:
  Budget rollup is now derived in pm-substrate via vendor → budget_category
  edge topology. The substrate's @pm/capability-wedding-budget subscribes to
  wedding.contract.payment_recorded and walks the graph:
    contract → [wedding/contract_vendor] → vendor → [wedding/vendor_budget_category] → budgetCategory

  Storing budget_category_id on vendor_contracts was the root cause of a
  production bug: the field was hardcoded None at contract creation, making
  the conditional rollup at vendor_service.record_payment:3129 silently
  unreachable. Manual milestone payments never updated budget_categories.actual_spent.

  See: JOATLABS P2.2 commit + architecture notes.

Safety:
  - Idempotent: safe to run multiple times (both dry-run and --apply).
  - Does NOT delete any contract documents.
  - $unset only removes the field; it leaves all other contract data intact.
  - The `pm_contract_id` field added in P2.2 is NOT touched by this migration;
    it was set on new contracts and is left as-is on existing ones.

Rollback:
  There is no rollback for this migration. The field being removed was only
  ever populated by the (now-removed) assignment lookup in create_contract.
  Contracts created before the assignment-lookup fix (pre-P2.1b) had it as
  None; contracts created after had a real category_id. Post-P2.2, neither
  value is used — the substrate graph is the source of truth.

Usage:
  # Dry run (shows counts, writes nothing):
  python scripts/migrate_remove_budget_category_id_from_vendor_contracts.py

  # Apply:
  python scripts/migrate_remove_budget_category_id_from_vendor_contracts.py --apply

  # Apply verbosely (logs sample affected IDs):
  python scripts/migrate_remove_budget_category_id_from_vendor_contracts.py --apply --verbose
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import mongo

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

COLLECTION = "vendor_contracts"
FIELD = "budget_category_id"


async def count_documents_with_field() -> int:
    """Count vendor_contracts documents that still have the field set (present, not just None)."""
    coll = mongo.db[COLLECTION]
    # Match documents where the field EXISTS (even if its value is None).
    return await coll.count_documents({FIELD: {"$exists": True}})


async def count_documents_with_non_null_field() -> int:
    """Count documents where the field has a real non-None value."""
    coll = mongo.db[COLLECTION]
    return await coll.count_documents({FIELD: {"$ne": None, "$exists": True}})


async def sample_documents_with_field(n: int = 5) -> list[dict]:
    """Return up to n sample documents that have the field."""
    coll = mongo.db[COLLECTION]
    cursor = coll.find({FIELD: {"$exists": True}}, {"_id": 1, FIELD: 1, "created_by": 1}).limit(n)
    return await cursor.to_list(length=n)


async def run_migration(apply: bool, verbose: bool) -> int:
    """
    Run the migration.

    Args:
        apply: If False, dry-run only (no writes).
        verbose: If True, log sample affected document IDs.

    Returns:
        0 on success, 1 on error.
    """
    logger.info("=" * 60)
    logger.info("Migration: remove %s from %s", FIELD, COLLECTION)
    logger.info("Mode: %s", "APPLY" if apply else "DRY RUN")
    logger.info("=" * 60)

    total_with_field = await count_documents_with_field()
    non_null_count = await count_documents_with_non_null_field()
    null_count = total_with_field - non_null_count

    logger.info("Documents with %s field present:     %d", FIELD, total_with_field)
    logger.info("  → field is non-None (had a value): %d", non_null_count)
    logger.info("  → field is None (always empty):    %d", null_count)

    if total_with_field == 0:
        logger.info("Nothing to do — field already absent from all documents.")
        return 0

    if verbose:
        samples = await sample_documents_with_field(n=5)
        logger.info("Sample documents:")
        for doc in samples:
            logger.info(
                "  _id=%s  %s=%r  created_by=%s",
                doc.get("_id"),
                FIELD,
                doc.get(FIELD),
                doc.get("created_by"),
            )

    if not apply:
        logger.info(
            "DRY RUN: would unset %s on %d documents. Re-run with --apply to execute.",
            FIELD,
            total_with_field,
        )
        return 0

    # Apply the migration.
    coll = mongo.db[COLLECTION]
    result = await coll.update_many(
        {FIELD: {"$exists": True}},
        {"$unset": {FIELD: ""}},
    )

    logger.info(
        "Applied: matched=%d modified=%d",
        result.matched_count,
        result.modified_count,
    )

    # Verify idempotency: re-count should be zero.
    remaining = await count_documents_with_field()
    if remaining > 0:
        logger.error(
            "Post-migration check FAILED: %d documents still have %s. "
            "Check for concurrent writes or a failed partial run.",
            remaining,
            FIELD,
        )
        return 1

    logger.info("✅ Post-migration check passed: %s absent from all %s documents.", FIELD, COLLECTION)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="Write the migration. Omit for dry-run.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Log sample affected document IDs before applying.",
    )
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    return await run_migration(apply=args.apply, verbose=args.verbose)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
