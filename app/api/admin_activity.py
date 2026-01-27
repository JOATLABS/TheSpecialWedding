"""
Admin Activity Log API Endpoints

Provides endpoints for root admins to view their activity history.
"""

from fastapi import APIRouter, Depends, Query
from typing import Optional
from app.dependencies.auth_extended import require_root_admin, ExtendedAuthUser
from app.services.admin_activity_service import admin_activity_service

router = APIRouter(tags=["ROOT_ADMIN"])


@router.get("/activity-log")
async def get_activity_log(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    action_type: Optional[str] = None,
    entity_type: Optional[str] = None,
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """
    Get paginated admin activity log - ROOT_ADMIN only

    Args:
        page: Page number (default 1)
        limit: Items per page (default 50, max 100)
        action_type: Filter by action type (invitation_sent, planner_suspended, etc.)
        entity_type: Filter by entity type (invitation, planner, subscription)
    """
    return await admin_activity_service.get_activity_log(
        page=page,
        limit=limit,
        action_type=action_type,
        entity_type=entity_type
    )


@router.get("/activity-log/recent")
async def get_recent_activities(
    limit: int = Query(10, ge=1, le=50),
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """
    Get most recent admin activities for dashboard display - ROOT_ADMIN only

    Args:
        limit: Maximum number of activities to return (default 10, max 50)
    """
    activities = await admin_activity_service.get_recent_activities(limit=limit)
    return {"activities": activities}
