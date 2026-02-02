from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


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
        description="Days until contract access token expires (7-90)"
    )
    deposit_due_days: int = Field(
        default=7,
        ge=1,
        le=60,
        description="Days after contract signing for deposit to be due (1-60)"
    )
    payment_reminder_days: List[int] = Field(
        default=[7, 3, 1],
        description="Days before due date to send payment reminders"
    )
    auto_followup_days: int = Field(
        default=3,
        ge=1,
        le=14,
        description="Days after sending to auto-generate follow-up for unsigned contracts"
    )
    default_currency: str = Field(
        default="USD",
        description="Default currency for contracts"
    )


class UserModel(BaseModel):
    """Extended user model supporting multiple roles"""
    id: str = Field(..., alias="_id")
    email: str = Field(..., description="User email")
    password_hash: str = Field(..., description="Hashed password")
    role: str = Field(default="wedding_planner", description="User role: ROOT_ADMIN, wedding_planner, vendor")
    # Wedding planner specific fields
    company_name: Optional[str] = Field(None, description="Wedding planning company name")
    plan_id: Optional[str] = Field(None, description="Current subscription plan ID")
    subscription_status: str = Field(default="trial", description="Subscription status: trial, active, cancelled")
    trial_end_date: Optional[datetime] = Field(None, description="Trial expiration date")

    # Billing information
    stripe_customer_id: Optional[str] = Field(None, description="Stripe customer ID")
    stripe_subscription_id: Optional[str] = Field(None, description="Stripe subscription ID")
    stripe_connect_id: Optional[str] = Field(None, description="Stripe Connect Account ID for receiving payments")

    # Wedding planner permissions and limits
    max_weddings: int = Field(default=1, description="Maximum weddings allowed")
    ai_credits_remaining: int = Field(default=10, description="Remaining AI credits this month")
    ai_credits_reset_date: Optional[datetime] = Field(None, description="When AI credits reset")

    # Business preferences (planner-configurable)
    contract_settings: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Planner's contract preferences (token_expiry_days, deposit_due_days, etc.)"
    )

    # Vendor specific fields (if role is vendor)
    assigned_wedding_ids: List[str] = Field(default_factory=list, description="Weddings this vendor has access to")
    service_type: Optional[str] = Field(None, description="Type of service for vendors")
    created_by: Optional[str] = Field(None, description="Wedding planner who created this vendor")
    # Profile
    first_name: Optional[str] = Field(None, description="User's first name")
    last_name: Optional[str] = Field(None, description="User's last name")
    profile_image_url: Optional[str] = Field(None, description="S3/R2 URL for profile image")
    timezone: Optional[str] = Field(default="America/Chicago", description="IANA timezone for display (e.g., 'America/Chicago', 'Africa/Lagos')")

    # SMS Support Configuration (for wedding planners)
    support_phone: Optional[str] = Field(None, description="Phone number for guests to call when they need help (shown in HELP responses)")

    # Onboarding (for wedding planners)
    onboarding_completed: bool = Field(default=False, description="Whether planner has completed onboarding tour")
    onboarding_completed_at: Optional[datetime] = Field(None, description="When onboarding was completed")
    onboarding_steps_completed: List[str] = Field(default_factory=list, description="List of completed onboarding step IDs")

    # System fields
    is_active: bool = Field(default=True, description="Whether account is active")
    email_verified: bool = Field(default=False, description="Whether email is verified")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")

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
                "ai_credits_remaining": 50
            }
        }

# Migration compatible: This extends functionality without breaking existing admin_users collection


class AdminUserModel(BaseModel):
    """Legacy admin user model - keeping for backward compatibility"""
    email: str = Field(..., description="Admin email")
    password_hash: str = Field(..., description="Hashed password")
    role: str = Field(default="admin", description="Always 'admin' for backward compatibility")
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "email": "thedeveloper@thespecialwedding.com",
                "password_hash": "hashed_password_here",
                "role": "admin"
            }
        }
# Note: New user-related features should use UserModel going forward
