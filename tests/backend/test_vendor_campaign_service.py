"""
Comprehensive test suite for VendorCampaignService (Phase 2).

Tests cover:
- Campaign CRUD operations
- Campaign lifecycle (submit, pause, complete)
- Creative CRUD and primary creative selection
- Lead retrieval
- Campaign statistics
- Ad serving / planner rail eligibility
- Campaign expiration
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

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

from app.services.vendor_campaign_service import VendorCampaignService
from app.models.advertising_campaign import CampaignStatus, CreativeReviewStatus
from tests.backend.conftest_advertising import (
    AsyncMockDatabase,
    make_campaign,
    make_creative,
    make_ad_lead,
    VENDOR_ID,
    VENDOR_EMAIL,
    VENDOR_NAME,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def service_and_db():
    """Create a fresh VendorCampaignService with mongomock database."""
    client = mongomock.MongoClient()
    raw_db = client["test_vendor_campaigns"]
    db = AsyncMockDatabase(raw_db)
    service = VendorCampaignService(db)
    return service, db, raw_db


# =============================================================================
# CAMPAIGN CRUD TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_create_campaign_returns_draft_with_defaults(service_and_db):
    """Verify create_campaign returns a draft campaign with correct defaults."""
    service, db, raw_db = service_and_db

    result = await service.create_campaign(
        vendor_id=VENDOR_ID,
        vendor_email=VENDOR_EMAIL,
        vendor_name=VENDOR_NAME,
        data={
            "campaign_name": "Test Campaign",
        },
    )

    assert result["_id"] is not None
    assert result["status"] == CampaignStatus.DRAFT.value
    assert result["campaign_name"] == "Test Campaign"
    assert result["goal"] == "profile_visits"
    assert result["daily_budget"] == 0.0
    assert result["total_budget"] == 0.0
    assert result["impression_count"] == 0
    assert result["quality_score"] == 50


@pytest.mark.asyncio
async def test_create_campaign_stores_vendor_identity(service_and_db):
    """Verify vendor identity fields are stored correctly."""
    service, db, raw_db = service_and_db

    result = await service.create_campaign(
        vendor_id=VENDOR_ID,
        vendor_email=VENDOR_EMAIL,
        vendor_name=VENDOR_NAME,
        data={"campaign_name": "Test", "vendor_category": "florist"},
    )

    assert result["vendor_id"] == VENDOR_ID
    assert result["vendor_email"] == VENDOR_EMAIL
    assert result["vendor_name"] == VENDOR_NAME
    assert result["vendor_category"] == "florist"
    assert result["created_by"] == VENDOR_EMAIL


@pytest.mark.asyncio
async def test_get_campaign_returns_serialized_doc(service_and_db):
    """Verify get_campaign returns _id as string."""
    service, db, raw_db = service_and_db

    # Insert raw doc with ObjectId
    campaign_oid = ObjectId()
    campaign_doc = make_campaign(vendor_id=VENDOR_ID, **{"_id": campaign_oid})
    raw_db["ad_campaigns"].insert_one(campaign_doc)

    result = await service.get_campaign(str(campaign_oid), vendor_id=VENDOR_ID)

    assert result["_id"] == str(campaign_oid)
    assert isinstance(result["_id"], str)


@pytest.mark.asyncio
async def test_get_campaign_enforces_vendor_scope(service_and_db):
    """Verify get_campaign rejects access across vendor boundaries."""
    service, db, raw_db = service_and_db

    # Insert campaign for vendor A
    campaign_oid = ObjectId()
    campaign_doc = make_campaign(vendor_id=VENDOR_ID, **{"_id": campaign_oid})
    raw_db["ad_campaigns"].insert_one(campaign_doc)

    # Vendor B tries to access it
    other_vendor_id = str(ObjectId())
    with pytest.raises(HTTPException) as exc_info:
        await service.get_campaign(str(campaign_oid), vendor_id=other_vendor_id)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_campaign_not_found_raises_404(service_and_db):
    """Verify get_campaign raises 404 for non-existent campaign."""
    service, db, raw_db = service_and_db

    fake_oid = str(ObjectId())
    with pytest.raises(HTTPException) as exc_info:
        await service.get_campaign(fake_oid, vendor_id=VENDOR_ID)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_list_campaigns_filters_by_vendor(service_and_db):
    """Verify list_campaigns returns only campaigns for the vendor."""
    service, db, raw_db = service_and_db

    other_vendor_id = str(ObjectId())

    # Insert campaigns for different vendors
    raw_db["ad_campaigns"].insert_one(
        {"_id": ObjectId(), **make_campaign(vendor_id=VENDOR_ID)}
    )
    raw_db["ad_campaigns"].insert_one(
        {"_id": ObjectId(), **make_campaign(vendor_id=VENDOR_ID)}
    )
    raw_db["ad_campaigns"].insert_one(
        {"_id": ObjectId(), **make_campaign(vendor_id=other_vendor_id)}
    )

    result = await service.list_campaigns(vendor_id=VENDOR_ID)

    assert len(result) == 2
    assert all(c["vendor_id"] == VENDOR_ID for c in result)


@pytest.mark.asyncio
async def test_list_campaigns_filters_by_status(service_and_db):
    """Verify list_campaigns can filter by status."""
    service, db, raw_db = service_and_db

    raw_db["ad_campaigns"].insert_one(
        {"_id": ObjectId(), **make_campaign(vendor_id=VENDOR_ID, status="draft")}
    )
    raw_db["ad_campaigns"].insert_one(
        {
            "_id": ObjectId(),
            **make_campaign(vendor_id=VENDOR_ID, status="pending_review"),
        }
    )
    raw_db["ad_campaigns"].insert_one(
        {"_id": ObjectId(), **make_campaign(vendor_id=VENDOR_ID, status="active")}
    )

    result = await service.list_campaigns(vendor_id=VENDOR_ID, status_filter="active")

    assert len(result) == 1
    assert result[0]["status"] == "active"


@pytest.mark.asyncio
async def test_update_campaign_only_drafts(service_and_db):
    """Verify update_campaign rejects non-draft campaigns."""
    service, db, raw_db = service_and_db

    campaign_oid = ObjectId()
    raw_db["ad_campaigns"].insert_one(
        {"_id": campaign_oid, **make_campaign(vendor_id=VENDOR_ID, status="active")}
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.update_campaign(
            campaign_id=str(campaign_oid),
            vendor_id=VENDOR_ID,
            updates={"campaign_name": "Updated"},
        )

    assert exc_info.value.status_code == 400
    assert "Only draft campaigns" in exc_info.value.detail


@pytest.mark.asyncio
async def test_update_campaign_strips_immutable_fields(service_and_db):
    """Verify update_campaign removes immutable fields."""
    service, db, raw_db = service_and_db

    campaign_oid = ObjectId()
    raw_db["ad_campaigns"].insert_one(
        {"_id": campaign_oid, **make_campaign(vendor_id=VENDOR_ID, status="draft")}
    )

    original_vendor_id = VENDOR_ID
    result = await service.update_campaign(
        campaign_id=str(campaign_oid),
        vendor_id=VENDOR_ID,
        updates={
            "campaign_name": "New Name",
            "vendor_id": "hacker_id",  # Try to change
            "created_at": datetime.now(timezone.utc),  # Try to change
            "status": "active",  # Try to change
        },
    )

    assert result["campaign_name"] == "New Name"
    assert result["vendor_id"] == original_vendor_id
    assert result["status"] == "draft"


@pytest.mark.asyncio
async def test_delete_campaign_only_drafts(service_and_db):
    """Verify delete_campaign rejects non-draft campaigns."""
    service, db, raw_db = service_and_db

    campaign_oid = ObjectId()
    raw_db["ad_campaigns"].insert_one(
        {"_id": campaign_oid, **make_campaign(vendor_id=VENDOR_ID, status="active")}
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.delete_campaign(str(campaign_oid), vendor_id=VENDOR_ID)

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_delete_campaign_removes_from_db(service_and_db):
    """Verify delete_campaign removes the campaign."""
    service, db, raw_db = service_and_db

    campaign_oid = ObjectId()
    raw_db["ad_campaigns"].insert_one(
        {"_id": campaign_oid, **make_campaign(vendor_id=VENDOR_ID, status="draft")}
    )

    result = await service.delete_campaign(str(campaign_oid), vendor_id=VENDOR_ID)

    assert result["deleted"] is True
    assert raw_db["ad_campaigns"].find_one({"_id": campaign_oid}) is None


# =============================================================================
# CAMPAIGN LIFECYCLE TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_submit_for_review_changes_status_to_pending_review(service_and_db):
    """Verify submit_for_review transitions draft to pending_review."""
    service, db, raw_db = service_and_db

    campaign_oid = ObjectId()
    creative_oid = ObjectId()
    raw_db["ad_campaigns"].insert_one(
        {
            "_id": campaign_oid,
            **make_campaign(
                vendor_id=VENDOR_ID,
                status="draft",
                primary_creative_id=str(creative_oid),
                vendor_category="florist",
                target_regions=["Dallas, TX"],
            ),
        }
    )

    result = await service.submit_for_review(str(campaign_oid), VENDOR_ID)

    assert result["status"] == CampaignStatus.PENDING_REVIEW.value
    assert result["submitted_at"] is not None


@pytest.mark.asyncio
async def test_submit_validates_readiness_missing_primary_creative(service_and_db):
    """Verify submit_for_review rejects campaigns missing primary creative."""
    service, db, raw_db = service_and_db

    campaign_oid = ObjectId()
    raw_db["ad_campaigns"].insert_one(
        {
            "_id": campaign_oid,
            **make_campaign(
                vendor_id=VENDOR_ID,
                status="draft",
                primary_creative_id=None,
                vendor_category="florist",
                target_regions=["Dallas, TX"],
            ),
        }
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.submit_for_review(str(campaign_oid), VENDOR_ID)

    assert exc_info.value.status_code == 400
    assert "primary creative" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_submit_validates_vendor_category_required(service_and_db):
    """Verify submit_for_review rejects campaigns without vendor_category."""
    service, db, raw_db = service_and_db

    campaign_oid = ObjectId()
    creative_oid = ObjectId()
    raw_db["ad_campaigns"].insert_one(
        {
            "_id": campaign_oid,
            **make_campaign(
                vendor_id=VENDOR_ID,
                status="draft",
                primary_creative_id=str(creative_oid),
                vendor_category=None,
                target_regions=["Dallas, TX"],
            ),
        }
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.submit_for_review(str(campaign_oid), VENDOR_ID)

    assert exc_info.value.status_code == 400
    assert "vendor category" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_submit_validates_target_regions_required(service_and_db):
    """Verify submit_for_review rejects campaigns without target_regions."""
    service, db, raw_db = service_and_db

    campaign_oid = ObjectId()
    creative_oid = ObjectId()
    raw_db["ad_campaigns"].insert_one(
        {
            "_id": campaign_oid,
            **make_campaign(
                vendor_id=VENDOR_ID,
                status="draft",
                primary_creative_id=str(creative_oid),
                vendor_category="florist",
                target_regions=[],
            ),
        }
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.submit_for_review(str(campaign_oid), VENDOR_ID)

    assert exc_info.value.status_code == 400
    assert "target region" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_submit_rejects_non_draft(service_and_db):
    """Verify submit_for_review rejects non-draft campaigns."""
    service, db, raw_db = service_and_db

    campaign_oid = ObjectId()
    raw_db["ad_campaigns"].insert_one(
        {"_id": campaign_oid, **make_campaign(vendor_id=VENDOR_ID, status="active")}
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.submit_for_review(str(campaign_oid), VENDOR_ID)

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_pause_campaign_changes_active_to_paused(service_and_db):
    """Verify pause_campaign transitions active to paused."""
    service, db, raw_db = service_and_db

    campaign_oid = ObjectId()
    raw_db["ad_campaigns"].insert_one(
        {"_id": campaign_oid, **make_campaign(vendor_id=VENDOR_ID, status="active")}
    )

    result = await service.pause_campaign(str(campaign_oid), VENDOR_ID)

    assert result["status"] == CampaignStatus.PAUSED.value


@pytest.mark.asyncio
async def test_pause_campaign_rejects_non_active(service_and_db):
    """Verify pause_campaign only works on active campaigns."""
    service, db, raw_db = service_and_db

    campaign_oid = ObjectId()
    raw_db["ad_campaigns"].insert_one(
        {"_id": campaign_oid, **make_campaign(vendor_id=VENDOR_ID, status="draft")}
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.pause_campaign(str(campaign_oid), VENDOR_ID)

    assert exc_info.value.status_code == 400


# =============================================================================
# CREATIVE CRUD TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_create_creative_links_to_campaign(service_and_db):
    """Verify create_creative adds creative_id to campaign's creative_ids."""
    service, db, raw_db = service_and_db

    campaign_oid = ObjectId()
    raw_db["ad_campaigns"].insert_one(
        {"_id": campaign_oid, **make_campaign(vendor_id=VENDOR_ID)}
    )

    result = await service.create_creative(
        campaign_id=str(campaign_oid),
        vendor_id=VENDOR_ID,
        data={
            "headline": "Spring Flowers",
            "description": "Beautiful bouquets",
        },
    )

    assert result["campaign_id"] == str(campaign_oid)
    assert result["vendor_id"] == VENDOR_ID

    # Verify campaign was updated
    campaign = raw_db["ad_campaigns"].find_one({"_id": campaign_oid})
    assert result["_id"] in campaign["creative_ids"]


@pytest.mark.asyncio
async def test_create_creative_sets_primary_if_first(service_and_db):
    """Verify first creative becomes primary if none exists."""
    service, db, raw_db = service_and_db

    campaign_oid = ObjectId()
    raw_db["ad_campaigns"].insert_one(
        {
            "_id": campaign_oid,
            **make_campaign(vendor_id=VENDOR_ID, primary_creative_id=None),
        }
    )

    result = await service.create_creative(
        campaign_id=str(campaign_oid),
        vendor_id=VENDOR_ID,
        data={
            "headline": "Spring Flowers",
            "description": "Beautiful bouquets",
        },
    )

    # Verify campaign's primary_creative_id was set
    campaign = raw_db["ad_campaigns"].find_one({"_id": campaign_oid})
    assert campaign["primary_creative_id"] == result["_id"]


@pytest.mark.asyncio
async def test_create_creative_explicit_primary(service_and_db):
    """Verify is_primary=True overrides the default behavior."""
    service, db, raw_db = service_and_db

    campaign_oid = ObjectId()
    existing_creative_oid = ObjectId()
    raw_db["ad_campaigns"].insert_one(
        {
            "_id": campaign_oid,
            **make_campaign(
                vendor_id=VENDOR_ID,
                primary_creative_id=str(existing_creative_oid),
            ),
        }
    )

    result = await service.create_creative(
        campaign_id=str(campaign_oid),
        vendor_id=VENDOR_ID,
        data={
            "headline": "New Primary",
            "description": "This becomes primary",
            "is_primary": True,
        },
    )

    campaign = raw_db["ad_campaigns"].find_one({"_id": campaign_oid})
    assert campaign["primary_creative_id"] == result["_id"]


@pytest.mark.asyncio
async def test_list_creatives_by_campaign(service_and_db):
    """Verify list_creatives returns creatives for a campaign."""
    service, db, raw_db = service_and_db

    campaign_oid = ObjectId()
    other_campaign_oid = ObjectId()

    raw_db["ad_creatives"].insert_one(
        {"_id": ObjectId(), **make_creative(str(campaign_oid), vendor_id=VENDOR_ID)}
    )
    raw_db["ad_creatives"].insert_one(
        {"_id": ObjectId(), **make_creative(str(campaign_oid), vendor_id=VENDOR_ID)}
    )
    raw_db["ad_creatives"].insert_one(
        {
            "_id": ObjectId(),
            **make_creative(str(other_campaign_oid), vendor_id=VENDOR_ID),
        }
    )

    result = await service.list_creatives(str(campaign_oid), vendor_id=VENDOR_ID)

    assert len(result) == 2
    assert all(c["campaign_id"] == str(campaign_oid) for c in result)


@pytest.mark.asyncio
async def test_update_creative_resets_review_on_content_change(service_and_db):
    """Verify updating content on approved creative resets it to pending."""
    service, db, raw_db = service_and_db

    creative_oid = ObjectId()
    raw_db["ad_creatives"].insert_one(
        {
            "_id": creative_oid,
            **make_creative(
                str(ObjectId()),
                vendor_id=VENDOR_ID,
                review_status=CreativeReviewStatus.APPROVED.value,
            ),
        }
    )

    result = await service.update_creative(
        creative_id=str(creative_oid),
        vendor_id=VENDOR_ID,
        updates={"headline": "New Headline"},
    )

    assert result["review_status"] == CreativeReviewStatus.PENDING.value
    assert result["submitted_at"] is not None


@pytest.mark.asyncio
async def test_set_primary_creative_updates_campaign(service_and_db):
    """Verify set_primary_creative updates the campaign."""
    service, db, raw_db = service_and_db

    campaign_oid = ObjectId()
    creative1_oid = ObjectId()
    creative2_oid = ObjectId()

    raw_db["ad_campaigns"].insert_one(
        {
            "_id": campaign_oid,
            **make_campaign(
                vendor_id=VENDOR_ID,
                primary_creative_id=str(creative1_oid),
            ),
        }
    )
    raw_db["ad_creatives"].insert_one(
        {
            "_id": creative1_oid,
            **make_creative(str(campaign_oid), vendor_id=VENDOR_ID, is_primary=True),
        }
    )
    raw_db["ad_creatives"].insert_one(
        {
            "_id": creative2_oid,
            **make_creative(str(campaign_oid), vendor_id=VENDOR_ID, is_primary=False),
        }
    )

    result = await service.set_primary_creative(
        campaign_id=str(campaign_oid),
        creative_id=str(creative2_oid),
        vendor_id=VENDOR_ID,
    )

    assert result["primary_creative_id"] == str(creative2_oid)


# =============================================================================
# LEADS TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_get_vendor_leads_returns_leads_across_campaigns(service_and_db):
    """Verify get_vendor_leads returns leads for all vendor campaigns."""
    service, db, raw_db = service_and_db

    campaign1_oid = ObjectId()
    campaign2_oid = ObjectId()

    # Insert campaigns
    raw_db["ad_campaigns"].insert_one(
        {"_id": campaign1_oid, **make_campaign(vendor_id=VENDOR_ID)}
    )
    raw_db["ad_campaigns"].insert_one(
        {"_id": campaign2_oid, **make_campaign(vendor_id=VENDOR_ID)}
    )

    # Insert leads for both campaigns
    raw_db["ad_leads"].insert_one(
        {"_id": ObjectId(), **make_ad_lead(str(campaign1_oid))}
    )
    raw_db["ad_leads"].insert_one(
        {"_id": ObjectId(), **make_ad_lead(str(campaign2_oid))}
    )

    result = await service.get_vendor_leads(vendor_id=VENDOR_ID)

    assert len(result) == 2


@pytest.mark.asyncio
async def test_get_vendor_leads_empty_when_no_campaigns(service_and_db):
    """Verify get_vendor_leads returns empty list when vendor has no campaigns."""
    service, db, raw_db = service_and_db

    result = await service.get_vendor_leads(vendor_id=VENDOR_ID)

    assert result == []


# =============================================================================
# CAMPAIGN STATS TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_get_campaign_stats_returns_totals_and_series(service_and_db):
    """Verify get_campaign_stats returns totals and daily series."""
    service, db, raw_db = service_and_db

    campaign_oid = ObjectId()
    raw_db["ad_campaigns"].insert_one(
        {
            "_id": campaign_oid,
            **make_campaign(
                vendor_id=VENDOR_ID,
                impression_count=1000,
                click_count=50,
                lead_count=5,
                conversion_count=2,
            ),
        }
    )

    result = await service.get_campaign_stats(str(campaign_oid), VENDOR_ID)

    assert result["campaign_id"] == str(campaign_oid)
    assert result["totals"]["impressions"] == 1000
    assert result["totals"]["clicks"] == 50
    assert result["totals"]["leads"] == 5
    assert result["totals"]["conversions"] == 2
    assert result["totals"]["ctr"] == 5.0  # 50 / 1000 * 100


# =============================================================================
# AD SERVING TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_get_servable_campaigns_only_active(service_and_db):
    """Verify get_servable_campaigns only returns active campaigns."""
    service, db, raw_db = service_and_db

    raw_db["ad_campaigns"].insert_one(
        {
            "_id": ObjectId(),
            **make_campaign(
                vendor_id=VENDOR_ID,
                status="active",
                primary_creative_id=str(ObjectId()),
            ),
        }
    )
    raw_db["ad_campaigns"].insert_one(
        {
            "_id": ObjectId(),
            **make_campaign(
                vendor_id=VENDOR_ID, status="draft", primary_creative_id=str(ObjectId())
            ),
        }
    )
    raw_db["ad_campaigns"].insert_one(
        {
            "_id": ObjectId(),
            **make_campaign(
                vendor_id=VENDOR_ID,
                status="paused",
                primary_creative_id=str(ObjectId()),
            ),
        }
    )

    result = await service.get_servable_campaigns()

    assert len(result) == 1
    assert result[0]["status"] == "active"


@pytest.mark.asyncio
async def test_get_servable_campaigns_checks_date_range(service_and_db):
    """Verify get_servable_campaigns checks start_date and end_date."""
    service, db, raw_db = service_and_db

    now = datetime.now(timezone.utc)
    past = now - timedelta(days=10)
    future = now + timedelta(days=10)

    # Active, within range
    raw_db["ad_campaigns"].insert_one(
        {
            "_id": ObjectId(),
            **make_campaign(
                vendor_id=VENDOR_ID,
                status="active",
                start_date=past,
                end_date=future,
                primary_creative_id=str(ObjectId()),
            ),
        }
    )

    # Active, but ended
    raw_db["ad_campaigns"].insert_one(
        {
            "_id": ObjectId(),
            **make_campaign(
                vendor_id=VENDOR_ID,
                status="active",
                start_date=past,
                end_date=past,  # Already ended
                primary_creative_id=str(ObjectId()),
            ),
        }
    )

    result = await service.get_servable_campaigns()

    assert len(result) == 1


@pytest.mark.asyncio
async def test_get_servable_campaigns_deduplicates_by_vendor(service_and_db):
    """Verify get_servable_campaigns returns only one campaign per vendor."""
    service, db, raw_db = service_and_db

    vendor1 = VENDOR_ID
    vendor2 = str(ObjectId())

    # Two campaigns from vendor1, one from vendor2
    raw_db["ad_campaigns"].insert_one(
        {
            "_id": ObjectId(),
            **make_campaign(
                vendor_id=vendor1,
                status="active",
                primary_creative_id=str(ObjectId()),
                quality_score=100,
            ),
        }
    )
    raw_db["ad_campaigns"].insert_one(
        {
            "_id": ObjectId(),
            **make_campaign(
                vendor_id=vendor1,
                status="active",
                primary_creative_id=str(ObjectId()),
                quality_score=50,  # Lower score
            ),
        }
    )
    raw_db["ad_campaigns"].insert_one(
        {
            "_id": ObjectId(),
            **make_campaign(
                vendor_id=vendor2,
                status="active",
                primary_creative_id=str(ObjectId()),
                quality_score=80,
            ),
        }
    )

    result = await service.get_servable_campaigns(limit=3)

    # Should get 2 campaigns (one per vendor)
    assert len(result) <= 2
    vendor_ids = [c["vendor_id"] for c in result]
    assert len(vendor_ids) == len(set(vendor_ids))  # All unique


# =============================================================================
# EXPIRATION TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_complete_expired_campaigns_marks_past_end_date(service_and_db):
    """Verify complete_expired_campaigns marks campaigns past end_date as completed."""
    service, db, raw_db = service_and_db

    now = datetime.now(timezone.utc)
    past_end = now - timedelta(days=1)

    campaign_oid = ObjectId()
    raw_db["ad_campaigns"].insert_one(
        {
            "_id": campaign_oid,
            **make_campaign(
                vendor_id=VENDOR_ID,
                status="active",
                end_date=past_end,
            ),
        }
    )

    count = await service.complete_expired_campaigns()

    assert count == 1
    updated = raw_db["ad_campaigns"].find_one({"_id": campaign_oid})
    assert updated["status"] == CampaignStatus.COMPLETED.value


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_create_campaign_accepts_all_data_fields(service_and_db):
    """Verify create_campaign accepts and stores all provided data fields."""
    service, db, raw_db = service_and_db

    result = await service.create_campaign(
        vendor_id=VENDOR_ID,
        vendor_email=VENDOR_EMAIL,
        vendor_name=VENDOR_NAME,
        data={
            "campaign_name": "Full Campaign",
            "campaign_description": "A complete campaign",
            "goal": "lead_generation",
            "target_categories": ["florist", "photographer"],
            "target_wedding_stages": ["planning"],
            "target_placements": ["vendor_rail"],
            "target_regions": ["Dallas, TX", "Houston, TX"],
            "daily_budget": 10.0,
            "total_budget": 300.0,
            "pacing_strategy": "accelerated",
            "vendor_category": "florist",
            "vendor_service_area": "Dallas",
            "metadata": {"key": "value"},
        },
    )

    assert result["campaign_description"] == "A complete campaign"
    assert result["goal"] == "lead_generation"
    assert result["target_categories"] == ["florist", "photographer"]
    assert result["daily_budget"] == 10.0


@pytest.mark.asyncio
async def test_get_campaign_without_vendor_check(service_and_db):
    """Verify get_campaign can be called without vendor_id for internal use."""
    service, db, raw_db = service_and_db

    campaign_oid = ObjectId()
    raw_db["ad_campaigns"].insert_one(
        {"_id": campaign_oid, **make_campaign(vendor_id=VENDOR_ID)}
    )

    result = await service.get_campaign(str(campaign_oid))

    assert result["_id"] == str(campaign_oid)


@pytest.mark.asyncio
async def test_list_creatives_without_vendor_check(service_and_db):
    """Verify list_creatives can be called without vendor_id."""
    service, db, raw_db = service_and_db

    campaign_oid = ObjectId()
    raw_db["ad_creatives"].insert_one(
        {"_id": ObjectId(), **make_creative(str(campaign_oid), vendor_id=VENDOR_ID)}
    )

    result = await service.list_creatives(str(campaign_oid))

    assert len(result) == 1


@pytest.mark.asyncio
async def test_update_campaign_updates_timestamp(service_and_db):
    """Verify update_campaign updates the updated_at timestamp."""
    service, db, raw_db = service_and_db

    campaign_oid = ObjectId()
    old_time = datetime.now(timezone.utc) - timedelta(hours=1)
    raw_db["ad_campaigns"].insert_one(
        {
            "_id": campaign_oid,
            **make_campaign(
                vendor_id=VENDOR_ID, status="draft", **{"updated_at": old_time}
            ),
        }
    )

    result = await service.update_campaign(
        campaign_id=str(campaign_oid),
        vendor_id=VENDOR_ID,
        updates={"campaign_name": "Updated"},
    )

    # mongomock may strip timezone info, so compare naive-to-naive
    updated = result["updated_at"].replace(tzinfo=None)
    old_naive = old_time.replace(tzinfo=None)
    assert updated > old_naive


@pytest.mark.asyncio
async def test_create_creative_sets_review_status_pending(service_and_db):
    """Verify newly created creatives have pending review status."""
    service, db, raw_db = service_and_db

    campaign_oid = ObjectId()
    raw_db["ad_campaigns"].insert_one(
        {"_id": campaign_oid, **make_campaign(vendor_id=VENDOR_ID)}
    )

    result = await service.create_creative(
        campaign_id=str(campaign_oid),
        vendor_id=VENDOR_ID,
        data={
            "headline": "Test",
            "description": "Test creative",
        },
    )

    assert result["review_status"] == CreativeReviewStatus.PENDING.value


@pytest.mark.asyncio
async def test_get_campaign_stats_handles_zero_impressions(service_and_db):
    """Verify CTR calculation handles zero impressions."""
    service, db, raw_db = service_and_db

    campaign_oid = ObjectId()
    raw_db["ad_campaigns"].insert_one(
        {
            "_id": campaign_oid,
            **make_campaign(
                vendor_id=VENDOR_ID,
                impression_count=0,
                click_count=0,
            ),
        }
    )

    result = await service.get_campaign_stats(str(campaign_oid), VENDOR_ID)

    assert result["totals"]["ctr"] == 0.0
