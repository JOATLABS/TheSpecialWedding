"""
Scheduler Job Tracker

Instruments scheduler endpoints in ``app/api/scheduler_jobs.py`` so every run
writes a row to the ``scheduler_job_runs`` Mongo collection. This is the
source of truth for the ROOT_ADMIN Scheduler tab on ``/admin/platform``.

The tracker is intentionally runtime-agnostic — it doesn't care whether the
request came from Cloudflare Workers cron, the legacy GitHub Actions
``calendar-scheduler.yml``, manual curl, or a future runner. It only cares
that the backend actually executed the job.

Usage (wrap the SERVICE CALL, not the endpoint handler, so FastAPI
BackgroundTasks still get tracked):

    async def _run():
        async with track_scheduler_job("task-reminders", {"dry_run": dry_run}) as ctx:
            ctx["result"] = await task_reminder_service.process_due_reminders(
                dry_run=dry_run
            )

    background_tasks.add_task(_run)

Why a ``ctx`` container instead of returning the result? Because the context
manager needs to persist the service's return value after the ``yield``, but
``async with`` doesn't give a way to bind the yield target back into the
caller's local unless we use a mutable object.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, Optional
from uuid import uuid4

from app.core.database import mongo

logger = logging.getLogger(__name__)

JOB_RUNS_COLLECTION = "scheduler_job_runs"

# ─── Job registry ──────────────────────────────────────────────────────────
# Keep this list in sync with the five endpoints in app/api/scheduler_jobs.py
# AND the cron schedules in cloudflare-workers/scheduler.wrangler.toml.
#
# expected_interval_minutes drives the "stale" flag in the admin UI: if a job
# hasn't completed successfully in > (interval * stale_multiplier), it is
# flagged red. Daily jobs get a looser multiplier because they naturally have
# a larger jitter window.

JOB_CALENDAR_INVITE_JOBS = "calendar-invite-jobs"
JOB_TASK_REMINDERS = "task-reminders"
JOB_CALENDAR_MAINTENANCE = "calendar-maintenance"
JOB_CLEANUP_REMINDERS = "cleanup-reminders"
JOB_PLANNER_ONBOARDING_EMAILS = "planner-onboarding-emails"

KNOWN_JOBS: Dict[str, Dict[str, Any]] = {
    JOB_CALENDAR_INVITE_JOBS: {
        "label": "Calendar invite jobs",
        "description": "Processes queued calendar invite delivery jobs.",
        "expected_interval_minutes": 5,
        "stale_multiplier": 3,  # red if > 15 min with no success
    },
    JOB_TASK_REMINDERS: {
        "label": "Task reminders",
        "description": "Sends push notifications for due task reminders.",
        "expected_interval_minutes": 5,
        "stale_multiplier": 3,
    },
    JOB_CALENDAR_MAINTENANCE: {
        "label": "Calendar maintenance",
        "description": "Retries failed calendar syncs and runs drift checks.",
        "expected_interval_minutes": 15,
        "stale_multiplier": 3,  # red if > 45 min with no success
    },
    JOB_CLEANUP_REMINDERS: {
        "label": "Cleanup reminders",
        "description": "Prunes old sent-reminder records to keep the DB lean.",
        "expected_interval_minutes": 24 * 60,  # daily
        "stale_multiplier": 2,  # red if > 48h with no success
    },
    JOB_PLANNER_ONBOARDING_EMAILS: {
        "label": "Planner onboarding emails",
        "description": "Drip sequence: day 1, 3, 5, 8, 12 after signup.",
        "expected_interval_minutes": 24 * 60,  # daily
        "stale_multiplier": 2,
    },
}

STATUS_RUNNING = "running"
STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"


# ─── Context manager ───────────────────────────────────────────────────────
@asynccontextmanager
async def track_scheduler_job(
    job_name: str,
    params: Optional[Dict[str, Any]] = None,
) -> AsyncIterator[Dict[str, Any]]:
    """Record a scheduler job run to Mongo.

    On entry: inserts a row with ``status="running"``.
    On exit:
      - If no exception: updates to ``status="success"``, writes
        ``ctx["result"]`` to the ``result`` field (if caller set one).
      - If exception: updates to ``status="failed"``, writes the stringified
        exception (truncated to 2000 chars) to ``error``, then re-raises.

    The mutable container yielded to the caller has a ``result`` key that the
    caller can set; whatever ends up there at ``__aexit__`` time is persisted.
    Don't put huge payloads in ``result`` — it's meant for small summary dicts
    like ``{"processed": 12, "failed": 0}``.
    """

    if job_name not in KNOWN_JOBS:
        # Not fatal — we still record it — but log so we notice unregistered jobs.
        logger.warning(
            "track_scheduler_job called with unknown job_name=%r; add it to KNOWN_JOBS",
            job_name,
        )

    run_id = str(uuid4())
    started_at = datetime.now(timezone.utc)
    container: Dict[str, Any] = {"result": None, "run_id": run_id}

    try:
        await mongo.db[JOB_RUNS_COLLECTION].insert_one(
            {
                "_id": run_id,
                "job_name": job_name,
                "started_at": started_at,
                "finished_at": None,
                "status": STATUS_RUNNING,
                "params": params or {},
                "result": None,
                "error": None,
            }
        )
    except Exception:  # noqa: BLE001
        # Don't let Mongo hiccups block the actual job. The job's own errors
        # matter much more than whether we got a row in.
        logger.exception("Failed to record scheduler_job_runs start row")

    try:
        yield container
    except Exception as exc:
        await _safe_update(
            run_id,
            {
                "status": STATUS_FAILED,
                "finished_at": datetime.now(timezone.utc),
                "error": str(exc)[:2000] or exc.__class__.__name__,
            },
        )
        raise
    else:
        await _safe_update(
            run_id,
            {
                "status": STATUS_SUCCESS,
                "finished_at": datetime.now(timezone.utc),
                "result": _truncate_result(container.get("result")),
            },
        )


async def _safe_update(run_id: str, fields: Dict[str, Any]) -> None:
    """Update a run row, swallowing (but logging) Mongo errors."""
    try:
        await mongo.db[JOB_RUNS_COLLECTION].update_one(
            {"_id": run_id},
            {"$set": fields},
        )
    except Exception:  # noqa: BLE001
        logger.exception(
            "Failed to update scheduler_job_runs row %s with %r", run_id, fields
        )


def _truncate_result(result: Any, max_chars: int = 4000) -> Any:
    """Protect Mongo from huge payloads — services sometimes return big dicts."""
    if result is None:
        return None
    try:
        import json

        serialized = json.dumps(result, default=str)
        if len(serialized) <= max_chars:
            return result
        return {
            "_truncated": True,
            "_preview": serialized[:max_chars],
            "_original_size": len(serialized),
        }
    except (TypeError, ValueError):
        # Non-serializable — stringify.
        text = str(result)
        return {"_stringified": text[:max_chars]}


# ─── Query helpers (used by admin_platform_metrics.py) ─────────────────────
async def get_last_run_per_job() -> Dict[str, Optional[Dict[str, Any]]]:
    """Return {job_name: last_run_document_or_None} for every KNOWN_JOBS entry.

    Runs are sorted by started_at desc, so "last" means most recently started.
    """
    pipeline = [
        {"$sort": {"started_at": -1}},
        {
            "$group": {
                "_id": "$job_name",
                "doc": {"$first": "$$ROOT"},
            }
        },
    ]
    cursor = mongo.db[JOB_RUNS_COLLECTION].aggregate(pipeline)
    results: Dict[str, Optional[Dict[str, Any]]] = {name: None for name in KNOWN_JOBS}
    async for row in cursor:
        results[row["_id"]] = row["doc"]
    return results


async def get_last_success_per_job() -> Dict[str, Optional[datetime]]:
    """Return {job_name: last_success_started_at_or_None}."""
    pipeline = [
        {"$match": {"status": STATUS_SUCCESS}},
        {"$sort": {"started_at": -1}},
        {
            "$group": {
                "_id": "$job_name",
                "started_at": {"$first": "$started_at"},
            }
        },
    ]
    cursor = mongo.db[JOB_RUNS_COLLECTION].aggregate(pipeline)
    results: Dict[str, Optional[datetime]] = {name: None for name in KNOWN_JOBS}
    async for row in cursor:
        results[row["_id"]] = row["started_at"]
    return results


async def get_recent_runs_for_job(
    job_name: str, limit: int = 50
) -> list[Dict[str, Any]]:
    """Return the N most recent runs for a single job, newest first."""
    cursor = (
        mongo.db[JOB_RUNS_COLLECTION]
        .find({"job_name": job_name})
        .sort("started_at", -1)
        .limit(limit)
    )
    return await cursor.to_list(length=limit)


def compute_stale_flag(
    job_name: str, last_success_at: Optional[datetime]
) -> Dict[str, Any]:
    """Return {is_stale, threshold_minutes, minutes_since_success}.

    A job is stale if it hasn't had a successful run in longer than
    expected_interval * stale_multiplier. If we have NO successful run on
    record at all, the job is stale by definition (e.g., just deployed).
    """
    job_config = KNOWN_JOBS.get(job_name)
    if not job_config:
        return {
            "is_stale": False,
            "threshold_minutes": None,
            "minutes_since_success": None,
        }

    threshold_minutes = (
        job_config["expected_interval_minutes"] * job_config["stale_multiplier"]
    )

    if last_success_at is None:
        return {
            "is_stale": True,
            "threshold_minutes": threshold_minutes,
            "minutes_since_success": None,
            "reason": "no_successful_run_recorded",
        }

    if last_success_at.tzinfo is None:
        last_success_at = last_success_at.replace(tzinfo=timezone.utc)

    delta = datetime.now(timezone.utc) - last_success_at
    minutes_since = delta.total_seconds() / 60

    return {
        "is_stale": minutes_since > threshold_minutes,
        "threshold_minutes": threshold_minutes,
        "minutes_since_success": round(minutes_since, 1),
    }
