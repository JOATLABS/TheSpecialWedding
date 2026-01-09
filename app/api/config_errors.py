"""
Configuration Error Reporting API

Public endpoint for frontend to report critical configuration errors.
No auth required since the app may be broken due to misconfiguration.
"""

import logging
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Request

from app.core.database import mongo
from app.services.config_validator import ROOT_ADMIN_EMAIL

logger = logging.getLogger(__name__)

router = APIRouter()

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


class ConfigErrorReport(BaseModel):
    error_type: str
    message: str
    variable_name: Optional[str] = None
    current_value: Optional[str] = None
    hostname: Optional[str] = None
    user_agent: Optional[str] = None


@router.post("/report-config-error")
async def report_config_error(report: ConfigErrorReport, request: Request):
    """
    Report a frontend configuration error.
    Logs to errors collection, creates notification, sends Ntfy alert.
    """
    error_id = str(uuid.uuid4())
    now = datetime.utcnow()

    client_ip = _get_client_ip(request)

    error_doc = {
        "error_id": error_id,
        "timestamp": now,
        "error_type": "ConfigurationError",
        "error_message": report.message,
        "severity": "critical",
        "acknowledged": False,
        "source": "frontend",
        "request": {
            "method": "FRONTEND_CONFIG",
            "path": report.hostname or "unknown",
            "client_ip": client_ip,
        },
        "metadata": {
            "variable_name": report.variable_name,
            "current_value": report.current_value,
            "hostname": report.hostname,
            "user_agent": report.user_agent,
        }
    }

    try:
        await mongo.db["errors"].insert_one(error_doc)
        logger.error(f"Config error logged: {error_id} - {report.message}")
    except Exception as e:
        logger.error(f"Failed to log config error: {e}")

    await _create_notification(error_id, report, now)
    await _send_ntfy_alert(report)

    return {"error_id": error_id, "reported": True}


async def _create_notification(error_id: str, report: ConfigErrorReport, timestamp: datetime):
    """Create in-app notification for root admin."""
    try:
        notification = {
            "title": f"CRITICAL: {report.error_type}",
            "message": report.message,
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
                "variable_name": report.variable_name,
                "hostname": report.hostname,
            }
        }

        existing = await mongo.db["notifications"].find_one({
            "type": "system_config",
            "status": "active",
            "metadata.variable_name": report.variable_name
        })

        if existing:
            await mongo.db["notifications"].update_one(
                {"_id": existing["_id"]},
                {"$set": {"message": report.message, "updated_at": timestamp}}
            )
        else:
            await mongo.db["notifications"].insert_one(notification)

    except Exception as e:
        logger.error(f"Failed to create notification: {e}")


async def _send_ntfy_alert(report: ConfigErrorReport):
    """Send Ntfy push notification."""
    ntfy = _get_ntfy_service()
    if not ntfy:
        return

    try:
        await ntfy.send_admin_alert(
            title=f"CRITICAL: {report.error_type}",
            message=f"{report.message}\n\nVariable: {report.variable_name}\nHost: {report.hostname}",
            priority="urgent",
            tags=["rotating_light", "warning", "gear"]
        )
    except Exception as e:
        logger.error(f"Failed to send Ntfy alert: {e}")


def _get_client_ip(request: Request) -> str:
    for header in ["X-Forwarded-For", "X-Real-IP", "CF-Connecting-IP"]:
        ip = request.headers.get(header)
        if ip:
            return ip.split(",")[0].strip()
    return getattr(request.client, "host", "unknown")