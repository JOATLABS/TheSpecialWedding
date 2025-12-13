"""
ROOT_ADMIN Platform Metrics API

Zero-cost monitoring solution using MongoDB and existing infrastructure.
Provides comprehensive metrics for the ROOT_ADMIN dashboard.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, Any, List, Optional, Iterable
from datetime import datetime, timedelta
from app.dependencies.auth_extended import require_root_admin, ExtendedAuthUser
from app.core.database import mongo
from bson import ObjectId
import logging

# Try to import psutil for system metrics (install if not present: pip install psutil)
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logging.warning("psutil not installed. System metrics will be unavailable. Install with: pip install psutil")


def _normalize_timestamp(value: Any) -> Optional[str]:
    """Return an ISO formatted timestamp string when possible."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        return value
    return None


def _coerce_datetime(value: Any) -> Optional[datetime]:
    """Convert string/datetime values into datetime objects when possible."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
    return None


def _derive_severity(explicit: Optional[str], status_code: Optional[int]) -> str:
    """Determine severity label from explicit value or HTTP status."""
    if explicit:
        return explicit
    if status_code is None:
        return "warning"
    if status_code >= 500:
        return "critical"
    if status_code >= 400:
        return "warning"
    return "info"


def _extract_error_summary(error: Dict[str, Any]) -> Dict[str, Any]:
    """Build a UI-friendly summary payload for dashboard error listings."""
    status_code = error.get("response_status") or error.get("status_code")
    request_info = error.get("request", {})

    endpoint = (
        request_info.get("path") or request_info.get("endpoint") or error.get("path")
    )
    method = request_info.get("method") or error.get("method")

    message = (
        error.get("error_message") or error.get("message") or error.get("detail")
    )
    if not message and method and endpoint and status_code:
        message = f"{method} {endpoint} returned {status_code}"
    elif not message:
        message = "Request failed"

    raw_id = error.get("error_id") or error.get("_id")

    return {
        "error_id": str(raw_id) if raw_id is not None else None,
        "error_type": error.get("error_type") or error.get("event_type") or "Application Error",
        "message": message,
        "severity": _derive_severity(error.get("severity"), status_code),
        "timestamp": _normalize_timestamp(error.get("timestamp")),
        "endpoint": endpoint,
        "status_code": status_code,
        "method": method,
        "user_id": error.get("user_id") or request_info.get("user_id"),
        "acknowledged": error.get("acknowledged", False),
    }


def _extract_error_detail(error: Dict[str, Any]) -> Dict[str, Any]:
    """Return detailed error document compatible with admin UI expectations."""
    summary = _extract_error_summary(error)
    request_info = error.get("request", {})

    normalized_request: Optional[Dict[str, Any]] = None

    if request_info:
        normalized_request = {
            "method": request_info.get("method"),
            "endpoint": (
                request_info.get("path") or request_info.get("endpoint") or summary.get("endpoint")
            ),
            "ip": (
                request_info.get("client_ip") or request_info.get("ip") or error.get("ip_address")
            ),
            "user_agent": request_info.get("user_agent") or error.get("user_agent"),
            "user_id": request_info.get("user_id") or summary.get("user_id"),
            "body": request_info.get("body"),
            "query_params": request_info.get("query_params"),
        }

        headers = request_info.get("headers")
        if headers is not None:
            normalized_request["headers"] = headers
    elif summary.get("endpoint"):
        normalized_request = {
            "method": summary.get("method"),
            "endpoint": summary.get("endpoint"),
            "ip": error.get("ip_address"),
            "user_agent": error.get("user_agent"),
            "user_id": summary.get("user_id"),
            "query_params": error.get("query_params"),
        }

    detail = {
        **summary,
        "stack_trace": error.get("stack_trace", ""),
        "request": normalized_request,
        "context": error.get("context"),
    }

    # Preserve any acknowledgement metadata if present
    for key in ["acknowledged_by", "acknowledged_at"]:
        if key in error:
            value = error[key]
            if key == "acknowledged_at":
                detail[key] = _normalize_timestamp(value)
            else:
                detail[key] = value

    return detail


CPU_PERCENT_INITIALIZED = False

if PSUTIL_AVAILABLE:
    try:
        psutil.cpu_percent(interval=None)
        CPU_PERCENT_INITIALIZED = True
    except Exception:
        CPU_PERCENT_INITIALIZED = False

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/platform", tags=["ROOT_ADMIN", "Monitoring"])


@router.get("/health")
async def get_platform_health(
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
            await mongo.db.command('ping')
            db_latency = (datetime.utcnow() - db_start).total_seconds() * 1000
            db_status = "healthy" if db_latency < 100 else "degraded"
        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
            db_status = "down"
            db_latency = 9999

        # System resources (if psutil available)
        cpu_metrics: Dict[str, Any] = {
            "percent": 0.0,
            "cores": 0,
            "status": "unknown"
        }
        memory_metrics: Dict[str, Any] = {
            "total_gb": 0.0,
            "used_gb": 0.0,
            "available_gb": 0.0,
            "percent_used": 0.0
        }
        disk_metrics: Dict[str, Any] = {
            "total_gb": 0.0,
            "used_gb": 0.0,
            "free_gb": 0.0,
            "percent_used": 0.0
        }

        if PSUTIL_AVAILABLE:
            try:
                disk = psutil.disk_usage('/')
                memory = psutil.virtual_memory()

                global CPU_PERCENT_INITIALIZED
                if not CPU_PERCENT_INITIALIZED:
                    psutil.cpu_percent(interval=None)
                    CPU_PERCENT_INITIALIZED = True

                cpu_percent = psutil.cpu_percent(interval=None)
                cpu_count = psutil.cpu_count(logical=True) or 0

                total_memory_gb = memory.total / (1024**3)
                used_memory_gb = (memory.total - memory.available) / (1024**3)

                total_disk_gb = disk.total / (1024**3)
                used_disk_gb = disk.used / (1024**3)

                cpu_metrics.update({
                    "percent": round(cpu_percent, 1),
                    "cores": cpu_count,
                    "status": "healthy" if cpu_percent < 85 else "degraded"
                })

                memory_metrics.update({
                    "total_gb": round(total_memory_gb, 2),
                    "used_gb": round(used_memory_gb, 2),
                    "available_gb": round(memory.available / (1024**3), 2),
                    "percent_used": round(memory.percent, 1)
                })

                disk_metrics.update({
                    "total_gb": round(total_disk_gb, 2),
                    "used_gb": round(used_disk_gb, 2),
                    "free_gb": round(disk.free / (1024**3), 2),
                    "percent_used": round(disk.percent, 1)
                })
            except Exception as e:
                logger.error(f"Failed to get system metrics: {str(e)}")
                cpu_metrics["status"] = "unavailable"
        else:
            cpu_metrics["status"] = "psutil_not_installed"

        # ==================== ERROR MONITORING ====================

        errors_collection_total = 0
        errors_collection_critical = 0
        self_hosted_errors = 0

        # Get errors from audit_logs (existing collection)
        error_pipeline = [
            {
                "$match": {
                    "timestamp": {"$gte": day_ago},
                    "response_status": {"$gte": 400}
                }
            },
            {
                "$facet": {
                    "total": [{"$count": "count"}],
                    "critical": [
                        {"$match": {"response_status": {"$gte": 500}}},
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

        error_stats_cursor = mongo.db["audit_logs"].aggregate(error_pipeline)
        error_stats_list = await error_stats_cursor.to_list(length=1)
        error_stats = error_stats_list[0] if error_stats_list else {}

        audit_total_errors = error_stats.get("total", [{}])[0].get("count", 0) if error_stats.get("total") else 0
        audit_critical_errors = error_stats.get("critical", [{}])[0].get("count", 0) if error_stats.get("critical") else 0
        top_error_endpoints = error_stats.get("by_endpoint", [])

        # Check if errors collection exists (self-hosted error tracking)
        try:
            self_hosted_errors = await mongo.db["errors"].count_documents({
                "timestamp": {"$gte": day_ago},
                "acknowledged": False
            })
            errors_collection_total = await mongo.db["errors"].count_documents({
                "timestamp": {"$gte": day_ago}
            })
            errors_collection_critical = await mongo.db["errors"].count_documents({
                "timestamp": {"$gte": day_ago},
                "severity": "critical"
            })
        except Exception:
            # Collection might not exist yet
            pass

        total_errors = audit_total_errors + errors_collection_total
        critical_errors = audit_critical_errors + errors_collection_critical

        # Build consolidated recent error list from both error sources
        recent_error_docs: List[Dict[str, Any]] = []
        seen_error_ids = set()

        def extend_recent_errors(docs: Iterable[Dict[str, Any]]):
            for doc in docs:
                doc_identifier = doc.get("error_id") or doc.get("_id")
                doc_identifier_str = str(doc_identifier) if doc_identifier is not None else None
                if doc_identifier_str and doc_identifier_str in seen_error_ids:
                    continue
                if doc_identifier_str:
                    seen_error_ids.add(doc_identifier_str)
                recent_error_docs.append(doc)
                if len(recent_error_docs) >= 10:
                    break

        try:
            errors_collection_cursor = mongo.db["errors"].find({
                "timestamp": {"$gte": day_ago}
            }).sort("timestamp", -1).limit(10)
            extend_recent_errors(await errors_collection_cursor.to_list(length=10))
        except Exception as exc:
            logger.warning("Failed to load recent errors from errors collection: %s", exc)

        if len(recent_error_docs) < 10:
            remaining = 10 - len(recent_error_docs)
            if remaining > 0:
                audit_recent_cursor = mongo.db["audit_logs"].find({
                    "timestamp": {"$gte": day_ago},
                    "response_status": {"$gte": 400}
                }).sort("timestamp", -1).limit(remaining)
                extend_recent_errors(await audit_recent_cursor.to_list(length=remaining))

        recent_error_docs.sort(
            key=lambda doc: _coerce_datetime(doc.get("timestamp")) or datetime.min,
            reverse=True
        )
        recent_errors = [_extract_error_summary(error) for error in recent_error_docs]

        # ==================== BUSINESS METRICS ====================

        # User statistics
        total_users = await mongo.db["users"].count_documents({})
        active_users_week = await mongo.db["users"].count_documents({
            "last_login": {"$gte": week_ago}
        })
        new_users_week = await mongo.db["users"].count_documents({
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

        sub_cursor = mongo.db["subscriptions"].aggregate(subscription_pipeline)
        sub_stats_list = await sub_cursor.to_list(length=1)
        sub_stats = sub_stats_list[0] if sub_stats_list else {}

        active_subscriptions = sub_stats.get("active", [{}])[0].get("count", 0) if sub_stats.get("active") else 0
        trial_subscriptions = sub_stats.get("trialing", [{}])[0].get("count", 0) if sub_stats.get("trialing") else 0
        canceled_subscriptions = sub_stats.get("canceled", [{}])[0].get("count", 0) if sub_stats.get("canceled") else 0

        # Calculate MRR/ARR
        # Get all active subscriptions with amounts
        active_subs_cursor = mongo.db["subscriptions"].find({
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
        total_trials = await mongo.db["subscriptions"].count_documents({
            "trial_end": {"$exists": True}
        })
        converted_trials = await mongo.db["subscriptions"].count_documents({
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

        slow_cursor = mongo.db["audit_logs"].aggregate(slow_endpoint_pipeline)
        slow_endpoints_raw = await slow_cursor.to_list(length=10)

        slow_endpoints: List[Dict[str, Any]] = []
        for endpoint in slow_endpoints_raw:
            slow_endpoints.append({
                "endpoint": endpoint.get("_id"),
                "avg_response_time": round(endpoint.get("avg_response_time", 0) / 1000, 3),
                "max_response_time": round(endpoint.get("max_response_time", 0) / 1000, 3),
                "request_count": endpoint.get("request_count", 0),
            })

        # ==================== WEDDING METRICS ====================

        total_weddings = await mongo.db["weddings"].count_documents({})
        active_weddings = await mongo.db["weddings"].count_documents({
            "status": {"$ne": "archived"}
        })

        # ==================== COMPILE RESPONSE ====================

        generated_at = now.isoformat()

        return {
            "generated_at": generated_at,
            "health": {
                "database": {
                    "status": db_status,
                    "latency_ms": round(db_latency, 2)
                },
                "cpu": cpu_metrics,
                "memory": memory_metrics,
                "disk": disk_metrics,
                "psutil_available": PSUTIL_AVAILABLE
            },
            "errors": {
                "total_24h": total_errors,
                "critical_24h": critical_errors,
                "unacknowledged": self_hosted_errors,
                "error_rate_per_hour": round(total_errors / 24, 2),
                "top_error_endpoints": [
                    {"endpoint": item.get("_id"), "count": item.get("count", 0)}
                    for item in top_error_endpoints
                ],
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
            "timestamp": generated_at
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
    cursor = mongo.db["platform_metrics"].find({
        "$or": [
            {"snapshot_time": {"$gte": start_date}},
            {
                "snapshot_time": {"$exists": False},
                "timestamp": {"$gte": start_date.isoformat()}
            }
        ]
    }).sort([
        ("snapshot_time", 1),
        ("timestamp", 1)
    ])

    history = await cursor.to_list(length=None)

    # Convert ObjectId to string
    for record in history:
        if "_id" in record:
            record["_id"] = str(record["_id"])
        if "snapshot_time" in record and isinstance(record["snapshot_time"], datetime):
            record["snapshot_time"] = record["snapshot_time"].isoformat()

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

    result = await mongo.db["platform_metrics"].insert_one(snapshot)

    health_metrics = snapshot.get("health", {})
    error_metrics = snapshot.get("errors", {})
    business_metrics = snapshot.get("business", {})
    performance_metrics = snapshot.get("performance", {})

    database_metrics = health_metrics.get("database", {})
    cpu_metrics = health_metrics.get("cpu", {})
    memory_metrics = health_metrics.get("memory", {})
    disk_metrics = health_metrics.get("disk", {})

    metrics_summary = {
        "health": {
            "database": {
                "status": database_metrics.get("status"),
                "latency_ms": database_metrics.get("latency_ms"),
            },
            "cpu": {
                "percent": cpu_metrics.get("percent"),
                "cores": cpu_metrics.get("cores"),
                "status": cpu_metrics.get("status"),
            },
            "memory": {
                "total_gb": memory_metrics.get("total_gb"),
                "used_gb": memory_metrics.get("used_gb"),
                "available_gb": memory_metrics.get("available_gb"),
                "percent_used": memory_metrics.get("percent_used"),
            },
            "disk": {
                "total_gb": disk_metrics.get("total_gb"),
                "used_gb": disk_metrics.get("used_gb"),
                "free_gb": disk_metrics.get("free_gb"),
                "percent_used": disk_metrics.get("percent_used"),
            },
            "psutil_available": health_metrics.get("psutil_available", False),
        },
        "errors": {
            "total_24h": error_metrics.get("total_24h"),
            "critical_24h": error_metrics.get("critical_24h"),
            "unacknowledged": error_metrics.get("unacknowledged"),
            "error_rate_per_hour": error_metrics.get("error_rate_per_hour"),
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
                    "endpoint": endpoint.get("endpoint"),
                    "avg_response_time": endpoint.get("avg_response_time"),
                    "max_response_time": endpoint.get("max_response_time"),
                    "request_count": endpoint.get("request_count"),
                }
                for endpoint in performance_metrics.get("slow_endpoints", [])
            ],
        },
    }

    return {
        "status": "success",
        "snapshot_id": str(result.inserted_id),
        "timestamp": snapshot["snapshot_time"].isoformat(),
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
    now = datetime.utcnow()
    default_cutoff = now - timedelta(days=30)

    errors_docs: List[Dict[str, Any]] = []
    seen_ids = set()

    def extend_errors(docs: Iterable[Dict[str, Any]]):
        for doc in docs:
            doc_identifier = doc.get("error_id") or doc.get("_id")
            doc_identifier_str = str(doc_identifier) if doc_identifier is not None else None
            if doc_identifier_str and doc_identifier_str in seen_ids:
                continue
            if doc_identifier_str:
                seen_ids.add(doc_identifier_str)
            errors_docs.append(doc)
            if len(errors_docs) >= limit:
                break

    errors_query: Dict[str, Any] = {"timestamp": {"$gte": default_cutoff}}
    if acknowledged is not None:
        errors_query["acknowledged"] = acknowledged
    if severity == "critical":
        errors_query["$or"] = [
            {"severity": "critical"},
            {"status_code": {"$gte": 500}},
        ]
    elif severity == "warning":
        errors_query["$or"] = [
            {"severity": {"$exists": True, "$ne": "critical"}},
            {
                "$and": [
                    {"severity": {"$exists": False}},
                    {"status_code": {"$gte": 400, "$lt": 500}},
                ]
            },
        ]

    try:
        cursor = mongo.db["errors"].find(errors_query).sort("timestamp", -1).limit(limit)
        extend_errors(await cursor.to_list(length=limit))
    except Exception as exc:
        logger.warning("Failed to query self-hosted errors collection: %s", exc)

    include_audit_fallback = acknowledged is None and len(errors_docs) < limit
    if include_audit_fallback:
        remaining = limit - len(errors_docs)
        if remaining > 0:
            audit_query: Dict[str, Any] = {
                "timestamp": {"$gte": default_cutoff},
                "response_status": {"$gte": 400},
            }
            if severity == "critical":
                audit_query["response_status"] = {"$gte": 500}
            elif severity == "warning":
                audit_query["response_status"] = {"$gte": 400, "$lt": 500}

            cursor = mongo.db["audit_logs"].find(audit_query).sort("timestamp", -1).limit(remaining)
            extend_errors(await cursor.to_list(length=remaining))

    errors_docs.sort(
        key=lambda doc: _coerce_datetime(doc.get("timestamp")) or datetime.min,
        reverse=True
    )
    normalized_errors = [_extract_error_summary(error) for error in errors_docs]

    return {
        "errors": normalized_errors,
        "total": len(normalized_errors),
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
        error = await mongo.db["errors"].find_one({"error_id": error_id})

        if not error and ObjectId.is_valid(error_id):
            # Try by ObjectId
            error = await mongo.db["errors"].find_one({"_id": ObjectId(error_id)})

        if not error and ObjectId.is_valid(error_id):
            # Try audit_logs as fallback
            error = await mongo.db["audit_logs"].find_one({"_id": ObjectId(error_id)})

        if not error:
            raise HTTPException(status_code=404, detail="Error not found")

        return _extract_error_detail(error)

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
        result = await mongo.db["errors"].update_one(
            {"error_id": error_id},
            {
                "$set": {
                    "acknowledged": True,
                    "acknowledged_by": current_user.email,
                    "acknowledged_at": datetime.utcnow()
                }
            }
        )

        if result.modified_count == 0 and ObjectId.is_valid(error_id):
            # Try by ObjectId
            result = await mongo.db["errors"].update_one(
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
    result = await mongo.db["errors"].delete_many({
        "timestamp": {"$lt": cutoff_date},
        "acknowledged": True
    })

    return {
        "status": "success",
        "deleted_count": result.deleted_count,
        "cutoff_date": cutoff_date.isoformat()
    }
