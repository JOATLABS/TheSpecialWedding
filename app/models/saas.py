from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class SubscriptionPlanModel(BaseModel):
    """Subscription plans configurable by ROOT_ADMIN"""

    id: str = Field(..., alias="_id")
    name: str = Field(..., description="Plan name (e.g., Basic, Pro, Enterprise)")
    price: float = Field(..., description="Monthly price in USD")
    features: list[str] = Field(
        default_factory=list, description="List of features included"
    )
    max_weddings: int = Field(default=1, description="Maximum weddings allowed")
    ai_credits_monthly: int = Field(default=0, description="Monthly AI credits")
    storage_gb: int = Field(default=1, description="Storage limit in GB")
    vendor_seats: int = Field(
        default=0, description="Number of vendor accounts allowed"
    )
    is_active: bool = Field(
        default=True, description="Whether plan is available for signup"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Config:
        populate_by_name = True


class SaasContentModel(BaseModel):
    """SAAS landing page content configurable by ROOT_ADMIN"""

    id: str = Field(..., alias="_id")
    section: str = Field(
        ..., description="Section name: hero, features, pricing, testimonials, etc."
    )
    content: dict[str, Any] = Field(..., description="Section content as flexible JSON")
    is_active: bool = Field(default=True, description="Whether section is displayed")
    display_order: int = Field(default=0, description="Display order on page")
    updated_by: str = Field(..., description="Admin email who last updated")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Config:
        populate_by_name = True


class AIUsageModel(BaseModel):
    """Track AI feature usage for billing and limits"""

    id: str = Field(..., alias="_id")
    user_email: str = Field(..., description="User who used AI feature")
    feature_type: str = Field(
        ..., description="AI feature used: presentation, email, budget, etc."
    )
    credits_used: int = Field(default=1, description="Credits consumed")
    wedding_id: str | None = Field(None, description="Associated wedding ID")
    request_data: dict[str, Any] | None = Field(None, description="Request metadata")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Config:
        populate_by_name = True


class VendorModel(BaseModel):
    """Vendors created by wedding planners"""

    id: str = Field(..., alias="_id")
    name: str = Field(..., description="Vendor name")
    email: str = Field(..., description="Vendor email")
    company: str | None = Field(None, description="Vendor company")
    service_type: str = Field(
        ..., description="Type of service: photographer, caterer, etc."
    )
    wedding_id: str = Field(..., description="Wedding they're assigned to")
    created_by: str = Field(..., description="Wedding planner email who created vendor")
    permissions: list[str] = Field(
        default_factory=list, description="Checklist sections they can update"
    )
    is_active: bool = Field(
        default=True, description="Whether vendor account is active"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_login: datetime | None = Field(None, description="Last login timestamp")

    class Config:
        populate_by_name = True


class WeddingChecklistModel(BaseModel):
    """Wedding checklist items that vendors can update"""

    id: str = Field(..., alias="_id")
    wedding_id: str = Field(..., description="Associated wedding")
    category: str = Field(
        ..., description="Checklist category: venue, catering, photography, etc."
    )
    task: str = Field(..., description="Task description")
    assigned_vendor_id: str | None = Field(
        None, description="Vendor responsible for this task"
    )
    status: str = Field(
        default="pending", description="Status: pending, in_progress, completed"
    )
    due_date: datetime | None = Field(None, description="Task due date")
    notes: str | None = Field(None, description="Additional notes")
    updated_by: str | None = Field(None, description="Last updated by (email)")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Config:
        populate_by_name = True
