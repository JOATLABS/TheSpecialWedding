"""
Configuration Error Reporting API

Public endpoint for frontend to report critical configuration errors.
Rate-limited and deduplicated to prevent abuse.
"""

import logging
import uuid
import re
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict
from pydantic import BaseModel, field_validator
from fastapi import APIRouter, Request, HTTPException

from app.core.database import mongo
from app.core.settings import settings
from app.utils.security_utils import rate_limiter

logger = logging.getLogger(__name__)

router = APIRouter()

# Deduplication: track recent error hashes (in-memory)
_recent_errors: Dict[str, datetime] = {}
DEDUP_WINDOW = 300  # 5 minutes

_ntfy_service = None


def _get_ntfy_service():
    global _ntfy_service
    if _ntfy_service is None:
        try:
            from app.services.ntfy_service import ntfy_service
            _ntfy_service = ntfy_service
        except ImportError:
            _ntfy_service = False
    return _ntfy_service if _ntfy_service else None


def _sanitize(value: Optional[str], max_len: int = 500) -> Optional[str]:
    if not value:
        return None
    value = re.sub(r'<[^>]+>', '', value)
    return value[:max_len]


class ConfigErrorReport(BaseModel):
    error_type: str
    message: str
    variable_name: Optional[str] = None
    current_value: Optional[str] = None
    hostname: Optional[str] = None
    user_agent: Optional[str] = None

    @field_validator('error_type', 'message', 'variable_name', 'hostname', mode='before')
    @classmethod
    def sanitize_strings(cls, v):
        if isinstance(v, str):
            return re.sub(r'<[^>]+>', '', v)[:500]
        return v

    @field_validator('current_value', mode='before')
    @classmethod
    def sanitize_value(cls, v):
        if isinstance(v, str):
            return re.sub(r'<[^>]+>', '', v)[:200]
        return v


def _is_duplicate(report: ConfigErrorReport) -> bool:
    now = datetime.utcnow()
    cutoff = now - timedelta(seconds=DEDUP_WINDOW)

    expired = [k for k, v in _recent_errors.items() if v < cutoff]
    for k in expired:
        del _recent_errors[k]

    error_hash = hashlib.md5(
        f"{report.error_type}:{report.variable_name}:{report.hostname}".encode()
    ).hexdigest()

    if error_hash in _recent_errors:
        return True

    _recent_errors[error_hash] = now
    return False


@router.post("/report-config-error")
async def report_config_error(report: ConfigErrorReport, request: Request):
    client_ip = _get_client_ip(request)

    # Use existing rate limiter
    if not rate_limiter.check_rate_limit(
        f"config_error:{client_ip}",
        limit=settings.rate_limit_auth_calls,
        window_seconds=settings.rate_limit_auth_period
    ):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    if _is_duplicate(report):
        return {"error_id": None, "reported": False, "reason": "duplicate"}

    error_id = str(uuid.uuid4())
    now = datetime.utcnow()

    # Check for existing unacknowledged error
    existing = await mongo.db["errors"].find_one({
        "error_type": "ConfigurationError",
        "metadata.variable_name": report.variable_name,
        "acknowledged": False,
        "timestamp": {"$gte": now - timedelta(hours=24)}
    })

    if existing:
        return {"error_id": str(existing.get("error_id")), "reported": False, "reason": "exists"}

    error_doc = {
        "error_id": error_id,
        "timestamp": now,
        "error_type": "ConfigurationError",
        "error_message": _sanitize(report.message),
        "severity": "critical",
        "acknowledged": False,
        "source": "frontend",
        "request": {
            "method": "FRONTEND_CONFIG",
            "path": _sanitize(report.hostname, 100) or "unknown",
            "client_ip": client_ip,
        },
        "metadata": {
            "variable_name": _sanitize(report.variable_name, 100),
            "current_value": _sanitize(report.current_value, 200),
            "hostname": _sanitize(report.hostname, 100),
        }
    }

    try:
        await mongo.db["errors"].insert_one(error_doc)
        logger.error(f"Config error: {error_id} - {report.variable_name}")
    except Exception as e:
        logger.error(f"Failed to log config error: {e}")
        raise HTTPException(status_code=500, detail="Failed to log error")

    await _create_notification(error_id, report, now)
    await _send_ntfy_alert(report)

    return {"error_id": error_id, "reported": True}


async def _create_notification(error_id: str, report: ConfigErrorReport, timestamp: datetime):
    try:
        existing = await mongo.db["notifications"].find_one({
            "type": "system_config",
            "status": "active",
            "metadata.variable_name": report.variable_name
        })

        if existing:
            await mongo.db["notifications"].update_one(
                {"_id": existing["_id"]},
                {"$set": {"updated_at": timestamp}}
            )
            return

        notification = {
            "title": f"CRITICAL: {_sanitize(report.error_type, 50)}",
            "message": _sanitize(report.message, 500),
            "type": "system_config",
            "target_audience": "root_admin",
            "created_by": "system",
            "created_at": timestamp,
            "updated_at": timestamp,
            "is_dismissible": True,
            "priority": "critical",
            "status": "active",
            "read_by": [],
            "dismissed_by": [],
            "metadata": {
                "error_id": error_id,
                "variable_name": _sanitize(report.variable_name, 100),
                "hostname": _sanitize(report.hostname, 100),
            }
        }

        await mongo.db["notifications"].insert_one(notification)
    except Exception as e:
        logger.error(f"Failed to create notification: {e}")


async def _send_ntfy_alert(report: ConfigErrorReport):
    ntfy = _get_ntfy_service()
    if not ntfy:
        return

    try:
        await ntfy.send_admin_alert(
            title=f"Config Error: {_sanitize(report.variable_name, 50)}",
            message=f"{_sanitize(report.message, 200)}\nHost: {_sanitize(report.hostname, 50)}",
            priority="urgent",
            tags=["rotating_light", "gear"]
        )
    except Exception as e:
        logger.error(f"Failed to send Ntfy alert: {e}")


def _get_client_ip(request: Request) -> str:
    for header in ["X-Forwarded-For", "X-Real-IP", "CF-Connecting-IP"]:
        ip = request.headers.get(header)
        if ip:
            return ip.split(",")[0].strip()[:45]
    return getattr(request.client, "host", "unknown")[:45]