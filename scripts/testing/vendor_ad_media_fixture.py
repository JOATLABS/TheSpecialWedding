# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bson import ObjectId
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.media_storage import MediaStorage, StorageTarget
from app.utils.auth_utils import get_password_hash

DEFAULT_FIXTURE = {
    "email": "qa_vendor_media@thespecialwedding.io",
    "password": "QaVendorMediaPass123!",  # pragma: allowlist secret
    "businessName": "QA Vendor Media",
    "vendorCategory": "photographer",
    "vendorLocation": "Austin, TX",
    "campaignName": "QA Vendor Media Draft Campaign",
}


def load_fixture(raw_fixture: str | None) -> dict[str, Any]:
    fixture = DEFAULT_FIXTURE.copy()
    if raw_fixture:
        fixture.update(json.loads(raw_fixture))
    return fixture


def get_db():
    mongo_uri = os.getenv(
        "VENDOR_AD_MEDIA_FIXTURE_MONGO_URI", "mongodb://localhost:27017"
    )
    db_name = os.getenv("VENDOR_AD_MEDIA_FIXTURE_DB", "wedding")
    return MongoClient(mongo_uri)[db_name]


def delete_vendor_media_prefixes(vendor_id: str) -> None:
    storage = MediaStorage()
    try:
        for prefix in (f"ads/{vendor_id}/", f"vendor-profiles/{vendor_id}/logo/"):
            cursor = None
            while True:
                page = storage.list_objects_page(
                    StorageTarget.AD_ASSETS,
                    prefix=prefix,
                    limit=1000,
                    cursor=cursor,
                )
                for item in page.get("Contents", []):
                    storage.delete_object(StorageTarget.AD_ASSETS, item["Key"])

                if not page.get("IsTruncated"):
                    break
                cursor = page.get("NextContinuationToken")
    except Exception:
        # Storage cleanup is best-effort for test fixtures; DB cleanup still matters.
        return


def cleanup_fixture(db, fixture: dict[str, Any]) -> dict[str, Any]:
    vendor = db["users"].find_one(
        {"email": fixture["email"], "role": "advertising_vendor"},
        {"_id": 1},
    )
    if vendor:
        vendor_id = str(vendor["_id"])
        db["ad_creatives"].delete_many({"vendor_id": vendor_id})
        db["ad_campaigns"].delete_many({"vendor_id": vendor_id})
        db["ad_events"].delete_many({"vendor_id": vendor_id})
        db["ad_leads"].delete_many({"vendor_id": vendor_id})
        db["lead_charges"].delete_many({"vendor_id": vendor_id})
        db["vendor_free_tier"].delete_many({"vendor_id": vendor_id})
        db["ad_billing"].delete_many({"vendor_id": vendor_id})
        db["users"].update_one(
            {"_id": vendor["_id"]},
            {"$set": {"logo_url": None, "updated_at": datetime.now(timezone.utc)}},
        )
        delete_vendor_media_prefixes(vendor_id)

    return {"ok": True}


def seed_fixture(db, fixture: dict[str, Any]) -> dict[str, Any]:
    existing_vendor = db["users"].find_one(
        {"email": fixture["email"], "role": "advertising_vendor"}
    )
    vendor_id = existing_vendor["_id"] if existing_vendor else ObjectId()

    cleanup_fixture(db, fixture)

    now = datetime.now(timezone.utc)
    db["users"].update_one(
        {"_id": vendor_id},
        {
            "$set": {
                "email": fixture["email"],
                "business_name": fixture["businessName"],
                "role": "advertising_vendor",
                "password_hash": get_password_hash(fixture["password"]),
                "must_change_password": False,
                "is_active": True,
                "email_verified": True,
                "email_verified_at": now,
                "vendor_account_status": "active",
                "registration_source": "vendor_self_signup",
                "vendor_category": fixture["vendorCategory"],
                "vendor_location": fixture["vendorLocation"],
                "vendor_phone": "+1-512-555-0110",
                "vendor_website": "https://example.com",
                "vendor_description": "Seeded advertising vendor for live media verification.",
                "logo_url": None,
                "is_free_tier": True,
                "updated_at": now,
            },
            "$setOnInsert": {
                "created_at": now,
            },
        },
        upsert=True,
    )

    campaign_id = ObjectId()
    db["ad_campaigns"].insert_one(
        {
            "_id": campaign_id,
            "vendor_id": str(vendor_id),
            "vendor_email": fixture["email"],
            "vendor_name": fixture["businessName"],
            "campaign_name": fixture["campaignName"],
            "campaign_description": "Seeded draft campaign for vendor media browser verification.",
            "goal": "profile_visits",
            "status": "draft",
            "target_categories": [],
            "target_wedding_stages": [],
            "target_placements": [],
            "target_regions": [fixture["vendorLocation"]],
            "daily_budget": 0.0,
            "total_budget": 0.0,
            "budget_consumed": 0.0,
            "pacing_strategy": "even",
            "bid_amount": 0.0,
            "bid_strategy": "fixed",
            "quality_score": 50,
            "impression_count": 0,
            "click_count": 0,
            "lead_count": 0,
            "conversion_count": 0,
            "primary_creative_id": None,
            "creative_ids": [],
            "submitted_at": None,
            "reviewed_at": None,
            "reviewed_by": None,
            "review_notes": None,
            "vendor_category": fixture["vendorCategory"],
            "vendor_service_area": fixture["vendorLocation"],
            "vendor_logo_url": None,
            "created_by": fixture["email"],
            "metadata": {},
            "created_at": now,
            "updated_at": now,
        }
    )

    return {
        "ok": True,
        "email": fixture["email"],
        "password": fixture["password"],
        "vendorId": str(vendor_id),
        "campaignId": str(campaign_id),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["seed", "cleanup"])
    parser.add_argument("--fixture", default=None)
    args = parser.parse_args()

    fixture = load_fixture(args.fixture)
    db = get_db()

    if args.action == "cleanup":
        payload = cleanup_fixture(db, fixture)
    else:
        payload = seed_fixture(db, fixture)

    print(json.dumps(payload))


if __name__ == "__main__":
    main()
