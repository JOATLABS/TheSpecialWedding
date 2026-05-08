"""
Planner Activity Notifications API

Endpoints for planner-specific activity notifications (RSVPs, forms, payments).
These are SEPARATE from platform notifications sent by root admin.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.dependencies.auth_extended import ExtendedAuthUser, require_admin_or_planner
from app.services.planner_notification_service import planner_notification_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/planner/activity-notifications", tags=["Planner Notifications"])
async def get_planner_activity_notifications(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=50, description="Items per page"),
    unread_only: bool = Query(False, description="Show only unread notifications"),
    wedding_id: Optional[str] = Query(None, description="Filter by wedding ID"),
    notification_type: Optional[str] = Query(None, description="Filter by type"),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """
    Get activity notifications for the current planner.

    Returns notifications for:
    - Form submissions
    - RSVP updates
    - Guest messages
    - Payment events
    - Contract signatures
    - Vendor responses
    """
    return await planner_notification_service.get_notifications(
        planner_id=current_user.email,
        page=page,
        limit=limit,
        unread_only=unread_only,
        wedding_id=wedding_id,
        notification_type=notification_type,
    )


@router.get("/planner/activity-notifications/count", tags=["Planner Notifications"])
async def get_planner_activity_notification_count(
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """Get activity notification counts for the current planner"""
    return await planner_notification_service.get_notification_count(
        planner_id=current_user.email
    )


@router.put(
    "/planner/activity-notifications/{notification_id}/read",
    tags=["Planner Notifications"],
)
async def mark_activity_notification_read(
    notification_id: str,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """Mark an activity notification as read"""
    return await planner_notification_service.mark_as_read(
        notification_id=notification_id, planner_id=current_user.email
    )


@router.put(
    "/planner/activity-notifications/{notification_id}/actioned",
    tags=["Planner Notifications"],
)
async def mark_activity_notification_actioned(
    notification_id: str,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """Mark an activity notification as actioned via its action button.

    Distinct from /read: read tracks visibility on the bell, actioned
    tracks whether the toast's CTA (e.g. "Send checklist") was actually
    invoked. The Stage 2 toast handler POSTs here once its outbound
    request succeeds so the bell stops re-prompting.
    """
    return await planner_notification_service.mark_action_completed(
        notification_id=notification_id, planner_id=current_user.email
    )


@router.put("/planner/activity-notifications/read-all", tags=["Planner Notifications"])
async def mark_all_activity_notifications_read(
    wedding_id: Optional[str] = Query(None, description="Filter by wedding ID"),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """Mark all activity notifications as read for the current planner"""
    return await planner_notification_service.mark_all_as_read(
        planner_id=current_user.email, wedding_id=wedding_id
    )


@router.delete(
    "/planner/activity-notifications/{notification_id}", tags=["Planner Notifications"]
)
async def delete_activity_notification(
    notification_id: str,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """Delete an activity notification"""
    return await planner_notification_service.delete_notification(
        notification_id=notification_id, planner_id=current_user.email
    )


# ==================== PUSH NOTIFICATIONS (WEB PUSH) ====================
# Note: Main Web Push endpoints are in /admin/web-push/*
# These are convenience aliases for the planner notification context


@router.get("/planner/push-status", tags=["Planner Notifications"])
async def get_push_status(
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """
    Get push notification status for the current planner.

    Returns whether Web Push is enabled on the server and if the user has subscribed.
    Use /admin/web-push/subscribe to enable browser push notifications.
    """
    from app.services.web_push_service import web_push_service

    is_subscribed = await web_push_service.check_user_subscribed(current_user.email)

    return {
        "enabled": web_push_service.enabled,
        "subscribed": is_subscribed,
        "message": (
            "Push notifications active"
            if is_subscribed
            else (
                "Not subscribed - enable in Account Settings"
                if web_push_service.enabled
                else "Push notifications not configured on server"
            )
        ),
    }


@router.post("/planner/push-test", tags=["Planner Notifications"])
async def send_test_push_notification(
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """
    Send a test push notification to verify your subscription is working.

    Make sure you've enabled push notifications in Account Settings first.
    """
    from app.services.web_push_service import web_push_service

    if not web_push_service.enabled:
        return {
            "success": False,
            "message": "Push notifications are not configured on this server",
        }

    result = await web_push_service.send_notification(
        user_id=current_user.email,
        title="Test Notification",
        body="Push notifications are working!",
        url="/admin/planner",
        tag="test-notification",
    )

    return {
        "success": result.get("success", False),
        "message": (
            f"Test notification sent to {result.get('sent', 0)} device(s)!"
            if result.get("success")
            else result.get("error", "No active subscriptions found")
        ),
    }
