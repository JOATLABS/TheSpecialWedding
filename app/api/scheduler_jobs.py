"""
Scheduler Jobs API

Endpoints that can be triggered by external schedulers (cron, Coolify scheduled tasks).
These endpoints process periodic jobs like task reminders, cleanup, etc.

Security: These endpoints require a scheduler API key to prevent unauthorized access.
Set SCHEDULER_API_KEY environment variable.

Example cron setup (every 5 minutes):
    */5 * * * * curl -X POST https://api.thespecialwedding.io/scheduler/task-reminders \
        -H "X-Scheduler-Key: YOUR_SCHEDULER_API_KEY"
"""

import os
import logging
from fastapi import APIRouter, HTTPException, Header, Query, BackgroundTasks
from typing import Optional
from datetime import datetime, timezone

from app.services.task_reminder_service import task_reminder_service

logger = logging.getLogger(__name__)

router = APIRouter()


def verify_scheduler_key(x_scheduler_key: Optional[str] = Header(None)):
    """Verify the scheduler API key"""
    expected_key = os.getenv("SCHEDULER_API_KEY")

    if not expected_key:
        logger.warning("SCHEDULER_API_KEY not configured - scheduler endpoints disabled")
        raise HTTPException(
            status_code=503,
            detail="Scheduler endpoints not configured. Set SCHEDULER_API_KEY environment variable."
        )

    if not x_scheduler_key or x_scheduler_key != expected_key:
        logger.warning("Invalid scheduler key attempted")
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing scheduler API key"
        )

    return True


@router.post("/task-reminders", tags=["Scheduler"])
async def process_task_reminders(
    background_tasks: BackgroundTasks,
    x_scheduler_key: Optional[str] = Header(None),
    dry_run: bool = Query(False, description="If true, only report what would be sent"),
    sync: bool = Query(False, description="If true, run synchronously instead of in background")
):
    """
    Process task reminders and send push notifications.

    This endpoint should be called by an external scheduler (cron job) every 5-15 minutes.
    It checks for calendar tasks with reminder_minutes set that are due for notification
    and sends push notifications via Web Push API.

    Headers:
        X-Scheduler-Key: Required scheduler API key

    Query Params:
        dry_run: If true, only logs what would be sent without actually sending
        sync: If true, runs synchronously and returns results (useful for debugging)
    """
    verify_scheduler_key(x_scheduler_key)

    if sync:
        # Run synchronously and return results
        results = await task_reminder_service.process_due_reminders(dry_run=dry_run)
        return results
    else:
        # Run in background
        background_tasks.add_task(
            task_reminder_service.process_due_reminders,
            dry_run=dry_run
        )
        return {
            "status": "accepted",
            "message": "Task reminder processing started in background",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


@router.post("/cleanup-reminders", tags=["Scheduler"])
async def cleanup_old_reminders(
    x_scheduler_key: Optional[str] = Header(None),
    days_old: int = Query(7, description="Remove records older than this many days")
):
    """
    Clean up old sent reminder records to prevent database bloat.

    This should be called less frequently, e.g., once per day.
    """
    verify_scheduler_key(x_scheduler_key)

    deleted_count = await task_reminder_service.cleanup_old_records(days_old=days_old)

    return {
        "status": "success",
        "deleted_count": deleted_count,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/health", tags=["Scheduler"])
async def scheduler_health():
    """
    Health check endpoint for scheduler monitoring.
    Does not require authentication.
    """
    scheduler_configured = bool(os.getenv("SCHEDULER_API_KEY"))

    return {
        "status": "healthy",
        "scheduler_configured": scheduler_configured,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
