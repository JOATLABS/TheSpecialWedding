from __future__ import annotations

import os
import sys
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from bson import ObjectId

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.services import calendar_maintenance_service as maintenance_module  # noqa: E402
from app.services.calendar_maintenance_service import CalendarMaintenanceService  # noqa: E402


class _ConnectionCursor:
    def __init__(self, docs: list[dict]) -> None:
        self.docs = docs
        self.limit_value: int | None = None
        self._index = 0

    def sort(self, *args, **kwargs) -> "_ConnectionCursor":
        return self

    def limit(self, value: int) -> "_ConnectionCursor":
        self.limit_value = value
        return self

    def __aiter__(self) -> "_ConnectionCursor":
        self._index = 0
        return self

    async def __anext__(self) -> dict:
        docs = (
            self.docs[: self.limit_value] if self.limit_value is not None else self.docs
        )
        if self._index >= len(docs):
            raise StopAsyncIteration
        doc = docs[self._index]
        self._index += 1
        return doc


class _ConnectionCollection:
    def __init__(self, docs: list[dict]) -> None:
        self.docs = docs
        self.seen_query: dict | None = None

    def find(self, query: dict) -> _ConnectionCursor:
        self.seen_query = query
        return _ConnectionCursor(self.docs)


@pytest.mark.asyncio
async def test_calendar_maintenance_routes_healthchecks_by_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(UTC)
    legacy_google_connection_id = ObjectId()
    aurinko_connection_id = ObjectId()
    service = CalendarMaintenanceService.__new__(CalendarMaintenanceService)
    service.connections_collection = _ConnectionCollection(
        [
            {
                "_id": legacy_google_connection_id,
                "provider": "google",
                "last_healthcheck_at": now - timedelta(hours=2),
            },
            {
                "_id": aurinko_connection_id,
                "provider": "google",
                "aurinko_account_id": "aurinko-account-1",
                "last_healthcheck_at": now - timedelta(hours=2),
            },
        ]
    )

    google_healthcheck = AsyncMock(return_value={})
    aurinko_healthcheck = AsyncMock(return_value={})
    sync_drift_check = AsyncMock(return_value=0)
    task_drift_check = AsyncMock(return_value=3)
    monkeypatch.setattr(
        maintenance_module.google_calendar_service,
        "healthcheck_connection",
        google_healthcheck,
    )
    monkeypatch.setattr(
        maintenance_module.calendar_provider_service,
        "healthcheck_connection",
        aurinko_healthcheck,
    )
    monkeypatch.setattr(
        maintenance_module.calendar_sync_service,
        "run_drift_checks",
        sync_drift_check,
    )
    monkeypatch.setattr(
        maintenance_module.aurinko_tasks_sync_service,
        "run_drift_checks",
        task_drift_check,
    )

    result = await service.run_drift_checks(limit=10)

    google_healthcheck.assert_awaited_once_with(str(legacy_google_connection_id))
    aurinko_healthcheck.assert_awaited_once_with(str(aurinko_connection_id))
    sync_drift_check.assert_awaited_once_with(limit=10)
    task_drift_check.assert_awaited_once_with(limit=10)
    assert result == {
        "checked_connections": 2,
        "checked_sync_rows": 0,
        "checked_task_sync_rows": 3,
    }


@pytest.mark.asyncio
async def test_calendar_maintenance_runs_event_and_task_retry_queues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = CalendarMaintenanceService.__new__(CalendarMaintenanceService)
    event_retries = AsyncMock(
        return_value={"processed": 2, "succeeded": 1, "failed": 1}
    )
    task_retries = AsyncMock(return_value={"processed": 3, "succeeded": 3, "failed": 0})
    monkeypatch.setattr(
        maintenance_module.calendar_sync_service,
        "process_due_retries",
        event_retries,
    )
    monkeypatch.setattr(
        maintenance_module.aurinko_tasks_sync_service,
        "process_due_retries",
        task_retries,
    )

    result = await service.process_due_sync_retries(limit=10)

    event_retries.assert_awaited_once_with(limit=10)
    task_retries.assert_awaited_once_with(limit=10)
    assert result == {
        "processed": 5,
        "succeeded": 4,
        "failed": 1,
        "calendar_event_syncs": {"processed": 2, "succeeded": 1, "failed": 1},
        "task_sync_records": {"processed": 3, "succeeded": 3, "failed": 0},
    }
