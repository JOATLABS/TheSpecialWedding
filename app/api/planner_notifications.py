"""
Planner Activity Notifications API

Endpoints for planner-specific activity notifications (RSVPs, forms, payments).
These are SEPARATE from platform notifications sent by root admin.
"""

from fastapi import APIRouter, Depends, Query
from typing import Optional
from app.dependencies.auth_extended import require_admin_or_planner, ExtendedAuthUser
from app.services.planner_notification_service import planner_notification_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/planner/activity-notifications", tags=["Planner Notifications"])
async def get_planner_activity_notifications(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=50, description="Items per page"),
    unread_only: bool = Query(False, description="Show only unread notifications"),
    wedding_id: Optional[str] = Query(None, description="Filter by wedding ID"),
    notification_type: Optional[str] = Query(None, description="Filter by type"),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
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
        notification_type=notification_type
    )


@router.get("/planner/activity-notifications/count", tags=["Planner Notifications"])
async def get_planner_activity_notification_count(
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Get activity notification counts for the current planner"""
    return await planner_notification_service.get_notification_count(
        planner_id=current_user.email
    )


@router.put("/planner/activity-notifications/{notification_id}/read", tags=["Planner Notifications"])
async def mark_activity_notification_read(
    notification_id: str,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Mark an activity notification as read"""
    return await planner_notification_service.mark_as_read(
        notification_id=notification_id,
        planner_id=current_user.email
    )


@router.put("/planner/activity-notifications/read-all", tags=["Planner Notifications"])
async def mark_all_activity_notifications_read(
    wedding_id: Optional[str] = Query(None, description="Filter by wedding ID"),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Mark all activity notifications as read for the current planner"""
    return await planner_notification_service.mark_all_as_read(
        planner_id=current_user.email,
        wedding_id=wedding_id
    )


@router.delete("/planner/activity-notifications/{notification_id}", tags=["Planner Notifications"])
async def delete_activity_notification(
    notification_id: str,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Delete an activity notification"""
    return await planner_notification_service.delete_notification(
        notification_id=notification_id,
        planner_id=current_user.email
    )