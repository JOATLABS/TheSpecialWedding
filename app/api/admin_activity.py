"""
Admin Activity Log API Endpoints

Provides endpoints for root admins to view their activity history.
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional, Dict, Any
from datetime import datetime, timedelta, timezone
from app.dependencies.auth_extended import require_root_admin, ExtendedAuthUser
from app.services.admin_activity_service import admin_activity_service
from app.utils.response import dict_response
from app.utils.query_validation import (
    validated_page,
    validated_limit_extended,
    validated_string_filter,
    validated_enum_filter
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ROOT_ADMIN"])


@router.get("/activity-log")
async def get_activity_log(
    page: int = Query(1, ge=1, le=10000, description="Page number"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    action_type: Optional[str] = Query(None, description="Filter by action type (invitation_sent, planner_suspended, etc.)"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type (invitation, planner, subscription)"),
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
    try:
        # Validate filter parameters
        action_type = validated_string_filter(action_type, max_length=50)
        entity_type = validated_string_filter(entity_type, max_length=50)

        return await admin_activity_service.get_activity_log(
            page=page,
            limit=limit,
            action_type=action_type,
            entity_type=entity_type
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get activity log: {str(e)}", exc_info=True)
        return dict_response(
            data={"activities": []},
            meta={
                "total": 0,
                "page": page,
                "pages": 0
            },
            message="Failed to load activity log"
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
    try:
        activities = await admin_activity_service.get_recent_activities(limit=limit)
        return dict_response(data={"activities": activities})
    except Exception as e:
        logger.error(f"Failed to get recent activities: {str(e)}", exc_info=True)
        return dict_response(data={"activities": []}, message="Failed to load recent activities")


@router.delete("/activity-log/cleanup")
async def cleanup_old_activities(
    days: int = Query(90, ge=7, le=365, description="Delete activities older than this many days"),
    current_user: ExtendedAuthUser = Depends(require_root_admin)
) -> Dict[str, Any]:
    """
    Clean up old admin activity log entries - ROOT_ADMIN only

    This endpoint manually deletes activity log entries older than the specified
    number of days. Note that TTL indexes also provide automatic cleanup.

    Args:
        days: Delete activities older than this many days (default 90, min 7, max 365)
    """
    try:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        result = await admin_activity_service.collection.delete_many({
            "created_at": {"$lt": cutoff_date}
        })

        logger.info(
            f"Admin activity cleanup by {current_user.email}: "
            f"deleted {result.deleted_count} entries older than {days} days"
        )

        return dict_response(
            data={
                "deleted_count": result.deleted_count,
                "cutoff_date": cutoff_date.isoformat() + "Z",
            },
            meta={"days": days},
            message="Activity log cleanup completed"
        )
    except Exception as e:
        logger.error(f"Failed to cleanup activity log: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to cleanup activity log: {str(e)}"
        )


@router.get("/activity-log/export")
async def export_activity_log(
    format: str = Query("json", description="Export format: json or csv"),
    action_type: Optional[str] = Query(None, description="Filter by action type"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    days: int = Query(90, ge=1, le=365, description="Export activities from the last N days"),
    current_user: ExtendedAuthUser = Depends(require_root_admin)
) -> Dict[str, Any]:
    """
    Export admin activity log for audit compliance - ROOT_ADMIN only

    Args:
        format: Export format (json or csv)
        action_type: Filter by action type
        entity_type: Filter by entity type
        days: Export activities from the last N days (default 90)
    """
    try:
        # Validate format parameter
        format = validated_enum_filter(format, ["json", "csv"]) or "json"

        # Validate filter parameters
        action_type = validated_string_filter(action_type, max_length=50)
        entity_type = validated_string_filter(entity_type, max_length=50)

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        query: Dict[str, Any] = {"created_at": {"$gte": cutoff_date}}

        if action_type:
            query["action_type"] = action_type

        if entity_type:
            query["entity_type"] = entity_type

        cursor = admin_activity_service.collection.find(query).sort("created_at", -1)
        activities = []

        async for doc in cursor:
            doc_id = doc.get("_id", "")
            created_at = doc.get("created_at")
            activities.append({
                "id": str(doc_id) if doc_id else "",
                "admin_id": doc.get("admin_id", ""),
                "action_type": doc.get("action_type", "unknown"),
                "title": doc.get("title", ""),
                "message": doc.get("message", ""),
                "entity_type": doc.get("entity_type"),
                "entity_id": doc.get("entity_id"),
                "metadata": doc.get("metadata", {}),
                "is_read": doc.get("is_read", False),
                "created_at": created_at.isoformat() if created_at else None
            })

        if format == "csv":
            # Generate CSV content
            import csv
            import io
            output = io.StringIO()
            if activities:
                fieldnames = ["id", "admin_id", "action_type", "title", "message",
                              "entity_type", "entity_id", "is_read", "created_at"]
                writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(activities)

            return {
                "format": "csv",
                "content": output.getvalue(),
                "count": len(activities),
                "exported_at": datetime.now(timezone.utc).isoformat() + "Z",
                "filters": {
                    "days": days,
                    "action_type": action_type,
                    "entity_type": entity_type
                }
            }
        else:
            return {
                "format": "json",
                "activities": activities,
                "count": len(activities),
                "exported_at": datetime.now(timezone.utc).isoformat() + "Z",
                "filters": {
                    "days": days,
                    "action_type": action_type,
                    "entity_type": entity_type
                }
            }
    except Exception as e:
        logger.error(f"Failed to export activity log: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to export activity log: {str(e)}"
        )
