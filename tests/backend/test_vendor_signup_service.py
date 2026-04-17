# ruff: noqa: E402

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import mongomock
import pytest
from bson import ObjectId

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault(
    "SECRET_KEY",
    "test-secret-key-this-is-long-enough-for-validation-testing-purposes-2026",
)
os.environ.setdefault("ROOT_ADMIN_EMAIL", "thedeveloper@thespecialwedding.io")

from app.services.vendor_signup_service import VendorSignupService
from tests.backend.conftest_advertising import AsyncMockDatabase


@pytest.fixture
def service_and_db():
    client = mongomock.MongoClient()
    raw_db = client["test_vendor_signup"]
    vendor_id = ObjectId()
    raw_db["users"].insert_one(
        {
            "_id": vendor_id,
            "email": "qa-vendor@example.com",
            "role": "advertising_vendor",
            "business_name": "QA Vendor",
            "vendor_category": "photographer",
            "vendor_location": "Austin, TX",
            "vendor_phone": "",
            "vendor_website": "",
            "vendor_description": "",
            "logo_url": None,
            "created_at": datetime.now(timezone.utc),
        }
    )
    raw_db["ad_campaigns"].insert_one(
        {
            "_id": ObjectId(),
            "vendor_id": str(vendor_id),
            "vendor_email": "qa-vendor@example.com",
            "vendor_name": "QA Vendor",
            "campaign_name": "QA Campaign",
            "status": "draft",
            "vendor_logo_url": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    )
    db = AsyncMockDatabase(raw_db)
    return VendorSignupService(db), raw_db, vendor_id


@pytest.mark.asyncio
async def test_update_vendor_profile_syncs_logo_into_existing_campaigns(
    service_and_db, monkeypatch
):
    service, raw_db, vendor_id = service_and_db
    logo_url = "https://ads.example.com/vendor-profiles/vendor-123/logo/logo.png"

    monkeypatch.setattr(
        "app.services.vendor_signup_service.AdUploadService.ensure_vendor_asset_url",
        lambda _self, url, *_args, **_kwargs: url,
    )

    result = await service.update_vendor_profile(
        "qa-vendor@example.com",
        {"logo_url": logo_url},
    )

    vendor = raw_db["users"].find_one({"_id": vendor_id})
    campaign = raw_db["ad_campaigns"].find_one({"vendor_id": str(vendor_id)})

    assert result["message"] == "Profile updated"
    assert vendor["logo_url"] == logo_url
    assert campaign["vendor_logo_url"] == logo_url


@pytest.mark.asyncio
async def test_update_vendor_profile_clears_logo_and_deletes_previous_managed_asset(
    service_and_db, monkeypatch
):
    service, raw_db, vendor_id = service_and_db
    previous_logo_url = (
        "https://ads.example.com/vendor-profiles/vendor-123/logo/previous-logo.png"
    )
    raw_db["users"].update_one(
        {"_id": vendor_id},
        {"$set": {"logo_url": previous_logo_url}},
    )
    raw_db["ad_campaigns"].update_many(
        {"vendor_id": str(vendor_id)},
        {"$set": {"vendor_logo_url": previous_logo_url}},
    )

    deleted_assets: list[tuple[str, str, object]] = []

    monkeypatch.setattr(
        "app.services.vendor_signup_service.AdUploadService.ensure_vendor_asset_url",
        lambda _self, url, *_args, **_kwargs: url,
    )
    monkeypatch.setattr(
        "app.services.vendor_signup_service.AdUploadService.delete_asset_url",
        lambda _self, url, vendor_id, asset_kind: (
            deleted_assets.append((url, vendor_id, asset_kind)) or True
        ),
    )

    await service.update_vendor_profile(
        "qa-vendor@example.com",
        {"logo_url": None},
    )

    vendor = raw_db["users"].find_one({"_id": vendor_id})
    campaign = raw_db["ad_campaigns"].find_one({"vendor_id": str(vendor_id)})

    assert vendor["logo_url"] is None
    assert campaign["vendor_logo_url"] is None
    assert deleted_assets == [(previous_logo_url, str(vendor_id), "vendor_logo")]
