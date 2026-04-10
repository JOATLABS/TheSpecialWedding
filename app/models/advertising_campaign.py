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
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import Field

from app.models.base import MongoModel

# =============================================================================
# ENUMS
# =============================================================================


class CampaignGoal(str, Enum):
    """What the vendor wants to achieve with the campaign."""

    PROFILE_VISITS = "profile_visits"  # CPC — get planners to view profile
    QUOTE_REQUESTS = "quote_requests"  # CPL — get planners to request quotes
    BOOKINGS = "bookings"  # CPA — get planners to book (Phase 4+)


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


class BillingModel(str, Enum):
    """How the vendor is charged for ad activity."""

    CPL = "cpl"  # Cost per lead (quote request + directory add)
    FREE = "free"  # No charge (root admin override)


class LeadChargeType(str, Enum):
    """Differentiates lead types for pricing."""

    QUOTE_REQUEST = "quote_request"
    ADD_TO_DIRECTORY = "add_to_directory"


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
        description="Independent advertiser vendor user _id (NOT vendor_profile_id)",
    )
    vendor_email: str = Field(
        ..., max_length=254, description="Vendor's registered email"
    )
    vendor_name: str = Field(
        ...,
        max_length=200,
        description="Vendor's business name (denormalized for display)",
    )

    # ── Campaign metadata ──
    campaign_name: str = Field(..., max_length=200, description="Campaign display name")
    campaign_description: Optional[str] = Field(
        None, max_length=1000, description="Campaign description"
    )
    goal: CampaignGoal = Field(
        default=CampaignGoal.PROFILE_VISITS,
        description="Campaign objective: profile_visits (CPC), quote_requests (CPL), bookings (CPA)",
    )
    status: CampaignStatus = Field(
        default=CampaignStatus.DRAFT, description="Campaign lifecycle status"
    )

    # ── Targeting ──
    target_categories: List[str] = Field(
        default_factory=list,
        description="VendorCategory values to target (empty = all)",
    )
    target_wedding_stages: List[str] = Field(
        default_factory=list, description="Wedding stages to target (empty = all)"
    )
    target_placements: List[str] = Field(
        default_factory=list,
        description="AdPlacementType values (empty = all placements)",
    )
    target_regions: List[str] = Field(
        default_factory=list, description="Geographic targeting: city, state, zip codes"
    )
    target_budget_min: Optional[float] = Field(
        None, ge=0, description="Only show to planners with wedding budget >= this"
    )
    target_budget_max: Optional[float] = Field(
        None, ge=0, description="Only show to planners with wedding budget <= this"
    )

    # ── Budget & pacing ──
    daily_budget: float = Field(
        default=0.0,
        ge=0,
        description="Daily budget cap in USD (0 = unlimited for free tier)",
    )
    total_budget: float = Field(
        default=0.0,
        ge=0,
        description="Lifetime budget cap in USD (0 = unlimited for free tier)",
    )
    budget_consumed: float = Field(default=0.0, ge=0, description="Total spend to date")
    pacing_strategy: PacingStrategy = Field(
        default=PacingStrategy.EVEN,
    )

    # ── Schedule ──
    start_date: Optional[datetime] = Field(None)
    end_date: Optional[datetime] = Field(None)

    # ── Billing model ──
    billing_model: str = Field(
        default="cpl",
        description="Billing model: 'cpl' (cost per lead) or 'free' (no charge)",
    )
    is_free_tier: bool = Field(
        default=False,
        description="Campaign-level free tier override. Set by root admin only.",
    )
    cpl_quote_request: float = Field(
        default=10.0, ge=0, description="Cost per quote_request lead in USD"
    )
    cpl_directory_add: float = Field(
        default=3.0, ge=0, description="Cost per add_to_directory lead in USD"
    )

    # ── Bidding (placeholder for auction engine) ──
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
        None,
        max_length=200,
        description="Special offer text (e.g., '20% off if booked by March 31')",
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
        description="{impression_served: N, click: N, lead_created: N, ...}",
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

    click_velocity: Optional[int] = Field(
        None, description="Clicks in last 5 min window"
    )
    details: Dict[str, Any] = Field(default_factory=dict)

    status: FraudSignalStatus = Field(default=FraudSignalStatus.PENDING)
    flagged_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    notes: Optional[str] = Field(None, max_length=2000)


# =============================================================================
# VENDOR AD BILLING
# =============================================================================


class VendorAdBilling(MongoModel):
    """
    Vendor spend tracking per campaign per billing period.

    Each lead (quote_request or add_to_directory) creates a charge record.
    Free-tier campaigns still create records with charge_amount=0 so the data
    pipeline works identically — only actual Stripe charges are skipped.
    """

    vendor_id: str = Field(...)
    campaign_id: str = Field(...)
    billing_period_start: datetime = Field(...)
    billing_period_end: datetime = Field(...)

    # ── Activity counters ──
    impressions: int = Field(default=0, ge=0)
    clicks: int = Field(default=0, ge=0)
    leads: int = Field(default=0, ge=0)
    quote_request_leads: int = Field(default=0, ge=0)
    directory_add_leads: int = Field(default=0, ge=0)
    conversions: int = Field(default=0, ge=0)

    # ── Spend ──
    total_spend: float = Field(
        default=0.0, ge=0, description="Total charges this period"
    )
    currency: str = Field(default="USD")
    is_free_tier: bool = Field(
        default=False,
        description="True if campaign/vendor was free-tier at billing time",
    )

    # ── Stripe integration ──
    payment_status: str = Field(
        default="pending", description="pending | invoiced | paid | failed | free"
    )
    stripe_invoice_id: Optional[str] = Field(None)
    stripe_customer_id: Optional[str] = Field(None)


class AdLeadCharge(MongoModel):
    """
    Individual CPL charge record. One per lead event.

    Created immediately when a lead occurs. For paid campaigns, triggers
    Stripe invoice item creation. For free-tier campaigns, charge_amount=0
    and stripe_invoice_item_id is null.
    """

    lead_id: str = Field(..., description="ObjectId ref to ad_leads")
    campaign_id: str = Field(...)
    vendor_id: str = Field(...)
    lead_type: str = Field(..., description="quote_request or add_to_directory")
    charge_amount: float = Field(default=0.0, ge=0, description="CPL amount in USD")
    currency: str = Field(default="USD")
    is_free_tier: bool = Field(default=False)

    # ── Stripe ──
    stripe_invoice_item_id: Optional[str] = Field(None)
    stripe_customer_id: Optional[str] = Field(None)
    charge_status: str = Field(
        default="pending", description="pending | charged | free | failed"
    )

    # ── Context ──
    planner_id: Optional[str] = Field(None)
    click_id: Optional[str] = Field(None)


# =============================================================================
# VENDOR FREE TIER CONFIG
# =============================================================================


class VendorFreeTierConfig(MongoModel):
    """
    Vendor-level free tier override. When enabled, ALL campaigns from
    this vendor are free regardless of campaign-level settings.
    Only root admin can create/modify these records.
    """

    vendor_id: str = Field(..., description="The advertising vendor user _id")
    vendor_email: str = Field(default="", max_length=254)
    vendor_name: str = Field(default="", max_length=200)
    is_free: bool = Field(default=True)
    reason: str = Field(
        default="",
        max_length=500,
        description="Why this vendor gets free tier (e.g., 'launch partner', 'promo')",
    )
    granted_by: str = Field(
        ..., max_length=254, description="Root admin email who granted it"
    )
    expires_at: Optional[datetime] = Field(
        None, description="Optional expiry. Null = permanent free tier."
    )


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
    bid_amount: float = Field(
        default=0.0, ge=0, description="CPL bid amount for auction ranking"
    )
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
    bid_amount: Optional[float] = Field(
        None, ge=0, description="CPL bid amount for auction ranking"
    )
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


class SetFreeTierRequest(MongoModel):
    """Root admin request to toggle free tier on a campaign or vendor."""

    is_free: bool = Field(...)
    reason: str = Field(default="", max_length=500)
    expires_at: Optional[datetime] = Field(None)


class UpdateCPLPricingRequest(MongoModel):
    """Root admin request to update CPL pricing on a campaign."""

    cpl_quote_request: Optional[float] = Field(None, ge=0)
    cpl_directory_add: Optional[float] = Field(None, ge=0)


# =============================================================================
# PLATFORM CONFIG (Singleton document in ad_platform_config collection)
# =============================================================================


class AdPlatformConfig(MongoModel):
    """
    Advertising platform configuration — singleton document.

    Stores all configurable settings for the ad system: feature flags,
    serving limits, fraud detection thresholds, and vendor signup settings.
    Managed exclusively by root admin via /admin/ads/config endpoints.

    Collection: ad_platform_config (always exactly 1 document, _id="singleton")
    """

    # ── Feature Flags ──
    ads_enabled: bool = Field(default=True)
    show_sponsored_badge: bool = Field(default=True)
    enable_event_tracking: bool = Field(default=True)
    require_creative_review: bool = Field(default=True)
    auto_approve_returning_vendors: bool = Field(default=False)

    # ── Serving Limits ──
    max_sponsored_per_page: int = Field(default=3, ge=1, le=10)
    impressions_per_session: int = Field(default=5, ge=1, le=20)
    freq_cap_per_campaign_planner_day: int = Field(default=3, ge=1, le=20)
    review_sla_hours: int = Field(default=48, ge=1, le=168)
    max_campaigns_per_vendor: int = Field(default=5, ge=1, le=50)

    # ── Fraud Detection ──
    max_clicks_per_planner_campaign_hour: int = Field(default=5, ge=1, le=50)
    hide_rate_auto_pause_threshold: int = Field(
        default=3,
        ge=1,
        le=20,
        description="Unique planners hiding in 7d before auto-pause",
    )
    click_velocity_window_minutes: int = Field(default=5, ge=1, le=60)
    auto_void_suspicious_clicks: bool = Field(default=True)

    # ── Vendor Signup ──
    vendor_domain: str = Field(default="vendor.thespecialwedding.io", max_length=100)
    auto_approve_signups: bool = Field(default=False)
    require_profile_completion: bool = Field(default=True)
    min_images_for_campaign: int = Field(default=1, ge=0, le=10)

    # ── Metadata ──
    updated_at: Optional[datetime] = Field(None)
    updated_by: Optional[str] = Field(None, max_length=254)


class UpdatePlatformConfigRequest(MongoModel):
    """Root admin request to update platform config. All fields optional — only provided fields are updated."""

    # Feature Flags
    ads_enabled: Optional[bool] = None
    show_sponsored_badge: Optional[bool] = None
    enable_event_tracking: Optional[bool] = None
    require_creative_review: Optional[bool] = None
    auto_approve_returning_vendors: Optional[bool] = None

    # Serving Limits
    max_sponsored_per_page: Optional[int] = Field(None, ge=1, le=10)
    impressions_per_session: Optional[int] = Field(None, ge=1, le=20)
    freq_cap_per_campaign_planner_day: Optional[int] = Field(None, ge=1, le=20)
    review_sla_hours: Optional[int] = Field(None, ge=1, le=168)
    max_campaigns_per_vendor: Optional[int] = Field(None, ge=1, le=50)

    # Fraud Detection
    max_clicks_per_planner_campaign_hour: Optional[int] = Field(None, ge=1, le=50)
    hide_rate_auto_pause_threshold: Optional[int] = Field(None, ge=1, le=20)
    click_velocity_window_minutes: Optional[int] = Field(None, ge=1, le=60)
    auto_void_suspicious_clicks: Optional[bool] = None

    # Vendor Signup
    vendor_domain: Optional[str] = Field(None, max_length=100)
    auto_approve_signups: Optional[bool] = None
    require_profile_completion: Optional[bool] = None
    min_images_for_campaign: Optional[int] = Field(None, ge=0, le=10)


# =============================================================================
# PLANNER AD PREFERENCES
# =============================================================================


class PlannerAdPreferences(MongoModel):
    """
    Per-planner ad preferences.

    Controls how sponsored content is displayed to this planner.
    Collection: planner_ad_preferences (unique on planner_id)
    """

    planner_id: str = Field(..., description="Planner user _id")

    # ── Vendor hiding ──
    hidden_vendor_ids: List[str] = Field(
        default_factory=list,
        description="Vendor IDs this planner has dismissed — never shown again",
    )

    # ── Category suppression ──
    suppressed_categories: List[str] = Field(
        default_factory=list,
        description="Vendor categories the planner has suppressed (e.g., already booked)",
    )

    # ── Frequency ──
    reduced_frequency: bool = Field(
        default=False,
        description="When true, show max 1 card instead of 3 (P10 decision)",
    )

    # ── Metadata ──
    updated_at: Optional[datetime] = Field(None)
