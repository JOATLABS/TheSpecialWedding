"""
Vendor Advertising Models — Phase 1 (Foundation)

Lightweight models for the sponsored vendor feature.
This is the manual-population approach (no auction engine).
Full ad campaign models will be added in Stage 4+.
"""

from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
from enum import Enum
from pydantic import Field, field_serializer

from app.models.base import MongoModel
from app.models.vendor import VendorCategory


# =============================================================================
# ENUMS
# =============================================================================

class AdCampaignStatus(str, Enum):
    """Status of an advertising campaign."""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class AdEventType(str, Enum):
    """Types of ad events that can be tracked."""
    IMPRESSION_SERVED = "impression_served"  # Ad was displayed
    IMPRESSION_VIEWABLE = "impression_viewable"  # Ad was viewable (IntersectionObserver-based)
    CLICK = "click"  # User clicked on ad
    VENDOR_PROFILE_VIEW = "vendor_profile_view"  # User viewed vendor profile/details
    VENDOR_ADDED_TO_WEDDING = "vendor_added_to_wedding"  # Vendor was added to wedding
    LEAD_CREATED = "lead_created"  # Lead was created from ad
    VENDOR_INVITED = "vendor_invited"  # Vendor was invited to wedding
    LEAD_ACCEPTED = "lead_accepted"  # Lead was accepted/responded
    VENDOR_RESPONDED = "vendor_responded"  # Vendor responded to lead
    DISMISS = "dismiss"  # User dismissed ad
    HOVER = "hover"  # User hovered over ad
    CONTACT_CLICK = "contact_click"  # User clicked contact button


class AdPlacement(str, Enum):
    """Locations where ads can appear on the platform."""
    VENDOR_RAIL = "vendor_rail"  # Sponsored vendors carousel
    VENDOR_DETAIL = "vendor_detail"  # On vendor detail page
    MILESTONE_MODULE = "milestone_module"  # Within wedding milestone modules
    DIRECTORY_BOOST = "directory_boost"  # Boosted in vendor directory


# =============================================================================
# SPONSORED VENDOR MODEL
# =============================================================================

class SponsoredVendor(MongoModel):
    """
    Sponsored vendor entry for manual ad placement.

    Represents a vendor that has been promoted to sponsored status
    for a specific placement and time period.
    """
    # Relationship to vendor
    vendor_profile_id: str = Field(
        ...,
        min_length=24,
        max_length=24,
        description="Reference to VendorProfile._id"
    )

    # Ad Placement Configuration
    placement: AdPlacement = Field(
        ...,
        description="Where this sponsored vendor appears"
    )
    priority: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Display priority (1-100, higher shows first)"
    )

    # Ad Content
    headline: Optional[str] = Field(
        None,
        max_length=100,
        description="Custom headline for the ad"
    )
    description: Optional[str] = Field(
        None,
        max_length=300,
        description="Custom description for the ad"
    )

    # Status & Visibility
    is_active: bool = Field(
        default=True,
        description="Whether this sponsored placement is currently active"
    )

    # Time Period
    start_date: Optional[datetime] = Field(
        None,
        description="When sponsorship begins"
    )
    end_date: Optional[datetime] = Field(
        None,
        description="When sponsorship ends"
    )

    # Targeting
    target_categories: List[VendorCategory] = Field(
        default_factory=list,
        description="Categories to target (empty = all)"
    )
    target_wedding_stages: List[str] = Field(
        default_factory=list,
        description="Wedding stages to target: engagement, planning, final_prep, wedding_week, post_wedding"
    )

    # Metadata
    created_by: str = Field(
        ...,
        max_length=254,
        description="Admin email who created this sponsored entry"
    )

    # Analytics
    impression_count: int = Field(
        default=0,
        ge=0,
        description="Total impressions for this sponsored vendor"
    )
    click_count: int = Field(
        default=0,
        ge=0,
        description="Total clicks for this sponsored vendor"
    )

    # Additional Data
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata for tracking or future extensions"
    )

    @property
    def ctr(self) -> float:
        """Calculate click-through rate (CTR)."""
        if self.impression_count == 0:
            return 0.0
        return (self.click_count / self.impression_count) * 100

    def is_within_date_range(self, check_date: Optional[datetime] = None) -> bool:
        """
        Check if the given date falls within the sponsorship period.

        Args:
            check_date: Date to check (defaults to now)

        Returns:
            True if date is within range or no date restrictions
        """
        if check_date is None:
            check_date = datetime.now(timezone.utc)

        if self.start_date and check_date < self.start_date:
            return False
        if self.end_date and check_date > self.end_date:
            return False

        return True


# =============================================================================
# AD EVENT MODEL
# =============================================================================

class AdEvent(MongoModel):
    """
    Tracks individual ad interactions and impressions.

    Records every click, impression, dismiss, etc. for analytics.
    """
    # Event Details
    event_type: AdEventType = Field(
        ...,
        description="Type of ad event"
    )

    # References
    sponsored_vendor_id: str = Field(
        ...,
        min_length=24,
        max_length=24,
        description="Reference to SponsoredVendor._id"
    )
    vendor_profile_id: str = Field(
        ...,
        min_length=24,
        max_length=24,
        description="Reference to VendorProfile._id"
    )
    placement: AdPlacement = Field(
        ...,
        description="Where the event occurred"
    )

    # Context
    wedding_id: Optional[str] = Field(
        None,
        min_length=24,
        max_length=24,
        description="Wedding being planned when event occurred"
    )
    planner_id: Optional[str] = Field(
        None,
        max_length=254,
        description="Email of planner who triggered event"
    )
    session_id: Optional[str] = Field(
        None,
        description="Session identifier for attribution"
    )
    click_id: Optional[str] = Field(
        None,
        description="UUID for click attribution and tracking"
    )

    # Additional Data
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional event context (user_agent, referrer, etc.)"
    )


# =============================================================================
# AD LEAD MODELS
# =============================================================================

class AdLeadStatus(str, Enum):
    """Status of an ad lead."""
    PENDING = "pending"
    CONTACTED = "contacted"
    RESPONDED = "responded"
    CONVERTED = "converted"
    CLOSED = "closed"


class AdLeadType(str, Enum):
    """Type of lead interaction."""
    QUOTE_REQUEST = "quote_request"
    MESSAGE = "message"
    ADD_TO_WEDDING = "add_to_wedding"
    VENDOR_INVITE = "vendor_invite"


class AdLead(MongoModel):
    """
    Tracks planner-to-vendor interactions originating from sponsored ads.

    Records leads created from ad clicks, including quote requests, messages,
    and vendor invitations from sponsored placements.
    """
    # Core identifiers
    sponsored_vendor_id: str = Field(
        ...,
        min_length=24,
        max_length=24,
        description="Reference to SponsoredVendor._id"
    )
    vendor_profile_id: str = Field(
        ...,
        min_length=24,
        max_length=24,
        description="Reference to VendorProfile._id"
    )
    planner_id: str = Field(
        ...,
        max_length=254,
        description="Email of planner who created the lead"
    )
    wedding_id: Optional[str] = Field(
        None,
        min_length=24,
        max_length=24,
        description="Reference to Wedding._id"
    )

    # Lead details
    lead_type: AdLeadType = Field(
        ...,
        description="Type of lead interaction"
    )
    status: AdLeadStatus = Field(
        default=AdLeadStatus.PENDING,
        description="Current status of the lead"
    )

    # Attribution
    click_id: Optional[str] = Field(
        None,
        description="UUID linking to originating ad click"
    )
    placement: AdPlacement = Field(
        default=AdPlacement.VENDOR_RAIL,
        description="Ad placement where lead originated"
    )

    # Lead content
    message: Optional[str] = Field(
        None,
        max_length=2000,
        description="Message or inquiry from planner"
    )
    quote_amount: Optional[float] = Field(
        None,
        ge=0,
        description="Quote amount if lead_type is QUOTE_REQUEST"
    )

    # Timestamps
    responded_at: Optional[datetime] = Field(
        None,
        description="When vendor responded to the lead"
    )
    converted_at: Optional[datetime] = Field(
        None,
        description="When lead was converted (booking made)"
    )

    # Metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional lead context and attributes"
    )


# =============================================================================
# PLANNER AD PREFERENCE MODEL
# =============================================================================

class PlannerAdPreference(MongoModel):
    """
    Stores planner preferences for ad display and interactions.

    Allows planners to hide vendors, categories, and reduce ad frequency.
    """
    # Core identifier
    planner_id: str = Field(
        ...,
        max_length=254,
        description="Email of the planner"
    )

    # Preferences
    hidden_vendor_ids: List[str] = Field(
        default_factory=list,
        description="List of SponsoredVendor IDs to hide from this planner"
    )
    hidden_categories: List[str] = Field(
        default_factory=list,
        description="List of VendorCategory values to hide"
    )
    reduced_frequency: bool = Field(
        default=False,
        description="Whether to show fewer ads to this planner"
    )

    # Per-wedding overrides
    wedding_overrides: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Wedding-specific preference overrides (keyed by wedding_id)"
    )


# =============================================================================
# ADVERTISING FEATURE FLAG MODEL
# =============================================================================

class AdvertisingFeatureFlag(MongoModel):
    """
    Controls whether the sponsored vendor feature is enabled.

    Lightweight feature flag with configurable settings.
    """
    # Feature Control
    feature_key: str = Field(
        default="sponsored_vendors",
        description="Feature key identifier"
    )
    is_enabled: bool = Field(
        default=False,
        description="Whether sponsored vendors feature is active"
    )

    # Audit Trail
    enabled_by: Optional[str] = Field(
        None,
        max_length=254,
        description="Admin email who enabled this feature"
    )
    enabled_at: Optional[datetime] = Field(
        None,
        description="When the feature was last enabled"
    )

    # Configuration
    config: Dict[str, Any] = Field(
        default_factory=lambda: {
            "max_sponsored_per_page": 3,
            "show_sponsored_badge": True,
            "show_sponsored_label": True,
            "enable_tracking": True,
            "min_priority_threshold": 1,
            "impressions_per_session_limit": 5
        },
        description="Feature configuration settings"
    )

    def get_config(self, key: str, default: Any = None) -> Any:
        """
        Safely retrieve a config value.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Config value or default
        """
        return self.config.get(key, default)


# =============================================================================
# PRE-AGGREGATED DAILY ROLLUP MODEL
# =============================================================================

class AdStatsDaily(MongoModel):
    """
    Pre-aggregated daily rollup of ad events per vendor per placement.

    Computed nightly via aggregation pipeline from ad_events.
    Dashboard queries read from this collection instead of scanning
    millions of raw events — response time drops from seconds to milliseconds.

    Unique constraint: (date, sponsored_vendor_id, placement)
    """
    # Partition key: UTC midnight of the day
    date: datetime = Field(
        ...,
        description="Day boundary (UTC midnight) — partition key"
    )

    # Dimension keys
    sponsored_vendor_id: str = Field(
        ...,
        min_length=24,
        max_length=24,
        description="Reference to SponsoredVendor._id"
    )
    vendor_profile_id: str = Field(
        ...,
        min_length=24,
        max_length=24,
        description="Reference to VendorProfile._id (denormalized for joins)"
    )
    placement: str = Field(
        ...,
        description="Ad placement where events occurred"
    )

    # Event counts — keyed by AdEventType value
    counts: Dict[str, int] = Field(
        default_factory=dict,
        description="Event counts per type: {impression_served: N, click: N, lead_created: N, ...}"
    )

    # Lead breakdown
    leads_by_type: Dict[str, int] = Field(
        default_factory=dict,
        description="Lead counts by type: {quote_request: N, message: N, ...}"
    )
    leads_by_status: Dict[str, int] = Field(
        default_factory=dict,
        description="Lead counts by status: {pending: N, contacted: N, ...}"
    )

    # Unique reach
    unique_planners: int = Field(
        default=0,
        ge=0,
        description="Distinct planner count for the day"
    )
    unique_weddings: int = Field(
        default=0,
        ge=0,
        description="Distinct wedding context count"
    )

    # Hourly distribution (for heatmap)
    hourly_clicks: List[int] = Field(
        default_factory=lambda: [0] * 24,
        description="Click distribution by hour (index 0-23)"
    )

    # Pre-computed metrics
    ctr: float = Field(
        default=0.0,
        description="Pre-computed click-through rate for the day"
    )


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class CreateSponsoredVendorRequest(MongoModel):
    """Request to create a new sponsored vendor."""
    vendor_profile_id: str = Field(..., min_length=24, max_length=24)
    placement: AdPlacement = Field(...)
    priority: int = Field(default=50, ge=1, le=100)
    headline: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=300)
    start_date: Optional[datetime] = Field(None)
    end_date: Optional[datetime] = Field(None)
    target_categories: List[VendorCategory] = Field(default_factory=list)
    target_wedding_stages: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class UpdateSponsoredVendorRequest(MongoModel):
    """Request to update an existing sponsored vendor."""
    priority: Optional[int] = Field(None, ge=1, le=100)
    headline: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=300)
    is_active: Optional[bool] = Field(None)
    start_date: Optional[datetime] = Field(None)
    end_date: Optional[datetime] = Field(None)
    target_categories: Optional[List[VendorCategory]] = Field(None)
    target_wedding_stages: Optional[List[str]] = Field(None)
    metadata: Optional[Dict[str, Any]] = Field(None)


class RecordAdEventRequest(MongoModel):
    """Request to record an ad event."""
    event_type: AdEventType = Field(...)
    sponsored_vendor_id: str = Field(..., min_length=24, max_length=24)
    vendor_profile_id: str = Field(..., min_length=24, max_length=24)
    placement: AdPlacement = Field(...)
    wedding_id: Optional[str] = Field(None, min_length=24, max_length=24)
    planner_id: Optional[str] = Field(None, max_length=254)
    session_id: Optional[str] = Field(None)
    click_id: Optional[str] = Field(None)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AdStatsResponse(MongoModel):
    """Response with ad statistics."""
    sponsored_vendor_id: str = Field(...)
    vendor_profile_id: str = Field(...)
    placement: AdPlacement = Field(...)
    total_impressions: int = Field(default=0)
    total_clicks: int = Field(default=0)
    ctr: float = Field(default=0.0)
    period_days: int = Field(default=7)
    recent_events_count: int = Field(default=0)


class CreateAdLeadRequest(MongoModel):
    """Request to create a new ad lead."""
    sponsored_vendor_id: str = Field(..., min_length=24, max_length=24)
    vendor_profile_id: str = Field(..., min_length=24, max_length=24)
    wedding_id: Optional[str] = Field(None, min_length=24, max_length=24)
    lead_type: AdLeadType = Field(...)
    message: Optional[str] = Field(None, max_length=2000)
    quote_amount: Optional[float] = Field(None, ge=0)
    click_id: Optional[str] = Field(None)
    placement: AdPlacement = Field(default=AdPlacement.VENDOR_RAIL)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AdLeadResponse(MongoModel):
    """Response model for ad lead details."""
    id: Optional[str] = Field(None, alias="_id")
    sponsored_vendor_id: str = Field(...)
    vendor_profile_id: str = Field(...)
    planner_id: str = Field(...)
    wedding_id: Optional[str] = Field(None)
    lead_type: AdLeadType = Field(...)
    status: AdLeadStatus = Field(...)
    click_id: Optional[str] = Field(None)
    placement: AdPlacement = Field(...)
    message: Optional[str] = Field(None)
    quote_amount: Optional[float] = Field(None)
    responded_at: Optional[datetime] = Field(None)
    converted_at: Optional[datetime] = Field(None)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = Field(None)
    updated_at: Optional[datetime] = Field(None)

    class ConfigDict:
        populate_by_name = True


class UpdateAdLeadStatusRequest(MongoModel):
    """Request to update ad lead status."""
    status: AdLeadStatus = Field(...)
    responded_at: Optional[datetime] = Field(None)
    converted_at: Optional[datetime] = Field(None)


class PlannerAdPreferenceResponse(MongoModel):
    """Response model for planner ad preferences."""
    planner_id: str = Field(...)
    hidden_vendor_ids: List[str] = Field(default_factory=list)
    hidden_categories: List[str] = Field(default_factory=list)
    reduced_frequency: bool = Field(default=False)
    wedding_overrides: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    created_at: Optional[datetime] = Field(None)
    updated_at: Optional[datetime] = Field(None)
