"""
Vendor Scraper — JSON Export

Exports scraped vendor profiles to a JSON file that can be imported
via the admin panel's Import Vendors modal.

Usage:
    python -m app.jobs.vendor_scraper.export_json <output_file>
    python -m app.jobs.vendor_scraper.export_json /path/to/vendors-2026-04-01.json
    python -m app.jobs.vendor_scraper.export_json --since 24  # only last 24 hours
"""

import asyncio
import argparse
import json
import logging
import sys
from datetime import datetime, timezone, timedelta

from app.core.database import mongo

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

# Fields to include in the export (subset of VendorProfile)
EXPORT_FIELDS = {
    "_id": 0,  # Exclude MongoDB ObjectId — import endpoint handles dedup
    "google_place_id": 1,
    "business_name": 1,
    "email": 1,
    "phone": 1,
    "website": 1,
    "address": 1,
    "city": 1,
    "state": 1,
    "country": 1,
    "postal_code": 1,
    "service_category": 1,
    "service_description": 1,
    "logo_url": 1,
    "typical_price_min": 1,
    "typical_price_max": 1,
    "currency": 1,
    "tags": 1,
    "source": 1,
    "scraped_at": 1,
    "scraped_from_city": 1,
    "created_at": 1,
}


def _serialize_datetime(obj):
    """JSON serializer for datetime objects."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


async def export_vendors(output_path: str, since_hours: int | None = None):
    """
    Export scraped vendors from MongoDB to a JSON file.

    Args:
        output_path: Where to write the JSON file
        since_hours: Only export vendors scraped within the last N hours (None = all scraped)
    """
    # Motor auto-connects on first query — no explicit connect() needed.
    db = mongo.db
    if db is None:
        logger.error("Database not initialized. Check MONGO_URI in your environment.")
        sys.exit(1)

    collection = db["vendor_profiles"]

    query = {"source": "scraped"}
    if since_hours:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)
        query["scraped_at"] = {"$gte": cutoff}

    cursor = collection.find(query, EXPORT_FIELDS).sort("scraped_at", -1)
    vendors = await cursor.to_list(length=None)

    if not vendors:
        logger.warning("No scraped vendors found matching the criteria.")
        # Write empty array so the file exists
        with open(output_path, "w") as f:
            json.dump([], f)
        mongo.close()
        return

    # Write JSON
    with open(output_path, "w") as f:
        json.dump(vendors, f, indent=2, default=_serialize_datetime)

    logger.info(f"Exported {len(vendors)} vendors to {output_path}")
    mongo.close()


def main():
    parser = argparse.ArgumentParser(description="Export scraped vendors to JSON")
    parser.add_argument("output", type=str, help="Output file path")
    parser.add_argument(
        "--since",
        type=int,
        default=None,
        help="Only export vendors scraped within the last N hours (default: all)",
    )
    args = parser.parse_args()

    asyncio.run(export_vendors(args.output, since_hours=args.since))


if __name__ == "__main__":
    main()
