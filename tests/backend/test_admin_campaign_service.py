"""
Tests for AdminCampaignService

Phase 2: Admin moderation console for campaign and creative review.
Tests cover review workflows, campaign monitoring, revenue tracking, and platform config.

All tests are async (@pytest.mark.asyncio).
"""

import mongomock
import pytest
from datetime import datetime, timezone
from bson import ObjectId

from app.services.admin_campaign_service import AdminCampaignService
from app.models.advertising_campaign import CampaignStatus, CreativeReviewStatus
from tests.backend.conftest_advertising import (
    AsyncMockDatabase,
    make_campaign,
    make_creative,
    make_ad_event,
    make_ad_lead,
    VENDOR_ID,
    VENDOR_EMAIL,
    VENDOR_NAME,
    ADMIN_EMAIL,
)


@pytest.fixture
def service_and_db():
    """Create a fresh AdminCampaignService with mongomock database."""
    client = mongomock.MongoClient()
    raw_db = client["test_db"]
    db = AsyncMockDatabase(raw_db)
    service = AdminCampaignService(db)
    return service, db, raw_db


# ═════════════════════════════════════════════════════════════════════════════
# REVIEW QUEUE TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_review_queue_returns_pending_campaigns_fifo(service_and_db):
    """Test that review queue returns pending campaigns in FIFO order (oldest first)."""
    service, _, raw_db = service_and_db

    now = datetime.now(timezone.utc)
    campaign_old = make_campaign(
        status=CampaignStatus.PENDING_REVIEW.value,
        submitted_at=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
    )
    campaign_new = make_campaign(
        status=CampaignStatus.PENDING_REVIEW.value,
        submitted_at=datetime(2025, 1, 2, 10, 0, tzinfo=timezone.utc),
    )

    raw_db["ad_campaigns"].insert_many([campaign_old, campaign_new])

    queue = await service.get_review_queue()

    assert len(queue) == 2
    # Oldest first (FIFO)
    assert queue[0]["campaign_name"] == campaign_old["campaign_name"]
    assert queue[1]["campaign_name"] == campaign_new["campaign_name"]


@pytest.mark.asyncio
async def test_get_review_queue_inlines_primary_creative(service_and_db):
    """Test that review queue inlines the primary creative."""
    service, _, raw_db = service_and_db

    campaign_doc = make_campaign(status=CampaignStatus.PENDING_REVIEW.value)
    campaign_id = str(ObjectId())
    campaign_doc["_id"] = ObjectId(campaign_id)
    campaign_doc["primary_creative_id"] = campaign_id

    creative_doc = make_creative(
        campaign_id=campaign_id,
        review_status=CreativeReviewStatus.PENDING.value,
    )
    creative_doc["_id"] = ObjectId(campaign_id)

    raw_db["ad_campaigns"].insert_one(campaign_doc)
    raw_db["ad_creatives"].insert_one(creative_doc)

    queue = await service.get_review_queue()

    assert len(queue) == 1
    assert "primary_creative" in queue[0]
    assert queue[0]["primary_creative"]["headline"] == creative_doc["headline"]


@pytest.mark.asyncio
async def test_get_review_counts_returns_all_statuses(service_and_db):
    """Test that review counts include all campaign statuses."""
    service, _, raw_db = service_and_db

    raw_db["ad_campaigns"].insert_many([
        make_campaign(status=CampaignStatus.PENDING_REVIEW.value),
        make_campaign(status=CampaignStatus.PENDING_REVIEW.value),
        make_campaign(status=CampaignStatus.ACTIVE.value),
        make_campaign(status=CampaignStatus.PAUSED.value),
        make_campaign(status=CampaignStatus.REJECTED.value),
        make_campaign(status=CampaignStatus.DRAFT.value),
    ])

    counts = await service.get_review_counts()

    assert counts["pending_review"] == 2
    assert counts["active"] == 1
    assert counts["paused"] == 1
    assert counts["rejected"] == 1
    assert counts["draft"] == 1
    assert counts["completed"] == 0
    assert counts["total"] == 6


# ═════════════════════════════════════════════════════════════════════════════
# CAMPAIGN REVIEW ACTIONS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_approve_campaign_sets_active_and_auto_approves_creatives(service_and_db):
    """Test that approving a campaign sets status to active and auto-approves pending creatives."""
    service, _, raw_db = service_and_db

    campaign_doc = make_campaign(status=CampaignStatus.PENDING_REVIEW.value)
    campaign_id = str(ObjectId())
    campaign_doc["_id"] = ObjectId(campaign_id)

    raw_db["ad_campaigns"].insert_one(campaign_doc)

    # Add pending creatives
    raw_db["ad_creatives"].insert_many([
        make_creative(
            campaign_id=campaign_id,
            review_status=CreativeReviewStatus.PENDING.value,
        ),
        make_creative(
            campaign_id=campaign_id,
            review_status=CreativeReviewStatus.PENDING.value,
        ),
    ])

    result = await service.approve_campaign(campaign_id, ADMIN_EMAIL, "Looks good!")

    assert result["status"] == CampaignStatus.ACTIVE.value
    assert result["reviewed_by"] == ADMIN_EMAIL
    assert result["review_notes"] == "Looks good!"

    # Check creatives are auto-approved
    creatives = list(raw_db["ad_creatives"].find({"campaign_id": campaign_id}))
    assert all(c["review_status"] == CreativeReviewStatus.APPROVED.value for c in creatives)


@pytest.mark.asyncio
async def test_approve_campaign_rejects_non_pending(service_and_db):
    """Test that approve_campaign rejects campaigns not in pending_review status."""
    service, _, raw_db = service_and_db

    campaign_doc = make_campaign(status=CampaignStatus.ACTIVE.value)
    campaign_id = str(ObjectId())
    campaign_doc["_id"] = ObjectId(campaign_id)
    raw_db["ad_campaigns"].insert_one(campaign_doc)

    with pytest.raises(Exception) as exc_info:
        await service.approve_campaign(campaign_id, ADMIN_EMAIL)

    assert "not in pending_review status" in str(exc_info.value) or "not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_reject_campaign_sets_rejected(service_and_db):
    """Test that reject_campaign sets status to rejected."""
    service, _, raw_db = service_and_db

    campaign_doc = make_campaign(status=CampaignStatus.PENDING_REVIEW.value)
    campaign_id = str(ObjectId())
    campaign_doc["_id"] = ObjectId(campaign_id)
    raw_db["ad_campaigns"].insert_one(campaign_doc)

    result = await service.reject_campaign(campaign_id, ADMIN_EMAIL, "Violates policy")

    assert result["status"] == CampaignStatus.REJECTED.value
    assert result["reviewed_by"] == ADMIN_EMAIL
    assert result["review_notes"] == "Violates policy"


@pytest.mark.asyncio
async def test_request_changes_returns_to_draft_with_notes(service_and_db):
    """Test that request_changes moves campaign back to draft and saves notes."""
    service, _, raw_db = service_and_db

    campaign_doc = make_campaign(status=CampaignStatus.PENDING_REVIEW.value)
    campaign_id = str(ObjectId())
    campaign_doc["_id"] = ObjectId(campaign_id)
    raw_db["ad_campaigns"].insert_one(campaign_doc)

    result = await service.request_changes(
        campaign_id,
        ADMIN_EMAIL,
        "Please update the headline to be more descriptive"
    )

    assert result["status"] == CampaignStatus.DRAFT.value
    assert result["reviewed_by"] == ADMIN_EMAIL
    assert "Please update the headline" in result["review_notes"]


@pytest.mark.asyncio
async def test_request_changes_requires_notes(service_and_db):
    """Test that request_changes requires non-empty review notes."""
    service, _, raw_db = service_and_db

    campaign_doc = make_campaign(status=CampaignStatus.PENDING_REVIEW.value)
    campaign_id = str(ObjectId())
    campaign_doc["_id"] = ObjectId(campaign_id)
    raw_db["ad_campaigns"].insert_one(campaign_doc)

    with pytest.raises(Exception) as exc_info:
        await service.request_changes(campaign_id, ADMIN_EMAIL, "")

    assert "required" in str(exc_info.value).lower()


# ═════════════════════════════════════════════════════════════════════════════
# CREATIVE REVIEW
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_creative_review_queue_returns_pending_only(service_and_db):
    """Test that creative review queue returns only pending creatives."""
    service, _, raw_db = service_and_db

    campaign_id = str(ObjectId())
    raw_db["ad_creatives"].insert_many([
        make_creative(
            campaign_id=campaign_id,
            review_status=CreativeReviewStatus.PENDING.value,
        ),
        make_creative(
            campaign_id=campaign_id,
            review_status=CreativeReviewStatus.PENDING.value,
        ),
        make_creative(
            campaign_id=campaign_id,
            review_status=CreativeReviewStatus.APPROVED.value,
        ),
    ])

    queue = await service.get_creative_review_queue()

    assert len(queue) == 2
    assert all(c["review_status"] == CreativeReviewStatus.PENDING.value for c in queue)


@pytest.mark.asyncio
async def test_approve_creative_sets_approved(service_and_db):
    """Test that approve_creative sets review_status to approved."""
    service, _, raw_db = service_and_db

    creative_doc = make_creative(
        campaign_id=str(ObjectId()),
        review_status=CreativeReviewStatus.PENDING.value,
    )
    creative_id = str(ObjectId())
    creative_doc["_id"] = ObjectId(creative_id)
    raw_db["ad_creatives"].insert_one(creative_doc)

    result = await service.approve_creative(creative_id, ADMIN_EMAIL, "Good quality")

    assert result["review_status"] == CreativeReviewStatus.APPROVED.value
    assert result["reviewed_by"] == ADMIN_EMAIL
    assert result["review_notes"] == "Good quality"


@pytest.mark.asyncio
async def test_reject_creative_sets_rejected(service_and_db):
    """Test that reject_creative sets review_status to rejected."""
    service, _, raw_db = service_and_db

    creative_doc = make_creative(
        campaign_id=str(ObjectId()),
        review_status=CreativeReviewStatus.PENDING.value,
    )
    creative_id = str(ObjectId())
    creative_doc["_id"] = ObjectId(creative_id)
    raw_db["ad_creatives"].insert_one(creative_doc)

    result = await service.reject_creative(creative_id, ADMIN_EMAIL, "Image is blurry")

    assert result["review_status"] == CreativeReviewStatus.REJECTED.value
    assert result["reviewed_by"] == ADMIN_EMAIL
    assert result["review_notes"] == "Image is blurry"


# ═════════════════════════════════════════════════════════════════════════════
# CAMPAIGN MONITORING
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_list_all_campaigns_no_filter(service_and_db):
    """Test that list_all_campaigns returns all campaigns when no filter is applied."""
    service, _, raw_db = service_and_db

    raw_db["ad_campaigns"].insert_many([
        make_campaign(status=CampaignStatus.ACTIVE.value),
        make_campaign(status=CampaignStatus.DRAFT.value),
        make_campaign(status=CampaignStatus.PAUSED.value),
    ])

    campaigns = await service.list_all_campaigns()

    assert len(campaigns) == 3


@pytest.mark.asyncio
async def test_list_all_campaigns_filter_by_status(service_and_db):
    """Test that list_all_campaigns filters by status."""
    service, _, raw_db = service_and_db

    raw_db["ad_campaigns"].insert_many([
        make_campaign(status=CampaignStatus.ACTIVE.value),
        make_campaign(status=CampaignStatus.ACTIVE.value),
        make_campaign(status=CampaignStatus.DRAFT.value),
    ])

    campaigns = await service.list_all_campaigns(status_filter=CampaignStatus.ACTIVE.value)

    assert len(campaigns) == 2
    assert all(c["status"] == CampaignStatus.ACTIVE.value for c in campaigns)


@pytest.mark.asyncio
async def test_admin_pause_active_campaign(service_and_db):
    """Test that admin_pause_campaign pauses an active campaign."""
    service, _, raw_db = service_and_db

    campaign_doc = make_campaign(status=CampaignStatus.ACTIVE.value)
    campaign_id = str(ObjectId())
    campaign_doc["_id"] = ObjectId(campaign_id)
    raw_db["ad_campaigns"].insert_one(campaign_doc)

    result = await service.admin_pause_campaign(
        campaign_id,
        ADMIN_EMAIL,
        "Manual pause for testing"
    )

    assert result["status"] == CampaignStatus.PAUSED.value
    assert "[Admin pause by" in result["review_notes"]


@pytest.mark.asyncio
async def test_admin_pause_non_active_fails(service_and_db):
    """Test that admin_pause_campaign fails when campaign is not active."""
    service, _, raw_db = service_and_db

    campaign_doc = make_campaign(status=CampaignStatus.DRAFT.value)
    campaign_id = str(ObjectId())
    campaign_doc["_id"] = ObjectId(campaign_id)
    raw_db["ad_campaigns"].insert_one(campaign_doc)

    with pytest.raises(Exception) as exc_info:
        await service.admin_pause_campaign(campaign_id, ADMIN_EMAIL)

    assert "not currently active" in str(exc_info.value) or "not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_admin_deactivate_from_any_non_terminal(service_and_db):
    """Test that admin_deactivate_campaign works from any non-terminal status."""
    service, _, raw_db = service_and_db

    for status in [CampaignStatus.DRAFT.value, CampaignStatus.PENDING_REVIEW.value,
                   CampaignStatus.ACTIVE.value, CampaignStatus.PAUSED.value]:
        campaign_doc = make_campaign(status=status)
        campaign_id = str(ObjectId())
        campaign_doc["_id"] = ObjectId(campaign_id)
        raw_db["ad_campaigns"].delete_many({})
        raw_db["ad_campaigns"].insert_one(campaign_doc)

        result = await service.admin_deactivate_campaign(campaign_id, ADMIN_EMAIL, "Policy violation")

        assert result["status"] == CampaignStatus.REJECTED.value


@pytest.mark.asyncio
async def test_admin_deactivate_terminal_fails(service_and_db):
    """Test that admin_deactivate_campaign fails from terminal statuses."""
    service, _, raw_db = service_and_db

    for terminal_status in [CampaignStatus.COMPLETED.value, CampaignStatus.REJECTED.value]:
        campaign_doc = make_campaign(status=terminal_status)
        campaign_id = str(ObjectId())
        campaign_doc["_id"] = ObjectId(campaign_id)
        raw_db["ad_campaigns"].delete_many({})
        raw_db["ad_campaigns"].insert_one(campaign_doc)

        with pytest.raises(Exception) as exc_info:
            await service.admin_deactivate_campaign(campaign_id, ADMIN_EMAIL)

        assert "terminal status" in str(exc_info.value).lower()


# ═════════════════════════════════════════════════════════════════════════════
# REVENUE
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_revenue_summary_returns_structure(service_and_db):
    """Test that get_revenue_summary returns the expected structure."""
    service, _, raw_db = service_and_db

    # Seed some campaigns and events
    raw_db["ad_campaigns"].insert_many([
        make_campaign(status=CampaignStatus.ACTIVE.value, vendor_id=VENDOR_ID),
        make_campaign(status=CampaignStatus.DRAFT.value),
    ])

    campaign_id = str(ObjectId())
    raw_db["ad_events"].insert_many([
        make_ad_event(campaign_id, event_type="impression_served"),
        make_ad_event(campaign_id, event_type="click"),
    ])

    result = await service.get_revenue_summary(days=30)

    # Validate structure (mongomock aggregation is limited, so just check shape)
    assert "period_days" in result
    assert "period_start" in result
    assert "campaign_counts" in result
    assert "engagement" in result
    assert "active_vendors" in result
    assert "total_revenue" in result
    assert "currency" in result

    # Free tier: total_revenue is always $0
    assert result["total_revenue"] == 0.0


# ═════════════════════════════════════════════════════════════════════════════
# PLANNER FEEDBACK
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_planner_feedback_returns_hidden_vendors(service_and_db):
    """Test that get_planner_feedback returns planners with hidden vendors."""
    service, _, raw_db = service_and_db

    raw_db["planner_ad_preferences"].insert_many([
        {
            "planner_id": "planner1@example.com",
            "hidden_vendor_ids": [VENDOR_ID],
            "hidden_categories": [],
            "reduced_frequency": False,
            "updated_at": datetime.now(timezone.utc),
        },
        {
            "planner_id": "planner2@example.com",
            "hidden_vendor_ids": [],
            "hidden_categories": ["florist"],
            "reduced_frequency": False,
            "updated_at": datetime.now(timezone.utc),
        },
    ])

    result = await service.get_planner_feedback()

    assert "feedback" in result
    assert "summary" in result
    assert result["summary"]["planners_with_feedback"] == 2
    assert result["summary"]["planners_hiding_vendors"] == 1


# ═════════════════════════════════════════════════════════════════════════════
# FRAUD SIGNALS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_fraud_signals_returns_list(service_and_db):
    """Test that get_fraud_signals returns a list of fraud signals."""
    service, _, raw_db = service_and_db

    raw_db["ad_fraud_signals"].insert_many([
        {
            "campaign_id": str(ObjectId()),
            "signal_type": "suspicious_clicks",
            "status": "new",
            "flagged_at": datetime.now(timezone.utc),
        },
        {
            "campaign_id": str(ObjectId()),
            "signal_type": "unusual_conversion_rate",
            "status": "investigating",
            "flagged_at": datetime.now(timezone.utc),
        },
    ])

    signals = await service.get_fraud_signals()

    assert len(signals) == 2
    assert signals[0]["status"] in ["new", "investigating"]


@pytest.mark.asyncio
async def test_update_fraud_signal_changes_status(service_and_db):
    """Test that update_fraud_signal changes the signal status."""
    service, _, raw_db = service_and_db

    signal_doc = {
        "_id": ObjectId(),
        "campaign_id": str(ObjectId()),
        "signal_type": "suspicious_clicks",
        "status": "new",
        "flagged_at": datetime.now(timezone.utc),
    }
    raw_db["ad_fraud_signals"].insert_one(signal_doc)
    signal_id = str(signal_doc["_id"])

    result = await service.update_fraud_signal(
        signal_id,
        ADMIN_EMAIL,
        "resolved",
        "False positive - normal traffic spike"
    )

    assert result["status"] == "resolved"
    assert result["notes"] == "False positive - normal traffic spike"


# ═════════════════════════════════════════════════════════════════════════════
# PLATFORM CONFIG
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_platform_config_returns_defaults_when_empty(service_and_db):
    """Test that get_platform_config returns defaults when no config exists."""
    service, _, raw_db = service_and_db

    result = await service.get_platform_config()

    assert result["feature_key"] == "sponsored_vendors"
    assert result["is_enabled"] is False
    assert "config" in result
    assert result["config"]["max_sponsored_per_page"] == 3
    assert result["config"]["show_sponsored_badge"] is True


@pytest.mark.asyncio
async def test_update_platform_config_upserts(service_and_db):
    """Test that update_platform_config upserts the config."""
    service, _, raw_db = service_and_db

    updates = {
        "is_enabled": True,
        "config": {
            "max_sponsored_per_page": 5,
            "show_sponsored_badge": False,
        },
    }

    result = await service.update_platform_config(ADMIN_EMAIL, updates)

    assert result["is_enabled"] is True
    assert result["enabled_by"] == ADMIN_EMAIL
    assert result["config"]["max_sponsored_per_page"] == 5

    # Verify upsert by checking it exists in DB
    config = raw_db["ad_feature_flags"].find_one({"feature_key": "sponsored_vendors"})
    assert config is not None
    assert config["is_enabled"] is True
