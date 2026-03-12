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
    IMPRESSION = "impression"  # Ad was displayed
    CLICK = "click"  # User clicked on ad
    DISMISS = "dismiss"  # User dismissed ad
    HOVER = "hover"  # User hovered over ad
    DETAIL_VIEW = "detail_view"  # User viewed vendor details
    CONTACT_CLICK = "contact_click"  # User clicked contact button
    ASSIGNMENT = "assignment"  # Vendor was assigned to wedding


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
