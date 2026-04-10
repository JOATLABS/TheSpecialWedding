"""
Migration: Backfill missing required fields on user_subscriptions and users collections.

Fixes:
  1. user_subscriptions missing: user_email, start_date, created_by
  2. users missing: trial_warning_sent, registration_source defaults

Run:
  python -m app.scripts.migrate_subscription_fields

Safe to run multiple times (idempotent).
"""

import asyncio
import os
import sys
from datetime import datetime, timezone

# Ensure project root is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.core.database import init_database, mongo  # noqa: E402


async def migrate():
    await init_database()
    db = mongo.db

    users_col = db["users"]
    subs_col = db["user_subscriptions"]

    print("=" * 60)
    print("Migration: Backfill subscription & user schema fields")
    print("=" * 60)

    # ── 1. Backfill user_subscriptions ──────────────────────────
    print("\n[1/2] Patching user_subscriptions...")

    # Find subscriptions missing any of the required fields
    missing_filter = {
        "$or": [
            {"user_email": {"$exists": False}},
            {"start_date": {"$exists": False}},
            {"created_by": {"$exists": False}},
        ]
    }

    cursor = subs_col.find(missing_filter)
    subs_patched = 0
    subs_skipped = 0

    async for sub in cursor:
        updates = {}

        # Backfill user_email from users collection
        if not sub.get("user_email"):
            user_id = sub.get("user_id")
            if user_id:
                try:
                    from bson import ObjectId

                    user = await users_col.find_one(
                        {"_id": ObjectId(user_id)}, {"email": 1}
                    )
                    if user:
                        updates["user_email"] = user["email"]
                    else:
                        # Try matching by string ID (some old records)
                        user = await users_col.find_one({"_id": user_id}, {"email": 1})
                        if user:
                            updates["user_email"] = user["email"]
                except Exception:
                    pass

            if "user_email" not in updates:
                # Last resort: use stripe_customer_id to find email
                updates["user_email"] = "unknown@migration.backfill"

        # Backfill start_date from created_at or current_period_start
        if not sub.get("start_date"):
            updates["start_date"] = (
                sub.get("current_period_start")
                or sub.get("created_at")
                or datetime.now(timezone.utc)
            )

        # Backfill created_by
        if not sub.get("created_by"):
            updates["created_by"] = "system:migration_backfill"

        if updates:
            updates["updated_at"] = datetime.now(timezone.utc)
            await subs_col.update_one({"_id": sub["_id"]}, {"$set": updates})
            subs_patched += 1
        else:
            subs_skipped += 1

    print(f"   Patched: {subs_patched}  |  Already OK: {subs_skipped}")

    # ── 2. Backfill users collection ────────────────────────────
    print("\n[2/2] Patching users (trial_warning_sent, registration_source)...")

    # Add trial_warning_sent default for planners missing it
    result1 = await users_col.update_many(
        {
            "role": "wedding_planner",
            "trial_warning_sent": {"$exists": False},
        },
        {"$set": {"trial_warning_sent": False}},
    )
    print(f"   trial_warning_sent added to {result1.modified_count} users")

    # Add registration_source default for users missing it
    result2 = await users_col.update_many(
        {
            "registration_source": {"$exists": False},
        },
        {"$set": {"registration_source": "legacy"}},
    )
    print(f"   registration_source added to {result2.modified_count} users")

    # ── Summary ─────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("Migration complete.")
    print(f"  Subscriptions patched: {subs_patched}")
    print(f"  Users updated (trial_warning_sent): {result1.modified_count}")
    print(f"  Users updated (registration_source): {result2.modified_count}")
    print("=" * 60)

    mongo.close()


if __name__ == "__main__":
    asyncio.run(migrate())
