"""
One-time migration: Backfill guest_id into activity_logs metadata.

Existing activity log entries for guest-related events (guest_added, guest_updated,
guest_deleted, rsvp_received, rsvp_updated, sms_sent, email_sent) were logged
without metadata.guest_id. This script matches them to guest records by
(wedding_id + guest_name) and writes the guest_id into metadata.

Usage:
    # Dry run (default) — shows what would change, writes nothing
    python -m app.scripts.backfill_activity_guest_ids

    # Apply changes
    python -m app.scripts.backfill_activity_guest_ids --apply

    # Verbose dry run
    python -m app.scripts.backfill_activity_guest_ids --verbose
"""

import asyncio
import argparse
import logging
from collections import defaultdict

from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Activity types that should have guest_id in metadata
GUEST_ACTIVITY_TYPES = [
    "guest_added",
    "guest_updated",
    "guest_deleted",
    "rsvp_received",
    "rsvp_updated",
    "sms_sent",
    "email_sent",
]

# Metadata fields that hold the guest name depending on activity type
NAME_FIELDS = ["guest_name", "recipient_name"]


async def build_guest_lookup(db) -> dict:
    """
    Build a lookup: (wedding_id, lowercase_guest_name) -> guest_id (str).

    If multiple guests share the same name within a wedding, we skip that
    name to avoid incorrect matches. A warning is logged.
    """
    guests_col = db["guests"]
    cursor = guests_col.find({}, {"_id": 1, "name": 1, "wedding_id": 1, "email": 1})

    # Temporary: (wedding_id, name_lower) -> [guest_id, ...]
    name_map: dict[tuple, list[str]] = defaultdict(list)
    email_map: dict[tuple, str] = {}  # (wedding_id, email_lower) -> guest_id

    async for guest in cursor:
        gid = str(guest["_id"])
        wid = guest.get("wedding_id", "")
        name = (guest.get("name") or "").strip().lower()
        email = (guest.get("email") or "").strip().lower()

        if wid and name:
            name_map[(wid, name)].append(gid)
        if wid and email:
            email_map[(wid, email)] = gid

    # Flatten — only keep unambiguous name matches
    lookup: dict[tuple, str] = {}
    ambiguous = 0
    for key, ids in name_map.items():
        if len(ids) == 1:
            lookup[key] = ids[0]
        else:
            ambiguous += 1
            logger.warning(
                "Ambiguous name match skipped: wedding=%s name='%s' (%d guests)",
                key[0],
                key[1],
                len(ids),
            )

    logger.info(
        "Guest lookup built: %d unique name matches, %d ambiguous skipped, %d email entries",
        len(lookup),
        ambiguous,
        len(email_map),
    )
    return lookup, email_map


def resolve_guest_id(activity, name_lookup, email_lookup) -> str | None:
    """Try to resolve a guest_id for an activity log entry."""
    metadata = activity.get("metadata") or {}
    wedding_id = activity.get("wedding_id", "")

    if not wedding_id:
        return None

    # Try name-based lookup first
    for field in NAME_FIELDS:
        name = (metadata.get(field) or "").strip().lower()
        if name:
            gid = name_lookup.get((wedding_id, name))
            if gid:
                return gid

    # Fallback: try email-based lookup
    for email_field in ["guest_email", "recipient_email"]:
        email = (metadata.get(email_field) or "").strip().lower()
        if email:
            gid = email_lookup.get((wedding_id, email))
            if gid:
                return gid

    return None


async def run_migration(apply: bool = False, verbose: bool = False):
    """Main migration logic."""
    client = AsyncIOMotorClient(settings.MONGO_URI)
    db = client[settings.MONGO_DB]
    activity_col = db["activity_logs"]

    logger.info("=" * 60)
    logger.info("Activity Log guest_id Backfill Migration")
    logger.info("Mode: %s", "APPLY" if apply else "DRY RUN")
    logger.info("Database: %s", settings.MONGO_DB)
    logger.info("=" * 60)

    # Step 1: Build guest lookup
    name_lookup, email_lookup = await build_guest_lookup(db)

    # Step 2: Find activity logs missing guest_id
    query = {
        "type": {"$in": GUEST_ACTIVITY_TYPES},
        "$or": [
            {"metadata.guest_id": {"$exists": False}},
            {"metadata.guest_id": None},
            {"metadata.guest_id": ""},
        ],
    }

    total = await activity_col.count_documents(query)
    logger.info("Found %d activity log entries missing guest_id", total)

    if total == 0:
        logger.info("Nothing to migrate. All entries already have guest_id.")
        client.close()
        return

    # Step 3: Process in batches
    batch_size = 500
    matched = 0
    unmatched = 0
    updated = 0
    errors = 0

    cursor = activity_col.find(query).batch_size(batch_size)
    bulk_ops = []

    async for activity in cursor:
        guest_id = resolve_guest_id(activity, name_lookup, email_lookup)

        if guest_id:
            matched += 1
            if verbose:
                logger.info(
                    "  MATCH: activity=%s type=%s -> guest_id=%s",
                    activity["_id"],
                    activity.get("type"),
                    guest_id,
                )
            if apply:
                from pymongo import UpdateOne

                bulk_ops.append(
                    UpdateOne(
                        {"_id": activity["_id"]},
                        {"$set": {"metadata.guest_id": guest_id}},
                    )
                )

                # Flush every batch_size
                if len(bulk_ops) >= batch_size:
                    try:
                        result = await activity_col.bulk_write(bulk_ops)
                        updated += result.modified_count
                    except Exception as e:
                        errors += len(bulk_ops)
                        logger.error("Bulk write error: %s", e)
                    bulk_ops = []
        else:
            unmatched += 1
            if verbose:
                meta = activity.get("metadata") or {}
                logger.info(
                    "  NO MATCH: activity=%s type=%s wedding=%s name='%s'",
                    activity["_id"],
                    activity.get("type"),
                    activity.get("wedding_id", "?"),
                    meta.get("guest_name") or meta.get("recipient_name") or "?",
                )

    # Flush remaining
    if apply and bulk_ops:
        try:
            result = await activity_col.bulk_write(bulk_ops)
            updated += result.modified_count
        except Exception as e:
            errors += len(bulk_ops)
            logger.error("Bulk write error: %s", e)

    # Step 4: Report
    logger.info("")
    logger.info("=" * 60)
    logger.info("Migration %s", "Complete" if apply else "Dry Run Complete")
    logger.info("-" * 60)
    logger.info("Total entries scanned:  %d", total)
    logger.info("Matched to a guest:     %d", matched)
    logger.info("Could not match:        %d", unmatched)
    if apply:
        logger.info("Successfully updated:   %d", updated)
        if errors:
            logger.warning("Errors:                 %d", errors)
    else:
        logger.info("")
        logger.info("This was a dry run. Run with --apply to write changes.")
    logger.info("=" * 60)

    client.close()


def main():
    parser = argparse.ArgumentParser(
        description="Backfill guest_id into activity_logs metadata"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually write changes to the database (default is dry run)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Log each individual match/miss",
    )
    args = parser.parse_args()

    asyncio.run(run_migration(apply=args.apply, verbose=args.verbose))


if __name__ == "__main__":
    main()
