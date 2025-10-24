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
        cpu_percent = 0.0
        cpu_cores = 0
        memory_percent_used = 0.0
        memory_used_gb = 0.0
        memory_total_gb = 0.0
        memory_available_gb = 0.0
        disk_percent_used = 0.0
        disk_free_gb = 0.0
        disk_total_gb = 0.0

        if PSUTIL_AVAILABLE:
            try:
                disk = psutil.disk_usage('/')
                memory = psutil.virtual_memory()
                cpu_percent = round(psutil.cpu_percent(interval=0.5), 1)
                cpu_cores = psutil.cpu_count(logical=True) or 0

                disk_percent_used = round(disk.percent, 1)
                disk_free_gb = round(disk.free / (1024**3), 2)
                disk_total_gb = round(disk.total / (1024**3), 2)

                memory_percent_used = round(memory.percent, 1)
                memory_total_gb = round(memory.total / (1024**3), 2)
                memory_used_gb = round(memory.used / (1024**3), 2)
                memory_available_gb = round(memory.available / (1024**3), 2)
            except Exception as e:
                logger.error(f"Failed to get system metrics: {str(e)}")
        else:
            logger.debug("psutil not available; returning zeroed system metrics")

        health_metrics = {
            "database": {
                "status": db_status,
                "latency_ms": round(db_latency, 2)
            },
            "cpu": {
                "percent": cpu_percent,
                "cores": cpu_cores
            },
            "memory": {
                "percent_used": memory_percent_used,
                "used_gb": memory_used_gb,
                "available_gb": memory_available_gb,
                "total_gb": memory_total_gb
            },
            "disk": {
                "percent_used": disk_percent_used,
                "free_gb": disk_free_gb,
                "total_gb": disk_total_gb
            }
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
        top_error_endpoints_raw = error_stats.get("by_endpoint", [])
        top_error_endpoints: List[Dict[str, Any]] = []

        for endpoint in top_error_endpoints_raw:
            identifier = endpoint.get("_id") if isinstance(endpoint, dict) else None
            path = None
            method = None

            if isinstance(identifier, dict):
                path = identifier.get("path")
                method = identifier.get("method")
            else:
                path = endpoint.get("_id") if isinstance(endpoint, dict) else endpoint

            top_error_endpoints.append({
                "endpoint": path,
                "path": path,
                "method": method,
                "count": endpoint.get("count", 0)
            })

        # Get recent errors for display
        recent_errors_query = {
            "$or": [
                {"status_code": {"$exists": True, "$gte": 400}},
                {"response_status": {"$exists": True, "$gte": 400}}
            ]
        }
        recent_errors_cursor = (
            async_mongo.db["audit_logs"]
            .find(recent_errors_query)
            .sort("timestamp", -1)
            .limit(10)
        )
        recent_errors_raw = await recent_errors_cursor.to_list(length=10)

        recent_errors: List[Dict[str, Any]] = []
        for error in recent_errors_raw:
            status_code = error.get("status_code")
            if status_code is None:
                status_code = error.get("response_status")

            if status_code is None:
                severity = "info"
            elif status_code >= 500:
                severity = "critical"
            else:
                severity = "warning"

            timestamp_value = error.get("timestamp")
            if isinstance(timestamp_value, datetime):
                timestamp_str = timestamp_value.isoformat()
            else:
                timestamp_str = timestamp_value

            message = (
                error.get("error_message")
                or error.get("message")
                or error.get("description")
                or "Request error"
            )

            recent_errors.append({
                "error_id": str(error.get("_id")) if error.get("_id") else None,
                "error_type": error.get("event_type") or "request_error",
                "severity": severity,
                "status_code": status_code,
                "endpoint": error.get("path"),
                "method": error.get("method"),
                "message": message,
                "response_time_ms": error.get("response_time_ms"),
                "timestamp": timestamp_str,
                "user_id": error.get("user_id")
            })

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
                    "_id": {"path": "$path", "method": "$method"},
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
        slow_endpoints_raw = await slow_cursor.to_list(length=10)

        slow_endpoints: List[Dict[str, Any]] = []
        for endpoint in slow_endpoints_raw:
            identifier = endpoint.get("_id") or {}
            path = identifier.get("path") if isinstance(identifier, dict) else identifier
            method = identifier.get("method") if isinstance(identifier, dict) else None

            avg_duration_ms = round(endpoint.get("avg_response_time", 0.0), 2)
            max_duration_ms = round(endpoint.get("max_response_time", 0.0), 2)
            call_count = endpoint.get("request_count", 0)

            slow_endpoints.append({
                "endpoint": path,
                "path": path,
                "method": method or "GET",
                "avg_duration_ms": avg_duration_ms,
                "avg_response_time_ms": avg_duration_ms,
                "max_duration_ms": max_duration_ms,
                "max_response_time_ms": max_duration_ms,
                "call_count": call_count,
                "request_count": call_count
            })

        # ==================== WEDDING METRICS ====================

        total_weddings = await async_mongo.db["weddings"].count_documents({})
        active_weddings = await async_mongo.db["weddings"].count_documents({
            "status": {"$ne": "archived"}
        })

        # ==================== COMPILE RESPONSE ====================

        generated_at = now.isoformat()

        return {
            "generated_at": generated_at,
            "timestamp": generated_at,
            "health": health_metrics,
            "errors": {
                "total_24h": total_errors,
                "critical_24h": critical_errors,
                "unacknowledged": self_hosted_errors,
                "error_rate_per_hour": round(total_errors / 24, 2) if total_errors else 0.0,
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
                "conversion_rate": round(conversion_rate, 2) if conversion_rate else 0.0,
                "mrr": round(mrr, 2),
                "arr": round(arr, 2),
                "total_weddings": total_weddings,
                "active_weddings": active_weddings
            },
            "performance": {
                "slow_endpoints": slow_endpoints
            }
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
    history_query = {
        "$or": [
            {"snapshot_time": {"$exists": True, "$gte": start_date}},
            {
                "snapshot_time": {"$exists": False},
                "timestamp": {"$gte": start_date.isoformat()}
            }
        ]
    }

    cursor = (
        async_mongo.db["platform_metrics"]
        .find(history_query)
        .sort([("snapshot_time", 1), ("timestamp", 1)])
    )

    history = await cursor.to_list(length=None)

    # Convert ObjectId to string
    for record in history:
        if "_id" in record:
            record["_id"] = str(record["_id"])

        snapshot_time = record.get("snapshot_time")
        if isinstance(snapshot_time, datetime):
            iso_value = snapshot_time.isoformat()
            record["snapshot_time"] = iso_value
            record.setdefault("generated_at", iso_value)

        timestamp_value = record.get("timestamp")
        if isinstance(timestamp_value, datetime):
            record["timestamp"] = timestamp_value.isoformat()

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

    health_metrics = snapshot.get("health", {})
    database_health = health_metrics.get("database", {})
    cpu_health = health_metrics.get("cpu", {})
    memory_health = health_metrics.get("memory", {})
    disk_health = health_metrics.get("disk", {})

    error_metrics = snapshot.get("errors", {})
    business_metrics = snapshot.get("business", {})
    performance_metrics = snapshot.get("performance", {})

    metrics_summary = {
        "health": {
            "database": {
                "status": database_health.get("status"),
                "latency_ms": database_health.get("latency_ms"),
            },
            "cpu": {
                "percent": cpu_health.get("percent"),
                "cores": cpu_health.get("cores"),
            },
            "memory": {
                "percent_used": memory_health.get("percent_used"),
                "used_gb": memory_health.get("used_gb"),
                "total_gb": memory_health.get("total_gb"),
            },
            "disk": {
                "percent_used": disk_health.get("percent_used"),
                "free_gb": disk_health.get("free_gb"),
                "total_gb": disk_health.get("total_gb"),
            },
        },
        "errors": {
            "total_24h": error_metrics.get("total_24h"),
            "critical_24h": error_metrics.get("critical_24h"),
            "unacknowledged": error_metrics.get("unacknowledged"),
            "error_rate_per_hour": error_metrics.get("error_rate_per_hour"),
            "recent_errors": [
                {
                    "error_id": err.get("error_id"),
                    "severity": err.get("severity"),
                    "status_code": err.get("status_code"),
                    "timestamp": err.get("timestamp"),
                }
                for err in error_metrics.get("recent_errors", [])
            ],
        },
        "business": {
            "total_users": business_metrics.get("total_users"),
            "active_users_week": business_metrics.get("active_users_week"),
            "new_users_week": business_metrics.get("new_users_week"),
            "active_subscriptions": business_metrics.get("active_subscriptions"),
            "trial_subscriptions": business_metrics.get("trial_subscriptions"),
            "canceled_subscriptions": business_metrics.get("canceled_subscriptions"),
            "conversion_rate": business_metrics.get("conversion_rate"),
            "mrr": business_metrics.get("mrr"),
            "arr": business_metrics.get("arr"),
            "total_weddings": business_metrics.get("total_weddings"),
            "active_weddings": business_metrics.get("active_weddings"),
        },
        "performance": {
            "slow_endpoints": [
                {
                    "path": endpoint.get("path") or endpoint.get("endpoint"),
                    "method": endpoint.get("method"),
                    "avg_duration_ms": endpoint.get("avg_duration_ms")
                    or endpoint.get("avg_response_time")
                    or endpoint.get("avg_response_time_ms"),
                    "call_count": endpoint.get("call_count")
                    or endpoint.get("request_count"),
                }
                for endpoint in performance_metrics.get("slow_endpoints", [])
            ],
        },
    }

    snapshot_time_iso = snapshot["snapshot_time"].isoformat()

    return {
        "status": "success",
        "snapshot_id": str(result.inserted_id),
        "timestamp": snapshot_time_iso,
        "generated_at": snapshot_time_iso,
        "metrics": metrics_summary,
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
