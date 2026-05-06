"""Queue and process background calendar jobs."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any, Optional

from pymongo import ReturnDocument

from app.core.config import settings
from app.core.database import mongo
from app.models.calendar_job import CalendarJobStatus, CalendarJobType
from app.services.meeting_invite_service import meeting_invite_service

logger = logging.getLogger(__name__)

_background_tasks: set[asyncio.Task[Any]] = set()
_MAX_BACKGROUND_TASKS = 50


def _run_background(coro: Any) -> None:
    done = {task for task in _background_tasks if task.done()}
    _background_tasks.difference_update(done)
    if len(_background_tasks) >= _MAX_BACKGROUND_TASKS:
        logger.warning(
            "[CalendarJobs] Background task queue full (%d), dropping wake-up task",
            _MAX_BACKGROUND_TASKS,
        )
        return
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


class CalendarJobService:
    """Database-backed queue for invite delivery and future calendar jobs."""

    def __init__(self) -> None:
        self.jobs_collection = mongo.get_calendar_jobs_collection()

    def _build_invite_dedupe_key(
        self,
        *,
        task: dict[str, Any],
        method: str,
        recipient_emails: list[str],
        reason: str,
    ) -> str:
        seed = json.dumps(
            {
                "task_id": str(task.get("_id")),
                "method": method,
                "reason": reason,
                "meeting_status": task.get("meeting_status"),
                "updated_at": (
                    updated_at_value.isoformat()
                    if isinstance(
                        (updated_at_value := task.get("updated_at")), datetime
                    )
                    else str(task.get("updated_at") or "")
                ),
                "recipient_emails": sorted(recipient_emails),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return sha256(seed.encode("utf-8")).hexdigest()

    def _queue_backoff(self, attempts: int) -> timedelta:
        capped_attempts = min(max(attempts, 1), settings.CALENDAR_JOB_MAX_ATTEMPTS)
        seconds = settings.CALENDAR_JOB_INITIAL_BACKOFF_SECONDS * (
            2 ** (capped_attempts - 1)
        )
        max_seconds = settings.CALENDAR_JOB_INITIAL_BACKOFF_SECONDS * 32
        return timedelta(seconds=min(seconds, max_seconds))

    async def enqueue_invite_job(
        self,
        task: dict[str, Any],
        *,
        method: str,
        recipient_emails: Optional[list[str]] = None,
        reason: str,
        source: str = "planner",
    ) -> list[dict[str, Any]]:
        recipients = sorted(
            {
                email
                for email in (
                    recipient_emails or task.get("couple_attendee_emails", [])
                )
                if email
            }
        )
        if not recipients:
            return []

        queued_invites = await meeting_invite_service.queue_invites(
            task,
            method=method,
            recipient_emails=recipients,
            source=source,
        )
        now = datetime.now(UTC)
        dedupe_key = self._build_invite_dedupe_key(
            task=task,
            method=method,
            recipient_emails=recipients,
            reason=reason,
        )

        await self.jobs_collection.find_one_and_update(
            {"dedupe_key": dedupe_key},
            {
                "$set": {
                    "job_type": CalendarJobType.MEETING_INVITE.value,
                    "status": CalendarJobStatus.QUEUED.value,
                    "task_id": str(task.get("_id")),
                    "owner_planner_id": task.get("owner_planner_id"),
                    "owner_planner_email": task.get("owner_planner_email")
                    or task.get("planner_email"),
                    "payload": {
                        "task": task,
                        "method": method,
                        "reason": reason,
                        "source": source,
                        "recipient_emails": recipients,
                    },
                    "run_at": now,
                    "max_attempts": settings.CALENDAR_JOB_MAX_ATTEMPTS,
                    "last_error": None,
                    "last_error_category": None,
                    "updated_at": now,
                },
                "$setOnInsert": {
                    "created_at": now,
                    "attempts": 0,
                    "dedupe_key": dedupe_key,
                },
                "$unset": {
                    "completed_at": "",
                    "expires_at": "",
                },
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )

        self.kick_due_jobs()
        return queued_invites

    def kick_due_jobs(self) -> None:
        _run_background(self.process_due_jobs(limit=settings.CALENDAR_JOB_BATCH_SIZE))

    async def _claim_due_job(self) -> dict[str, Any] | None:
        now = datetime.now(UTC)
        stale_cutoff = now - timedelta(minutes=5)
        return await self.jobs_collection.find_one_and_update(
            {
                "job_type": CalendarJobType.MEETING_INVITE.value,
                "$or": [
                    {
                        "status": {
                            "$in": [
                                CalendarJobStatus.QUEUED.value,
                                CalendarJobStatus.FAILED.value,
                            ]
                        },
                        "run_at": {"$lte": now},
                    },
                    {
                        "status": CalendarJobStatus.PROCESSING.value,
                        "updated_at": {"$lt": stale_cutoff},
                    },
                ],
            },
            {
                "$set": {
                    "status": CalendarJobStatus.PROCESSING.value,
                    "updated_at": now,
                }
            },
            sort=[("run_at", 1), ("created_at", 1)],
            return_document=ReturnDocument.AFTER,
        )

    async def process_due_jobs(self, *, limit: int) -> dict[str, int]:
        processed = 0
        succeeded = 0
        failed = 0
        while processed < limit:
            job = await self._claim_due_job()
            if not isinstance(job, dict):
                break
            processed += 1
            result = await self._process_job(job)
            if result:
                succeeded += 1
            else:
                failed += 1
        return {"processed": processed, "succeeded": succeeded, "failed": failed}

    async def _process_job(self, job: dict[str, Any]) -> bool:
        now = datetime.now(UTC)
        payload = job.get("payload", {})
        if job.get("job_type") != CalendarJobType.MEETING_INVITE.value:
            await self.jobs_collection.update_one(
                {"_id": job["_id"]},
                {
                    "$set": {
                        "status": CalendarJobStatus.FAILED.value,
                        "last_error": "Unsupported calendar job type",
                        "last_error_category": "unsupported_job_type",
                        "updated_at": now,
                        "completed_at": now,
                        "expires_at": now + timedelta(days=7),
                    }
                },
            )
            return False

        task = payload.get("task")
        if not isinstance(task, dict):
            await self.jobs_collection.update_one(
                {"_id": job["_id"]},
                {
                    "$set": {
                        "status": CalendarJobStatus.FAILED.value,
                        "last_error": "Calendar invite job is missing a task payload",
                        "last_error_category": "invalid_payload",
                        "updated_at": now,
                        "completed_at": now,
                        "expires_at": now + timedelta(days=7),
                    }
                },
            )
            return False

        method = str(payload.get("method") or "REQUEST")
        recipient_emails = [
            email
            for email in payload.get("recipient_emails", [])
            if isinstance(email, str)
        ]
        if method == "CANCEL":
            results = await meeting_invite_service.send_cancellations(
                task,
                recipient_emails=recipient_emails,
            )
        else:
            results = await meeting_invite_service.send_invites(
                task,
                recipient_emails=recipient_emails,
            )

        failed_recipients = [
            row.get("recipient_email")
            for row in results
            if not row.get("success") and row.get("recipient_email")
        ]
        attempts = int(job.get("attempts") or 0) + 1
        if not failed_recipients:
            await self.jobs_collection.update_one(
                {"_id": job["_id"]},
                {
                    "$set": {
                        "status": CalendarJobStatus.COMPLETED.value,
                        "attempts": attempts,
                        "last_error": None,
                        "last_error_category": None,
                        "updated_at": now,
                        "completed_at": now,
                        "expires_at": now + timedelta(days=7),
                    }
                },
            )
            return True

        terminal = attempts >= int(
            job.get("max_attempts") or settings.CALENDAR_JOB_MAX_ATTEMPTS
        )
        await self.jobs_collection.update_one(
            {"_id": job["_id"]},
            {
                "$set": {
                    "status": (
                        CalendarJobStatus.FAILED.value
                        if terminal
                        else CalendarJobStatus.QUEUED.value
                    ),
                    "attempts": attempts,
                    "last_error": f"Failed to deliver invites to {len(failed_recipients)} recipient(s)",
                    "last_error_category": "invite_delivery_failed",
                    "payload.recipient_emails": failed_recipients,
                    "run_at": now + self._queue_backoff(attempts),
                    "updated_at": now,
                    "completed_at": now if terminal else None,
                    "expires_at": (now + timedelta(days=7)) if terminal else None,
                }
            },
        )
        return False


calendar_job_service = CalendarJobService()
