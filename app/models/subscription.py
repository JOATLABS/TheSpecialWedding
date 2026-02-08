from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class SubscriptionStatus(str, Enum):
    """Subscription status enumeration"""
    PENDING_PAYMENT = "pending_payment"
    TRIAL = "trial"
    ACTIVE = "active"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    SUSPENDED = "suspended"


class BillingInterval(str, Enum):
    """Billing interval enumeration"""
    MONTHLY = "monthly"
    YEARLY = "yearly"
    LIFETIME = "lifetime"


class SubscriptionPlanModel(BaseModel):
    """Subscription plan model"""
    id: str = Field(..., alias="_id", description="Unique plan identifier")
    name: str = Field(..., description="Plan name (e.g., 'Starter', 'Professional')")
    description: Optional[str] = Field(None, description="Plan description")

    # Pricing
    price_monthly: float = Field(0, description="Monthly price in USD")
    price_yearly: Optional[float] = Field(None, description="Yearly price in USD (if different from 12x monthly)")

    # Metered Billing Support
    is_metered: bool = Field(False, description="Whether this plan uses metered billing")
    meter_event_name: Optional[str] = Field(None, description="Stripe Meter Event Name for usage reporting")
    meter_id: Optional[str] = Field(None, description="Stripe Meter ID")

    # Features and Limits
    max_weddings: int = Field(1, description="Maximum weddings allowed (-1 for unlimited)")
    max_guests_per_wedding: int = Field(100, description="Maximum guests per wedding (-1 for unlimited)")
    ai_credits_monthly: int = Field(10, description="AI credits per month")
    storage_gb: int = Field(1, description="Storage limit in GB")
    staff_seats: int = Field(0, description="Number of staff accounts allowed")
    # Feature flags - vendor_management enables/disables the entire vendor feature
    features: Dict[str, bool] = Field(default_factory=dict, description="Feature availability flags")
    features_list: Optional[List[str]] = Field(None, description="Human-readable feature highlights for display")

    # System fields
    is_active: bool = Field(True, description="Whether plan is available for new subscriptions")
    is_featured: bool = Field(False, description="Whether to highlight this plan")
    sort_order: int = Field(0, description="Sort order for backend queries")
    display_order: Optional[int] = Field(None, description="Display order for frontend (falls back to sort_order)")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str = Field(..., description="ROOT_ADMIN email who created this plan")
    
    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "_id": "plan_starter",
                "name": "Starter",
                "description": "Perfect for getting started with wedding planning",
                "price_monthly": 0,
                "price_yearly": 0,
                "is_metered": False,
                "max_weddings": 1,
                "max_guests_per_wedding": 100,
                "ai_credits_monthly": 10,
                "storage_gb": 1,
                "staff_seats": 0,
                "features": {
                    "basic_rsvp": True,
                    "simple_website": True,
                    "email_notifications": True,
                    "guest_management": True,
                    "ai_tools": False,
                    "advanced_reporting": False,
                    "white_label": False
                },
                "is_active": True,
                "is_featured": False,
                "sort_order": 1,
                "created_by": "thedeveloper@thespecialwedding.com"
            }
        }


class UserSubscriptionModel(BaseModel):
    """User subscription instance model"""
    id: str = Field(..., alias="_id", description="Unique subscription identifier")
    user_id: str = Field(..., description="User ID this subscription belongs to")
    user_email: str = Field(..., description="User email for reference")
    plan_id: str = Field(..., description="Subscription plan ID")

    # Plan snapshot at subscription time (grandfathering support)
    # These limits are LOCKED at subscription creation - don't change when plan is modified
    plan_snapshot: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Snapshot of plan limits at subscription time for grandfathering"
    )

    # Subscription details
    status: SubscriptionStatus = Field(SubscriptionStatus.TRIAL, description="Current subscription status")
    billing_interval: BillingInterval = Field(BillingInterval.MONTHLY, description="Billing frequency")

    # Dates
    start_date: datetime = Field(default_factory=datetime.utcnow, description="Subscription start date")
    trial_end_date: Optional[datetime] = Field(None, description="Trial expiration date")
    current_period_start: datetime = Field(default_factory=datetime.utcnow, description="Current billing period start")
    current_period_end: datetime = Field(..., description="Current billing period end")
    cancelled_at: Optional[datetime] = Field(None, description="Cancellation date")
    trial_expired_at: Optional[datetime] = Field(None, description="When trial was expired by system")
    cancellation_reason: Optional[str] = Field(None, description="Reason for cancellation")

    # Usage tracking
    usage: Dict[str, Any] = Field(default_factory=dict, description="Current usage statistics")

    # Payment integration
    stripe_customer_id: Optional[str] = Field(None, description="Stripe customer ID")
    stripe_subscription_id: Optional[str] = Field(None, description="Stripe subscription ID")
    stripe_checkout_session_id: Optional[str] = Field(None, description="Stripe checkout session ID")
    payment_status: Optional[str] = Field(None, description="Payment status from Stripe (paid, unpaid, past_due)")

    # System fields
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str = Field(..., description="ROOT_ADMIN email who created this subscription")
    
    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "_id": "sub_user123_plan456",
                "user_id": "user_12345",
                "user_email": "planner@example.com",
                "plan_id": "plan_professional",
                "status": "active",
                "billing_interval": "monthly",
                "usage": {
                    "weddings_created": 2,
                    "ai_credits_used": 45,
                    "storage_used_gb": 2.3,
                    "staff_seats_used": 1
                },
                "created_by": "thedeveloper@thespecialwedding.com"
            }
        }


class UsageTrackingModel(BaseModel):
    """Usage tracking for subscription limits"""
    user_id: str = Field(..., description="User ID")
    subscription_id: str = Field(..., description="Subscription ID")
    # Current usage
    weddings_count: int = Field(0, description="Current number of weddings")
    ai_credits_used_month: int = Field(0, description="AI credits used this month")
    storage_used_gb: float = Field(0, description="Storage used in GB")
    staff_seats_used: int = Field(0, description="Active staff accounts")

    # Monthly tracking
    current_month: str = Field(..., description="Current tracking month (YYYY-MM)")
    credits_reset_date: datetime = Field(..., description="When AI credits reset")

    # System fields
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user_12345",
                "subscription_id": "sub_user123_plan456",
                "weddings_count": 3,
                "ai_credits_used_month": 75,
                "storage_used_gb": 4.2,
                "staff_seats_used": 2,
                "current_month": "2025-08",
                "credits_reset_date": "2025-09-01T00:00:00Z"
            }
        }


# Request/Response models for API
class CreateSubscriptionPlanRequest(BaseModel):
    """Request model for creating subscription plans"""
    name: str
    description: Optional[str] = None
    price_monthly: float
    price_yearly: Optional[float] = None
    is_metered: bool = False
    meter_event_name: Optional[str] = None
    meter_id: Optional[str] = None
    max_weddings: int = 1
    max_guests_per_wedding: int = 100
    ai_credits_monthly: int = 10
    storage_gb: int = 1
    staff_seats: int = 0
    features: Dict[str, bool] = Field(default_factory=dict)
    is_featured: bool = False
    sort_order: int = 0


class UpdateSubscriptionPlanRequest(BaseModel):
    """Request model for updating subscription plans"""
    name: Optional[str] = None
    description: Optional[str] = None
    price_monthly: Optional[float] = None
    price_yearly: Optional[float] = None
    is_metered: Optional[bool] = None
    meter_event_name: Optional[str] = None
    meter_id: Optional[str] = None
    max_weddings: Optional[int] = None
    max_guests_per_wedding: Optional[int] = None
    ai_credits_monthly: Optional[int] = None
    storage_gb: Optional[int] = None
    staff_seats: Optional[int] = None
    features: Optional[Dict[str, bool]] = None
    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None
    sort_order: Optional[int] = None


class AssignSubscriptionRequest(BaseModel):
    """Request model for assigning subscription to user"""
    plan_id: str
    billing_interval: BillingInterval = BillingInterval.MONTHLY
    trial_days: int = Field(default=0, ge=0, description="Trial days (0 = no trial)")
