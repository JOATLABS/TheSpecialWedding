"""
P0 Refactor — MongoDB Index Migrations
─────────────────────────────────────────────────────────────────────────
Creates indexes required by the P0 architectural refactors:

  1. stripe_webhook_events — unique on event_id, compound on status+created_at
  2. forms — compound index with form_type discriminator
  3. user_subscriptions — compound index including version (optimistic lock)

Best Practice References:
  [5] MongoDB Polymorphic Patterns (Jan 2026) — "Include the discriminator in indexes"
  [8] Webhook Idempotency (DEV Community, 2025) — "Unique constraint on stripeEventId"

Usage:
  python scripts/create_indexes_p0.py
  python scripts/create_indexes_p0.py --dry-run
"""

import argparse
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# Index definitions: (collection, index_spec, kwargs)
INDEXES = [
    # ── Webhook event deduplication [8] ──────────────────────────────
    (
        "stripe_webhook_events",
        [("event_id", 1)],
        {"unique": True, "name": "idx_event_id_unique"},
    ),
    (
        "stripe_webhook_events",
        [("status", 1), ("created_at", 1)],
        {"name": "idx_status_created_at"},
    ),
    # ── Form polymorphic discriminator [5] ───────────────────────────
    (
        "forms",
        [("form_type", 1), ("created_by", 1), ("created_at", -1)],
        {"name": "idx_form_type_creator_date"},
    ),
    (
        "forms",
        [("form_type", 1), ("wedding_id", 1)],
        {
            "name": "idx_form_type_wedding",
            "partialFilterExpression": {"wedding_id": {"$exists": True, "$ne": None}},
        },
    ),
    # ── Subscription optimistic locking [8] ──────────────────────────
    (
        "user_subscriptions",
        [("user_id", 1), ("status", 1), ("version", 1)],
        {"name": "idx_user_status_version"},
    ),
]


async def create_indexes(dry_run: bool = False):
    from app.core.database import mongo

    await mongo.connect()

    try:
        for collection_name, index_spec, kwargs in INDEXES:
            index_name = kwargs.get("name", str(index_spec))
            collection = mongo.db[collection_name]

            # Check if index already exists
            existing = await collection.index_information()
            if index_name in existing:
                logger.info(f"  ✓ {collection_name}.{index_name} — already exists")
                continue

            if dry_run:
                logger.info(
                    f"  [DRY RUN] Would create {collection_name}.{index_name}: {index_spec}"
                )
                continue

            logger.info(f"  → Creating {collection_name}.{index_name}: {index_spec}")
            await collection.create_index(index_spec, **kwargs)
            logger.info(f"  ✓ {collection_name}.{index_name} — created")

        logger.info("✅ Index migration complete.")

    finally:
        await mongo.close()


def main():
    parser = argparse.ArgumentParser(
        description="Create MongoDB indexes for P0 refactors"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    args = parser.parse_args()

    logger.info("P0 Refactor — MongoDB Index Migration")
    logger.info("=" * 50)
    asyncio.run(create_indexes(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
