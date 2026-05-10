from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.constants.billing import (
    BILLING_MODEL_METERED,
    CANONICAL_PUBLIC_PLAN_METER_EVENT_NAME,
)


class SubscriptionStatus(str, Enum):
    """Subscription status enumeration.

    Note: PAST_DUE and TRIAL_EXPIRING added to support the explicit state
    machine (P0-12).  The state machine validates transitions — see
    docs/P0_ARCHITECTURAL_REFACTORS.md for the full transition graph.
    """

    PENDING_CHECKOUT = "pending_checkout"
    PENDING_PAYMENT = "pending_payment"
    TRIAL = "trial"
    TRIAL_EXPIRING = "trial_expiring"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    SUSPENDED = "suspended"


SUBSCRIPTION_STATUS_ALIASES = {
    "trialing": SubscriptionStatus.TRIAL.value,
    "canceled": SubscriptionStatus.CANCELLED.value,
    "cancelled": SubscriptionStatus.CANCELLED.value,
    "incomplete": SubscriptionStatus.PENDING_PAYMENT.value,
    "incomplete_expired": SubscriptionStatus.EXPIRED.value,
    "unpaid": SubscriptionStatus.SUSPENDED.value,
}

ACTIVE_SUBSCRIPTION_STATUSES = frozenset(
    {
        SubscriptionStatus.ACTIVE.value,
        SubscriptionStatus.TRIAL.value,
        SubscriptionStatus.TRIAL_EXPIRING.value,
    }
)

BILLING_PORTAL_RECOVERY_SUBSCRIPTION_STATUSES = frozenset(
    {
        SubscriptionStatus.PAST_DUE.value,
        SubscriptionStatus.SUSPENDED.value,
    }
)

PLANNER_BLOCKED_SUBSCRIPTION_STATUSES = frozenset(
    {
        SubscriptionStatus.PENDING_CHECKOUT.value,
        SubscriptionStatus.PENDING_PAYMENT.value,
        SubscriptionStatus.PAST_DUE.value,
        SubscriptionStatus.CANCELLED.value,
        SubscriptionStatus.EXPIRED.value,
        SubscriptionStatus.SUSPENDED.value,
        "inactive",
        "pending",
    }
)

PUBLIC_CHECKOUT_ALLOWED_STATUSES = frozenset(
    {
        SubscriptionStatus.PENDING_PAYMENT.value,
        SubscriptionStatus.PENDING_CHECKOUT.value,
    }
)


def normalize_subscription_status(status: Optional[str]) -> Optional[str]:
    """Return the canonical internal subscription status string."""

    if status is None:
        return None

    normalized = status.strip().lower()
    if not normalized:
        return None

    return SUBSCRIPTION_STATUS_ALIASES.get(normalized, normalized)


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
    price_yearly: Optional[float] = Field(
        None, description="Yearly price in USD (if different from 12x monthly)"
    )

    # Stripe Integration
    stripe_product_id: Optional[str] = Field(None, description="Stripe product ID")
    stripe_price_id_monthly: Optional[str] = Field(
        None, description="Stripe price ID for monthly billing"
    )
    stripe_price_id_yearly: Optional[str] = Field(
        None, description="Stripe price ID for yearly billing"
    )

    # Metered Billing Support
    billing_model: str = Field(
        BILLING_MODEL_METERED,
        description="Canonical billing model for this plan: flat_rate or metered",
    )
    is_metered: bool = Field(True, description="Whether this plan uses metered billing")
    meter_event_name: Optional[str] = Field(
        CANONICAL_PUBLIC_PLAN_METER_EVENT_NAME,
        description="Stripe Meter Event Name for usage reporting",
    )
    meter_id: Optional[str] = Field(None, description="Stripe Meter ID")

    # Features and Limits
    max_weddings: int = Field(
        1, description="Maximum weddings allowed (-1 for unlimited)"
    )
    max_guests_per_wedding: int = Field(
        100, description="Maximum guests per wedding (-1 for unlimited)"
    )
    ai_credits_monthly: int = Field(10, description="AI credits per month")
    storage_gb: int = Field(1, description="Storage limit in GB")
    staff_seats: int = Field(0, description="Number of staff accounts allowed")
    # Feature flags - vendor_management enables/disables the entire vendor feature
    features: Dict[str, bool] = Field(
        default_factory=dict, description="Feature availability flags"
    )
    features_list: Optional[List[str]] = Field(
        None, description="Human-readable feature highlights for display"
    )

    # System fields
    is_active: bool = Field(
        True, description="Whether plan is available for new subscriptions"
    )
    is_featured: bool = Field(False, description="Whether to highlight this plan")
    sort_order: int = Field(0, description="Sort order for backend queries")
    display_order: Optional[int] = Field(
        None, description="Display order for frontend (falls back to sort_order)"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
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
                "billing_model": "metered",
                "is_metered": True,
                "meter_event_name": "wedding_active",
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
                    "white_label": False,
                },
                "is_active": True,
                "is_featured": False,
                "sort_order": 1,
                "created_by": "thedeveloper@thespecialwedding.io",
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
        description="Snapshot of plan limits at subscription time for grandfathering",
    )

    # Subscription details
    status: SubscriptionStatus = Field(
        SubscriptionStatus.TRIAL, description="Current subscription status"
    )
    billing_interval: BillingInterval = Field(
        BillingInterval.MONTHLY, description="Billing frequency"
    )

    # Dates
    start_date: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Subscription start date",
    )
    trial_start_date: Optional[datetime] = Field(
        None, description="Trial start date from Stripe"
    )
    trial_end_date: Optional[datetime] = Field(
        None, description="Trial expiration date"
    )
    current_period_start: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Current billing period start",
    )
    current_period_end: datetime = Field(..., description="Current billing period end")
    cancelled_at: Optional[datetime] = Field(None, description="Cancellation date")
    trial_expired_at: Optional[datetime] = Field(
        None, description="When trial was expired by system"
    )
    cancellation_reason: Optional[str] = Field(
        None, description="Reason for cancellation"
    )
    archived_at: Optional[datetime] = Field(
        None, description="When subscription was archived for cleanup"
    )
    stripe_checkout_completed_at: Optional[datetime] = Field(
        None, description="When Stripe checkout was completed"
    )
    last_payment_date: Optional[datetime] = Field(
        None, description="Date of last successful payment"
    )
    last_payment_attempt: Optional[datetime] = Field(
        None, description="Date of last payment attempt"
    )

    # Usage tracking
    usage: Dict[str, Any] = Field(
        default_factory=dict, description="Current usage statistics"
    )

    # Payment integration
    stripe_customer_id: Optional[str] = Field(None, description="Stripe customer ID")
    stripe_subscription_id: Optional[str] = Field(
        None, description="Stripe subscription ID"
    )
    stripe_status: Optional[str] = Field(
        None, description="Raw Stripe subscription status"
    )
    stripe_checkout_session_id: Optional[str] = Field(
        None, description="Stripe checkout session ID"
    )
    payment_status: Optional[str] = Field(
        None, description="Payment status from Stripe (paid, unpaid, past_due)"
    )
    expired_reason: Optional[str] = Field(
        None, description="Reason for expiration (e.g., checkout_session_expired)"
    )
    trial_will_end_notified_at: Optional[datetime] = Field(
        None, description="When trial ending notification was sent"
    )

    # ── Optimistic locking & state history (P0-11 / P0-12) ────────
    # Per "Building Reliable Stripe Subscriptions" (DEV Community, 2025):
    # include `version` in update filters to prevent race conditions when
    # concurrent webhooks target the same subscription.
    # Ref: https://dev.to/aniefon_umanah_ac5f21311c/building-reliable-stripe-subscriptions-in-nestjs-webhook-idempotency-and-optimistic-locking-3o91
    version: int = Field(
        default=1,
        description="Optimistic lock version — increment on every write, include in update filter",
    )
    state_history: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Append-only log of state transitions [{from, to, trigger, at, metadata}]. "
        "IMPORTANT: When appending via $push, use $slice: -100 to cap at 100 entries "
        "and prevent unbounded document growth.",
    )

    # System fields
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = Field(
        ..., description="ROOT_ADMIN email who created this subscription"
    )

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
                "version": 3,
                "state_history": [
                    {
                        "from": "trial",
                        "to": "active",
                        "trigger": "checkout.session.completed",
                        "at": "2025-08-15T10:30:00Z",
                    }
                ],
                "usage": {
                    "weddings_count": 2,
                    "ai_credits_used_month": 45,
                    "storage_used_gb": 2.3,
                    "staff_seats_used": 1,
                },
                "created_by": "thedeveloper@thespecialwedding.io",
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
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

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
                "credits_reset_date": "2025-09-01T00:00:00Z",
            }
        }


# Request/Response models for API
class CreateSubscriptionPlanRequest(BaseModel):
    """Request model for creating subscription plans"""

    name: str
    description: Optional[str] = None
    price_monthly: float
    price_yearly: Optional[float] = None
    is_metered: bool = True
    meter_event_name: Optional[str] = CANONICAL_PUBLIC_PLAN_METER_EVENT_NAME
    meter_id: Optional[str] = None
    max_weddings: int = 1
    max_guests_per_wedding: int = 100
    ai_credits_monthly: int = 10
    storage_gb: int = 1
    staff_seats: int = 0
    features: Dict[str, bool] = Field(default_factory=dict)
    features_list: Optional[List[str]] = None
    is_featured: bool = False
    sort_order: int = 0
    display_order: Optional[int] = None
    trial_days: int = Field(default=0, ge=0, description="Trial days (0 = no trial)")


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
    features_list: Optional[List[str]] = None
    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None
    sort_order: Optional[int] = None
    display_order: Optional[int] = None
    trial_days: Optional[int] = Field(
        default=None, ge=0, description="Trial days (0 = no trial)"
    )


class AssignSubscriptionRequest(BaseModel):
    """Request model for assigning subscription to user"""

    plan_id: str
    billing_interval: BillingInterval = BillingInterval.MONTHLY
    trial_days: int = Field(default=0, ge=0, description="Trial days (0 = no trial)")
