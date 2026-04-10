"""
Comprehensive tests for Phase 1 advertising campaign models.

Tests all enums, Pydantic models, and model properties:
- 9 enums with correct values and serialization
- AdCampaign model: construction, defaults, properties (ctr, is_servable)
- AdCreative model: construction, defaults
- Request models: validation, partial updates
- Stats models: defaults (hourly arrays, counters)

Pure Pydantic model tests — no database or mongomock needed.
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("ROOT_ADMIN_EMAIL", "thedeveloper@thespecialwedding.io")

from app.models.advertising_campaign import (
    # Enums
    CampaignGoal,
    CampaignStatus,
    CreativeReviewStatus,
    CreativeType,
    PacingStrategy,
    BidStrategy,
    FraudSignalType,
    FraudSignalStatus,
    VendorAccountStatus,
    # Models
    AdCampaign,
    AdCreative,
    CampaignDayStats,
    PlacementDayStats,
    AdFraudSignal,
    VendorAdBilling,
    # Request models
    CreateCampaignRequest,
    UpdateCampaignRequest,
    CreateCreativeRequest,
    ReviewCampaignDecisionRequest,
    ReviewCreativeDecisionRequest,
)


# =============================================================================
# ENUM TESTS
# =============================================================================


class TestCampaignGoalEnum:
    """Test CampaignGoal enum values and serialization."""

    def test_campaign_goal_has_all_values(self):
        """All expected campaign goals exist."""
        assert CampaignGoal.PROFILE_VISITS.value == "profile_visits"
        assert CampaignGoal.QUOTE_REQUESTS.value == "quote_requests"
        assert CampaignGoal.BOOKINGS.value == "bookings"

    def test_campaign_goal_is_string_enum(self):
        """CampaignGoal serializes as string."""
        goal = CampaignGoal.PROFILE_VISITS
        assert isinstance(goal.value, str)
        assert str(goal.value) == "profile_visits"

    def test_campaign_goal_serialization(self):
        """CampaignGoal can be serialized to JSON."""
        goal = CampaignGoal.QUOTE_REQUESTS
        assert goal.value == "quote_requests"


class TestCampaignStatusEnum:
    """Test CampaignStatus enum values and serialization."""

    def test_campaign_status_has_all_values(self):
        """All expected campaign statuses exist."""
        assert CampaignStatus.DRAFT.value == "draft"
        assert CampaignStatus.PENDING_REVIEW.value == "pending_review"
        assert CampaignStatus.ACTIVE.value == "active"
        assert CampaignStatus.PAUSED.value == "paused"
        assert CampaignStatus.COMPLETED.value == "completed"
        assert CampaignStatus.REJECTED.value == "rejected"

    def test_campaign_status_is_string_enum(self):
        """CampaignStatus serializes as string."""
        status = CampaignStatus.ACTIVE
        assert isinstance(status.value, str)
        assert str(status.value) == "active"


class TestCreativeReviewStatusEnum:
    """Test CreativeReviewStatus enum values and serialization."""

    def test_creative_review_status_has_all_values(self):
        """All expected review statuses exist."""
        assert CreativeReviewStatus.PENDING.value == "pending"
        assert CreativeReviewStatus.APPROVED.value == "approved"
        assert CreativeReviewStatus.REJECTED.value == "rejected"
        assert CreativeReviewStatus.CHANGES_REQUESTED.value == "changes_requested"

    def test_creative_review_status_is_string_enum(self):
        """CreativeReviewStatus serializes as string."""
        status = CreativeReviewStatus.APPROVED
        assert isinstance(status.value, str)


class TestCreativeTypeEnum:
    """Test CreativeType enum values and serialization."""

    def test_creative_type_has_all_values(self):
        """All expected creative types exist."""
        assert CreativeType.IMAGE.value == "image"
        assert CreativeType.TEXT.value == "text"

    def test_creative_type_is_string_enum(self):
        """CreativeType serializes as string."""
        ctype = CreativeType.IMAGE
        assert isinstance(ctype.value, str)


class TestPacingStrategyEnum:
    """Test PacingStrategy enum values and serialization."""

    def test_pacing_strategy_has_all_values(self):
        """All expected pacing strategies exist."""
        assert PacingStrategy.EVEN.value == "even"
        assert PacingStrategy.ACCELERATED.value == "accelerated"

    def test_pacing_strategy_is_string_enum(self):
        """PacingStrategy serializes as string."""
        strategy = PacingStrategy.EVEN
        assert isinstance(strategy.value, str)


class TestBidStrategyEnum:
    """Test BidStrategy enum values and serialization."""

    def test_bid_strategy_has_all_values(self):
        """All expected bid strategies exist."""
        assert BidStrategy.FIXED.value == "fixed"
        assert BidStrategy.AUTO.value == "auto"

    def test_bid_strategy_is_string_enum(self):
        """BidStrategy serializes as string."""
        strategy = BidStrategy.FIXED
        assert isinstance(strategy.value, str)


class TestFraudSignalTypeEnum:
    """Test FraudSignalType enum values and serialization."""

    def test_fraud_signal_type_has_all_values(self):
        """All expected fraud signal types exist."""
        assert FraudSignalType.UNUSUAL_TRAFFIC.value == "unusual_traffic"
        assert FraudSignalType.DUPLICATE_CLICK.value == "duplicate_click"
        assert FraudSignalType.BOT_PATTERN.value == "bot_pattern"
        assert FraudSignalType.GEOGRAPHIC_ANOMALY.value == "geographic_anomaly"
        assert FraudSignalType.RAPID_CLICKS.value == "rapid_clicks"

    def test_fraud_signal_type_is_string_enum(self):
        """FraudSignalType serializes as string."""
        signal_type = FraudSignalType.BOT_PATTERN
        assert isinstance(signal_type.value, str)


class TestFraudSignalStatusEnum:
    """Test FraudSignalStatus enum values and serialization."""

    def test_fraud_signal_status_has_all_values(self):
        """All expected fraud statuses exist."""
        assert FraudSignalStatus.PENDING.value == "pending"
        assert FraudSignalStatus.INVESTIGATED.value == "investigated"
        assert FraudSignalStatus.FALSE_ALARM.value == "false_alarm"
        assert FraudSignalStatus.CONFIRMED_FRAUD.value == "confirmed_fraud"

    def test_fraud_signal_status_is_string_enum(self):
        """FraudSignalStatus serializes as string."""
        status = FraudSignalStatus.PENDING
        assert isinstance(status.value, str)


class TestVendorAccountStatusEnum:
    """Test VendorAccountStatus enum values and serialization."""

    def test_vendor_account_status_has_all_values(self):
        """All expected vendor account statuses exist."""
        assert VendorAccountStatus.PENDING_APPROVAL.value == "pending_approval"
        assert VendorAccountStatus.ACTIVE.value == "active"
        assert VendorAccountStatus.SUSPENDED.value == "suspended"
        assert VendorAccountStatus.INACTIVE.value == "inactive"

    def test_vendor_account_status_is_string_enum(self):
        """VendorAccountStatus serializes as string."""
        status = VendorAccountStatus.ACTIVE
        assert isinstance(status.value, str)


# =============================================================================
# AD CAMPAIGN MODEL TESTS
# =============================================================================


class TestAdCampaignConstruction:
    """Test AdCampaign model construction with required fields."""

    def test_construct_with_required_fields(self):
        """AdCampaign can be constructed with minimal required fields."""
        campaign = AdCampaign(
            vendor_id="vendor_123",
            vendor_email="vendor@example.com",
            vendor_name="Bloom & Petal",
            campaign_name="Spring Collection",
            created_by="vendor@example.com",
        )
        assert campaign.vendor_id == "vendor_123"
        assert campaign.vendor_email == "vendor@example.com"
        assert campaign.vendor_name == "Bloom & Petal"
        assert campaign.campaign_name == "Spring Collection"
        assert campaign.created_by == "vendor@example.com"

    def test_construct_with_optional_fields(self):
        """AdCampaign accepts optional fields."""
        now = datetime.now(timezone.utc)
        campaign = AdCampaign(
            vendor_id="vendor_123",
            vendor_email="vendor@example.com",
            vendor_name="Bloom & Petal",
            campaign_name="Spring Collection",
            campaign_description="Beautiful spring arrangements",
            goal=CampaignGoal.QUOTE_REQUESTS,
            start_date=now,
            end_date=now + timedelta(days=30),
            created_by="vendor@example.com",
        )
        assert campaign.campaign_description == "Beautiful spring arrangements"
        assert campaign.goal == CampaignGoal.QUOTE_REQUESTS
        assert campaign.start_date == now
        assert campaign.end_date == now + timedelta(days=30)


class TestAdCampaignDefaults:
    """Test AdCampaign default values."""

    def test_default_status_is_draft(self):
        """Campaign status defaults to DRAFT."""
        campaign = AdCampaign(
            vendor_id="vendor_123",
            vendor_email="vendor@example.com",
            vendor_name="Bloom & Petal",
            campaign_name="Spring Collection",
            created_by="vendor@example.com",
        )
        assert campaign.status == CampaignStatus.DRAFT

    def test_default_quality_score_is_50(self):
        """Campaign quality_score defaults to 50."""
        campaign = AdCampaign(
            vendor_id="vendor_123",
            vendor_email="vendor@example.com",
            vendor_name="Bloom & Petal",
            campaign_name="Spring Collection",
            created_by="vendor@example.com",
        )
        assert campaign.quality_score == 50

    def test_default_counters_are_zero(self):
        """Campaign performance counters default to 0."""
        campaign = AdCampaign(
            vendor_id="vendor_123",
            vendor_email="vendor@example.com",
            vendor_name="Bloom & Petal",
            campaign_name="Spring Collection",
            created_by="vendor@example.com",
        )
        assert campaign.impression_count == 0
        assert campaign.click_count == 0
        assert campaign.lead_count == 0
        assert campaign.conversion_count == 0
        assert campaign.budget_consumed == 0.0

    def test_default_goal_is_profile_visits(self):
        """Campaign goal defaults to PROFILE_VISITS."""
        campaign = AdCampaign(
            vendor_id="vendor_123",
            vendor_email="vendor@example.com",
            vendor_name="Bloom & Petal",
            campaign_name="Spring Collection",
            created_by="vendor@example.com",
        )
        assert campaign.goal == CampaignGoal.PROFILE_VISITS

    def test_default_pacing_strategy_is_even(self):
        """Campaign pacing_strategy defaults to EVEN."""
        campaign = AdCampaign(
            vendor_id="vendor_123",
            vendor_email="vendor@example.com",
            vendor_name="Bloom & Petal",
            campaign_name="Spring Collection",
            created_by="vendor@example.com",
        )
        assert campaign.pacing_strategy == PacingStrategy.EVEN

    def test_default_bid_strategy_is_fixed(self):
        """Campaign bid_strategy defaults to FIXED."""
        campaign = AdCampaign(
            vendor_id="vendor_123",
            vendor_email="vendor@example.com",
            vendor_name="Bloom & Petal",
            campaign_name="Spring Collection",
            created_by="vendor@example.com",
        )
        assert campaign.bid_strategy == BidStrategy.FIXED

    def test_default_creative_lists_are_empty(self):
        """Campaign creative lists default to empty."""
        campaign = AdCampaign(
            vendor_id="vendor_123",
            vendor_email="vendor@example.com",
            vendor_name="Bloom & Petal",
            campaign_name="Spring Collection",
            created_by="vendor@example.com",
        )
        assert campaign.primary_creative_id is None
        assert campaign.creative_ids == []

    def test_default_targeting_lists_are_empty(self):
        """Campaign targeting lists default to empty."""
        campaign = AdCampaign(
            vendor_id="vendor_123",
            vendor_email="vendor@example.com",
            vendor_name="Bloom & Petal",
            campaign_name="Spring Collection",
            created_by="vendor@example.com",
        )
        assert campaign.target_categories == []
        assert campaign.target_wedding_stages == []
        assert campaign.target_placements == []
        assert campaign.target_regions == []


class TestAdCampaignCTRProperty:
    """Test AdCampaign.ctr property calculation."""

    def test_ctr_returns_zero_when_no_impressions(self):
        """CTR is 0 when impression_count is 0."""
        campaign = AdCampaign(
            vendor_id="vendor_123",
            vendor_email="vendor@example.com",
            vendor_name="Bloom & Petal",
            campaign_name="Spring Collection",
            impression_count=0,
            click_count=0,
            created_by="vendor@example.com",
        )
        assert campaign.ctr == 0.0

    def test_ctr_calculation_with_data(self):
        """CTR is calculated correctly: (clicks / impressions) * 100."""
        campaign = AdCampaign(
            vendor_id="vendor_123",
            vendor_email="vendor@example.com",
            vendor_name="Bloom & Petal",
            campaign_name="Spring Collection",
            impression_count=1000,
            click_count=50,
            created_by="vendor@example.com",
        )
        assert campaign.ctr == 5.0

    def test_ctr_calculation_with_partial_clicks(self):
        """CTR calculation works with partial percentages."""
        campaign = AdCampaign(
            vendor_id="vendor_123",
            vendor_email="vendor@example.com",
            vendor_name="Bloom & Petal",
            campaign_name="Spring Collection",
            impression_count=2000,
            click_count=25,
            created_by="vendor@example.com",
        )
        assert campaign.ctr == 1.25


class TestAdCampaignIsServableProperty:
    """Test AdCampaign.is_servable property."""

    def test_is_servable_false_when_not_active(self):
        """Campaign is not servable when status != ACTIVE."""
        campaign = AdCampaign(
            vendor_id="vendor_123",
            vendor_email="vendor@example.com",
            vendor_name="Bloom & Petal",
            campaign_name="Spring Collection",
            status=CampaignStatus.DRAFT,
            primary_creative_id="creative_123",
            created_by="vendor@example.com",
        )
        assert campaign.is_servable is False

    def test_is_servable_false_when_no_primary_creative(self):
        """Campaign is not servable without primary_creative_id."""
        campaign = AdCampaign(
            vendor_id="vendor_123",
            vendor_email="vendor@example.com",
            vendor_name="Bloom & Petal",
            campaign_name="Spring Collection",
            status=CampaignStatus.ACTIVE,
            primary_creative_id=None,
            created_by="vendor@example.com",
        )
        assert campaign.is_servable is False

    def test_is_servable_false_when_before_start_date(self):
        """Campaign is not servable before start_date."""
        now = datetime.now(timezone.utc)
        future = now + timedelta(days=1)
        campaign = AdCampaign(
            vendor_id="vendor_123",
            vendor_email="vendor@example.com",
            vendor_name="Bloom & Petal",
            campaign_name="Spring Collection",
            status=CampaignStatus.ACTIVE,
            primary_creative_id="creative_123",
            start_date=future,
            created_by="vendor@example.com",
        )
        assert campaign.is_servable is False

    def test_is_servable_false_when_after_end_date(self):
        """Campaign is not servable after end_date."""
        now = datetime.now(timezone.utc)
        past = now - timedelta(days=1)
        campaign = AdCampaign(
            vendor_id="vendor_123",
            vendor_email="vendor@example.com",
            vendor_name="Bloom & Petal",
            campaign_name="Spring Collection",
            status=CampaignStatus.ACTIVE,
            primary_creative_id="creative_123",
            end_date=past,
            created_by="vendor@example.com",
        )
        assert campaign.is_servable is False

    def test_is_servable_false_when_budget_exhausted(self):
        """Campaign is not servable when total_budget is reached."""
        campaign = AdCampaign(
            vendor_id="vendor_123",
            vendor_email="vendor@example.com",
            vendor_name="Bloom & Petal",
            campaign_name="Spring Collection",
            status=CampaignStatus.ACTIVE,
            primary_creative_id="creative_123",
            total_budget=100.0,
            budget_consumed=100.0,
            created_by="vendor@example.com",
        )
        assert campaign.is_servable is False

    def test_is_servable_true_when_all_conditions_met(self):
        """Campaign is servable when all conditions are met."""
        now = datetime.now(timezone.utc)
        past = now - timedelta(days=1)
        future = now + timedelta(days=1)
        campaign = AdCampaign(
            vendor_id="vendor_123",
            vendor_email="vendor@example.com",
            vendor_name="Bloom & Petal",
            campaign_name="Spring Collection",
            status=CampaignStatus.ACTIVE,
            primary_creative_id="creative_123",
            start_date=past,
            end_date=future,
            total_budget=100.0,
            budget_consumed=50.0,
            created_by="vendor@example.com",
        )
        assert campaign.is_servable is True

    def test_is_servable_true_when_unlimited_budget(self):
        """Campaign is servable with unlimited budget (total_budget=0)."""
        now = datetime.now(timezone.utc)
        past = now - timedelta(days=1)
        future = now + timedelta(days=1)
        campaign = AdCampaign(
            vendor_id="vendor_123",
            vendor_email="vendor@example.com",
            vendor_name="Bloom & Petal",
            campaign_name="Spring Collection",
            status=CampaignStatus.ACTIVE,
            primary_creative_id="creative_123",
            start_date=past,
            end_date=future,
            total_budget=0.0,  # Unlimited
            budget_consumed=1000.0,
            created_by="vendor@example.com",
        )
        assert campaign.is_servable is True


# =============================================================================
# AD CREATIVE MODEL TESTS
# =============================================================================


class TestAdCreativeConstruction:
    """Test AdCreative model construction."""

    def test_construct_with_required_fields(self):
        """AdCreative can be constructed with required fields."""
        creative = AdCreative(
            campaign_id="campaign_123",
            vendor_id="vendor_123",
            headline="Spring Arrangements",
            description="Beautiful hand-tied bouquets",
        )
        assert creative.campaign_id == "campaign_123"
        assert creative.vendor_id == "vendor_123"
        assert creative.headline == "Spring Arrangements"
        assert creative.description == "Beautiful hand-tied bouquets"

    def test_construct_with_all_fields(self):
        """AdCreative accepts all optional fields."""
        creative = AdCreative(
            campaign_id="campaign_123",
            vendor_id="vendor_123",
            creative_type=CreativeType.IMAGE,
            image_url="https://cdn.example.com/image.jpg",
            image_alt_text="Spring bouquet",
            headline="Spring Arrangements",
            description="Beautiful hand-tied bouquets",
            offer="20% off for March bookings",
            call_to_action="View Portfolio",
            is_primary=True,
        )
        assert creative.creative_type == CreativeType.IMAGE
        assert creative.image_url == "https://cdn.example.com/image.jpg"
        assert creative.image_alt_text == "Spring bouquet"
        assert creative.offer == "20% off for March bookings"
        assert creative.call_to_action == "View Portfolio"
        assert creative.is_primary is True


class TestAdCreativeDefaults:
    """Test AdCreative default values."""

    def test_default_review_status_is_pending(self):
        """Creative review_status defaults to PENDING."""
        creative = AdCreative(
            campaign_id="campaign_123",
            vendor_id="vendor_123",
            headline="Spring Arrangements",
            description="Beautiful hand-tied bouquets",
        )
        assert creative.review_status == CreativeReviewStatus.PENDING

    def test_default_creative_type_is_image(self):
        """Creative type defaults to IMAGE."""
        creative = AdCreative(
            campaign_id="campaign_123",
            vendor_id="vendor_123",
            headline="Spring Arrangements",
            description="Beautiful hand-tied bouquets",
        )
        assert creative.creative_type == CreativeType.IMAGE

    def test_default_call_to_action(self):
        """Creative call_to_action defaults to 'View Portfolio'."""
        creative = AdCreative(
            campaign_id="campaign_123",
            vendor_id="vendor_123",
            headline="Spring Arrangements",
            description="Beautiful hand-tied bouquets",
        )
        assert creative.call_to_action == "View Portfolio"

    def test_default_is_primary_is_false(self):
        """Creative is_primary defaults to False."""
        creative = AdCreative(
            campaign_id="campaign_123",
            vendor_id="vendor_123",
            headline="Spring Arrangements",
            description="Beautiful hand-tied bouquets",
        )
        assert creative.is_primary is False


# =============================================================================
# REQUEST MODEL TESTS
# =============================================================================


class TestCreateCampaignRequest:
    """Test CreateCampaignRequest validation."""

    def test_accepts_valid_data(self):
        """CreateCampaignRequest accepts valid campaign data."""
        request = CreateCampaignRequest(
            campaign_name="Spring Collection",
            goal=CampaignGoal.QUOTE_REQUESTS,
        )
        assert request.campaign_name == "Spring Collection"
        assert request.goal == CampaignGoal.QUOTE_REQUESTS

    def test_accepts_all_optional_fields(self):
        """CreateCampaignRequest accepts all optional fields."""
        now = datetime.now(timezone.utc)
        request = CreateCampaignRequest(
            campaign_name="Spring Collection",
            campaign_description="Beautiful spring themes",
            goal=CampaignGoal.QUOTE_REQUESTS,
            target_categories=["florist", "photographer"],
            target_wedding_stages=["engagement"],
            target_placements=["vendor_rail"],
            target_regions=["Dallas, TX"],
            target_budget_min=10000.0,
            target_budget_max=50000.0,
            daily_budget=50.0,
            total_budget=1000.0,
            pacing_strategy=PacingStrategy.ACCELERATED,
            start_date=now,
            end_date=now + timedelta(days=30),
            vendor_category="florist",
            vendor_service_area="Dallas, TX",
            metadata={"campaign_type": "seasonal"},
        )
        assert request.campaign_name == "Spring Collection"
        assert request.campaign_description == "Beautiful spring themes"
        assert request.daily_budget == 50.0
        assert request.target_categories == ["florist", "photographer"]

    def test_defaults_goal_to_profile_visits(self):
        """CreateCampaignRequest defaults goal to PROFILE_VISITS."""
        request = CreateCampaignRequest(campaign_name="Spring Collection")
        assert request.goal == CampaignGoal.PROFILE_VISITS


class TestUpdateCampaignRequest:
    """Test UpdateCampaignRequest allows partial updates."""

    def test_all_fields_optional(self):
        """UpdateCampaignRequest allows all fields to be omitted."""
        request = UpdateCampaignRequest()
        assert request.campaign_name is None
        assert request.goal is None

    def test_partial_update_campaign_name_only(self):
        """UpdateCampaignRequest can update only campaign_name."""
        request = UpdateCampaignRequest(campaign_name="New Name")
        assert request.campaign_name == "New Name"
        assert request.goal is None
        assert request.daily_budget is None

    def test_partial_update_multiple_fields(self):
        """UpdateCampaignRequest can update multiple fields."""
        request = UpdateCampaignRequest(
            campaign_name="New Name",
            goal=CampaignGoal.BOOKINGS,
            daily_budget=75.0,
        )
        assert request.campaign_name == "New Name"
        assert request.goal == CampaignGoal.BOOKINGS
        assert request.daily_budget == 75.0
        assert request.campaign_description is None

    def test_exclude_unset_allows_sparse_updates(self):
        """UpdateCampaignRequest exclude_unset works for sparse updates."""
        request = UpdateCampaignRequest(
            campaign_name="Updated Name",
            daily_budget=100.0,
        )
        data = request.model_dump(exclude_unset=True)
        assert "campaign_name" in data
        assert "daily_budget" in data
        assert "campaign_description" not in data


class TestCreateCreativeRequest:
    """Test CreateCreativeRequest validation."""

    def test_accepts_valid_data(self):
        """CreateCreativeRequest accepts valid creative data."""
        request = CreateCreativeRequest(
            headline="Spring Arrangements",
            description="Beautiful hand-tied bouquets",
        )
        assert request.headline == "Spring Arrangements"
        assert request.description == "Beautiful hand-tied bouquets"

    def test_accepts_all_optional_fields(self):
        """CreateCreativeRequest accepts all optional fields."""
        request = CreateCreativeRequest(
            creative_type=CreativeType.IMAGE,
            image_url="https://cdn.example.com/image.jpg",
            image_alt_text="Spring bouquet",
            headline="Spring Arrangements",
            description="Beautiful hand-tied bouquets",
            offer="20% off",
            call_to_action="Book Now",
            is_primary=True,
            metadata={"asset_id": "123"},
        )
        assert request.creative_type == CreativeType.IMAGE
        assert request.image_url == "https://cdn.example.com/image.jpg"
        assert request.offer == "20% off"
        assert request.is_primary is True

    def test_defaults_creative_type_to_image(self):
        """CreateCreativeRequest defaults creative_type to IMAGE."""
        request = CreateCreativeRequest(
            headline="Spring Arrangements",
            description="Beautiful hand-tied bouquets",
        )
        assert request.creative_type == CreativeType.IMAGE

    def test_defaults_call_to_action(self):
        """CreateCreativeRequest defaults call_to_action to 'View Portfolio'."""
        request = CreateCreativeRequest(
            headline="Spring Arrangements",
            description="Beautiful hand-tied bouquets",
        )
        assert request.call_to_action == "View Portfolio"


class TestReviewCampaignDecisionRequest:
    """Test ReviewCampaignDecisionRequest."""

    def test_accepts_optional_review_notes(self):
        """ReviewCampaignDecisionRequest accepts optional review_notes."""
        request = ReviewCampaignDecisionRequest(
            review_notes="Approved with minor adjustments"
        )
        assert request.review_notes == "Approved with minor adjustments"

    def test_review_notes_can_be_omitted(self):
        """ReviewCampaignDecisionRequest allows review_notes to be None."""
        request = ReviewCampaignDecisionRequest()
        assert request.review_notes is None


class TestReviewCreativeDecisionRequest:
    """Test ReviewCreativeDecisionRequest."""

    def test_accepts_optional_review_notes(self):
        """ReviewCreativeDecisionRequest accepts optional review_notes."""
        request = ReviewCreativeDecisionRequest(
            review_notes="Image needs higher resolution"
        )
        assert request.review_notes == "Image needs higher resolution"

    def test_review_notes_can_be_omitted(self):
        """ReviewCreativeDecisionRequest allows review_notes to be None."""
        request = ReviewCreativeDecisionRequest()
        assert request.review_notes is None


# =============================================================================
# CAMPAIGN DAY STATS TESTS
# =============================================================================


class TestCampaignDayStatsDefaults:
    """Test CampaignDayStats default values."""

    def test_hourly_arrays_default_to_zeros(self):
        """CampaignDayStats hourly arrays default to [0]*24."""
        now = datetime.now(timezone.utc)
        stats = CampaignDayStats(
            date=now,
            campaign_id="campaign_123",
            vendor_id="vendor_123",
        )
        assert len(stats.hourly_impressions) == 24
        assert all(x == 0 for x in stats.hourly_impressions)
        assert len(stats.hourly_clicks) == 24
        assert all(x == 0 for x in stats.hourly_clicks)

    def test_counters_default_to_zero(self):
        """CampaignDayStats counters default to 0."""
        now = datetime.now(timezone.utc)
        stats = CampaignDayStats(
            date=now,
            campaign_id="campaign_123",
            vendor_id="vendor_123",
        )
        assert stats.unique_planners == 0
        assert stats.unique_weddings == 0
        assert stats.ctr == 0.0
        assert stats.conversion_rate == 0.0
        assert stats.spend == 0.0

    def test_event_dicts_default_to_empty(self):
        """CampaignDayStats event dicts default to empty."""
        now = datetime.now(timezone.utc)
        stats = CampaignDayStats(
            date=now,
            campaign_id="campaign_123",
            vendor_id="vendor_123",
        )
        assert stats.events == {}
        assert stats.leads_by_type == {}
        assert stats.leads_by_status == {}


# =============================================================================
# PLACEMENT DAY STATS TESTS
# =============================================================================


class TestPlacementDayStatsDefaults:
    """Test PlacementDayStats default values."""

    def test_counters_default_to_zero(self):
        """PlacementDayStats counters default to 0."""
        now = datetime.now(timezone.utc)
        stats = PlacementDayStats(
            date=now,
            placement="vendor_rail",
        )
        assert stats.impressions == 0
        assert stats.clicks == 0
        assert stats.leads == 0
        assert stats.ctr == 0.0
        assert stats.unique_planners == 0
        assert stats.unique_campaigns == 0

    def test_construct_with_values(self):
        """PlacementDayStats can be constructed with values."""
        now = datetime.now(timezone.utc)
        stats = PlacementDayStats(
            date=now,
            placement="vendor_rail",
            impressions=100,
            clicks=5,
            leads=2,
            ctr=5.0,
            unique_planners=30,
            unique_campaigns=4,
        )
        assert stats.impressions == 100
        assert stats.clicks == 5
        assert stats.leads == 2
        assert stats.ctr == 5.0


# =============================================================================
# AD FRAUD SIGNAL TESTS
# =============================================================================


class TestAdFraudSignalConstruction:
    """Test AdFraudSignal model construction."""

    def test_construct_with_required_fields(self):
        """AdFraudSignal can be constructed with required fields."""
        signal = AdFraudSignal(
            signal_type=FraudSignalType.BOT_PATTERN,
        )
        assert signal.signal_type == FraudSignalType.BOT_PATTERN

    def test_default_status_is_pending(self):
        """AdFraudSignal status defaults to PENDING."""
        signal = AdFraudSignal(
            signal_type=FraudSignalType.UNUSUAL_TRAFFIC,
        )
        assert signal.status == FraudSignalStatus.PENDING

    def test_default_flagged_at_is_now(self):
        """AdFraudSignal flagged_at defaults to now."""
        before = datetime.now(timezone.utc)
        signal = AdFraudSignal(
            signal_type=FraudSignalType.RAPID_CLICKS,
        )
        after = datetime.now(timezone.utc)
        assert before <= signal.flagged_at <= after


# =============================================================================
# VENDOR AD BILLING TESTS
# =============================================================================


class TestVendorAdBillingDefaults:
    """Test VendorAdBilling default values."""

    def test_counters_default_to_zero(self):
        """VendorAdBilling counters default to 0."""
        now = datetime.now(timezone.utc)
        billing = VendorAdBilling(
            vendor_id="vendor_123",
            campaign_id="campaign_123",
            billing_period_start=now,
            billing_period_end=now + timedelta(days=30),
        )
        assert billing.impressions == 0
        assert billing.clicks == 0
        assert billing.leads == 0
        assert billing.conversions == 0
        assert billing.total_spend == 0.0

    def test_default_payment_status_is_pending(self):
        """VendorAdBilling payment_status defaults to 'pending'."""
        now = datetime.now(timezone.utc)
        billing = VendorAdBilling(
            vendor_id="vendor_123",
            campaign_id="campaign_123",
            billing_period_start=now,
            billing_period_end=now + timedelta(days=30),
        )
        assert billing.payment_status == "pending"

    def test_default_currency_is_usd(self):
        """VendorAdBilling currency defaults to 'USD'."""
        now = datetime.now(timezone.utc)
        billing = VendorAdBilling(
            vendor_id="vendor_123",
            campaign_id="campaign_123",
            billing_period_start=now,
            billing_period_end=now + timedelta(days=30),
        )
        assert billing.currency == "USD"
