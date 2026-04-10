"""
Vendor Signup API Router

Public endpoint for vendor self-registration + authenticated endpoints for
password change and profile management during onboarding.

Phase 10 of the Vendor Advertising Monetization Platform.

Routes:
    POST /api/v1/vendors/signup          — Public self-signup
    POST /api/v1/vendors/change-password — Vendor changes temp password (auth required)
    GET  /api/v1/vendors/profile         — Get own profile + completeness (auth required)
    PUT  /api/v1/vendors/profile         — Update own profile (auth required)
"""

import logging
import re
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from app.core.database import mongo
from app.dependencies.auth_extended import ExtendedAuthUser, get_current_user_extended
from app.services.vendor_signup_service import VendorSignupService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/vendors", tags=["Vendor Signup"])


# =============================================================================
# REQUEST MODELS
# =============================================================================


class VendorSignupRequest(BaseModel):
    """Public vendor signup form."""

    email: str = Field(..., min_length=5, max_length=254)
    business_name: str = Field(..., min_length=2, max_length=200)
    category: str = Field(default="", max_length=100)
    location: str = Field(default="", max_length=200)
    phone: str = Field(default="", max_length=20)
    website: str = Field(default="", max_length=300)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", v):
            raise ValueError("Invalid email address")
        return v


class ChangePasswordRequest(BaseModel):
    """Vendor changes temp password on first login."""

    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[!@#$%^&*()_+\-\[\]{}|;:,.<>?]", v):
            raise ValueError("Password must contain at least one special character")
        return v


class UpdateProfileRequest(BaseModel):
    """Vendor profile update."""

    business_name: Optional[str] = Field(None, min_length=2, max_length=200)
    vendor_category: Optional[str] = Field(None, max_length=100)
    vendor_location: Optional[str] = Field(None, max_length=200)
    vendor_phone: Optional[str] = Field(None, max_length=20)
    vendor_website: Optional[str] = Field(None, max_length=300)
    vendor_description: Optional[str] = Field(None, max_length=2000)
    logo_url: Optional[str] = Field(None, max_length=500)
    portfolio_urls: Optional[List[str]] = None


# =============================================================================
# DEPENDENCY INJECTION
# =============================================================================


async def get_vendor_signup_service() -> VendorSignupService:
    return VendorSignupService(mongo.db)


async def require_advertising_vendor(
    current_user: ExtendedAuthUser = Depends(get_current_user_extended),
) -> ExtendedAuthUser:
    """Require advertising_vendor role or root admin."""
    if current_user.is_root_admin or current_user.is_advertising_vendor:
        return current_user
    raise HTTPException(status_code=403, detail="Advertising vendor access required")


# =============================================================================
# ENDPOINTS
# =============================================================================


@router.post("/signup", status_code=201)
async def vendor_signup(
    data: VendorSignupRequest,
    service: VendorSignupService = Depends(get_vendor_signup_service),
):
    """
    Public vendor self-signup.

    Creates a vendor account in pending_approval status.
    If auto_approve_signups is enabled, approves immediately.
    """
    return await service.signup(data.model_dump())


@router.post("/change-password")
async def vendor_change_password(
    data: ChangePasswordRequest,
    service: VendorSignupService = Depends(get_vendor_signup_service),
    current_user: ExtendedAuthUser = Depends(require_advertising_vendor),
):
    """
    Vendor changes their temporary password on first login.

    Clears must_change_password flag and temp_password_expires_at.
    """
    return await service.change_temp_password(
        vendor_email=current_user.email,
        temp_password=data.current_password,
        new_password=data.new_password,
    )


@router.get("/profile")
async def get_vendor_profile(
    service: VendorSignupService = Depends(get_vendor_signup_service),
    current_user: ExtendedAuthUser = Depends(require_advertising_vendor),
):
    """Get vendor profile with completeness status."""
    return await service.get_vendor_profile(current_user.email)


@router.put("/profile")
async def update_vendor_profile(
    data: UpdateProfileRequest,
    service: VendorSignupService = Depends(get_vendor_signup_service),
    current_user: ExtendedAuthUser = Depends(require_advertising_vendor),
):
    """Update vendor profile fields."""
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    return await service.update_vendor_profile(current_user.email, updates)


# =============================================================================
# VENDOR WEB PUSH SUBSCRIPTION ENDPOINTS
# =============================================================================


class VendorPushSubscriptionKeys(BaseModel):
    """VAPID keys from browser push subscription."""

    p256dh: str
    auth: str


class VendorPushSubscription(BaseModel):
    """Push subscription from browser's PushManager."""

    endpoint: str
    keys: VendorPushSubscriptionKeys
    expirationTime: Optional[int] = None


class VendorSubscribeRequest(BaseModel):
    """Wrapper for push subscription from vendor frontend."""

    subscription: VendorPushSubscription


class VendorUnsubscribeRequest(BaseModel):
    """Request to unsubscribe from push notifications."""

    endpoint: str = ""


@router.get("/web-push/vapid-public-key")
async def vendor_get_vapid_public_key():
    """Get the VAPID public key for vendor push subscription."""
    from app.services.web_push_service import web_push_service

    public_key = web_push_service.get_public_key()
    if not public_key:
        raise HTTPException(
            status_code=503,
            detail="Push notifications not configured on this server",
        )
    return {"vapid_public_key": public_key}


@router.post("/web-push/subscribe")
async def vendor_subscribe_to_push(
    body: VendorSubscribeRequest,
    request: Request,
    current_user: ExtendedAuthUser = Depends(require_advertising_vendor),
):
    """Subscribe vendor to push notifications."""
    from app.services.web_push_service import web_push_service

    user_agent = request.headers.get("User-Agent")

    subscription_data = {
        "endpoint": body.subscription.endpoint,
        "keys": body.subscription.keys.model_dump(),
        "expirationTime": body.subscription.expirationTime,
    }

    success = await web_push_service.save_subscription(
        user_id=current_user.email,
        subscription=subscription_data,
        user_agent=user_agent,
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to save subscription")

    return {"success": True, "message": "Subscribed to push notifications"}


@router.delete("/web-push/unsubscribe")
async def vendor_unsubscribe_from_push(
    body: Optional[VendorUnsubscribeRequest] = None,
    current_user: ExtendedAuthUser = Depends(require_advertising_vendor),
):
    """Unsubscribe vendor from push notifications."""
    from app.services.web_push_service import web_push_service

    if body and body.endpoint:
        success = await web_push_service.remove_subscription(
            body.endpoint,
            user_id=current_user.email,
        )
        return {
            "success": success,
            "message": "Subscription removed" if success else "Subscription not found",
        }
    else:
        count = await web_push_service.remove_user_subscriptions(current_user.email)
        return {"success": True, "message": f"Removed {count} subscription(s)"}


@router.get("/web-push/status")
async def vendor_get_push_status(
    current_user: ExtendedAuthUser = Depends(require_advertising_vendor),
):
    """Check if the current vendor has push notifications enabled."""
    from app.services.web_push_service import web_push_service

    is_subscribed = await web_push_service.check_user_subscribed(current_user.email)
    is_enabled = web_push_service.enabled

    return {
        "enabled": is_enabled,
        "subscribed": is_subscribed,
        "message": (
            "Push notifications are active"
            if is_subscribed
            else (
                "Not subscribed to push notifications"
                if is_enabled
                else "Push notifications not configured on server"
            )
        ),
    }


@router.post("/web-push/test")
async def vendor_send_test_notification(
    current_user: ExtendedAuthUser = Depends(require_advertising_vendor),
):
    """Send a test push notification to the current vendor."""
    from app.services.web_push_service import web_push_service

    if not web_push_service.enabled:
        raise HTTPException(status_code=503, detail="Push notifications not configured")

    result = await web_push_service.send_notification(
        user_id=current_user.email,
        title="Test Notification",
        body="Push notifications are working!",
        url="/portal/ads",
        tag="test-notification",
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=result.get("error", "No active subscriptions found"),
        )

    return {
        "success": True,
        "message": f"Test notification sent to {result.get('sent', 0)} device(s)",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Vendor In-Portal Notifications
# Vendors use the shared /admin/user/notifications/* endpoints from
# notification_management.py. The require_admin_or_planner dependency now
# includes advertising_vendor, so no duplicate endpoints are needed here.
# ═══════════════════════════════════════════════════════════════════════════════
