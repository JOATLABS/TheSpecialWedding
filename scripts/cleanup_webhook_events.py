"""
Webhook Event Cleanup Script
─────────────────────────────────────────────────────────────────────────
Deletes processed Stripe webhook events older than the retention period
to prevent unbounded collection growth.

Best Practice Reference:
  "Schedule via cron to prevent table bloat while maintaining audit trail."
  — Building Reliable Stripe Subscriptions (DEV Community, 2025)

Usage:
  python scripts/cleanup_webhook_events.py                  # Default 30 days
  python scripts/cleanup_webhook_events.py --retention 60   # Custom retention
  python scripts/cleanup_webhook_events.py --dry-run        # Preview only

Recommended cron schedule: weekly
  0 3 * * 0  cd /app && python scripts/cleanup_webhook_events.py >> /var/log/webhook_cleanup.log 2>&1
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def cleanup_webhook_events(retention_days: int = 30, dry_run: bool = False):
    """Delete processed webhook events older than retention_days."""
    from app.core.database import mongo

    # Connect to MongoDB
    await mongo.connect()

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        collection = mongo.db["stripe_webhook_events"]

        # Delete events that were successfully processed.
        # Legacy events (pre-status-tracking) have no "status" field but DO
        # have "processed_at" — include them via $or so they don't accumulate.
        query = {
            "$or": [
                {"status": "processed", "processed_at": {"$lt": cutoff}},
                {"status": {"$exists": False}, "processed_at": {"$lt": cutoff}},
            ],
        }

        # Count first
        count = await collection.count_documents(query)
        logger.info(
            f"Found {count} processed webhook events older than {retention_days} days "
            f"(cutoff: {cutoff.isoformat()})"
        )

        if count == 0:
            logger.info("Nothing to clean up.")
            return 0

        if dry_run:
            logger.info(f"[DRY RUN] Would delete {count} events. No changes made.")
            return count

        # Delete in batches to avoid long locks.
        # Max iterations guard prevents infinite loops if concurrent inserts
        # keep adding matching documents between batches.
        batch_size = 500
        max_iterations = (count // batch_size) + 10  # generous headroom
        total_deleted = 0
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            # Find a batch of IDs to delete
            cursor = collection.find(query, {"_id": 1}).limit(batch_size)
            batch_ids = [doc["_id"] async for doc in cursor]

            if not batch_ids:
                break

            result = await collection.delete_many({"_id": {"$in": batch_ids}})
            total_deleted += result.deleted_count
            logger.info(f"  Deleted batch: {result.deleted_count} events (total: {total_deleted}/{count})")

        if iteration >= max_iterations:
            logger.warning(
                f"⚠️  Reached max iteration limit ({max_iterations}). "
                f"Deleted {total_deleted} of {count} events. Re-run if needed."
            )

        logger.info(f"✅ Cleanup complete. Deleted {total_deleted} webhook events.")

        # Also report on failed events (don't delete — they need investigation)
        failed_count = await collection.count_documents({"status": "failed"})
        if failed_count > 0:
            logger.warning(
                f"⚠️  {failed_count} failed webhook events remain. "
                "Review these in the stripe_webhook_events collection."
            )

        # Report on stuck "processing" events (older than 1 hour = likely crashed)
        stuck_cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        stuck_count = await collection.count_documents({
            "status": "processing",
            "created_at": {"$lt": stuck_cutoff},
        })
        if stuck_count > 0:
            logger.warning(
                f"⚠️  {stuck_count} events stuck in 'processing' state (>1 hour old). "
                "These likely represent crashed webhook handlers. Stripe will retry them."
            )

        return total_deleted

    finally:
        await mongo.close()


def main():
    parser = argparse.ArgumentParser(description="Clean up old processed Stripe webhook events")
    parser.add_argument(
        "--retention",
        type=int,
        default=30,
        help="Number of days to retain processed events (default: 30)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be deleted without making changes",
    )
    args = parser.parse_args()

    deleted = asyncio.run(cleanup_webhook_events(
        retention_days=args.retention,
        dry_run=args.dry_run,
    ))
    sys.exit(0 if deleted >= 0 else 1)


if __name__ == "__main__":
    main()
