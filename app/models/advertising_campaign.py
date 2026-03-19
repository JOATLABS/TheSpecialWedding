"""
Vendor Advertising Campaign Models — Full Platform Architecture

Independent advertising system where vendors sign up at vendor.thespecialwedding.io,
create campaigns, upload creatives, and manage ads. Completely decoupled from the
planner vendor directory.

Collections:
- ad_campaigns: Vendor-created campaigns with targeting, budget, schedule
- ad_creatives: Image/headline/description/offer/CTA per campaign
- campaign_day_stats: Daily rollup per campaign (replaces vendor-centric ad_stats_daily)
- placement_day_stats: Daily rollup per placement type
- ad_fraud_signals: TTL-indexed anomaly detection
- vendor_ad_billing: Vendor spend tracking (placeholder for free tier)

PRD Reference: Sections 6-8 (Full architecture, not Section 14.3 simplified version)
"""

from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
from enum import Enum
from pydantic import Field

from app.models.base import MongoModel


# =============================================================================
# ENUMS
# =============================================================================

class CampaignGoal(str, Enum):
    """What the vendor wants to achieve with the campaign."""
    PROFILE_VISITS = "profile_visits"    # CPC — get planners to view profile
    QUOTE_REQUESTS = "quote_requests"    # CPL — get planners to request quotes
    BOOKINGS = "bookings"               # CPA — get planners to book (Phase 4+)


class CampaignStatus(str, Enum):
    """Campaign lifecycle status."""
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    REJECTED = "rejected"


class CreativeReviewStatus(str, Enum):
    """Review status for campaign creatives."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CHANGES_REQUESTED = "changes_requested"


class CreativeType(str, Enum):
    """Types of ad creative assets."""
    IMAGE = "image"
    TEXT = "text"


class PacingStrategy(str, Enum):
    """How budget is distributed over campaign duration."""
    EVEN = "even"
    ACCELERATED = "accelerated"


class BidStrategy(str, Enum):
    """Bidding strategy for auction (Phase 4+)."""
    FIXED = "fixed"
    AUTO = "auto"


class FraudSignalType(str, Enum):
    """Types of fraud/anomaly signals."""
    UNUSUAL_TRAFFIC = "unusual_traffic"
    DUPLICATE_CLICK = "duplicate_click"
    BOT_PATTERN = "bot_pattern"
    GEOGRAPHIC_ANOMALY = "geographic_anomaly"
    RAPID_CLICKS = "rapid_clicks"


class FraudSignalStatus(str, Enum):
    """Status of a fraud investigation."""
    PENDING = "pending"
    INVESTIGATED = "investigated"
    FALSE_ALARM = "false_alarm"
    CONFIRMED_FRAUD = "confirmed_fraud"


class VendorAccountStatus(str, Enum):
    """Status of an advertising vendor account."""
    PENDING_APPROVAL = "pending_approval"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    INACTIVE = "inactive"


# =============================================================================
# AD CAMPAIGN MODEL
# =============================================================================

class AdCampaign(MongoModel):
    """
    Vendor-created advertising campaign.

    Core entity of the advertising platform. A vendor signs up independently,
    creates a campaign with targeting/budget/schedule, attaches creatives,
    submits for review. Once approved by the root admin, the campaign serves
    ads to planners in the sponsored vendor rail.

    vendor_id here is an INDEPENDENT advertiser identity (role: advertising_vendor),
    NOT a planner's vendor_profile_id. A florist in Dallas can advertise without
    any planner having added them to their vendor directory.

    Images stored in separate R2 bucket: vendor-ad-assets (S3_AD_BUCKET_NAME).
    """

    # ── Vendor identity (independent of planner vendor directory) ──
    vendor_id: str = Field(
        ...,
        description="Independent advertiser vendor user _id (NOT vendor_profile_id)"
    )
    vendor_email: str = Field(
        ...,
        max_length=254,
        description="Vendor's registered email"
    )
    vendor_name: str = Field(
        ...,
        max_length=200,
        description="Vendor's business name (denormalized for display)"
    )

    # ── Campaign metadata ──
    campaign_name: str = Field(
        ...,
        max_length=200,
        description="Campaign display name"
    )
    campaign_description: Optional[str] = Field(
        None,
        max_length=1000,
        description="Campaign description"
    )
    goal: CampaignGoal = Field(
        default=CampaignGoal.PROFILE_VISITS,
        description="Campaign objective: profile_visits (CPC), quote_requests (CPL), bookings (CPA)"
    )
    status: CampaignStatus = Field(
        default=CampaignStatus.DRAFT,
        description="Campaign lifecycle status"
    )

    # ── Targeting ──
    target_categories: List[str] = Field(
        default_factory=list,
        description="VendorCategory values to target (empty = all)"
    )
    target_wedding_stages: List[str] = Field(
        default_factory=list,
        description="Wedding stages to target (empty = all)"
    )
    target_placements: List[str] = Field(
        default_factory=list,
        description="AdPlacementType values (empty = all placements)"
    )
    target_regions: List[str] = Field(
        default_factory=list,
        description="Geographic targeting: city, state, zip codes"
    )
    target_budget_min: Optional[float] = Field(
        None, ge=0,
        description="Only show to planners with wedding budget >= this"
    )
    target_budget_max: Optional[float] = Field(
        None, ge=0,
        description="Only show to planners with wedding budget <= this"
    )

    # ── Budget & pacing ──
    daily_budget: float = Field(
        default=0.0, ge=0,
        description="Daily budget cap in USD (0 = unlimited for free tier)"
    )
    total_budget: float = Field(
        default=0.0, ge=0,
        description="Lifetime budget cap in USD (0 = unlimited for free tier)"
    )
    budget_consumed: float = Field(
        default=0.0, ge=0,
        description="Total spend to date"
    )
    pacing_strategy: PacingStrategy = Field(
        default=PacingStrategy.EVEN,
    )

    # ── Schedule ──
    start_date: Optional[datetime] = Field(None)
    end_date: Optional[datetime] = Field(None)

    # ── Bidding (placeholder, always 0 for free tier) ──
    bid_amount: float = Field(default=0.0, ge=0)
    bid_strategy: BidStrategy = Field(default=BidStrategy.FIXED)

    # ── Performance counters (denormalized, updated on events) ──
    quality_score: int = Field(default=50, ge=1, le=100)
    impression_count: int = Field(default=0, ge=0)
    click_count: int = Field(default=0, ge=0)
    lead_count: int = Field(default=0, ge=0)
    conversion_count: int = Field(default=0, ge=0)

    # ── Creatives ──
    primary_creative_id: Optional[str] = Field(
        None, description="ObjectId ref to primary AdCreative"
    )
    creative_ids: List[str] = Field(
        default_factory=list, description="All creative ObjectIds for this campaign"
    )

    # ── Review workflow ──
    submitted_at: Optional[datetime] = Field(None)
    reviewed_at: Optional[datetime] = Field(None)
    reviewed_by: Optional[str] = Field(None, max_length=254)
    review_notes: Optional[str] = Field(None, max_length=2000)

    # ── Vendor category & location (for matching with planner needs) ──
    vendor_category: Optional[str] = Field(
        None, description="Primary VendorCategory of the advertising vendor"
    )
    vendor_service_area: Optional[str] = Field(
        None, max_length=500, description="Vendor's service area (city, state)"
    )
    vendor_logo_url: Optional[str] = Field(
        None, description="CDN URL for vendor image (from vendor-ad-assets R2 bucket)"
    )

    # ── System ──
    created_by: str = Field(..., max_length=254)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def ctr(self) -> float:
        if self.impression_count == 0:
            return 0.0
        return (self.click_count / self.impression_count) * 100

    @property
    def is_servable(self) -> bool:
        """Can this campaign serve ads right now?"""
        if self.status != CampaignStatus.ACTIVE:
            return False
        if not self.primary_creative_id:
            return False
        now = datetime.now(timezone.utc)
        if self.start_date and now < self.start_date:
            return False
        if self.end_date and now > self.end_date:
            return False
        if self.total_budget > 0 and self.budget_consumed >= self.total_budget:
            return False
        return True


# =============================================================================
# AD CREATIVE MODEL
# =============================================================================

class AdCreative(MongoModel):
    """
    Creative asset for an ad campaign.

    Contains the actual ad content shown to planners: image, headline,
    description, offer, and call-to-action. Subject to root admin review.

    Images stored in R2 bucket: vendor-ad-assets (S3_AD_BUCKET_NAME).
    Key format: ads/{vendor_id}/{timestamp}_{filename}
    """

    campaign_id: str = Field(..., description="ObjectId ref to AdCampaign")
    vendor_id: str = Field(..., description="Denormalized vendor ID for access control")

    # ── Creative content ──
    creative_type: CreativeType = Field(default=CreativeType.IMAGE)
    image_url: Optional[str] = Field(
        None, description="CDN URL from vendor-ad-assets R2 bucket"
    )
    image_alt_text: Optional[str] = Field(None, max_length=200)
    headline: str = Field(..., max_length=100)
    description: str = Field(..., max_length=300)
    offer: Optional[str] = Field(
        None, max_length=200,
        description="Special offer text (e.g., '20% off if booked by March 31')"
    )
    call_to_action: str = Field(default="View Portfolio", max_length=50)

    # ── Review ──
    review_status: CreativeReviewStatus = Field(default=CreativeReviewStatus.PENDING)
    submitted_at: Optional[datetime] = Field(None)
    reviewed_at: Optional[datetime] = Field(None)
    reviewed_by: Optional[str] = Field(None, max_length=254)
    review_notes: Optional[str] = Field(None, max_length=2000)

    is_primary: bool = Field(default=False)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# CAMPAIGN DAY STATS (ROLLUP)
# =============================================================================

class CampaignDayStats(MongoModel):
    """
    Pre-aggregated daily rollup per campaign.

    Replaces the vendor-centric ad_stats_daily with campaign-centric stats.
    Computed nightly from raw ad_events. Dashboard reads from here.

    Unique constraint: (date, campaign_id)
    """

    date: datetime = Field(..., description="Day boundary (UTC midnight)")
    campaign_id: str = Field(..., description="ObjectId ref to AdCampaign")
    vendor_id: str = Field(..., description="Denormalized vendor ID")

    # ── Event counts ──
    events: Dict[str, int] = Field(
        default_factory=dict,
        description="{impression_served: N, click: N, lead_created: N, ...}"
    )

    # ── Lead breakdown ──
    leads_by_type: Dict[str, int] = Field(default_factory=dict)
    leads_by_status: Dict[str, int] = Field(default_factory=dict)

    # ── Reach ──
    unique_planners: int = Field(default=0, ge=0)
    unique_weddings: int = Field(default=0, ge=0)

    # ── Hourly distribution ──
    hourly_impressions: List[int] = Field(default_factory=lambda: [0] * 24)
    hourly_clicks: List[int] = Field(default_factory=lambda: [0] * 24)

    # ── Computed metrics ──
    ctr: float = Field(default=0.0)
    conversion_rate: float = Field(default=0.0)
    spend: float = Field(default=0.0, ge=0, description="Daily spend (0 for free tier)")


# =============================================================================
# PLACEMENT DAY STATS (ROLLUP)
# =============================================================================

class PlacementDayStats(MongoModel):
    """
    Daily rollup per ad placement type.

    Platform-level reporting: which placements perform best?
    Unique constraint: (date, placement)
    """

    date: datetime = Field(...)
    placement: str = Field(...)

    impressions: int = Field(default=0, ge=0)
    clicks: int = Field(default=0, ge=0)
    leads: int = Field(default=0, ge=0)
    ctr: float = Field(default=0.0)

    unique_planners: int = Field(default=0, ge=0)
    unique_campaigns: int = Field(default=0, ge=0)


# =============================================================================
# FRAUD SIGNAL
# =============================================================================

class AdFraudSignal(MongoModel):
    """
    TTL-indexed fraud/anomaly detection record. Auto-expires after 7 days.
    """

    signal_type: FraudSignalType = Field(...)
    campaign_id: Optional[str] = Field(None)
    vendor_id: Optional[str] = Field(None)
    planner_id: Optional[str] = Field(None, max_length=254)
    session_id: Optional[str] = Field(None)

    click_velocity: Optional[int] = Field(None, description="Clicks in last 5 min window")
    details: Dict[str, Any] = Field(default_factory=dict)

    status: FraudSignalStatus = Field(default=FraudSignalStatus.PENDING)
    flagged_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    notes: Optional[str] = Field(None, max_length=2000)


# =============================================================================
# VENDOR AD BILLING (PLACEHOLDER)
# =============================================================================

class VendorAdBilling(MongoModel):
    """
    Vendor spend tracking. Placeholder for free tier (all values $0).
    When billing goes live, tracks spend per campaign per billing period.
    """

    vendor_id: str = Field(...)
    campaign_id: str = Field(...)
    billing_period_start: datetime = Field(...)
    billing_period_end: datetime = Field(...)

    impressions: int = Field(default=0, ge=0)
    clicks: int = Field(default=0, ge=0)
    leads: int = Field(default=0, ge=0)
    conversions: int = Field(default=0, ge=0)
    total_spend: float = Field(default=0.0, ge=0, description="Always 0 for free tier")
    currency: str = Field(default="USD")

    payment_status: str = Field(default="pending")
    stripe_invoice_id: Optional[str] = Field(None)


# =============================================================================
# REQUEST / RESPONSE MODELS
# =============================================================================

class CreateCampaignRequest(MongoModel):
    """Request to create a new ad campaign."""
    campaign_name: str = Field(..., max_length=200)
    campaign_description: Optional[str] = Field(None, max_length=1000)
    goal: CampaignGoal = Field(default=CampaignGoal.PROFILE_VISITS)
    target_categories: List[str] = Field(default_factory=list)
    target_wedding_stages: List[str] = Field(default_factory=list)
    target_placements: List[str] = Field(default_factory=list)
    target_regions: List[str] = Field(default_factory=list)
    target_budget_min: Optional[float] = Field(None, ge=0)
    target_budget_max: Optional[float] = Field(None, ge=0)
    daily_budget: float = Field(default=0.0, ge=0)
    total_budget: float = Field(default=0.0, ge=0)
    pacing_strategy: PacingStrategy = Field(default=PacingStrategy.EVEN)
    start_date: Optional[datetime] = Field(None)
    end_date: Optional[datetime] = Field(None)
    vendor_category: Optional[str] = Field(None)
    vendor_service_area: Optional[str] = Field(None, max_length=500)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class UpdateCampaignRequest(MongoModel):
    """Request to update a draft campaign. Only mutable fields."""
    campaign_name: Optional[str] = Field(None, max_length=200)
    campaign_description: Optional[str] = Field(None, max_length=1000)
    goal: Optional[CampaignGoal] = Field(None)
    target_categories: Optional[List[str]] = Field(None)
    target_wedding_stages: Optional[List[str]] = Field(None)
    target_placements: Optional[List[str]] = Field(None)
    target_regions: Optional[List[str]] = Field(None)
    target_budget_min: Optional[float] = Field(None, ge=0)
    target_budget_max: Optional[float] = Field(None, ge=0)
    daily_budget: Optional[float] = Field(None, ge=0)
    total_budget: Optional[float] = Field(None, ge=0)
    pacing_strategy: Optional[PacingStrategy] = Field(None)
    start_date: Optional[datetime] = Field(None)
    end_date: Optional[datetime] = Field(None)
    vendor_category: Optional[str] = Field(None)
    vendor_service_area: Optional[str] = Field(None, max_length=500)
    metadata: Optional[Dict[str, Any]] = Field(None)


class CreateCreativeRequest(MongoModel):
    """Request to create a new ad creative."""
    creative_type: CreativeType = Field(default=CreativeType.IMAGE)
    image_url: Optional[str] = Field(None)
    image_alt_text: Optional[str] = Field(None, max_length=200)
    headline: str = Field(..., max_length=100)
    description: str = Field(..., max_length=300)
    offer: Optional[str] = Field(None, max_length=200)
    call_to_action: str = Field(default="View Portfolio", max_length=50)
    is_primary: bool = Field(default=False)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ReviewCampaignDecisionRequest(MongoModel):
    """Root admin request to review a campaign (approve/reject/request changes)."""
    review_notes: Optional[str] = Field(None, max_length=2000)


class ReviewCreativeDecisionRequest(MongoModel):
    """Root admin request to review a creative."""
    review_notes: Optional[str] = Field(None, max_length=2000)
