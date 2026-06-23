# ruff: noqa: E402

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import mongomock
import pytest
from bson import ObjectId
from fastapi import HTTPException

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


@pytest.mark.asyncio
async def test_approve_vendor_marks_email_verified_and_requires_password_change(
    service_and_db, monkeypatch
):
    service, raw_db, vendor_id = service_and_db
    raw_db["users"].update_one(
        {"_id": vendor_id},
        {
            "$set": {
                "vendor_account_status": "pending_approval",
                "is_active": False,
                "password_hash": None,
            }
        },
    )

    sent_passwords: list[str] = []

    async def _capture_approval_email(email: str, temp_password: str):
        assert email == "qa-vendor@example.com"
        sent_passwords.append(temp_password)

    monkeypatch.setattr(service, "_send_approval_email", _capture_approval_email)

    result = await service._approve_vendor(
        str(vendor_id),
        "qa-vendor@example.com",
        admin_email="admin@example.com",
    )

    vendor = raw_db["users"].find_one({"_id": vendor_id})

    assert result["status"] == "active"
    assert vendor["vendor_account_status"] == "active"
    assert vendor["is_active"] is True
    assert vendor["must_change_password"] is True
    assert vendor["email_verified"] is True
    assert vendor["email_verified_at"] is not None
    assert vendor["temp_password_expires_at"] is not None
    assert vendor["password_hash"]
    assert sent_passwords


@pytest.mark.asyncio
async def test_approve_vendor_fails_closed_when_frontend_url_missing(
    service_and_db, monkeypatch
):
    service, raw_db, vendor_id = service_and_db
    raw_db["users"].update_one(
        {"_id": vendor_id},
        {
            "$set": {
                "vendor_account_status": "pending_approval",
                "is_active": False,
                "password_hash": None,
            }
        },
    )

    monkeypatch.setattr(
        "app.services.vendor_signup_service.app_settings.frontend_url", None
    )

    with pytest.raises(HTTPException) as exc_info:
        await service._approve_vendor(
            str(vendor_id),
            "qa-vendor@example.com",
            admin_email="admin@example.com",
        )

    vendor = raw_db["users"].find_one({"_id": vendor_id})

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Vendor portal URL is not configured"
    assert vendor["vendor_account_status"] == "pending_approval"
    assert vendor["is_active"] is False
    assert vendor["password_hash"] is None


@pytest.mark.asyncio
async def test_vendor_signup_admin_alert_targets_root_admin_not_vendor(
    service_and_db,
):
    service, _raw_db, vendor_id = service_and_db
    calls = []

    async def _capture_notification(notification_data, created_by):
        calls.append(
            {
                "notification_data": notification_data,
                "created_by": created_by,
            }
        )
        return {"id": "notification-1"}

    service.notification_service = SimpleNamespace(
        create_notification=_capture_notification
    )

    await service._notify_admin_new_signup(
        vendor_email="vendor@example.com",
        business_name="Vendor Studio",
        vendor_id=str(vendor_id),
    )

    assert calls[0]["created_by"] == "system"
    notification = calls[0]["notification_data"]
    assert notification["target_audience"] == "root_admin"
    assert notification["type"] == "vendor_signup"
    assert "user_id" not in notification
