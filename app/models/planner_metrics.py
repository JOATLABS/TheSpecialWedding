"""
Pydantic response models for planner metrics API endpoints.

Used by:
- GET /planner/metrics
- GET /planner/activity-log
- GET /planner/weddings
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from app.models.wedding import EventModel, PrivacySettingsModel


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
    confirmed_rsvps: int = 0
    pending_rsvps: int = 0
    declined_rsvps: int = 0


class RevenueMetricsModel(BaseModel):
    """Revenue metrics calculated from subscription data."""
    monthly_bookings: int = Field(default=0, ge=0, description="New weddings booked this month")
    total_revenue: float = Field(default=0.0, ge=0.0, description="Total monthly revenue in USD")
    average_wedding_value: float = Field(default=0.0, ge=0.0, description="Average revenue per wedding in USD")


class ActivityItemModel(BaseModel):
    """Single activity entry in the activity log."""
    id: str
    type: str = "info"
    message: str = ""
    timestamp: str = ""
    wedding_id: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


class PlannerMetricsResponse(BaseModel):
    """Response model for GET /planner/metrics."""
    summary: MetricsSummaryModel = Field(default_factory=MetricsSummaryModel)
    weddings: List[WeddingMetricsModel] = Field(default_factory=list)
    recent_activity: List[ActivityItemModel] = Field(default_factory=list)
    revenue_metrics: RevenueMetricsModel = Field(default_factory=RevenueMetricsModel)


class ActivityLogResponse(BaseModel):
    """Response model for GET /planner/activity-log."""
    activities: List[ActivityItemModel] = Field(default_factory=list)
    total: int = 0


class PlannerWeddingModel(BaseModel):
    """Wedding data for GET /planner/weddings."""
    id: str = Field(..., serialization_alias="_id")
    couple_names: str = ""
    date: str = ""
    slug: str = ""
    assigned_planner_email: Optional[str] = None
    assigned_planner_id: Optional[str] = None
    status: str = "active"
    venue: Optional[str] = None
    guest_count: int = 0
    created_at: str = ""
    updated_at: str = ""
    events: List[Any] = Field(default_factory=list)
    privacy_settings: Optional[PrivacySettingsModel] = None
    rsvp_config: Optional[Dict[str, Any]] = None
    theme_config: Optional[Dict[str, Any]] = None
    registries: List[Any] = Field(default_factory=list)
    faqs: List[Any] = Field(default_factory=list)
    our_story: Optional[Dict[str, Any]] = None
    wedding_party: List[Any] = Field(default_factory=list)
    featured_image: Optional[str] = Field(None, description="S3 key for the featured background image")

    class Config:
        populate_by_name = True

    def model_dump(self, **kwargs):
        """Override to use _id in output."""
        kwargs.setdefault('by_alias', True)
        return super().model_dump(**kwargs)
