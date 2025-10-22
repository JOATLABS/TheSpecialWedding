"""
ROOT_ADMIN Platform Metrics API

Zero-cost monitoring solution using MongoDB and existing infrastructure.
Provides comprehensive metrics for the ROOT_ADMIN dashboard.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from app.dependencies.auth_extended import require_root_admin, ExtendedAuthUser
from app.core.database_async import async_mongo
from bson import ObjectId
import logging

# Try to import psutil for system metrics (install if not present: pip install psutil)
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logging.warning("psutil not installed. System metrics will be unavailable. Install with: pip install psutil")

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/platform", tags=["ROOT_ADMIN", "Monitoring"])


@router.get("/metrics")
async def get_platform_metrics(
    current_user: ExtendedAuthUser = Depends(require_root_admin)
) -> Dict[str, Any]:
    """
    Get comprehensive platform metrics for ROOT_ADMIN dashboard

    Returns:
        - System health (database, disk, memory, CPU)
        - Error statistics (24h)
        - Business metrics (users, subscriptions, MRR/ARR)
        - Performance metrics (slow endpoints)
    """
    now = datetime.utcnow()
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)

    try:
        # ==================== SYSTEM HEALTH ====================

        # Database health check
        try:
            db_start = datetime.utcnow()
            await async_mongo.db.command('ping')
            db_latency = (datetime.utcnow() - db_start).total_seconds() * 1000
            db_status = "healthy" if db_latency < 100 else "degraded"
        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
            db_status = "down"
            db_latency = 9999

        # System resources (if psutil available)
        system_metrics = {}
        if PSUTIL_AVAILABLE:
            try:
                disk = psutil.disk_usage('/')
                memory = psutil.virtual_memory()
                cpu = psutil.cpu_percent(interval=0.5)

                system_metrics = {
                    "disk_usage_percent": round(disk.percent, 1),
                    "disk_free_gb": round(disk.free / (1024**3), 2),
                    "memory_usage_percent": round(memory.percent, 1),
                    "memory_available_gb": round(memory.available / (1024**3), 2),
                    "cpu_usage_percent": round(cpu, 1)
                }
            except Exception as e:
                logger.error(f"Failed to get system metrics: {str(e)}")
                system_metrics = {
                    "disk_usage_percent": 0,
                    "memory_usage_percent": 0,
                    "cpu_usage_percent": 0,
                    "error": "Unable to fetch system metrics"
                }
        else:
            system_metrics = {
                "error": "psutil not installed"
            }

        # ==================== ERROR MONITORING ====================

        # Get errors from audit_logs (existing collection)
        error_pipeline = [
            {
                "$match": {
                    "timestamp": {"$gte": day_ago},
                    "status_code": {"$gte": 400}
                }
            },
            {
                "$facet": {
                    "total": [{"$count": "count"}],
                    "critical": [
                        {"$match": {"status_code": {"$gte": 500}}},
                        {"$count": "count"}
                    ],
                    "by_endpoint": [
                        {"$group": {"_id": "$path", "count": {"$sum": 1}}},
                        {"$sort": {"count": -1}},
                        {"$limit": 5}
                    ]
                }
            }
        ]

        error_stats_cursor = async_mongo.db["audit_logs"].aggregate(error_pipeline)
        error_stats_list = await error_stats_cursor.to_list(length=1)
        error_stats = error_stats_list[0] if error_stats_list else {}

        total_errors = error_stats.get("total", [{}])[0].get("count", 0)
        critical_errors = error_stats.get("critical", [{}])[0].get("count", 0)
        top_error_endpoints = error_stats.get("by_endpoint", [])

        # Get recent errors for display
        recent_errors_cursor = async_mongo.db["audit_logs"].find({
            "status_code": {"$gte": 400}
        }).sort("timestamp", -1).limit(10)
        recent_errors = await recent_errors_cursor.to_list(length=10)

        # Convert ObjectId to string for JSON serialization
        for error in recent_errors:
            if "_id" in error:
                error["_id"] = str(error["_id"])

        # Check if errors collection exists (self-hosted error tracking)
        self_hosted_errors = 0
        try:
            self_hosted_errors = await async_mongo.db["errors"].count_documents({
                "timestamp": {"$gte": day_ago},
                "acknowledged": False
            })
        except Exception:
            # Collection might not exist yet
            pass

        # ==================== BUSINESS METRICS ====================

        # User statistics
        total_users = await async_mongo.db["users"].count_documents({})
        active_users_week = await async_mongo.db["users"].count_documents({
            "last_login": {"$gte": week_ago}
        })
        new_users_week = await async_mongo.db["users"].count_documents({
            "created_at": {"$gte": week_ago}
        })

        # Subscription statistics
        subscription_pipeline = [
            {
                "$facet": {
                    "active": [
                        {"$match": {"status": "active"}},
                        {"$count": "count"}
                    ],
                    "trialing": [
                        {"$match": {"status": "trialing"}},
                        {"$count": "count"}
                    ],
                    "canceled": [
                        {"$match": {"status": "canceled"}},
                        {"$count": "count"}
                    ],
                    "by_plan": [
                        {"$match": {"status": "active"}},
                        {"$group": {"_id": "$plan_id", "count": {"$sum": 1}}},
                        {"$sort": {"count": -1}}
                    ]
                }
            }
        ]

        sub_cursor = async_mongo.db["subscriptions"].aggregate(subscription_pipeline)
        sub_stats_list = await sub_cursor.to_list(length=1)
        sub_stats = sub_stats_list[0] if sub_stats_list else {}

        active_subscriptions = sub_stats.get("active", [{}])[0].get("count", 0)
        trial_subscriptions = sub_stats.get("trialing", [{}])[0].get("count", 0)
        canceled_subscriptions = sub_stats.get("canceled", [{}])[0].get("count", 0)

        # Calculate MRR/ARR
        # Get all active subscriptions with amounts
        active_subs_cursor = async_mongo.db["subscriptions"].find({
            "status": "active"
        })
        active_subs = await active_subs_cursor.to_list(length=None)

        mrr = 0
        for sub in active_subs:
            amount = sub.get("amount", 0)
            interval = sub.get("billing_interval", "monthly")

            if interval == "monthly":
                mrr += amount
            elif interval == "yearly":
                mrr += amount / 12  # Convert yearly to monthly

        arr = mrr * 12

        # Trial conversion rate
        total_trials = await async_mongo.db["subscriptions"].count_documents({
            "trial_end": {"$exists": True}
        })
        converted_trials = await async_mongo.db["subscriptions"].count_documents({
            "trial_end": {"$exists": True},
            "status": "active"
        })
        conversion_rate = (converted_trials / total_trials * 100) if total_trials > 0 else 0

        # ==================== PERFORMANCE METRICS ====================

        # Get slow requests from audit_logs
        slow_endpoint_pipeline = [
            {
                "$match": {
                    "timestamp": {"$gte": day_ago},
                    "response_time_ms": {"$exists": True, "$gte": 1000}  # >1 second
                }
            },
            {
                "$group": {
                    "_id": "$path",
                    "avg_response_time": {"$avg": "$response_time_ms"},
                    "max_response_time": {"$max": "$response_time_ms"},
                    "request_count": {"$sum": 1}
                }
            },
            {
                "$sort": {"avg_response_time": -1}
            },
            {
                "$limit": 10
            }
        ]

        slow_cursor = async_mongo.db["audit_logs"].aggregate(slow_endpoint_pipeline)
        slow_endpoints = await slow_cursor.to_list(length=10)

        # Format slow endpoints
        for endpoint in slow_endpoints:
            endpoint["avg_response_time"] = round(endpoint["avg_response_time"] / 1000, 3)  # Convert to seconds
            endpoint["max_response_time"] = round(endpoint["max_response_time"] / 1000, 3)
            endpoint["endpoint"] = endpoint.pop("_id")

        # ==================== WEDDING METRICS ====================

        total_weddings = await async_mongo.db["weddings"].count_documents({})
        active_weddings = await async_mongo.db["weddings"].count_documents({
            "status": {"$ne": "archived"}
        })

        # ==================== COMPILE RESPONSE ====================

        return {
            "health": {
                "database": db_status,
                "db_latency_ms": round(db_latency, 2),
                **system_metrics
            },
            "errors": {
                "total_24h": total_errors,
                "critical_24h": critical_errors,
                "unacknowledged": self_hosted_errors,
                "error_rate_per_hour": round(total_errors / 24, 2),
                "top_error_endpoints": top_error_endpoints,
                "recent_errors": recent_errors
            },
            "business": {
                "total_users": total_users,
                "active_users_week": active_users_week,
                "new_users_week": new_users_week,
                "active_subscriptions": active_subscriptions,
                "trial_subscriptions": trial_subscriptions,
                "canceled_subscriptions": canceled_subscriptions,
                "conversion_rate": round(conversion_rate, 2),
                "mrr": round(mrr, 2),
                "arr": round(arr, 2),
                "total_weddings": total_weddings,
                "active_weddings": active_weddings
            },
            "performance": {
                "slow_endpoints": slow_endpoints
            },
            "timestamp": now.isoformat()
        }

    except Exception as e:
        logger.error(f"Failed to get platform metrics: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch metrics: {str(e)}")


@router.get("/metrics/history")
async def get_metrics_history(
    days: int = Query(7, ge=1, le=90, description="Number of days of history"),
    current_user: ExtendedAuthUser = Depends(require_root_admin)
) -> Dict[str, Any]:
    """
    Get historical metrics for charts/trends

    Args:
        days: Number of days to retrieve (1-90)
    """
    start_date = datetime.utcnow() - timedelta(days=days)

    # Get stored metrics snapshots
    cursor = async_mongo.db["platform_metrics"].find({
        "timestamp": {"$gte": start_date}
    }).sort("timestamp", 1)

    history = await cursor.to_list(length=None)

    # Convert ObjectId to string
    for record in history:
        if "_id" in record:
            record["_id"] = str(record["_id"])

    return {
        "history": history,
        "period_days": days,
        "data_points": len(history)
    }


@router.post("/metrics/snapshot")
async def save_metrics_snapshot(
    current_user: ExtendedAuthUser = Depends(require_root_admin)
) -> Dict[str, Any]:
    """
    Save current metrics as a snapshot for historical tracking

    This should be called periodically (e.g., via Cloudflare Workers Cron)
    to build historical data for trends/charts.
    """
    # Get current metrics
    metrics = await get_platform_metrics(current_user)

    # Save to platform_metrics collection
    snapshot = {
        **metrics,
        "snapshot_time": datetime.utcnow()
    }

    result = await async_mongo.db["platform_metrics"].insert_one(snapshot)

    return {
        "status": "success",
        "snapshot_id": str(result.inserted_id),
        "timestamp": snapshot["snapshot_time"].isoformat()
    }


@router.get("/errors/recent")
async def get_recent_errors(
    limit: int = Query(50, ge=1, le=200, description="Number of errors to retrieve"),
    severity: Optional[str] = Query(None, description="Filter by severity: all, critical, warning"),
    acknowledged: Optional[bool] = Query(None, description="Filter by acknowledged status"),
    current_user: ExtendedAuthUser = Depends(require_root_admin)
) -> Dict[str, Any]:
    """
    Get recent errors with filtering options
    """
    # Build query
    query = {}

    if severity == "critical":
        query["status_code"] = {"$gte": 500}
    elif severity == "warning":
        query["status_code"] = {"$gte": 400, "$lt": 500}

    if acknowledged is not None:
        query["acknowledged"] = acknowledged

    # Get from errors collection (self-hosted) if it exists
    errors = []
    try:
        cursor = async_mongo.db["errors"].find(query).sort("timestamp", -1).limit(limit)
        errors = await cursor.to_list(length=limit)
    except Exception:
        # Fallback to audit_logs
        query["status_code"] = {"$gte": 400}
        cursor = async_mongo.db["audit_logs"].find(query).sort("timestamp", -1).limit(limit)
        errors = await cursor.to_list(length=limit)

    # Convert ObjectId to string
    for error in errors:
        if "_id" in error:
            error["_id"] = str(error["_id"])

    return {
        "errors": errors,
        "total": len(errors),
        "filters": {
            "severity": severity,
            "acknowledged": acknowledged
        }
    }


@router.get("/errors/{error_id}")
async def get_error_details(
    error_id: str,
    current_user: ExtendedAuthUser = Depends(require_root_admin)
) -> Dict[str, Any]:
    """Get detailed information about a specific error"""

    try:
        # Try errors collection first
        error = await async_mongo.db["errors"].find_one({"error_id": error_id})

        if not error:
            # Try by ObjectId
            error = await async_mongo.db["errors"].find_one({"_id": ObjectId(error_id)})

        if not error:
            # Try audit_logs as fallback
            error = await async_mongo.db["audit_logs"].find_one({"_id": ObjectId(error_id)})

        if not error:
            raise HTTPException(status_code=404, detail="Error not found")

        # Convert ObjectId to string
        if "_id" in error:
            error["_id"] = str(error["_id"])

        return error

    except Exception as e:
        logger.error(f"Failed to get error details: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/errors/{error_id}/acknowledge")
async def acknowledge_error(
    error_id: str,
    current_user: ExtendedAuthUser = Depends(require_root_admin)
) -> Dict[str, Any]:
    """Mark an error as acknowledged"""

    try:
        # Update in errors collection
        result = await async_mongo.db["errors"].update_one(
            {"error_id": error_id},
            {
                "$set": {
                    "acknowledged": True,
                    "acknowledged_by": current_user.email,
                    "acknowledged_at": datetime.utcnow()
                }
            }
        )

        if result.modified_count == 0:
            # Try by ObjectId
            result = await async_mongo.db["errors"].update_one(
                {"_id": ObjectId(error_id)},
                {
                    "$set": {
                        "acknowledged": True,
                        "acknowledged_by": current_user.email,
                        "acknowledged_at": datetime.utcnow()
                    }
                }
            )

        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Error not found")

        return {
            "status": "success",
            "acknowledged": True,
            "acknowledged_by": current_user.email
        }

    except Exception as e:
        logger.error(f"Failed to acknowledge error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/errors/cleanup")
async def cleanup_old_errors(
    days: int = Query(30, ge=7, le=365, description="Delete errors older than this many days"),
    current_user: ExtendedAuthUser = Depends(require_root_admin)
) -> Dict[str, Any]:
    """
    Clean up old acknowledged errors

    Args:
        days: Delete errors older than this many days (default: 30)
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    # Delete from errors collection
    result = await async_mongo.db["errors"].delete_many({
        "timestamp": {"$lt": cutoff_date},
        "acknowledged": True
    })

    return {
        "status": "success",
        "deleted_count": result.deleted_count,
        "cutoff_date": cutoff_date.isoformat()
    }
