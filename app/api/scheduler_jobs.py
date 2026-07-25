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

import hashlib
import hmac
import logging
import os
import time
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query, Request

from app.services.calendar_job_service import calendar_job_service
from app.services.calendar_maintenance_service import calendar_maintenance_service
from app.services.planner_onboarding_email_service import (
    planner_onboarding_email_service,
)
from app.services.task_reminder_service import task_reminder_service
from app.utils.scheduler_job_tracker import (
    JOB_CALENDAR_INVITE_JOBS,
    JOB_CALENDAR_MAINTENANCE,
    JOB_CLEANUP_REMINDERS,
    JOB_PLANNER_ONBOARDING_EMAILS,
    JOB_TASK_REMINDERS,
    track_scheduler_job,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Maximum allowed clock skew for HMAC timestamp validation (5 minutes)
_HMAC_MAX_SKEW_SECONDS = 300


def _verify_hmac(
    request: Request,
    x_scheduler_signature: str | None,
    x_scheduler_timestamp: str | None,
):
    """Verify HMAC-SHA256 request signature with timestamp replay protection.

    Callers must send:
        X-Scheduler-Timestamp: <unix epoch seconds>
        X-Scheduler-Signature: sha256=<hex digest>

    The signed payload is: ``<timestamp>.<method>.<path>``
    """
    secret = os.getenv("SCHEDULER_HMAC_SECRET")
    if not secret:
        return  # HMAC not configured — fall through to legacy key check

    if not x_scheduler_signature or not x_scheduler_timestamp:
        raise HTTPException(
            status_code=401, detail="Missing HMAC signature or timestamp header"
        )

    # Replay protection: reject timestamps too far from server time
    try:
        ts = int(x_scheduler_timestamp)
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid scheduler timestamp")

    if abs(time.time() - ts) > _HMAC_MAX_SKEW_SECONDS:
        logger.warning(
            "Scheduler HMAC timestamp outside skew window: %s", x_scheduler_timestamp
        )
        raise HTTPException(
            status_code=401,
            detail="Scheduler timestamp expired or too far in the future",
        )

    # Build signed payload: timestamp.METHOD.path
    payload = f"{x_scheduler_timestamp}.{request.method}.{request.url.path}"
    expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    received = x_scheduler_signature.removeprefix("sha256=")

    if not hmac.compare_digest(expected, received):
        logger.warning("Scheduler HMAC signature mismatch")
        raise HTTPException(status_code=401, detail="Invalid scheduler signature")


def verify_scheduler_key(
    request: Request,
    x_scheduler_key: str | None = Header(None),
    x_scheduler_signature: str | None = Header(None),
    x_scheduler_timestamp: str | None = Header(None),
):
    """Verify scheduler authentication.

    Supports two modes:
    1. HMAC-SHA256 signing (preferred) — set SCHEDULER_HMAC_SECRET env var
    2. Legacy static API key — set SCHEDULER_API_KEY env var
    """
    hmac_secret = os.getenv("SCHEDULER_HMAC_SECRET")

    # Prefer HMAC if configured
    if hmac_secret:
        _verify_hmac(request, x_scheduler_signature, x_scheduler_timestamp)
        return True

    # Fall back to legacy static key
    expected_key = os.getenv("SCHEDULER_API_KEY")

    if not expected_key:
        logger.warning(
            "Neither SCHEDULER_HMAC_SECRET nor SCHEDULER_API_KEY configured - scheduler endpoints disabled"
        )
        raise HTTPException(
            status_code=503,
            detail="Scheduler endpoints not configured. Set SCHEDULER_HMAC_SECRET or SCHEDULER_API_KEY environment variable.",
        )

    if not x_scheduler_key or not hmac.compare_digest(x_scheduler_key, expected_key):
        logger.warning("Invalid scheduler key attempted")
        raise HTTPException(
            status_code=401, detail="Invalid or missing scheduler API key"
        )

    return True


@router.post("/task-reminders", tags=["Scheduler"])
async def process_task_reminders(
    request: Request,
    background_tasks: BackgroundTasks,
    x_scheduler_key: str | None = Header(None),
    x_scheduler_signature: str | None = Header(None),
    x_scheduler_timestamp: str | None = Header(None),
    dry_run: bool = Query(False, description="If true, only report what would be sent"),
    sync: bool = Query(
        False, description="If true, run synchronously instead of in background"
    ),
):
    """
    Process task reminders and send push notifications.

    This endpoint should be called by an external scheduler (cron job) every 5-15 minutes.
    It checks for calendar tasks with reminder_minutes set that are due for notification
    and sends push notifications via Web Push API.

    Headers:
        X-Scheduler-Signature: sha256=<HMAC hex digest> (preferred)
        X-Scheduler-Timestamp: <unix epoch seconds> (required with signature)
        X-Scheduler-Key: Legacy static API key (fallback)

    Query Params:
        dry_run: If true, only logs what would be sent without actually sending
        sync: If true, runs synchronously and returns results (useful for debugging)
    """
    verify_scheduler_key(
        request, x_scheduler_key, x_scheduler_signature, x_scheduler_timestamp
    )

    params = {"dry_run": dry_run}

    if sync:
        # Run synchronously and return results — tracker wraps the service call
        # so we persist start/finish/status for the Scheduler tab.
        async with track_scheduler_job(JOB_TASK_REMINDERS, params) as _ctx:
            results = await task_reminder_service.process_due_reminders(dry_run=dry_run)
            _ctx["result"] = results
        return results

    async def _tracked_task_reminders() -> None:
        # BackgroundTasks runs this after the response is sent; the tracker
        # persists the outcome even though the HTTP caller never sees it.
        async with track_scheduler_job(JOB_TASK_REMINDERS, params) as _ctx:
            _ctx["result"] = await task_reminder_service.process_due_reminders(
                dry_run=dry_run
            )

    background_tasks.add_task(_tracked_task_reminders)
    return {
        "status": "accepted",
        "message": "Task reminder processing started in background",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.post("/cleanup-reminders", tags=["Scheduler"])
async def cleanup_old_reminders(
    request: Request,
    x_scheduler_key: str | None = Header(None),
    x_scheduler_signature: str | None = Header(None),
    x_scheduler_timestamp: str | None = Header(None),
    days_old: int = Query(7, description="Remove records older than this many days"),
):
    """
    Clean up old sent reminder records to prevent database bloat.

    This should be called less frequently, e.g., once per day.
    """
    verify_scheduler_key(
        request, x_scheduler_key, x_scheduler_signature, x_scheduler_timestamp
    )

    async with track_scheduler_job(
        JOB_CLEANUP_REMINDERS, {"days_old": days_old}
    ) as _ctx:
        deleted_count = await task_reminder_service.cleanup_old_records(
            days_old=days_old
        )
        _ctx["result"] = {"deleted_count": deleted_count}

    return {
        "status": "success",
        "deleted_count": deleted_count,
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/health", tags=["Scheduler"])
async def scheduler_health():
    """
    Health check endpoint for scheduler monitoring.
    Does not require authentication.
    """
    hmac_configured = bool(os.getenv("SCHEDULER_HMAC_SECRET"))
    legacy_key_configured = bool(os.getenv("SCHEDULER_API_KEY"))
    scheduler_configured = hmac_configured or legacy_key_configured
    if hmac_configured:
        auth_mode = "hmac"
    elif legacy_key_configured:
        auth_mode = "api_key"
    else:
        auth_mode = "disabled"

    return {
        "status": "healthy",
        "scheduler_configured": scheduler_configured,
        "auth_mode": auth_mode,
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.post("/planner-onboarding-emails", tags=["Scheduler"])
async def process_planner_onboarding_emails(
    request: Request,
    background_tasks: BackgroundTasks,
    x_scheduler_key: str | None = Header(None),
    x_scheduler_signature: str | None = Header(None),
    x_scheduler_timestamp: str | None = Header(None),
    dry_run: bool = Query(
        False, description="If true, report what would be sent without sending"
    ),
    sync: bool = Query(
        False, description="If true, run synchronously and return results"
    ),
):
    """
    Process the wedding planner onboarding email sequence.

    This endpoint is intended for a daily scheduler and sends due onboarding
    emails at day 1, 3, 5, 8, and 12 after the day-0 welcome email.
    """
    verify_scheduler_key(
        request, x_scheduler_key, x_scheduler_signature, x_scheduler_timestamp
    )

    params = {"dry_run": dry_run}

    if sync:
        async with track_scheduler_job(JOB_PLANNER_ONBOARDING_EMAILS, params) as _ctx:
            result = await planner_onboarding_email_service.process_due_emails(
                dry_run=dry_run
            )
            _ctx["result"] = result
        return result

    async def _tracked_planner_onboarding() -> None:
        async with track_scheduler_job(JOB_PLANNER_ONBOARDING_EMAILS, params) as _ctx:
            _ctx["result"] = await planner_onboarding_email_service.process_due_emails(
                dry_run=dry_run
            )

    background_tasks.add_task(_tracked_planner_onboarding)
    return {
        "status": "accepted",
        "message": "Planner onboarding email processing started in background",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.post("/calendar-invite-jobs", tags=["Scheduler"])
async def process_calendar_invite_jobs(
    request: Request,
    background_tasks: BackgroundTasks,
    x_scheduler_key: str | None = Header(None),
    x_scheduler_signature: str | None = Header(None),
    x_scheduler_timestamp: str | None = Header(None),
    limit: int = Query(25, ge=1, le=200),
    sync: bool = Query(
        False, description="If true, run synchronously and return processing results"
    ),
):
    """Process queued calendar invite jobs off the API request path."""
    verify_scheduler_key(
        request, x_scheduler_key, x_scheduler_signature, x_scheduler_timestamp
    )

    params = {"limit": limit}

    if sync:
        async with track_scheduler_job(JOB_CALENDAR_INVITE_JOBS, params) as _ctx:
            results = await calendar_job_service.process_due_jobs(limit=limit)
            _ctx["result"] = results
        return {
            "status": "success",
            "results": results,
            "timestamp": datetime.now(UTC).isoformat(),
        }

    async def _tracked_calendar_invite_jobs() -> None:
        async with track_scheduler_job(JOB_CALENDAR_INVITE_JOBS, params) as _ctx:
            _ctx["result"] = await calendar_job_service.process_due_jobs(limit=limit)

    background_tasks.add_task(_tracked_calendar_invite_jobs)
    return {
        "status": "accepted",
        "message": "Calendar invite job processing started in background",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.post("/calendar-maintenance", tags=["Scheduler"])
async def process_calendar_maintenance(
    request: Request,
    background_tasks: BackgroundTasks,
    x_scheduler_key: str | None = Header(None),
    x_scheduler_signature: str | None = Header(None),
    x_scheduler_timestamp: str | None = Header(None),
    retry_limit: int = Query(50, ge=1, le=200),
    drift_limit: int = Query(50, ge=1, le=200),
    sync: bool = Query(
        False, description="If true, run synchronously and return processing results"
    ),
):
    """Process due sync retries and provider drift checks."""
    verify_scheduler_key(
        request, x_scheduler_key, x_scheduler_signature, x_scheduler_timestamp
    )

    params = {"retry_limit": retry_limit, "drift_limit": drift_limit}

    async def _run_maintenance() -> dict[str, object]:
        retry_results = await calendar_maintenance_service.process_due_sync_retries(
            limit=retry_limit
        )
        drift_results = await calendar_maintenance_service.run_drift_checks(
            limit=drift_limit
        )
        return {
            "retry_results": retry_results,
            "drift_results": drift_results,
        }

    if sync:
        async with track_scheduler_job(JOB_CALENDAR_MAINTENANCE, params) as _ctx:
            results = await _run_maintenance()
            _ctx["result"] = results
        return {
            "status": "success",
            "results": results,
            "timestamp": datetime.now(UTC).isoformat(),
        }

    async def _tracked_maintenance() -> None:
        # Combined into a single tracked run (one row per tick, not two) —
        # drift + retry are two halves of the same logical job from the
        # monitoring UI's perspective.
        async with track_scheduler_job(JOB_CALENDAR_MAINTENANCE, params) as _ctx:
            _ctx["result"] = await _run_maintenance()

    background_tasks.add_task(_tracked_maintenance)
    return {
        "status": "accepted",
        "message": "Calendar maintenance started in background",
        "timestamp": datetime.now(UTC).isoformat(),
    }
