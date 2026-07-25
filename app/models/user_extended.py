from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class ContractSettings(BaseModel):
    """
    Planner-configurable contract and payment settings.

    These override system defaults, allowing each planner to customize
    their contract workflow based on their business model.
    """

    token_expiry_days: int = Field(
        default=30,
        ge=7,
        le=90,
        description="Days until contract access token expires (7-90)",
    )
    deposit_due_days: int = Field(
        default=7,
        ge=1,
        le=60,
        description="Days after contract signing for deposit to be due (1-60)",
    )
    payment_reminder_days: list[int] = Field(
        default=[7, 3, 1], description="Days before due date to send payment reminders"
    )
    auto_followup_days: int = Field(
        default=3,
        ge=1,
        le=14,
        description="Days after sending to auto-generate follow-up for unsigned contracts",
    )
    default_currency: str = Field(
        default="USD", description="Default currency for contracts"
    )


class UserModel(BaseModel):
    """Extended user model supporting multiple roles"""

    id: str = Field(..., alias="_id")
    email: str = Field(..., description="User email")
    password_hash: str = Field(..., description="Hashed password")
    role: str = Field(
        default="wedding_planner",
        description="User role: ROOT_ADMIN, wedding_planner, vendor",
    )
    # Wedding planner specific fields
    company_name: str | None = Field(None, description="Wedding planning company name")
    plan_id: str | None = Field(None, description="Current subscription plan ID")
    subscription_status: str = Field(
        default="trial", description="Subscription status: trial, active, cancelled"
    )
    trial_end_date: datetime | None = Field(None, description="Trial expiration date")
    trial_warning_sent: bool = Field(
        default=False, description="Whether trial expiration warning email was sent"
    )
    trial_expired_at: datetime | None = Field(
        None, description="When the trial was expired by the system"
    )

    # Registration metadata
    registration_source: str | None = Field(
        None, description="How the user signed up: public_signup, admin_invite, etc."
    )

    # Billing information
    stripe_customer_id: str | None = Field(None, description="Stripe customer ID")
    stripe_subscription_id: str | None = Field(
        None, description="Stripe subscription ID"
    )
    stripe_connect_id: str | None = Field(
        None, description="Stripe Connect Account ID for receiving payments"
    )

    # Wedding planner permissions and limits
    max_weddings: int = Field(default=1, description="Maximum weddings allowed")
    ai_credits_remaining: int = Field(
        default=10, description="Remaining AI credits this month"
    )
    ai_credits_reset_date: datetime | None = Field(
        None, description="When AI credits reset"
    )

    # Business preferences (planner-configurable)
    contract_settings: dict[str, Any] | None = Field(
        default=None,
        description="Planner's contract preferences (token_expiry_days, deposit_due_days, etc.)",
    )

    # Team member fields (if role is team_member)
    parent_planner_id: str | None = Field(
        None, description="Owner planner's user ID (set when role=team_member)"
    )
    team_member_id: str | None = Field(
        None, description="Reference to team_members collection doc ID"
    )

    # Vendor specific fields (if role is vendor)
    assigned_wedding_ids: list[str] = Field(
        default_factory=list, description="Weddings this vendor has access to"
    )
    service_type: str | None = Field(None, description="Type of service for vendors")
    created_by: str | None = Field(
        None, description="Wedding planner who created this vendor"
    )
    # Profile
    first_name: str | None = Field(None, description="User's first name")
    last_name: str | None = Field(None, description="User's last name")
    profile_image_url: str | None = Field(
        None, description="S3/R2 URL for profile image"
    )
    timezone: str | None = Field(
        default="America/Chicago",
        description="IANA timezone for display (e.g., 'America/Chicago', 'Africa/Lagos')",
    )

    # SMS Support Configuration (for wedding planners)
    support_phone: str | None = Field(
        None,
        description="Phone number for guests to call when they need help (shown in HELP responses)",
    )

    # Onboarding (for wedding planners)
    onboarding_completed: bool = Field(
        default=False, description="Whether planner has completed onboarding tour"
    )
    onboarding_completed_at: datetime | None = Field(
        None, description="When onboarding was completed"
    )
    onboarding_steps_completed: list[str] = Field(
        default_factory=list, description="List of completed onboarding step IDs"
    )

    # System fields
    is_active: bool = Field(default=True, description="Whether account is active")
    email_verified: bool = Field(default=False, description="Whether email is verified")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_login: datetime | None = Field(None, description="Last login timestamp")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "_id": "user_001",
                "email": "planner@example.com",
                "role": "wedding_planner",
                "company_name": "Dream Weddings LLC",
                "plan_id": "plan_signature",
                "subscription_status": "active",
                "max_weddings": 5,
                "ai_credits_remaining": 50,
            }
        }


# Migration compatible: This extends functionality without breaking existing admin_users collection


class AdminUserModel(BaseModel):
    """Legacy admin user model"""

    email: str = Field(..., description="Admin email")
    password_hash: str = Field(..., description="Hashed password")
    role: str = Field(
        ..., description="User role: ROOT_ADMIN, wedding_planner, or vendor"
    )
    created_at: datetime | None = Field(default_factory=lambda: datetime.now(UTC))

    class Config:
        json_schema_extra = {
            "example": {
                "email": "thedeveloper@thespecialwedding.io",
                "password_hash": "hashed_password_here",
                "role": "wedding_planner",
            }
        }


# Note: New user-related features should use UserModel going forward
