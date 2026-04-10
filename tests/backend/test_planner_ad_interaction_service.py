"""
Comprehensive test suite for PlannerAdInteractionService (Phase 3).

Tests cover:
- Add to Directory flow (10+ tests)
- Request Quote flow (12+ tests)
- Get Sponsored Cards flow (6+ tests)
- Check Directory Status flow (3+ tests)

Total: 30+ tests
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import mongomock
import pytest
from bson import ObjectId
from fastapi import HTTPException

# Setup path and environment
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("ROOT_ADMIN_EMAIL", "thedeveloper@thespecialwedding.io")

from app.models.advertising_campaign import CampaignStatus
from app.services.planner_ad_interaction_service import PlannerAdInteractionService
from tests.backend.conftest_advertising import (
    VENDOR_EMAIL,
    VENDOR_ID,
    VENDOR_NAME,
    AsyncMockDatabase,
    make_campaign,
    make_creative,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def service_and_db():
    """Create a fresh PlannerAdInteractionService with mongomock database."""
    client = mongomock.MongoClient()
    raw_db = client["test_planner_interactions"]
    db = AsyncMockDatabase(raw_db)
    service = PlannerAdInteractionService(db, email_service=None)
    return service, db, raw_db


@pytest.fixture
def service_with_email():
    """Create a PlannerAdInteractionService with mocked email service."""
    client = mongomock.MongoClient()
    raw_db = client["test_planner_interactions_email"]
    db = AsyncMockDatabase(raw_db)
    email_service = AsyncMock()
    service = PlannerAdInteractionService(db, email_service=email_service)
    return service, db, raw_db, email_service


# =============================================================================
# ADD TO DIRECTORY TESTS (10+ tests)
# =============================================================================


@pytest.mark.asyncio
async def test_add_to_directory_success(service_and_db):
    """Successfully add vendor to directory from active campaign."""
    service, db, raw_db = service_and_db

    # Create active campaign with creative
    campaign_doc = make_campaign(status=CampaignStatus.ACTIVE.value)
    campaign_result = raw_db["ad_campaigns"].insert_one(campaign_doc)
    campaign_id = str(campaign_result.inserted_id)

    creative_doc = make_creative(campaign_id)
    creative_result = raw_db["ad_creatives"].insert_one(creative_doc)
    creative_id = str(creative_result.inserted_id)

    # Update campaign with primary creative
    raw_db["ad_campaigns"].update_one(
        {"_id": campaign_result.inserted_id},
        {"$set": {"primary_creative_id": creative_id}},
    )

    planner_email = "planner@example.com"
    result = await service.add_to_directory(
        campaign_id=campaign_id, planner_id="planner123", planner_email=planner_email
    )

    assert result["status"] == "added_to_directory"
    assert "vendor_profile" in result
    assert "lead_id" in result
    assert result["vendor_profile"]["created_by"] == planner_email
    assert result["vendor_profile"]["planner_id"] == "planner123"
    assert result["vendor_profile"]["business_name"] == VENDOR_NAME
    assert result["vendor_profile"]["source"] == "sponsored_ad"
    assert result["vendor_profile"]["source_campaign_id"] == campaign_id


@pytest.mark.asyncio
async def test_add_to_directory_creates_vendor_profile(service_and_db):
    """Create vendor_profile with correct fields."""
    service, db, raw_db = service_and_db

    campaign_doc = make_campaign(status=CampaignStatus.ACTIVE.value)
    campaign_result = raw_db["ad_campaigns"].insert_one(campaign_doc)
    campaign_id = str(campaign_result.inserted_id)

    creative_doc = make_creative(campaign_id)
    creative_result = raw_db["ad_creatives"].insert_one(creative_doc)
    creative_id = str(creative_result.inserted_id)

    raw_db["ad_campaigns"].update_one(
        {"_id": campaign_result.inserted_id},
        {"$set": {"primary_creative_id": creative_id}},
    )

    planner_email = "planner@example.com"
    result = await service.add_to_directory(
        campaign_id=campaign_id, planner_id="planner123", planner_email=planner_email
    )

    vendor_profile = result["vendor_profile"]
    assert vendor_profile["business_name"] == VENDOR_NAME
    assert vendor_profile["email"] == VENDOR_EMAIL
    assert vendor_profile["planner_id"] == "planner123"
    assert vendor_profile["source"] == "sponsored_ad"
    assert vendor_profile["source_campaign_id"] == campaign_id
    assert vendor_profile["source_vendor_id"] == VENDOR_ID
    assert vendor_profile["source_creative_id"] == creative_id
    assert vendor_profile["service_category"] == "florist"
    assert vendor_profile["is_active"] is True
    assert vendor_profile["tags"] == ["sponsored_ad"]


@pytest.mark.asyncio
async def test_add_to_directory_creates_ad_lead(service_and_db):
    """Create ad_lead with lead_type: 'add_to_directory', status: 'converted'."""
    service, db, raw_db = service_and_db

    campaign_doc = make_campaign(status=CampaignStatus.ACTIVE.value)
    campaign_result = raw_db["ad_campaigns"].insert_one(campaign_doc)
    campaign_id = str(campaign_result.inserted_id)

    creative_doc = make_creative(campaign_id)
    creative_result = raw_db["ad_creatives"].insert_one(creative_doc)
    creative_id = str(creative_result.inserted_id)

    raw_db["ad_campaigns"].update_one(
        {"_id": campaign_result.inserted_id},
        {"$set": {"primary_creative_id": creative_id}},
    )

    planner_email = "planner@example.com"
    await service.add_to_directory(
        campaign_id=campaign_id, planner_id="planner123", planner_email=planner_email
    )

    leads = list(raw_db["ad_leads"].find({}))
    assert len(leads) == 1
    lead = leads[0]
    assert lead["lead_type"] == "add_to_directory"
    assert lead["status"] == "converted"
    assert lead["campaign_id"] == campaign_id
    assert lead["planner_id"] == planner_email
    assert lead["converted_at"] is not None


@pytest.mark.asyncio
async def test_add_to_directory_creates_ad_event(service_and_db):
    """Create ad_event with event_type: 'vendor_added_to_directory'."""
    service, db, raw_db = service_and_db

    campaign_doc = make_campaign(status=CampaignStatus.ACTIVE.value)
    campaign_result = raw_db["ad_campaigns"].insert_one(campaign_doc)
    campaign_id = str(campaign_result.inserted_id)

    creative_doc = make_creative(campaign_id)
    creative_result = raw_db["ad_creatives"].insert_one(creative_doc)
    creative_id = str(creative_result.inserted_id)

    raw_db["ad_campaigns"].update_one(
        {"_id": campaign_result.inserted_id},
        {"$set": {"primary_creative_id": creative_id}},
    )

    planner_email = "planner@example.com"
    await service.add_to_directory(
        campaign_id=campaign_id, planner_id="planner123", planner_email=planner_email
    )

    events = list(raw_db["ad_events"].find({}))
    assert len(events) == 1
    event = events[0]
    assert event["event_type"] == "vendor_added_to_directory"
    assert event["campaign_id"] == campaign_id
    assert event["planner_id"] == planner_email


@pytest.mark.asyncio
async def test_add_to_directory_increments_campaign_counters(service_and_db):
    """Increment campaign lead_count and conversion_count."""
    service, db, raw_db = service_and_db

    campaign_doc = make_campaign(status=CampaignStatus.ACTIVE.value)
    campaign_result = raw_db["ad_campaigns"].insert_one(campaign_doc)
    campaign_id = str(campaign_result.inserted_id)

    creative_doc = make_creative(campaign_id)
    creative_result = raw_db["ad_creatives"].insert_one(creative_doc)
    creative_id = str(creative_result.inserted_id)

    raw_db["ad_campaigns"].update_one(
        {"_id": campaign_result.inserted_id},
        {"$set": {"primary_creative_id": creative_id}},
    )

    planner_email = "planner@example.com"
    await service.add_to_directory(
        campaign_id=campaign_id, planner_id="planner123", planner_email=planner_email
    )

    campaign = raw_db["ad_campaigns"].find_one({"_id": campaign_result.inserted_id})
    assert campaign["lead_count"] == 1
    assert campaign["conversion_count"] == 1


@pytest.mark.asyncio
async def test_add_to_directory_duplicate_returns_409(service_and_db):
    """Return 409 if planner already added vendor from same campaign."""
    service, db, raw_db = service_and_db

    campaign_doc = make_campaign(status=CampaignStatus.ACTIVE.value)
    campaign_result = raw_db["ad_campaigns"].insert_one(campaign_doc)
    campaign_id = str(campaign_result.inserted_id)

    creative_doc = make_creative(campaign_id)
    creative_result = raw_db["ad_creatives"].insert_one(creative_doc)
    creative_id = str(creative_result.inserted_id)

    raw_db["ad_campaigns"].update_one(
        {"_id": campaign_result.inserted_id},
        {"$set": {"primary_creative_id": creative_id}},
    )

    planner_email = "planner@example.com"

    # First add should succeed
    await service.add_to_directory(
        campaign_id=campaign_id, planner_id="planner123", planner_email=planner_email
    )

    # Second add should fail
    with pytest.raises(HTTPException) as exc:
        await service.add_to_directory(
            campaign_id=campaign_id,
            planner_id="planner123",
            planner_email=planner_email,
        )
    assert exc.value.status_code == 409
    assert "already in your directory" in exc.value.detail


@pytest.mark.asyncio
async def test_add_to_directory_campaign_not_found_returns_404(service_and_db):
    """Return 404 if campaign doesn't exist."""
    service, db, raw_db = service_and_db

    planner_email = "planner@example.com"
    with pytest.raises(HTTPException) as exc:
        await service.add_to_directory(
            campaign_id=str(ObjectId()),
            planner_id="planner123",
            planner_email=planner_email,
        )
    assert exc.value.status_code == 404
    assert "Campaign not found" in exc.value.detail


@pytest.mark.asyncio
async def test_add_to_directory_campaign_not_active_returns_400(service_and_db):
    """Return 400 if campaign is not active."""
    service, db, raw_db = service_and_db

    for status in [
        CampaignStatus.DRAFT.value,
        CampaignStatus.PAUSED.value,
        CampaignStatus.COMPLETED.value,
    ]:
        campaign_doc = make_campaign(status=status)
        campaign_result = raw_db["ad_campaigns"].insert_one(campaign_doc)
        campaign_id = str(campaign_result.inserted_id)

        planner_email = "planner@example.com"
        with pytest.raises(HTTPException) as exc:
            await service.add_to_directory(
                campaign_id=campaign_id,
                planner_id="planner123",
                planner_email=planner_email,
            )
        assert exc.value.status_code == 400
        assert "not active" in exc.value.detail


@pytest.mark.asyncio
async def test_add_to_directory_includes_creative_description(service_and_db):
    """Include primary creative description in vendor_profile.service_description."""
    service, db, raw_db = service_and_db

    campaign_doc = make_campaign(status=CampaignStatus.ACTIVE.value)
    campaign_result = raw_db["ad_campaigns"].insert_one(campaign_doc)
    campaign_id = str(campaign_result.inserted_id)

    custom_description = "Premium bouquets for every occasion"
    creative_doc = make_creative(campaign_id, description=custom_description)
    creative_result = raw_db["ad_creatives"].insert_one(creative_doc)
    creative_id = str(creative_result.inserted_id)

    raw_db["ad_campaigns"].update_one(
        {"_id": campaign_result.inserted_id},
        {"$set": {"primary_creative_id": creative_id}},
    )

    planner_email = "planner@example.com"
    result = await service.add_to_directory(
        campaign_id=campaign_id, planner_id="planner123", planner_email=planner_email
    )

    assert result["vendor_profile"]["service_description"] == custom_description


@pytest.mark.asyncio
async def test_add_to_directory_no_primary_creative_handles_gracefully(service_and_db):
    """Handle campaign with no primary creative gracefully."""
    service, db, raw_db = service_and_db

    campaign_doc = make_campaign(
        status=CampaignStatus.ACTIVE.value, primary_creative_id=None
    )
    campaign_result = raw_db["ad_campaigns"].insert_one(campaign_doc)
    campaign_id = str(campaign_result.inserted_id)

    planner_email = "planner@example.com"
    result = await service.add_to_directory(
        campaign_id=campaign_id, planner_id="planner123", planner_email=planner_email
    )

    assert result["vendor_profile"]["service_description"] is None
    assert result["vendor_profile"]["source_creative_id"] is None


@pytest.mark.asyncio
async def test_add_to_directory_with_click_id(service_and_db):
    """Add to directory preserves provided click_id."""
    service, db, raw_db = service_and_db

    campaign_doc = make_campaign(status=CampaignStatus.ACTIVE.value)
    campaign_result = raw_db["ad_campaigns"].insert_one(campaign_doc)
    campaign_id = str(campaign_result.inserted_id)

    creative_doc = make_creative(campaign_id)
    creative_result = raw_db["ad_creatives"].insert_one(creative_doc)
    creative_id = str(creative_result.inserted_id)

    raw_db["ad_campaigns"].update_one(
        {"_id": campaign_result.inserted_id},
        {"$set": {"primary_creative_id": creative_id}},
    )

    planner_email = "planner@example.com"
    custom_click_id = "custom-click-123"
    await service.add_to_directory(
        campaign_id=campaign_id,
        planner_id="planner123",
        planner_email=planner_email,
        click_id=custom_click_id,
    )

    event = raw_db["ad_events"].find_one({})
    assert event["click_id"] == custom_click_id


# =============================================================================
# REQUEST QUOTE TESTS (12+ tests)
# =============================================================================


@pytest.mark.asyncio
async def test_request_quote_success(service_and_db):
    """Successfully create quote request lead."""
    service, db, raw_db = service_and_db

    campaign_doc = make_campaign(status=CampaignStatus.ACTIVE.value)
    campaign_result = raw_db["ad_campaigns"].insert_one(campaign_doc)
    campaign_id = str(campaign_result.inserted_id)

    creative_doc = make_creative(campaign_id)
    creative_result = raw_db["ad_creatives"].insert_one(creative_doc)
    creative_id = str(creative_result.inserted_id)

    raw_db["ad_campaigns"].update_one(
        {"_id": campaign_result.inserted_id},
        {"$set": {"primary_creative_id": creative_id}},
    )

    planner_email = "planner@example.com"
    result = await service.request_quote(
        campaign_id=campaign_id,
        planner_id="planner123",
        planner_email=planner_email,
        planner_name="Jane Planner",
        message="I'd like a quote for my June wedding",
        auto_add_to_directory=False,
    )

    assert result["status"] == "quote_requested"
    assert "lead_id" in result
    assert result["email_sent"] is False
    assert result["auto_added_to_directory"] is False


@pytest.mark.asyncio
async def test_request_quote_creates_ad_lead(service_and_db):
    """Create ad_lead with lead_type: 'quote_request', status: 'pending'."""
    service, db, raw_db = service_and_db

    campaign_doc = make_campaign(status=CampaignStatus.ACTIVE.value)
    campaign_result = raw_db["ad_campaigns"].insert_one(campaign_doc)
    campaign_id = str(campaign_result.inserted_id)

    creative_doc = make_creative(campaign_id)
    creative_result = raw_db["ad_creatives"].insert_one(creative_doc)
    creative_id = str(creative_result.inserted_id)

    raw_db["ad_campaigns"].update_one(
        {"_id": campaign_result.inserted_id},
        {"$set": {"primary_creative_id": creative_id}},
    )

    planner_email = "planner@example.com"
    message = "I'd like a quote for my June wedding"
    await service.request_quote(
        campaign_id=campaign_id,
        planner_id="planner123",
        planner_email=planner_email,
        planner_name="Jane Planner",
        message=message,
        auto_add_to_directory=False,
    )

    leads = list(raw_db["ad_leads"].find({}))
    assert len(leads) == 1
    lead = leads[0]
    assert lead["lead_type"] == "quote_request"
    assert lead["status"] == "pending"
    assert lead["message"] == message
    assert lead["campaign_id"] == campaign_id
    assert lead["planner_id"] == planner_email


@pytest.mark.asyncio
async def test_request_quote_creates_ad_event(service_and_db):
    """Create ad_event with event_type: 'lead_created'."""
    service, db, raw_db = service_and_db

    campaign_doc = make_campaign(status=CampaignStatus.ACTIVE.value)
    campaign_result = raw_db["ad_campaigns"].insert_one(campaign_doc)
    campaign_id = str(campaign_result.inserted_id)

    creative_doc = make_creative(campaign_id)
    creative_result = raw_db["ad_creatives"].insert_one(creative_doc)
    creative_id = str(creative_result.inserted_id)

    raw_db["ad_campaigns"].update_one(
        {"_id": campaign_result.inserted_id},
        {"$set": {"primary_creative_id": creative_id}},
    )

    planner_email = "planner@example.com"
    await service.request_quote(
        campaign_id=campaign_id,
        planner_id="planner123",
        planner_email=planner_email,
        planner_name="Jane Planner",
        message="Quote request message",
        auto_add_to_directory=False,
    )

    events = list(raw_db["ad_events"].find({}))
    assert len(events) == 1
    event = events[0]
    assert event["event_type"] == "lead_created"
    assert event["campaign_id"] == campaign_id
    assert event["planner_id"] == planner_email


@pytest.mark.asyncio
async def test_request_quote_increments_lead_count_not_conversion_count(service_and_db):
    """Increment campaign lead_count (but NOT conversion_count)."""
    service, db, raw_db = service_and_db

    campaign_doc = make_campaign(status=CampaignStatus.ACTIVE.value)
    campaign_result = raw_db["ad_campaigns"].insert_one(campaign_doc)
    campaign_id = str(campaign_result.inserted_id)

    creative_doc = make_creative(campaign_id)
    creative_result = raw_db["ad_creatives"].insert_one(creative_doc)
    creative_id = str(creative_result.inserted_id)

    raw_db["ad_campaigns"].update_one(
        {"_id": campaign_result.inserted_id},
        {"$set": {"primary_creative_id": creative_id}},
    )

    planner_email = "planner@example.com"
    await service.request_quote(
        campaign_id=campaign_id,
        planner_id="planner123",
        planner_email=planner_email,
        planner_name="Jane Planner",
        message="Quote request",
        auto_add_to_directory=False,
    )

    campaign = raw_db["ad_campaigns"].find_one({"_id": campaign_result.inserted_id})
    assert campaign["lead_count"] == 1
    assert campaign["conversion_count"] == 0


@pytest.mark.asyncio
async def test_request_quote_empty_message_returns_400(service_and_db):
    """Return 400 if message is empty."""
    service, db, raw_db = service_and_db

    campaign_doc = make_campaign(status=CampaignStatus.ACTIVE.value)
    campaign_result = raw_db["ad_campaigns"].insert_one(campaign_doc)
    campaign_id = str(campaign_result.inserted_id)

    creative_doc = make_creative(campaign_id)
    creative_result = raw_db["ad_creatives"].insert_one(creative_doc)

    raw_db["ad_campaigns"].update_one(
        {"_id": campaign_result.inserted_id},
        {"$set": {"primary_creative_id": str(creative_result.inserted_id)}},
    )

    planner_email = "planner@example.com"
    with pytest.raises(HTTPException) as exc:
        await service.request_quote(
            campaign_id=campaign_id,
            planner_id="planner123",
            planner_email=planner_email,
            planner_name="Jane Planner",
            message="",
            auto_add_to_directory=False,
        )
    assert exc.value.status_code == 400
    assert "empty" in exc.value.detail


@pytest.mark.asyncio
async def test_request_quote_campaign_not_found_returns_404(service_and_db):
    """Return 404 if campaign doesn't exist."""
    service, db, raw_db = service_and_db

    planner_email = "planner@example.com"
    with pytest.raises(HTTPException) as exc:
        await service.request_quote(
            campaign_id=str(ObjectId()),
            planner_id="planner123",
            planner_email=planner_email,
            planner_name="Jane Planner",
            message="Quote request",
            auto_add_to_directory=False,
        )
    assert exc.value.status_code == 404
    assert "Campaign not found" in exc.value.detail


@pytest.mark.asyncio
async def test_request_quote_campaign_not_active_returns_400(service_and_db):
    """Return 400 if campaign is not active."""
    service, db, raw_db = service_and_db

    campaign_doc = make_campaign(status=CampaignStatus.DRAFT.value)
    campaign_result = raw_db["ad_campaigns"].insert_one(campaign_doc)
    campaign_id = str(campaign_result.inserted_id)

    planner_email = "planner@example.com"
    with pytest.raises(HTTPException) as exc:
        await service.request_quote(
            campaign_id=campaign_id,
            planner_id="planner123",
            planner_email=planner_email,
            planner_name="Jane Planner",
            message="Quote request",
            auto_add_to_directory=False,
        )
    assert exc.value.status_code == 400
    assert "not active" in exc.value.detail


@pytest.mark.asyncio
async def test_request_quote_auto_add_to_directory_true(service_and_db):
    """Auto-add vendor to directory when auto_add_to_directory=True."""
    service, db, raw_db = service_and_db

    campaign_doc = make_campaign(status=CampaignStatus.ACTIVE.value)
    campaign_result = raw_db["ad_campaigns"].insert_one(campaign_doc)
    campaign_id = str(campaign_result.inserted_id)

    creative_doc = make_creative(campaign_id)
    creative_result = raw_db["ad_creatives"].insert_one(creative_doc)
    creative_id = str(creative_result.inserted_id)

    raw_db["ad_campaigns"].update_one(
        {"_id": campaign_result.inserted_id},
        {"$set": {"primary_creative_id": creative_id}},
    )

    planner_email = "planner@example.com"
    result = await service.request_quote(
        campaign_id=campaign_id,
        planner_id="planner123",
        planner_email=planner_email,
        planner_name="Jane Planner",
        message="Quote request",
        auto_add_to_directory=True,
    )

    assert result["auto_added_to_directory"] is True
    assert result["vendor_profile_id"] is not None

    profiles = list(raw_db["vendor_profiles"].find({"created_by": planner_email}))
    assert len(profiles) == 1
    assert profiles[0]["source_campaign_id"] == campaign_id


@pytest.mark.asyncio
async def test_request_quote_auto_add_to_directory_false(service_and_db):
    """Not auto-add when auto_add_to_directory=False."""
    service, db, raw_db = service_and_db

    campaign_doc = make_campaign(status=CampaignStatus.ACTIVE.value)
    campaign_result = raw_db["ad_campaigns"].insert_one(campaign_doc)
    campaign_id = str(campaign_result.inserted_id)

    creative_doc = make_creative(campaign_id)
    creative_result = raw_db["ad_creatives"].insert_one(creative_doc)
    creative_id = str(creative_result.inserted_id)

    raw_db["ad_campaigns"].update_one(
        {"_id": campaign_result.inserted_id},
        {"$set": {"primary_creative_id": creative_id}},
    )

    planner_email = "planner@example.com"
    result = await service.request_quote(
        campaign_id=campaign_id,
        planner_id="planner123",
        planner_email=planner_email,
        planner_name="Jane Planner",
        message="Quote request",
        auto_add_to_directory=False,
    )

    assert result["auto_added_to_directory"] is False
    assert result["vendor_profile_id"] is None

    profiles = list(raw_db["vendor_profiles"].find({"created_by": planner_email}))
    assert len(profiles) == 0


@pytest.mark.asyncio
async def test_request_quote_no_duplicate_directory_entry(service_and_db):
    """Not duplicate directory entry if vendor already added."""
    service, db, raw_db = service_and_db

    campaign_doc = make_campaign(status=CampaignStatus.ACTIVE.value)
    campaign_result = raw_db["ad_campaigns"].insert_one(campaign_doc)
    campaign_id = str(campaign_result.inserted_id)

    creative_doc = make_creative(campaign_id)
    creative_result = raw_db["ad_creatives"].insert_one(creative_doc)
    creative_id = str(creative_result.inserted_id)

    raw_db["ad_campaigns"].update_one(
        {"_id": campaign_result.inserted_id},
        {"$set": {"primary_creative_id": creative_id}},
    )

    planner_email = "planner@example.com"

    # First request with auto-add
    await service.request_quote(
        campaign_id=campaign_id,
        planner_id="planner123",
        planner_email=planner_email,
        planner_name="Jane Planner",
        message="First quote request",
        auto_add_to_directory=True,
    )

    # Second request with auto-add (should not duplicate)
    result = await service.request_quote(
        campaign_id=campaign_id,
        planner_id="planner123",
        planner_email=planner_email,
        planner_name="Jane Planner",
        message="Second quote request",
        auto_add_to_directory=True,
    )

    assert result["auto_added_to_directory"] is False

    profiles = list(raw_db["vendor_profiles"].find({"created_by": planner_email}))
    assert len(profiles) == 1


@pytest.mark.asyncio
async def test_request_quote_stores_wedding_context(service_and_db):
    """Store wedding_context in lead metadata."""
    service, db, raw_db = service_and_db

    campaign_doc = make_campaign(status=CampaignStatus.ACTIVE.value)
    campaign_result = raw_db["ad_campaigns"].insert_one(campaign_doc)
    campaign_id = str(campaign_result.inserted_id)

    creative_doc = make_creative(campaign_id)
    creative_result = raw_db["ad_creatives"].insert_one(creative_doc)
    creative_id = str(creative_result.inserted_id)

    raw_db["ad_campaigns"].update_one(
        {"_id": campaign_result.inserted_id},
        {"$set": {"primary_creative_id": creative_id}},
    )

    planner_email = "planner@example.com"
    wedding_context = {
        "date": "2026-06-15",
        "location": "Dallas, TX",
        "guest_count": 150,
        "venue": "The Grand Hotel",
        "budget_range": "$50,000 - $75,000",
    }
    await service.request_quote(
        campaign_id=campaign_id,
        planner_id="planner123",
        planner_email=planner_email,
        planner_name="Jane Planner",
        message="Quote request",
        wedding_context=wedding_context,
        auto_add_to_directory=False,
    )

    lead = raw_db["ad_leads"].find_one({})
    assert lead["metadata"]["wedding_context"] == wedding_context


@pytest.mark.asyncio
async def test_request_quote_calls_email_service(service_with_email):
    """Email service called when available."""
    service, db, raw_db, email_service = service_with_email

    campaign_doc = make_campaign(status=CampaignStatus.ACTIVE.value)
    campaign_result = raw_db["ad_campaigns"].insert_one(campaign_doc)
    campaign_id = str(campaign_result.inserted_id)

    creative_doc = make_creative(campaign_id)
    creative_result = raw_db["ad_creatives"].insert_one(creative_doc)
    creative_id = str(creative_result.inserted_id)

    raw_db["ad_campaigns"].update_one(
        {"_id": campaign_result.inserted_id},
        {"$set": {"primary_creative_id": creative_id}},
    )

    planner_email = "planner@example.com"
    planner_name = "Jane Planner"
    message = "Quote request message"

    result = await service.request_quote(
        campaign_id=campaign_id,
        planner_id="planner123",
        planner_email=planner_email,
        planner_name=planner_name,
        message=message,
        auto_add_to_directory=False,
    )

    assert result["email_sent"] is True
    email_service.send_email.assert_called_once()

    call_kwargs = email_service.send_email.call_args[1]
    assert call_kwargs["to_email"] == VENDOR_EMAIL
    assert planner_name in call_kwargs["subject"]
    assert message in call_kwargs["html_content"]


@pytest.mark.asyncio
async def test_request_quote_email_failure_doesnt_break_flow(service_with_email):
    """Email failure doesn't break the flow (service returns email_sent=False)."""
    service, db, raw_db, email_service = service_with_email
    email_service.send_email.side_effect = Exception("Email service error")

    campaign_doc = make_campaign(status=CampaignStatus.ACTIVE.value)
    campaign_result = raw_db["ad_campaigns"].insert_one(campaign_doc)
    campaign_id = str(campaign_result.inserted_id)

    creative_doc = make_creative(campaign_id)
    creative_result = raw_db["ad_creatives"].insert_one(creative_doc)
    creative_id = str(creative_result.inserted_id)

    raw_db["ad_campaigns"].update_one(
        {"_id": campaign_result.inserted_id},
        {"$set": {"primary_creative_id": creative_id}},
    )

    planner_email = "planner@example.com"
    result = await service.request_quote(
        campaign_id=campaign_id,
        planner_id="planner123",
        planner_email=planner_email,
        planner_name="Jane Planner",
        message="Quote request",
        auto_add_to_directory=False,
    )

    assert result["status"] == "quote_requested"
    assert result["email_sent"] is False
    assert "lead_id" in result


# =============================================================================
# GET SPONSORED CARDS TESTS (6+ tests)
# =============================================================================


@pytest.mark.asyncio
async def test_get_sponsored_cards_returns_active_campaigns(service_and_db):
    """Return active campaigns with primary creative enrichment."""
    service, db, raw_db = service_and_db

    campaign_doc = make_campaign(status=CampaignStatus.ACTIVE.value)
    campaign_result = raw_db["ad_campaigns"].insert_one(campaign_doc)
    campaign_id = str(campaign_result.inserted_id)

    creative_doc = make_creative(campaign_id)
    creative_result = raw_db["ad_creatives"].insert_one(creative_doc)
    creative_id = str(creative_result.inserted_id)

    raw_db["ad_campaigns"].update_one(
        {"_id": campaign_result.inserted_id},
        {"$set": {"primary_creative_id": creative_id}},
    )

    planner_email = "planner@example.com"
    cards = await service.get_sponsored_cards(planner_email=planner_email, limit=10)

    assert len(cards) == 1
    card = cards[0]
    assert card["campaign_id"] == campaign_id
    assert card["vendor_name"] == VENDOR_NAME
    assert card["creative"] is not None
    assert card["creative"]["creative_id"] == creative_id


@pytest.mark.asyncio
async def test_get_sponsored_cards_excludes_already_added(service_and_db):
    """Exclude campaigns where planner already added vendor to directory."""
    service, db, raw_db = service_and_db

    campaign_doc = make_campaign(status=CampaignStatus.ACTIVE.value)
    campaign_result = raw_db["ad_campaigns"].insert_one(campaign_doc)
    campaign_id = str(campaign_result.inserted_id)

    creative_doc = make_creative(campaign_id)
    creative_result = raw_db["ad_creatives"].insert_one(creative_doc)
    creative_id = str(creative_result.inserted_id)

    raw_db["ad_campaigns"].update_one(
        {"_id": campaign_result.inserted_id},
        {"$set": {"primary_creative_id": creative_id}},
    )

    planner_email = "planner@example.com"

    # Add vendor to directory
    await service.add_to_directory(
        campaign_id=campaign_id, planner_id="planner123", planner_email=planner_email
    )

    # Get sponsored cards should not include this campaign
    cards = await service.get_sponsored_cards(planner_email=planner_email, limit=10)

    assert len(cards) == 0


@pytest.mark.asyncio
async def test_get_sponsored_cards_deduplicates_by_vendor(service_and_db):
    """Deduplicate by vendor_id."""
    service, db, raw_db = service_and_db

    vendor_id = str(ObjectId())

    # Create two campaigns for same vendor
    for i in range(2):
        campaign_doc = make_campaign(
            vendor_id=vendor_id, status=CampaignStatus.ACTIVE.value
        )
        campaign_result = raw_db["ad_campaigns"].insert_one(campaign_doc)
        campaign_id = str(campaign_result.inserted_id)

        creative_doc = make_creative(campaign_id, vendor_id=vendor_id)
        creative_result = raw_db["ad_creatives"].insert_one(creative_doc)
        creative_id = str(creative_result.inserted_id)

        raw_db["ad_campaigns"].update_one(
            {"_id": campaign_result.inserted_id},
            {"$set": {"primary_creative_id": creative_id}},
        )

    planner_email = "planner@example.com"
    cards = await service.get_sponsored_cards(planner_email=planner_email, limit=10)

    # Should only return one card (first campaign)
    assert len(cards) == 1


@pytest.mark.asyncio
async def test_get_sponsored_cards_respects_limit(service_and_db):
    """Respect limit parameter."""
    service, db, raw_db = service_and_db

    # Create 5 campaigns
    for i in range(5):
        vendor_id = str(ObjectId())
        campaign_doc = make_campaign(
            vendor_id=vendor_id,
            status=CampaignStatus.ACTIVE.value,
            quality_score=50 + i,
        )
        campaign_result = raw_db["ad_campaigns"].insert_one(campaign_doc)
        campaign_id = str(campaign_result.inserted_id)

        creative_doc = make_creative(campaign_id, vendor_id=vendor_id)
        creative_result = raw_db["ad_creatives"].insert_one(creative_doc)
        creative_id = str(creative_result.inserted_id)

        raw_db["ad_campaigns"].update_one(
            {"_id": campaign_result.inserted_id},
            {"$set": {"primary_creative_id": creative_id}},
        )

    planner_email = "planner@example.com"
    cards = await service.get_sponsored_cards(planner_email=planner_email, limit=2)

    assert len(cards) == 2


@pytest.mark.asyncio
async def test_get_sponsored_cards_filters_by_categories(service_and_db):
    """Filter by categories."""
    service, db, raw_db = service_and_db

    # Create florist campaign
    campaign_doc = make_campaign(
        status=CampaignStatus.ACTIVE.value, vendor_category="florist"
    )
    campaign_result = raw_db["ad_campaigns"].insert_one(campaign_doc)
    campaign_id = str(campaign_result.inserted_id)

    creative_doc = make_creative(campaign_id)
    creative_result = raw_db["ad_creatives"].insert_one(creative_doc)
    creative_id = str(creative_result.inserted_id)

    raw_db["ad_campaigns"].update_one(
        {"_id": campaign_result.inserted_id},
        {"$set": {"primary_creative_id": creative_id}},
    )

    # Create photographer campaign
    campaign_doc2 = make_campaign(
        vendor_id=str(ObjectId()),
        status=CampaignStatus.ACTIVE.value,
        vendor_category="photographer",
    )
    campaign_result2 = raw_db["ad_campaigns"].insert_one(campaign_doc2)
    campaign_id2 = str(campaign_result2.inserted_id)

    creative_doc2 = make_creative(campaign_id2)
    creative_result2 = raw_db["ad_creatives"].insert_one(creative_doc2)
    creative_id2 = str(creative_result2.inserted_id)

    raw_db["ad_campaigns"].update_one(
        {"_id": campaign_result2.inserted_id},
        {"$set": {"primary_creative_id": creative_id2}},
    )

    planner_email = "planner@example.com"
    cards = await service.get_sponsored_cards(
        planner_email=planner_email, categories=["florist"], limit=10
    )

    assert len(cards) == 1
    assert cards[0]["vendor_category"] == "florist"


@pytest.mark.asyncio
async def test_get_sponsored_cards_empty_when_no_active_campaigns(service_and_db):
    """Return empty list when no active campaigns."""
    service, db, raw_db = service_and_db

    planner_email = "planner@example.com"
    cards = await service.get_sponsored_cards(planner_email=planner_email, limit=10)

    assert cards == []


# =============================================================================
# CHECK DIRECTORY STATUS TESTS (3+ tests)
# =============================================================================


@pytest.mark.asyncio
async def test_check_directory_status_in_directory(service_and_db):
    """Return in_directory: True when vendor already added."""
    service, db, raw_db = service_and_db

    campaign_doc = make_campaign(status=CampaignStatus.ACTIVE.value)
    campaign_result = raw_db["ad_campaigns"].insert_one(campaign_doc)
    campaign_id = str(campaign_result.inserted_id)

    creative_doc = make_creative(campaign_id)
    creative_result = raw_db["ad_creatives"].insert_one(creative_doc)
    creative_id = str(creative_result.inserted_id)

    raw_db["ad_campaigns"].update_one(
        {"_id": campaign_result.inserted_id},
        {"$set": {"primary_creative_id": creative_id}},
    )

    planner_email = "planner@example.com"

    # Add to directory
    result = await service.add_to_directory(
        campaign_id=campaign_id, planner_id="planner123", planner_email=planner_email
    )
    vendor_profile_id = result["vendor_profile"]["_id"]

    # Check status
    status = await service.check_directory_status(
        campaign_id=campaign_id, planner_email=planner_email
    )

    assert status["in_directory"] is True
    assert status["vendor_profile_id"] == vendor_profile_id
    assert status["campaign_id"] == campaign_id


@pytest.mark.asyncio
async def test_check_directory_status_not_in_directory(service_and_db):
    """Return in_directory: False when vendor not added."""
    service, db, raw_db = service_and_db

    campaign_doc = make_campaign(status=CampaignStatus.ACTIVE.value)
    campaign_result = raw_db["ad_campaigns"].insert_one(campaign_doc)
    campaign_id = str(campaign_result.inserted_id)

    planner_email = "planner@example.com"

    status = await service.check_directory_status(
        campaign_id=campaign_id, planner_email=planner_email
    )

    assert status["in_directory"] is False
    assert status["vendor_profile_id"] is None


@pytest.mark.asyncio
async def test_check_directory_status_returns_vendor_profile_id(service_and_db):
    """Return vendor_profile_id when in directory."""
    service, db, raw_db = service_and_db

    campaign_doc = make_campaign(status=CampaignStatus.ACTIVE.value)
    campaign_result = raw_db["ad_campaigns"].insert_one(campaign_doc)
    campaign_id = str(campaign_result.inserted_id)

    creative_doc = make_creative(campaign_id)
    creative_result = raw_db["ad_creatives"].insert_one(creative_doc)
    creative_id = str(creative_result.inserted_id)

    raw_db["ad_campaigns"].update_one(
        {"_id": campaign_result.inserted_id},
        {"$set": {"primary_creative_id": creative_id}},
    )

    planner_email = "planner@example.com"
    add_result = await service.add_to_directory(
        campaign_id=campaign_id, planner_id="planner123", planner_email=planner_email
    )

    status = await service.check_directory_status(
        campaign_id=campaign_id, planner_email=planner_email
    )

    assert status["vendor_profile_id"] == add_result["vendor_profile"]["_id"]
