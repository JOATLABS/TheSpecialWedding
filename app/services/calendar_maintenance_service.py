"""Scheduled retry and drift maintenance for shared calendar syncs."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.config import settings
from app.core.database import mongo
from app.services.aurinko_tasks_sync_service import aurinko_tasks_sync_service
from app.services.calendar_provider_service import calendar_provider_service
from app.services.calendar_sync_service import calendar_sync_service
from app.services.google_calendar_service import google_calendar_service


class CalendarMaintenanceService:
    """Process scheduled sync retries and provider drift checks."""

    def __init__(self) -> None:
        self.connections_collection = mongo.get_calendar_connections_collection()
        self.syncs_collection = mongo.get_calendar_event_syncs_collection()

    async def process_due_sync_retries(self, *, limit: int) -> dict[str, Any]:
        event_results = await calendar_sync_service.process_due_retries(limit=limit)
        task_results = await aurinko_tasks_sync_service.process_due_retries(limit=limit)
        return {
            "processed": int(event_results.get("processed") or 0)
            + int(task_results.get("processed") or 0),
            "succeeded": int(event_results.get("succeeded") or 0)
            + int(task_results.get("succeeded") or 0),
            "failed": int(event_results.get("failed") or 0)
            + int(task_results.get("failed") or 0),
            "calendar_event_syncs": event_results,
            "task_sync_records": task_results,
        }

    async def run_drift_checks(self, *, limit: int) -> dict[str, int]:
        now = datetime.now(UTC)
        connection_cutoff = now - timedelta(
            minutes=settings.CALENDAR_DRIFT_CHECK_INTERVAL_MINUTES
        )
        checked_connections = 0
        connection_cursor = (
            self.connections_collection.find(
                {
                    "$or": [
                        {"last_healthcheck_at": {"$exists": False}},
                        {"last_healthcheck_at": None},
                        {"last_healthcheck_at": {"$lt": connection_cutoff}},
                    ]
                }
            )
            .sort("last_healthcheck_at", 1)
            .limit(limit)
        )
        async for connection_doc in connection_cursor:
            connection_id = str(connection_doc["_id"])
            if connection_doc.get("aurinko_account_id"):
                await calendar_provider_service.healthcheck_connection(connection_id)
            else:
                await google_calendar_service.healthcheck_connection(connection_id)
            checked_connections += 1

        checked_sync_rows = await calendar_sync_service.run_drift_checks(limit=limit)
        checked_task_sync_rows = await aurinko_tasks_sync_service.run_drift_checks(
            limit=limit
        )
        return {
            "checked_connections": checked_connections,
            "checked_sync_rows": checked_sync_rows,
            "checked_task_sync_rows": checked_task_sync_rows,
        }


calendar_maintenance_service = CalendarMaintenanceService()
