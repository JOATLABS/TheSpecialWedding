"""
Web Push API Endpoints

Handles browser push notification subscriptions and sending.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.dependencies.auth_extended import ExtendedAuthUser, require_admin_or_planner
from app.services.web_push_service import web_push_service

logger = logging.getLogger(__name__)

router = APIRouter()


class PushSubscriptionKeys(BaseModel):
    """VAPID keys from browser subscription"""

    p256dh: str
    auth: str


class PushSubscription(BaseModel):
    """Push subscription from browser's PushManager"""

    endpoint: str
    keys: PushSubscriptionKeys
    expirationTime: Optional[int] = None


class SubscribeRequest(BaseModel):
    """Wrapper for push subscription from frontend"""

    subscription: PushSubscription


class UnsubscribeRequest(BaseModel):
    """Request to unsubscribe from push notifications"""

    endpoint: str


class PushNotificationRequest(BaseModel):
    """Request to send a push notification"""

    title: str
    body: str
    url: Optional[str] = None
    tag: Optional[str] = None


@router.get("/web-push/vapid-public-key", tags=["Web Push"])
async def get_vapid_public_key():
    """
    Get the VAPID public key for subscribing to push notifications.
    This is called by the frontend to register with the push service.
    """
    public_key = web_push_service.get_public_key()

    if not public_key:
        raise HTTPException(
            status_code=503, detail="Push notifications not configured on this server"
        )

    return {"vapid_public_key": public_key}


@router.post("/web-push/subscribe", tags=["Web Push"])
async def subscribe_to_push(
    body: SubscribeRequest,
    request: Request,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """
    Subscribe to push notifications.

    Called by the frontend after the user grants notification permission
    and the browser creates a push subscription.
    """
    user_agent = request.headers.get("User-Agent")

    # Convert keys model to dict for storage
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


@router.delete("/web-push/unsubscribe", tags=["Web Push"])
async def unsubscribe_from_push(
    body: Optional[UnsubscribeRequest] = None,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """
    Unsubscribe from push notifications.
    If endpoint is provided, removes only that subscription.
    Otherwise removes all subscriptions for the current user.
    """
    if body and body.endpoint:
        # Remove specific subscription by endpoint
        success = await web_push_service.remove_subscription(
            body.endpoint,
            user_id=current_user.email,
        )
        return {
            "success": success,
            "message": "Subscription removed" if success else "Subscription not found",
        }
    else:
        # Remove all subscriptions for user
        count = await web_push_service.remove_user_subscriptions(current_user.email)
        return {"success": True, "message": f"Removed {count} subscription(s)"}


@router.get("/web-push/status", tags=["Web Push"])
async def get_push_status(
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """
    Check if the current user has push notifications enabled.
    """
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


@router.post("/web-push/test", tags=["Web Push"])
async def send_test_notification(
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """
    Send a test push notification to the current user.
    """
    if not web_push_service.enabled:
        raise HTTPException(status_code=503, detail="Push notifications not configured")

    result = await web_push_service.send_notification(
        user_id=current_user.email,
        title="Test Notification",
        body="Push notifications are working!",
        url="/admin/planner",
        tag="test-notification",
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=400, detail=result.get("error", "No active subscriptions found")
        )

    return {
        "success": True,
        "message": f"Test notification sent to {result.get('sent', 0)} device(s)",
    }
