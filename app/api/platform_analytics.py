"""
Platform Analytics API Endpoints
Provides comprehensive analytics for ROOT_ADMIN users only
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from app.dependencies.auth_extended import get_current_user_extended, ExtendedAuthUser
from app.services.platform_analytics_service import PlatformAnalyticsService
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter()
analytics_service = PlatformAnalyticsService()

@router.get("/saas/analytics/overview", tags=["Platform Analytics"])
def get_platform_analytics_overview(
    timeframe: str = Query("30days", regex="^(7days|30days|90days|1year)$"),
    current_user: ExtendedAuthUser = Depends(get_current_user_extended)
):
    """
    Get comprehensive platform analytics overview
    ROOT_ADMIN access only
    """

    # Strict access control - ROOT_ADMIN only
    if not current_user.is_root_admin:
        logger.warning(
            f"Unauthorized platform analytics access attempt by {current_user.email} "
            f"with role {current_user.role}"
        )
        raise HTTPException(
            status_code=403,
            detail="Access denied. ROOT_ADMIN role required for platform analytics."
        )

    try:
        logger.info(f"Platform analytics accessed by {current_user.email} for timeframe: {timeframe}")

        # Get comprehensive metrics
        metrics = analytics_service.get_platform_overview(timeframe)

        return {
            "success": True,
            "data": metrics,
            "timeframe": timeframe
        }

    except Exception as e:
        logger.error(f"Error fetching platform analytics: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve platform analytics"
        )

@router.get("/saas/analytics/{metric_type}", tags=["Platform Analytics"])
def get_detailed_analytics(
    metric_type: str,
    timeframe: str = Query("30days", regex="^(7days|30days|90days|1year)$"),
    current_user: ExtendedAuthUser = Depends(get_current_user_extended)
):
    """
    Get detailed analytics for a specific metric type
    ROOT_ADMIN access only

    Metric types:
    - users: User growth and engagement
    - subscriptions: Subscription metrics and MRR
    - usage: Feature usage and adoption
    - performance: System performance metrics
    - revenue: Revenue breakdown and projections
    """

    # Strict access control - ROOT_ADMIN only
    if not current_user.is_root_admin:
        logger.warning(
            f"Unauthorized detailed analytics access attempt by {current_user.email} "
            f"for metric type: {metric_type}"
        )
        raise HTTPException(
            status_code=403,
            detail="Access denied. ROOT_ADMIN role required for platform analytics."
        )

    # Validate metric type
    valid_metric_types = ["users", "subscriptions", "usage", "performance", "revenue"]
    if metric_type not in valid_metric_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid metric type. Valid types: {', '.join(valid_metric_types)}"
        )

    try:
        logger.info(
            f"Detailed {metric_type} analytics accessed by {current_user.email} "
            f"for timeframe: {timeframe}"
        )

        # Get detailed metrics
        detailed_metrics = analytics_service.get_detailed_analytics(metric_type, timeframe)

        return {
            "success": True,
            "metric_type": metric_type,
            "data": detailed_metrics,
            "timeframe": timeframe
        }

    except Exception as e:
        logger.error(f"Error fetching detailed analytics for {metric_type}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve {metric_type} analytics"
        )

@router.post("/saas/analytics/refresh-cache", tags=["Platform Analytics"])
def refresh_analytics_cache(
    current_user: ExtendedAuthUser = Depends(get_current_user_extended)
):
    """
    Force refresh analytics cache
    ROOT_ADMIN access only
    """

    # Strict access control - ROOT_ADMIN only
    if not current_user.is_root_admin:
        logger.warning(
            f"Unauthorized cache refresh attempt by {current_user.email}"
        )
        raise HTTPException(
            status_code=403,
            detail="Access denied. ROOT_ADMIN role required."
        )

    try:
        # Clear cache by regenerating all metrics
        timeframes = ["7days", "30days", "90days", "1year"]

        for tf in timeframes:
            analytics_service.get_platform_overview(tf)

        logger.info(f"Analytics cache refreshed by {current_user.email}")

        return {
            "success": True,
            "message": "Analytics cache refreshed successfully",
            "refreshed_timeframes": timeframes
        }

    except Exception as e:
        logger.error(f"Error refreshing analytics cache: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to refresh analytics cache"
        )

@router.get("/saas/analytics/export", tags=["Platform Analytics"])
def export_analytics_data(
    format: str = Query("json", regex="^(json|csv)$"),
    timeframe: str = Query("30days", regex="^(7days|30days|90days|1year)$"),
    current_user: ExtendedAuthUser = Depends(get_current_user_extended)
):
    """
    Export analytics data in JSON or CSV format
    ROOT_ADMIN access only
    """

    # Strict access control - ROOT_ADMIN only
    if not current_user.is_root_admin:
        logger.warning(
            f"Unauthorized analytics export attempt by {current_user.email}"
        )
        raise HTTPException(
            status_code=403,
            detail="Access denied. ROOT_ADMIN role required."
        )

    try:
        # Get all analytics data
        metrics = analytics_service.get_platform_overview(timeframe)

        if format == "csv":
            # Convert to CSV format
            import csv
            import io

            output = io.StringIO()
            writer = csv.writer(output)

            # Write headers
            writer.writerow(["Metric", "Value", "Category"])

            # Users metrics
            for key, value in metrics["users"].items():
                if isinstance(value, dict):
                    for subkey, subvalue in value.items():
                        writer.writerow([f"users_{key}_{subkey}", subvalue, "Users"])
                else:
                    writer.writerow([f"users_{key}", value, "Users"])

            # Subscriptions metrics
            for key, value in metrics["subscriptions"].items():
                if isinstance(value, dict):
                    for subkey, subvalue in value.items():
                        writer.writerow([f"subscriptions_{key}_{subkey}", subvalue, "Subscriptions"])
                else:
                    writer.writerow([f"subscriptions_{key}", value, "Subscriptions"])

            # Usage metrics
            for key, value in metrics["usage"].items():
                if isinstance(value, dict):
                    for subkey, subvalue in value.items():
                        writer.writerow([f"usage_{key}_{subkey}", subvalue, "Usage"])
                else:
                    writer.writerow([f"usage_{key}", value, "Usage"])

            # Performance metrics
            for key, value in metrics["performance"].items():
                if not isinstance(value, (list, dict)):
                    writer.writerow([f"performance_{key}", value, "Performance"])

            # Revenue metrics
            for key, value in metrics["revenue"].items():
                if not isinstance(value, dict):
                    writer.writerow([f"revenue_{key}", value, "Revenue"])

            csv_content = output.getvalue()

            from fastapi.responses import Response
            return Response(
                content=csv_content,
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename=analytics_{timeframe}.csv"
                }
            )
        else:
            # Return JSON
            return metrics

    except Exception as e:
        logger.error(f"Error exporting analytics data: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to export analytics data"
        )