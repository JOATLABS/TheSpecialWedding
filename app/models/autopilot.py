"""
Wedding Finance Autopilot Models

Data models for Package, Contract, and ScheduledPayment entities.
These models power the Package → Contract → Autopilot payment flow.
"""
from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_serializer
from app.models.base import MongoModel
from app.utils.pydantic_objectid import PyObjectId, generate_object_id


# ============================================================================
# PACKAGE MODELS (WFA-101)
# ============================================================================

class PackageServiceItem(BaseModel):
    """A service included in a package."""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    included: bool = True


class ScheduleItem(BaseModel):
    """A single payment in the schedule."""
    name: str = Field(..., min_length=1, max_length=100)
    trigger: Literal["on_signing", "days_after_signing", "days_before_wedding", "fixed_date"]

    # Trigger-specific fields
    days_after: Optional[int] = Field(None, ge=0)
    days_before: Optional[int] = Field(None, ge=0)
    fixed_date: Optional[date] = None

    # Amount (one of these should be set)
    amount: Optional[float] = Field(None, ge=0)
    percentage: Optional[float] = Field(None, ge=0, le=100)

    @field_serializer('amount', when_used='json')
    def serialize_amount(self, value) -> Optional[float]:
        return float(value) if value is not None else None

    @field_serializer('fixed_date', when_used='json')
    def serialize_fixed_date(self, value) -> Optional[str]:
        return value.isoformat() if value else None


class WeddingPackage(MongoModel):
    """
    A reusable service package template.

    Packages define what services are offered and how payment is structured.
    They can be saved as templates and reused for multiple couples.
    """
    id: PyObjectId = Field(default_factory=generate_object_id, alias="_id")
    planner_id: str = Field(..., description="Planner's user ID")

    # Package details
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    services: List[PackageServiceItem] = Field(default_factory=list)

    # Pricing (stored as float for MongoDB BSON compatibility)
    total_amount: float = Field(..., ge=0)
    currency: str = Field(default="usd", pattern="^[a-z]{3}$")

    # Payment schedule
    payment_schedule: List[ScheduleItem] = Field(default_factory=list)

    # Terms
    cancellation_policy: str = Field(default="")
    late_payment_policy: Optional[str] = None
    custom_terms: Optional[str] = None

    # Meta
    is_template: bool = False
    status: Literal["draft", "active", "archived"] = "draft"

    # Usage stats
    contracts_count: int = Field(default=0, ge=0)

    @field_serializer('total_amount', when_used='always')
    def serialize_total_amount(self, value) -> float:
        return float(value) if value else 0.0


# ============================================================================
# CONTRACT MODELS (WFA-102)
# ============================================================================

class CoupleInfo(BaseModel):
    """Couple contact information."""
    partner1_name: str = Field(..., min_length=1, max_length=100)
    partner2_name: Optional[str] = Field(None, max_length=100)
    email: str = Field(..., max_length=254)
    phone: Optional[str] = Field(None, max_length=20)

    @property
    def display_name(self) -> str:
        """Get display name for the couple."""
        if self.partner2_name:
            return f"{self.partner1_name} & {self.partner2_name}"
        return self.partner1_name


class ContractSignature(BaseModel):
    """Digital signature record."""
    signed_by: str = Field(..., min_length=1, max_length=200)
    signed_at: datetime = Field(default_factory=datetime.utcnow)
    ip_address: str = Field(..., max_length=45)
    user_agent: str = Field(..., max_length=500)

    @field_serializer('signed_at', when_used='json')
    def serialize_signed_at(self, value) -> Optional[str]:
        return value.isoformat() if value else None


class Contract(MongoModel):
    """
    A signed agreement between planner and couple.

    Contracts are created from packages and track the signing process,
    payment method, and scheduled payments.
    """
    id: PyObjectId = Field(default_factory=generate_object_id, alias="_id")
    package_id: str = Field(..., description="Source package ID")
    planner_id: str = Field(..., description="Planner's user ID")
    wedding_id: Optional[str] = Field(None, description="Linked wedding ID")

    # Access token for public contract viewing
    token: str = Field(..., min_length=32, max_length=64)

    # TODO - Making sure to remember that the Couple are not the platform users but the customer of the planners)
    couple: CoupleInfo
    wedding_date: Optional[date] = None
    venue: Optional[str] = Field(None, max_length=200)
    planner_name: Optional[str] = Field(None, max_length=200)
    planner_email: Optional[str] = Field(None, max_length=254)
    planner_phone: Optional[str] = Field(None, max_length=50)
    planner_logo: Optional[str] = None

    # Package snapshot (in case package is updated later)
    package_snapshot: dict = Field(default_factory=dict)

    # Signature
    signature: Optional[ContractSignature] = None

    # Payment (Stripe)
    stripe_customer_id: Optional[str] = None
    stripe_payment_method_id: Optional[str] = None
    payment_method_last4: Optional[str] = Field(None, max_length=4)
    payment_method_brand: Optional[str] = Field(None, max_length=20)

    # Document
    document_url: Optional[str] = None

    # Status
    status: Literal["draft", "sent", "viewed", "signed", "active", "completed", "cancelled"] = "draft"

    # Timestamps
    sent_at: Optional[datetime] = None
    viewed_at: Optional[datetime] = None
    signed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None

    @field_serializer('wedding_date', when_used='json')
    def serialize_wedding_date(self, value) -> Optional[str]:
        return value.isoformat() if value else None

    @field_serializer('sent_at', 'viewed_at', 'signed_at', 'completed_at', 'cancelled_at', when_used='json')
    def serialize_datetimes(self, value) -> Optional[str]:
        return value.isoformat() if value else None


# ============================================================================
# SCHEDULED PAYMENT MODELS (WFA-103)
# ============================================================================

class ScheduledPayment(MongoModel):
    """
    An individual scheduled payment instance.

    Created when a contract is signed. Each scheduled payment tracks
    its own status, retry attempts, and payment outcome.
    """
    id: PyObjectId = Field(default_factory=generate_object_id, alias="_id")
    contract_id: str = Field(..., description="Parent contract ID")
    planner_id: str = Field(..., description="Planner's user ID")

    # Payment details
    name: str = Field(..., min_length=1, max_length=100)
    amount: float = Field(..., ge=0)
    currency: str = Field(default="usd", pattern="^[a-z]{3}$")
    due_date: date

    # Execution status
    status: Literal["scheduled", "processing", "succeeded", "failed", "cancelled", "paid_externally"] = "scheduled"
    stripe_payment_intent_id: Optional[str] = None

    # Retry tracking
    attempt_count: int = Field(default=0, ge=0)
    last_attempt_at: Optional[datetime] = None
    next_retry_at: Optional[datetime] = None
    failure_reason: Optional[str] = None

    # Completion
    paid_at: Optional[datetime] = None
    receipt_url: Optional[str] = None

    # External payment
    paid_externally: bool = False
    external_payment_note: Optional[str] = None
    external_payment_method: Optional[str] = None  # cash, check, wire, etc.

    # Reminder tracking
    reminder_sent_at: Optional[datetime] = None

    @field_serializer('amount', when_used='json')
    def serialize_amount(self, value) -> float:
        return float(value) if value else 0.0

    @field_serializer('due_date', when_used='json')
    def serialize_due_date(self, value) -> Optional[str]:
        return value.isoformat() if value else None

    @field_serializer('last_attempt_at', 'next_retry_at', 'paid_at', 'reminder_sent_at', when_used='json')
    def serialize_datetimes(self, value) -> Optional[str]:
        return value.isoformat() if value else None


# ============================================================================
# AI MODELS (for WFA-201, WFA-202)
# ============================================================================

class AICache(BaseModel):
    """Cached AI response for deduplication and cost savings."""
    id: str = Field(..., alias="_id")  # ai:{feature}:{tenant_id}:{context_hash}
    feature: str = Field(..., description="AI feature name")
    tenant_id: str = Field(..., description="Wedding or Planner ID")
    context_hash: str = Field(..., description="Hash of input context")
    response: dict = Field(default_factory=dict)
    expires_at: datetime
    hit_count: int = Field(default=0, ge=0)

    @field_serializer('expires_at', when_used='json')
    def serialize_expires_at(self, value) -> Optional[str]:
        return value.isoformat() if value else None


class AIUsageLog(MongoModel):
    """AI usage audit log for tracking and billing."""
    id: PyObjectId = Field(default_factory=generate_object_id, alias="_id")
    user_id: str = Field(..., description="User who made the request")
    tenant_id: str = Field(..., description="Wedding or Planner ID")
    feature: str = Field(..., description="AI feature used")
    credits_used: int = Field(..., ge=0)
    latency_ms: float = Field(..., ge=0)
    status: Literal["success", "error", "cached"] = "success"
    error: Optional[str] = None

    # Request metadata
    request_hash: Optional[str] = None
    response_tokens: Optional[int] = None
