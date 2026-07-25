"""
Pydantic response models for planner metrics API endpoints.

Used by:
- GET /planner/metrics
- GET /planner/activity-log
- GET /planner/weddings
"""

from typing import Any

from pydantic import BaseModel, Field

from app.models.wedding import PrivacySettingsModel


class RSVPStatsModel(BaseModel):
    """RSVP statistics for a single wedding."""

    confirmed: int = Field(default=0, ge=0)
    declined: int = Field(default=0, ge=0)
    pending: int = Field(default=0, ge=0)
    total_responses: int = Field(default=0, ge=0)
    response_rate: float = Field(default=0.0, ge=0.0, le=100.0)


class WeddingMetricsModel(BaseModel):
    """Metrics for a single wedding in the planner dashboard."""

    id: str
    couple_names: str = ""
    date: str = ""
    slug: str = ""
    status: str = "active"
    guest_count: int = 0
    rsvp_stats: RSVPStatsModel = Field(default_factory=RSVPStatsModel)
    progress_percentage: int = Field(default=0, ge=0, le=100)
    days_until_wedding: int = 0
    created_at: str = ""
    assigned_planner_email: str = ""


class MetricsSummaryModel(BaseModel):
    """Aggregated summary statistics across all weddings."""

    total_weddings: int = 0
    active_weddings: int = 0
    upcoming_weddings: int = 0
    past_weddings: int = 0
    total_guests: int = 0
    total_plus_ones_allowed: int = Field(
        default=0,
        ge=0,
        description="Sum of number_of_plus_ones_allowed across all guests",
    )
    total_plus_ones_submitted: int = Field(
        default=0, ge=0, description="Actual plus-ones submitted"
    )
    confirmed_rsvps: int = 0
    confirmed_plus_ones_allowed: int = Field(
        default=0, ge=0, description="Plus-ones allowed for confirmed guests"
    )
    confirmed_plus_ones_submitted: int = Field(
        default=0, ge=0, description="Plus-ones submitted by confirmed guests"
    )
    pending_rsvps: int = 0
    pending_plus_ones_allowed: int = Field(
        default=0, ge=0, description="Plus-ones allowed for pending guests"
    )
    declined_rsvps: int = 0


class RevenueMetricsModel(BaseModel):
    """Revenue metrics calculated from subscription data."""

    monthly_bookings: int = Field(
        default=0, ge=0, description="New weddings booked this month"
    )
    total_revenue: float = Field(
        default=0.0, ge=0.0, description="Total monthly revenue in USD"
    )
    average_wedding_value: float = Field(
        default=0.0, ge=0.0, description="Average revenue per wedding in USD"
    )


class ActivityItemModel(BaseModel):
    """Single activity entry in the activity log."""

    id: str
    type: str = "info"
    message: str = ""
    timestamp: str = ""
    wedding_id: str | None = None
    metadata: dict = Field(default_factory=dict)


class PlannerMetricsResponse(BaseModel):
    """Response model for GET /planner/metrics."""

    summary: MetricsSummaryModel = Field(default_factory=MetricsSummaryModel)
    weddings: list[WeddingMetricsModel] = Field(default_factory=list)
    recent_activity: list[ActivityItemModel] = Field(default_factory=list)
    revenue_metrics: RevenueMetricsModel = Field(default_factory=RevenueMetricsModel)


class ActivityLogResponse(BaseModel):
    """Response model for GET /planner/activity-log."""

    activities: list[ActivityItemModel] = Field(default_factory=list)
    total: int = 0
    page: int = Field(default=1, ge=1, description="Current page number")
    limit: int = Field(default=50, ge=1, le=200, description="Number of items per page")
    pages: int = Field(default=0, ge=0, description="Total number of pages")


class PlannerWeddingModel(BaseModel):
    """Wedding data for GET /planner/weddings."""

    id: str = Field(..., serialization_alias="_id")
    couple_names: str = ""
    date: str = ""
    slug: str = ""
    assigned_planner_email: str | None = None
    assigned_planner_id: str | None = None
    status: str = "active"
    venue: str | None = None
    guest_count: int = 0
    created_at: str = ""
    updated_at: str = ""
    events: list[Any] = Field(default_factory=list)
    privacy_settings: PrivacySettingsModel | None = None
    rsvp_config: dict[str, Any] | None = None
    theme_config: dict[str, Any] | None = None
    registries: list[Any] = Field(default_factory=list)
    faqs: list[Any] = Field(default_factory=list)
    our_story: dict[str, Any] | None = None
    wedding_party: list[Any] = Field(default_factory=list)
    featured_image: str | None = Field(
        None, description="S3 key for the featured background image"
    )

    class Config:
        populate_by_name = True

    def model_dump(self, **kwargs):
        """Override to use _id in output."""
        kwargs.setdefault("by_alias", True)
        return super().model_dump(**kwargs)
