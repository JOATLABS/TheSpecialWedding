"""
ROOT_ADMIN Platform Metrics API

Zero-cost monitoring solution using MongoDB and existing infrastructure.
Provides comprehensive metrics for the ROOT_ADMIN dashboard.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
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
    """Return an ISO formatted timestamp string with Z suffix for UTC indication."""
    if isinstance(value, datetime):
        # Add Z suffix to indicate UTC time (critical for correct frontend timezone conversion)
        iso_str = value.isoformat()
        return iso_str if iso_str.endswith("Z") else iso_str + "Z"
    if isinstance(value, str):
        # Ensure existing strings have Z suffix if they look like UTC timestamps
        if value and not value.endswith("Z") and "+" not in value and "-" not in value[-6:]:
            return value + "Z"
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
    """Return detailed error document with full debugging information for root admin."""
    summary = _extract_error_summary(error)
    request_info = error.get("request", {})
    user_info = error.get("user", {})

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
            # Filter out potentially sensitive headers already done in error_handler
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

    # Get the full stack trace for debugging
    stack_trace = error.get("stack_trace", "")
    if not stack_trace:
        # Try alternative field names
        stack_trace = error.get("traceback", "") or error.get("exception_traceback", "")

    # Extract response payload for debugging
    response_payload = error.get("response", {})
    if isinstance(response_payload, dict):
        response_info = {
            "status_code": response_payload.get("error", {}).get("code") or summary.get("status_code"),
            "error_code": response_payload.get("error", {}).get("code"),
            "response_message": response_payload.get("error", {}).get("message"),
        }
    else:
        response_info = None

    detail = {
        **summary,
        "stack_trace": stack_trace,
        "request": normalized_request,
        "response": response_info,
        "context": error.get("context"),
        # Additional debugging information
        "environment": error.get("environment"),
        "user_authenticated": user_info.get("authenticated", False) if user_info else None,
        "error_source": error.get("source", "backend"),
        "metadata": error.get("metadata"),
        # Full error message (unsanitized for root admin)
        "full_error_message": error.get("error_message") or error.get("message"),
        # Original exception type
        "exception_type": error.get("error_type") or type(error).__name__,
    }

    # Preserve any acknowledgement metadata if present
    for key in ["acknowledged_by", "acknowledged_at"]:
        if key in error:
            value = error[key]
            if key == "acknowledged_at":
                detail[key] = _normalize_timestamp(value)
            else:
                detail[key] = value

    # Add troubleshooting hints based on error type
    detail["troubleshooting_hints"] = _generate_troubleshooting_hints(detail)

    return detail


def _generate_troubleshooting_hints(error_detail: Dict[str, Any]) -> List[str]:
    """Generate contextual troubleshooting hints based on error details."""
    hints: List[str] = []
    error_type = error_detail.get("exception_type", "")
    status_code = error_detail.get("status_code")
    endpoint = error_detail.get("endpoint", "")
    stack_trace = error_detail.get("stack_trace", "")

    # Status code based hints
    if status_code == 401:
        hints.append("Check if the authentication token is valid and not expired")
        hints.append("Verify the user has the correct permissions for this endpoint")
    elif status_code == 403:
        hints.append("User is authenticated but lacks permission for this action")
        hints.append("Check role-based access control settings")
    elif status_code == 404:
        hints.append("Verify the requested resource exists in the database")
        hints.append("Check if the URL path and parameters are correct")
    elif status_code == 500:
        hints.append("Review the stack trace for the root cause")
        hints.append("Check server logs for additional context around this timestamp")

    # Error type based hints
    if "Database" in error_type or "Mongo" in error_type:
        hints.append("Check database connection and credentials")
        hints.append("Verify MongoDB is running and accessible")
    elif "Timeout" in error_type or "timeout" in str(stack_trace).lower():
        hints.append("Check for slow database queries or external API calls")
        hints.append("Consider increasing timeout limits or optimizing the operation")
    elif "Key" in error_type or "Attribute" in error_type:
        hints.append("Check for missing required fields in the request or database document")
        hints.append("Verify the data structure matches expected schema")
    elif "Validation" in error_type:
        hints.append("Check the request payload against the API schema")
        hints.append("Verify all required fields are provided and have correct types")

    # Endpoint specific hints
    if "/webhook/" in endpoint:
        hints.append("Verify webhook signature and payload format")
        hints.append("Check webhook configuration in the external service")
    elif "/ai/" in endpoint:
        hints.append("Check AI service API key and rate limits")
        hints.append("Verify the AI service is operational")
    elif "/auth/" in endpoint:
        hints.append("Check authentication service configuration")
        hints.append("Verify OAuth/JWT settings if applicable")

    # Default hints if none generated
    if not hints:
        hints.append("Review the stack trace above to identify the source of the error")
        hints.append("Check application logs for additional context around this timestamp")
        hints.append("Verify the request parameters and endpoint configuration")

    return hints


async def _check_twilio_health(since: datetime) -> Dict[str, Any]:
    """
    Check Twilio SMS service health and delivery statistics.

    Returns:
        Dict with status, configuration, and delivery metrics
    """
    import os

    result = {
        "status": "unknown",
        "configured": False,
        "account_sid_set": False,
        "auth_token_set": False,
        "messaging_service_sid_set": False,
        "status_callback_configured": False,
        "delivery_stats_24h": {
            "total_sent": 0,
            "delivered": 0,
            "failed": 0,
            "undelivered": 0,
            "pending": 0,
            "delivery_rate": 0.0
        },
        "error": None
    }

    # Check environment variables
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    messaging_service_sid = os.getenv("TWILIO_MESSAGING_SERVICE_SID")
    status_callback_url = os.getenv("TWILIO_STATUS_CALLBACK_URL")

    result["account_sid_set"] = bool(account_sid)
    result["auth_token_set"] = bool(auth_token)
    result["messaging_service_sid_set"] = bool(messaging_service_sid)
    result["status_callback_configured"] = bool(status_callback_url)

    # Check if all required credentials are set
    result["configured"] = all([account_sid, auth_token, messaging_service_sid])

    if not result["configured"]:
        result["status"] = "not_configured"
        missing = []
        if not account_sid:
            missing.append("TWILIO_ACCOUNT_SID")
        if not auth_token:
            missing.append("TWILIO_AUTH_TOKEN")
        if not messaging_service_sid:
            missing.append("TWILIO_MESSAGING_SERVICE_SID")
        result["error"] = f"Missing: {', '.join(missing)}"
        return result

    # Get delivery statistics from reminders_sent collection
    try:
        pipeline = [
            {
                "$match": {
                    "provider": "twilio",
                    "sent_at": {"$gte": since}
                }
            },
            {
                "$facet": {
                    "total": [{"$count": "count"}],
                    "by_status": [
                        {"$group": {"_id": "$delivery_status", "count": {"$sum": 1}}}
                    ],
                    "failed": [
                        {"$match": {"status": {"$regex": "^failed"}}},
                        {"$count": "count"}
                    ]
                }
            }
        ]

        cursor = mongo.db["reminders_sent"].aggregate(pipeline)
        stats_list = await cursor.to_list(length=1)
        stats = stats_list[0] if stats_list else {}

        total_sent = stats.get("total", [{}])[0].get("count", 0) if stats.get("total") else 0
        failed_on_send = stats.get("failed", [{}])[0].get("count", 0) if stats.get("failed") else 0

        # Parse delivery statuses
        delivered = 0
        undelivered = 0
        pending = 0

        for status_item in stats.get("by_status", []):
            status = status_item.get("_id")
            count = status_item.get("count", 0)

            if status in ["delivered"]:
                delivered += count
            elif status in ["undelivered", "failed"]:
                undelivered += count
            elif status in ["queued", "accepted", "sending", "sent"]:
                pending += count

        # Calculate delivery rate (excluding pending)
        completed = delivered + undelivered + failed_on_send
        delivery_rate = (delivered / completed * 100) if completed > 0 else 100.0

        result["delivery_stats_24h"] = {
            "total_sent": total_sent,
            "delivered": delivered,
            "failed": failed_on_send + undelivered,
            "undelivered": undelivered,
            "pending": pending,
            "delivery_rate": round(delivery_rate, 1)
        }

        # Determine overall status
        if total_sent == 0:
            result["status"] = "healthy"  # No SMS sent, but configured
        elif delivery_rate >= 95:
            result["status"] = "healthy"
        elif delivery_rate >= 80:
            result["status"] = "degraded"
        else:
            result["status"] = "unhealthy"

        # Warn if status callback not configured
        if not status_callback_url:
            result["status"] = "warning" if result["status"] == "healthy" else result["status"]
            result["error"] = "TWILIO_STATUS_CALLBACK_URL not configured - delivery tracking disabled"

    except Exception as e:
        logger.error(f"Failed to get Twilio delivery stats: {str(e)}")
        result["status"] = "error"
        result["error"] = f"Failed to query delivery stats: {str(e)}"

    return result


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

        # Get comprehensive endpoint performance metrics from audit_logs
        endpoint_performance_pipeline = [
            {
                "$match": {
                    "timestamp": {"$gte": day_ago},
                    "response_time_ms": {"$exists": True},
                    "path": {"$exists": True, "$ne": None}
                }
            },
            {
                "$group": {
                    "_id": "$path",
                    "avg_response_time_ms": {"$avg": "$response_time_ms"},
                    "min_response_time_ms": {"$min": "$response_time_ms"},
                    "max_response_time_ms": {"$max": "$response_time_ms"},
                    "total_requests": {"$sum": 1},
                    "error_count": {
                        "$sum": {
                            "$cond": [{"$gte": ["$response_status", 400]}, 1, 0]
                        }
                    },
                    "response_times": {"$push": "$response_time_ms"}
                }
            },
            {
                "$match": {
                    "total_requests": {"$gte": 1}
                }
            },
            {
                "$sort": {"avg_response_time_ms": -1}
            },
            {
                "$limit": 20
            }
        ]

        perf_cursor = mongo.db["audit_logs"].aggregate(endpoint_performance_pipeline)
        endpoint_metrics_raw = await perf_cursor.to_list(length=20)

        # Calculate percentiles and format response
        endpoint_performance: List[Dict[str, Any]] = []
        slow_endpoints: List[Dict[str, Any]] = []

        for endpoint in endpoint_metrics_raw:
            response_times = sorted(endpoint.get("response_times", []))
            total_requests = endpoint.get("total_requests", 0)
            error_count = endpoint.get("error_count", 0)

            # Calculate percentiles
            p50 = response_times[int(len(response_times) * 0.5)] if response_times else 0
            p95 = response_times[int(len(response_times) * 0.95)] if response_times else 0
            p99 = response_times[int(len(response_times) * 0.99)] if response_times else 0

            avg_ms = endpoint.get("avg_response_time_ms", 0)
            max_ms = endpoint.get("max_response_time_ms", 0)
            error_rate = (error_count / total_requests * 100) if total_requests > 0 else 0

            # Determine performance status
            if avg_ms > 1000:
                status = "critical"
            elif avg_ms > 500:
                status = "warning"
            elif avg_ms > 200:
                status = "moderate"
            else:
                status = "healthy"

            perf_entry = {
                "endpoint": endpoint.get("_id"),
                "avg_response_time_ms": round(avg_ms, 1),
                "min_response_time_ms": round(endpoint.get("min_response_time_ms", 0), 1),
                "max_response_time_ms": round(max_ms, 1),
                "p50_ms": round(p50, 1),
                "p95_ms": round(p95, 1),
                "p99_ms": round(p99, 1),
                "request_count": total_requests,
                "error_count": error_count,
                "error_rate": round(error_rate, 2),
                "status": status
            }
            endpoint_performance.append(perf_entry)

            # Track slow endpoints separately (>500ms avg or >1s max)
            if avg_ms > 500 or max_ms > 1000:
                slow_endpoints.append(perf_entry)

        # Get overall performance summary
        total_requests_24h = sum(ep.get("request_count", 0) for ep in endpoint_performance)
        total_errors_24h = sum(ep.get("error_count", 0) for ep in endpoint_performance)
        overall_error_rate = (total_errors_24h / total_requests_24h * 100) if total_requests_24h > 0 else 0

        # Calculate overall average response time
        overall_avg_pipeline = [
            {
                "$match": {
                    "timestamp": {"$gte": day_ago},
                    "response_time_ms": {"$exists": True}
                }
            },
            {
                "$group": {
                    "_id": None,
                    "avg_response_time_ms": {"$avg": "$response_time_ms"}
                }
            }
        ]
        overall_cursor = mongo.db["audit_logs"].aggregate(overall_avg_pipeline)
        overall_result = await overall_cursor.to_list(length=1)
        overall_avg_ms = overall_result[0].get("avg_response_time_ms", 0) if overall_result else 0

        # ==================== WEDDING METRICS ====================

        total_weddings = await mongo.db["weddings"].count_documents({})
        active_weddings = await mongo.db["weddings"].count_documents({
            "status": {"$ne": "archived"}
        })

        # ==================== SERVICE HEALTH ====================

        # Web Push notification service health
        try:
            from app.services.web_push_service import web_push_service
            web_push_health = await web_push_service.health_check()
        except Exception as e:
            logger.error(f"Failed to check Web Push health: {str(e)}")
            web_push_health = {
                "status": "error",
                "error": f"Health check failed: {str(e)}",
                "enabled": False,
                "configured": False
            }

        # Twilio SMS service health
        twilio_health = await _check_twilio_health(day_ago)

        # ==================== COMPILE RESPONSE ====================

        # Use Z suffix to indicate UTC time (critical for correct frontend timezone conversion)
        generated_at = now.isoformat() + "Z"

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
                "summary": {
                    "total_requests_24h": total_requests_24h,
                    "total_errors_24h": total_errors_24h,
                    "overall_error_rate": round(overall_error_rate, 2),
                    "overall_avg_response_time_ms": round(overall_avg_ms, 1),
                    "slow_endpoint_count": len(slow_endpoints),
                    "monitored_endpoint_count": len(endpoint_performance)
                },
                "endpoints": endpoint_performance,
                "slow_endpoints": slow_endpoints
            },
            "services": {
                "web_push": web_push_health,
                "twilio": twilio_health
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
            record["snapshot_time"] = record["snapshot_time"].isoformat() + "Z"

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
    metrics = await get_platform_health(current_user)

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
    services_metrics = snapshot.get("services", {})

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
        "services": {
            "web_push": {
                "status": services_metrics.get("web_push", {}).get("status"),
                "enabled": services_metrics.get("web_push", {}).get("enabled"),
                "total_subscriptions": services_metrics.get("web_push", {}).get("total_subscriptions"),
                "error": services_metrics.get("web_push", {}).get("error"),
            },
            "twilio": {
                "status": services_metrics.get("twilio", {}).get("status"),
                "configured": services_metrics.get("twilio", {}).get("configured"),
                "delivery_stats_24h": services_metrics.get("twilio", {}).get("delivery_stats_24h"),
                "error": services_metrics.get("twilio", {}).get("error"),
            },
        },
    }

    return {
        "status": "success",
        "snapshot_id": str(result.inserted_id),
        "timestamp": snapshot["snapshot_time"].isoformat() + "Z",
        "metrics": metrics_summary,
    }


@router.get("/errors/recent")
async def get_recent_errors(
    limit: int = Query(50, ge=1, le=200, description="Number of errors per page"),
    cursor: Optional[str] = Query(None, description="Cursor for pagination (last error_id from previous page)"),
    direction: str = Query("next", description="Pagination direction: 'next' or 'prev'"),
    severity: Optional[str] = Query(None, description="Filter by severity: all, critical, warning"),
    acknowledged: Optional[bool] = Query(None, description="Filter by acknowledged status"),
    current_user: ExtendedAuthUser = Depends(require_root_admin)
) -> Dict[str, Any]:
    """
    Get recent errors with filtering and cursor-based pagination.

    Cursor-based pagination provides O(1) performance regardless of offset,
    unlike skip() which degrades at high offsets.

    Args:
        limit: Number of errors per page (1-200)
        cursor: The error_id from the last item of the previous page
        direction: 'next' for older errors, 'prev' for newer errors
        severity: Filter by severity level
        acknowledged: Filter by acknowledged status
    """
    now = datetime.utcnow()
    default_cutoff = now - timedelta(days=30)

    # Build base query for errors collection
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

    # Get total count for UI display
    total_errors = 0
    total_audit = 0
    try:
        total_errors = await mongo.db["errors"].count_documents(errors_query)
    except Exception as exc:
        logger.warning("Failed to count errors: %s", exc)

    # Build audit_logs query for fallback
    audit_query: Dict[str, Any] = {
        "timestamp": {"$gte": default_cutoff},
        "response_status": {"$gte": 400},
    }
    if severity == "critical":
        audit_query["response_status"] = {"$gte": 500}
    elif severity == "warning":
        audit_query["response_status"] = {"$gte": 400, "$lt": 500}

    # Only count audit_logs if not filtering for acknowledged=True
    if acknowledged is not True:
        try:
            total_audit = await mongo.db["audit_logs"].count_documents(audit_query)
        except Exception as exc:
            logger.warning("Failed to count audit_logs: %s", exc)

    total_count = total_errors + total_audit

    # Fetch errors with cursor-based pagination
    errors_docs: List[Dict[str, Any]] = []
    seen_ids = set()

    def extend_errors(docs: Iterable[Dict[str, Any]], max_items: int):
        added = 0
        for doc in docs:
            if added >= max_items:
                break
            doc_identifier = doc.get("error_id") or doc.get("_id")
            doc_identifier_str = str(doc_identifier) if doc_identifier is not None else None
            if doc_identifier_str and doc_identifier_str in seen_ids:
                continue
            if doc_identifier_str:
                seen_ids.add(doc_identifier_str)
            errors_docs.append(doc)
            added += 1

    try:
        # Apply cursor-based pagination using _id range query
        cursor_query = errors_query.copy()

        if cursor:
            # Find the cursor document to get its _id for range query
            cursor_doc = None
            if ObjectId.is_valid(cursor):
                cursor_doc = await mongo.db["errors"].find_one({"_id": ObjectId(cursor)})
            if not cursor_doc:
                cursor_doc = await mongo.db["errors"].find_one({"error_id": cursor})

            if cursor_doc and "_id" in cursor_doc:
                cursor_id = cursor_doc["_id"]
                # For descending sort (newest first):
                # - "next" page: get items with _id < cursor_id (older)
                # - "prev" page: get items with _id > cursor_id (newer)
                if direction == "prev":
                    cursor_query["_id"] = {"$gt": cursor_id}
                    sort_direction = 1  # Ascending to get items just after cursor
                else:
                    cursor_query["_id"] = {"$lt": cursor_id}
                    sort_direction = -1  # Descending (normal order)
            else:
                sort_direction = -1
        else:
            sort_direction = -1  # Default: newest first

        # Fetch one extra to determine if there are more pages
        fetch_limit = limit + 1
        db_cursor = mongo.db["errors"].find(cursor_query).sort("_id", sort_direction).limit(fetch_limit)
        fetched_docs = await db_cursor.to_list(length=fetch_limit)

        # If going backwards, reverse to maintain consistent order
        if direction == "prev" and cursor:
            fetched_docs.reverse()

        # Check if there are more results
        has_more = len(fetched_docs) > limit
        if has_more:
            fetched_docs = fetched_docs[:limit]

        extend_errors(fetched_docs, limit)

    except Exception as exc:
        logger.warning("Failed to query self-hosted errors collection: %s", exc)

    # Include audit_logs for remaining items if needed (only for first page without cursor)
    include_audit_fallback = acknowledged is not True and len(errors_docs) < limit and not cursor
    if include_audit_fallback:
        remaining = limit - len(errors_docs)
        if remaining > 0:
            audit_cursor = mongo.db["audit_logs"].find(audit_query).sort("timestamp", -1).limit(remaining)
            extend_errors(await audit_cursor.to_list(length=remaining), remaining)

    errors_docs.sort(
        key=lambda doc: _coerce_datetime(doc.get("timestamp")) or datetime.min,
        reverse=True
    )
    normalized_errors = [_extract_error_summary(error) for error in errors_docs]

    # Calculate cursors for next/prev navigation
    next_cursor = None
    prev_cursor = None

    if normalized_errors:
        # Next cursor: last item's error_id (for fetching older errors)
        next_cursor = normalized_errors[-1].get("error_id") if has_more or (cursor and direction == "prev") else None
        # Prev cursor: first item's error_id (for fetching newer errors)
        prev_cursor = normalized_errors[0].get("error_id") if cursor else None

    total_pages = (total_count + limit - 1) // limit if limit > 0 else 1

    return {
        "errors": normalized_errors,
        "total": total_count,
        "limit": limit,
        "total_pages": total_pages,
        "has_next": next_cursor is not None,
        "has_prev": prev_cursor is not None,
        "next_cursor": next_cursor,
        "prev_cursor": prev_cursor,
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
    """Mark an error as acknowledged in errors or audit_logs collection"""

    try:
        acknowledged_at = datetime.utcnow()
        update_payload = {
            "$set": {
                "acknowledged": True,
                "acknowledged_by": current_user.email,
                "acknowledged_at": acknowledged_at
            }
        }

        # Try errors collection first - by error_id field
        result = await mongo.db["errors"].update_one(
            {"error_id": error_id},
            update_payload
        )

        # Try errors collection by ObjectId if not found
        if result.modified_count == 0 and ObjectId.is_valid(error_id):
            result = await mongo.db["errors"].update_one(
                {"_id": ObjectId(error_id)},
                update_payload
            )

        # Try audit_logs collection as fallback (these only have _id, not error_id)
        if result.modified_count == 0 and ObjectId.is_valid(error_id):
            result = await mongo.db["audit_logs"].update_one(
                {"_id": ObjectId(error_id)},
                update_payload
            )

        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Error not found")

        return {
            "status": "success",
            "acknowledged": True,
            "acknowledged_by": current_user.email,
            "acknowledged_at": acknowledged_at.isoformat() + "Z"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to acknowledge error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


class BulkAcknowledgeRequest(BaseModel):
    error_ids: List[str]
    delete_after_acknowledge: bool = False


class ErrorExportFormat(str):
    JSON = "json"
    CSV = "csv"


@router.post("/errors/acknowledge-bulk")
async def acknowledge_errors_bulk(
    request: BulkAcknowledgeRequest,
    current_user: ExtendedAuthUser = Depends(require_root_admin)
) -> Dict[str, Any]:
    """Acknowledge multiple errors in both errors and audit_logs collections"""

    try:
        acknowledged_at = datetime.utcnow()
        update_payload = {
            "$set": {
                "acknowledged": True,
                "acknowledged_by": current_user.email,
                "acknowledged_at": acknowledged_at
            }
        }

        # Build filter for both error_id and ObjectId matches
        object_ids = [ObjectId(eid) for eid in request.error_ids if ObjectId.is_valid(eid)]

        # Update errors collection (supports both error_id field and _id)
        errors_result = await mongo.db["errors"].update_many(
            {
                "$or": [
                    {"error_id": {"$in": request.error_ids}},
                    {"_id": {"$in": object_ids}}
                ]
            },
            update_payload
        )

        # Update audit_logs collection (only has _id, not error_id field)
        audit_result = await mongo.db["audit_logs"].update_many(
            {"_id": {"$in": object_ids}},
            update_payload
        )

        total_acknowledged = errors_result.modified_count + audit_result.modified_count

        return {
            "status": "success",
            "acknowledged_count": total_acknowledged,
            "errors_acknowledged": errors_result.modified_count,
            "audit_logs_acknowledged": audit_result.modified_count,
            "requested_count": len(request.error_ids),
            "acknowledged_by": current_user.email,
            "acknowledged_at": acknowledged_at.isoformat() + "Z"
        }

    except Exception as e:
        logger.error(f"Failed to bulk acknowledge errors: {str(e)}")
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
        "cutoff_date": cutoff_date.isoformat() + "Z"
    }
