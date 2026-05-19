"""Unit tests for Aurinko task mirroring.

These tests keep the service contracts local: no Mongo, no Aurinko network.
They pin owner-scoped connection selection, outbound task payload shape, and
delete/orphan lifecycle behavior.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from bson import ObjectId

from app.models.calendar_connection import CalendarConnectionStatus
from app.models.calendar_sync import CalendarSyncStatusValue
from app.services.aurinko_tasks_sync_service import AurinkoTasksSyncService


class _InsertResult:
    def __init__(self, inserted_id: ObjectId) -> None:
        self.inserted_id = inserted_id


class _Cursor:
    def __init__(self, docs: list[dict[str, Any]]) -> None:
        self.docs = docs
        self.limit_value: int | None = None

    def sort(self, *args, **kwargs) -> "_Cursor":
        return self

    def limit(self, value: int) -> "_Cursor":
        self.limit_value = value
        return self

    async def to_list(self, length: int | None = None) -> list[dict[str, Any]]:
        effective_length = length if length is not None else self.limit_value
        return (
            self.docs[:effective_length] if effective_length is not None else self.docs
        )


class _Collection:
    def __init__(self, docs: list[dict[str, Any]] | None = None) -> None:
        self.docs = docs or []
        self.updates: list[tuple[dict[str, Any], dict[str, Any], bool]] = []

    def _matches(self, doc: dict[str, Any], query: dict[str, Any]) -> bool:
        for key, expected in query.items():
            if key == "$or":
                if not any(self._matches(doc, clause) for clause in expected):
                    return False
                continue
            actual = doc.get(key)
            if isinstance(expected, dict):
                if "$nin" in expected and actual in expected["$nin"]:
                    return False
                if "$ne" in expected and actual == expected["$ne"]:
                    return False
                if "$exists" in expected and (key in doc) != expected["$exists"]:
                    return False
                if "$lte" in expected and not (
                    actual is not None and actual <= expected["$lte"]
                ):
                    return False
                if "$lt" in expected and not (
                    actual is not None and actual < expected["$lt"]
                ):
                    return False
                continue
            if actual != expected:
                return False
        return True

    async def find_one(self, query: dict[str, Any]) -> dict[str, Any] | None:
        return next((doc for doc in self.docs if self._matches(doc, query)), None)

    def find(self, query: dict[str, Any]) -> _Cursor:
        return _Cursor([doc for doc in self.docs if self._matches(doc, query)])

    async def insert_one(self, doc: dict[str, Any]) -> _InsertResult:
        inserted_id = doc.get("_id") or ObjectId()
        self.docs.append({**doc, "_id": inserted_id})
        return _InsertResult(inserted_id)

    async def update_one(
        self,
        query: dict[str, Any],
        update: dict[str, Any],
        upsert: bool = False,
    ) -> None:
        self.updates.append((query, update, upsert))
        doc = await self.find_one(query)
        if doc is None:
            if not upsert:
                return
            doc = {
                key: value
                for key, value in query.items()
                if not isinstance(value, dict)
            }
            doc.update(update.get("$setOnInsert", {}))
            self.docs.append(doc)
        doc.update(update.get("$set", {}))


class _TaskClient:
    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []
        self.updated: list[dict[str, Any]] = []
        self.deleted: list[dict[str, Any]] = []
        self.fetched: list[dict[str, Any]] = []
        self.get_task_payload: dict[str, Any] = {
            "id": "aurinko-task-1",
            "etag": "etag-fresh",
        }
        self.get_task_error: Exception | None = None

    async def create_task(
        self, *, account_token: str, tasklist_id: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        self.created.append(
            {"account_token": account_token, "tasklist_id": tasklist_id, "body": body}
        )
        return {"id": "aurinko-task-1", "etag": "etag-1"}

    async def update_task(
        self,
        *,
        account_token: str,
        tasklist_id: str,
        task_id: str,
        body: dict[str, Any],
        etag: str | None = None,
    ) -> dict[str, Any]:
        self.updated.append(
            {
                "account_token": account_token,
                "tasklist_id": tasklist_id,
                "task_id": task_id,
                "body": body,
                "etag": etag,
            }
        )
        return {"id": task_id, "etag": "etag-2"}

    async def delete_task(
        self, *, account_token: str, tasklist_id: str, task_id: str
    ) -> None:
        self.deleted.append(
            {
                "account_token": account_token,
                "tasklist_id": tasklist_id,
                "task_id": task_id,
            }
        )

    async def get_task(
        self, *, account_token: str, tasklist_id: str, task_id: str
    ) -> dict[str, Any]:
        self.fetched.append(
            {
                "account_token": account_token,
                "tasklist_id": tasklist_id,
                "task_id": task_id,
            }
        )
        if self.get_task_error:
            raise self.get_task_error
        return self.get_task_payload


class _Provider:
    def __init__(self) -> None:
        self.client = _TaskClient()

    async def _account_token_for_connection(self, connection: dict[str, Any]) -> str:
        if connection.get("no_token"):
            return ""
        return f"token:{connection['_id']}"

    def _classify_aurinko_exception(self, exc: Exception) -> dict[str, Any]:
        if isinstance(exc, httpx.HTTPStatusError):
            status_code = exc.response.status_code
            return {
                "retryable": status_code >= 500 or status_code == 429,
                "error_category": "not_found" if status_code == 404 else "temporary",
                "error_message": f"Aurinko HTTP {status_code}",
                "status_code": status_code,
            }
        return {
            "retryable": False,
            "error_category": "unknown",
            "error_message": str(exc),
            "status_code": None,
        }


def _service(
    *,
    tasks: _Collection,
    connections: _Collection,
    syncs: _Collection,
    provider: _Provider | None = None,
) -> AurinkoTasksSyncService:
    service = AurinkoTasksSyncService.__new__(AurinkoTasksSyncService)
    service.tasks_collection = tasks
    service.connections_collection = connections
    service.syncs_collection = syncs
    service.provider = provider or _Provider()
    return service


@pytest.mark.asyncio
async def test_mirror_planner_task_creates_aurinko_task_and_sync_record() -> None:
    task_id = ObjectId()
    connection_id = ObjectId()
    due = datetime(2026, 6, 1, 15, 30, tzinfo=UTC)
    provider = _Provider()
    service = _service(
        tasks=_Collection(
            [
                {
                    "_id": task_id,
                    "title": "Book florist",
                    "notes": "Confirm centerpiece quote",
                    "status": "pending",
                    "priority": "high",
                    "due_date": due,
                    "owner_planner_id": "planner-1",
                    "owner_planner_email": "planner@example.com",
                }
            ]
        ),
        connections=_Collection(
            [
                {
                    "_id": connection_id,
                    "connection_status": CalendarConnectionStatus.ACTIVE.value,
                    "task_sync_enabled": True,
                    "task_sync_tasklist_id": "tasks-default",
                    "owner_planner_id": "planner-1",
                    "owner_planner_email": "planner@example.com",
                    "user_id": "user-1",
                    "user_email": "planner@example.com",
                    "provider": "google",
                }
            ]
        ),
        syncs=_Collection(),
        provider=provider,
    )

    result = await service.mirror_planner_task_to_aurinko(str(task_id))

    assert result == [
        {
            "connection_id": str(connection_id),
            "aurinko_task_id": "aurinko-task-1",
            "sync_status": CalendarSyncStatusValue.SYNCED.value,
        }
    ]
    assert provider.client.created[0]["tasklist_id"] == "tasks-default"
    assert provider.client.created[0]["body"] == {
        "title": "Book florist",
        "notes": "Confirm centerpiece quote",
        "status": "notStarted",
        "importance": "high",
        "due": due.isoformat(),
    }
    sync_doc = service.syncs_collection.docs[0]
    assert sync_doc["planner_task_id"] == str(task_id)
    assert sync_doc["connection_id"] == str(connection_id)
    assert sync_doc["aurinko_task_id"] == "aurinko-task-1"
    assert sync_doc["sync_status"] == CalendarSyncStatusValue.SYNCED.value


@pytest.mark.asyncio
async def test_mirror_planner_task_dedupes_same_account_tasklist_rows() -> None:
    """Legacy picker commits may have enabled one task list on many calendar rows.

    One planner task should still create only one Aurinko task for that
    account/task-list resource.
    """
    task_id = ObjectId()
    first_connection_id = ObjectId()
    default_connection_id = ObjectId()
    provider = _Provider()
    service = _service(
        tasks=_Collection(
            [
                {
                    "_id": task_id,
                    "title": "Book florist",
                    "status": "pending",
                    "owner_planner_id": "planner-1",
                    "owner_planner_email": "planner@example.com",
                }
            ]
        ),
        connections=_Collection(
            [
                {
                    "_id": first_connection_id,
                    "aurinko_account_id": "acct-1",
                    "connection_status": CalendarConnectionStatus.ACTIVE.value,
                    "task_sync_enabled": True,
                    "task_sync_tasklist_id": "tasks-default",
                    "owner_planner_id": "planner-1",
                    "owner_planner_email": "planner@example.com",
                    "user_id": "user-1",
                    "user_email": "planner@example.com",
                    "provider": "google",
                },
                {
                    "_id": default_connection_id,
                    "aurinko_account_id": "acct-1",
                    "connection_status": CalendarConnectionStatus.ACTIVE.value,
                    "task_sync_enabled": True,
                    "task_sync_tasklist_id": "tasks-default",
                    "is_default_write_target": True,
                    "owner_planner_id": "planner-1",
                    "owner_planner_email": "planner@example.com",
                    "user_id": "user-1",
                    "user_email": "planner@example.com",
                    "provider": "google",
                },
            ]
        ),
        syncs=_Collection(),
        provider=provider,
    )

    result = await service.mirror_planner_task_to_aurinko(str(task_id))

    assert result == [
        {
            "connection_id": str(default_connection_id),
            "aurinko_task_id": "aurinko-task-1",
            "sync_status": CalendarSyncStatusValue.SYNCED.value,
        }
    ]
    assert len(provider.client.created) == 1
    assert (
        provider.client.created[0]["account_token"] == f"token:{default_connection_id}"
    )
    assert service.syncs_collection.docs[0]["connection_id"] == str(
        default_connection_id
    )


@pytest.mark.asyncio
async def test_mirror_planner_task_marks_missing_credentials_nonretryable() -> None:
    task_id = ObjectId()
    connection_id = ObjectId()
    service = _service(
        tasks=_Collection(
            [
                {
                    "_id": task_id,
                    "title": "Book florist",
                    "status": "pending",
                    "owner_planner_id": "planner-1",
                    "owner_planner_email": "planner@example.com",
                }
            ]
        ),
        connections=_Collection(
            [
                {
                    "_id": connection_id,
                    "connection_status": CalendarConnectionStatus.ACTIVE.value,
                    "task_sync_enabled": True,
                    "task_sync_tasklist_id": "tasks-default",
                    "owner_planner_id": "planner-1",
                    "owner_planner_email": "planner@example.com",
                    "no_token": True,
                }
            ]
        ),
        syncs=_Collection(),
    )

    result = await service.mirror_planner_task_to_aurinko(str(task_id))

    assert result == []
    sync_doc = service.syncs_collection.docs[0]
    assert sync_doc["sync_status"] == CalendarSyncStatusValue.FAILED.value
    assert sync_doc["last_error_category"] == "credentials_unavailable"
    assert sync_doc["retryable_error"] is False


@pytest.mark.asyncio
async def test_apply_external_task_change_creates_internal_task_when_no_mapping() -> (
    None
):
    connection_id = ObjectId()
    service = _service(
        tasks=_Collection(),
        connections=_Collection(
            [
                {
                    "_id": connection_id,
                    "task_sync_tasklist_id": "tasks-default",
                    "owner_planner_id": "planner-1",
                    "owner_planner_email": "planner@example.com",
                    "user_id": "user-1",
                    "user_email": "planner@example.com",
                    "provider": "google",
                }
            ]
        ),
        syncs=_Collection(),
    )

    await service.apply_external_task_change(
        connection_id=str(connection_id),
        aurinko_task_id="aurinko-task-2",
        change_type="updated",
        snapshot={
            "title": "Phone follow-up",
            "notes": "Call bakery",
            "status": "completed",
            "due": "2026-06-02T18:00:00Z",
            "startDateTime": "2026-06-02T17:00:00Z",
            "etag": "etag-7",
        },
    )

    inserted_task = service.tasks_collection.docs[0]
    assert inserted_task["title"] == "Phone follow-up"
    assert inserted_task["status"] == "completed"
    assert inserted_task["owner_planner_id"] == "planner-1"
    assert inserted_task["due_date"] == datetime(2026, 6, 2, 18, 0, tzinfo=UTC)
    sync_doc = service.syncs_collection.docs[0]
    assert sync_doc["aurinko_task_id"] == "aurinko-task-2"
    assert sync_doc["planner_task_id"] == str(inserted_task["_id"])
    assert sync_doc["last_external_etag"] == "etag-7"


@pytest.mark.asyncio
async def test_unmirror_planner_task_deletes_external_before_orphaning() -> None:
    connection_id = ObjectId()
    sync_id = ObjectId()
    provider = _Provider()
    service = _service(
        tasks=_Collection(),
        connections=_Collection(
            [
                {
                    "_id": connection_id,
                    "task_sync_tasklist_id": "tasks-default",
                }
            ]
        ),
        syncs=_Collection(
            [
                {
                    "_id": sync_id,
                    "planner_task_id": "task-1",
                    "connection_id": str(connection_id),
                    "aurinko_task_id": "aurinko-task-3",
                    "aurinko_tasklist_id": "tasks-default",
                    "sync_status": CalendarSyncStatusValue.SYNCED.value,
                }
            ]
        ),
        provider=provider,
    )

    await service.unmirror_planner_task("task-1")

    assert provider.client.deleted == [
        {
            "account_token": f"token:{connection_id}",
            "tasklist_id": "tasks-default",
            "task_id": "aurinko-task-3",
        }
    ]
    sync_doc = service.syncs_collection.docs[0]
    assert sync_doc["sync_status"] == CalendarSyncStatusValue.ORPHANED.value
    assert sync_doc["last_error"] == "Internal planner task removed or sync disabled"


@pytest.mark.asyncio
async def test_process_due_retries_remirrors_failed_task_sync_record() -> None:
    task_id = ObjectId()
    connection_id = ObjectId()
    sync_id = ObjectId()
    provider = _Provider()
    service = _service(
        tasks=_Collection(
            [
                {
                    "_id": task_id,
                    "title": "Book florist",
                    "status": "pending",
                    "owner_planner_id": "planner-1",
                    "owner_planner_email": "planner@example.com",
                }
            ]
        ),
        connections=_Collection(
            [
                {
                    "_id": connection_id,
                    "aurinko_account_id": "acct-1",
                    "connection_status": CalendarConnectionStatus.ACTIVE.value,
                    "task_sync_enabled": True,
                    "task_sync_tasklist_id": "tasks-default",
                    "owner_planner_id": "planner-1",
                    "owner_planner_email": "planner@example.com",
                    "user_id": "user-1",
                    "user_email": "planner@example.com",
                    "provider": "google",
                }
            ]
        ),
        syncs=_Collection(
            [
                {
                    "_id": sync_id,
                    "planner_task_id": str(task_id),
                    "connection_id": str(connection_id),
                    "aurinko_task_id": "aurinko-task-1",
                    "aurinko_tasklist_id": "tasks-default",
                    "last_external_etag": "etag-old",
                    "sync_status": CalendarSyncStatusValue.FAILED.value,
                    "retryable_error": True,
                    "retry_count": 1,
                    "next_retry_at": datetime.now(UTC) - timedelta(minutes=5),
                }
            ]
        ),
        provider=provider,
    )

    result = await service.process_due_retries(limit=10)

    assert result == {"processed": 1, "succeeded": 1, "failed": 0}
    assert provider.client.updated == [
        {
            "account_token": f"token:{connection_id}",
            "tasklist_id": "tasks-default",
            "task_id": "aurinko-task-1",
            "body": {
                "title": "Book florist",
                "notes": "",
                "status": "notStarted",
                "importance": "normal",
            },
            "etag": "etag-old",
        }
    ]
    sync_doc = service.syncs_collection.docs[0]
    assert sync_doc["sync_status"] == CalendarSyncStatusValue.SYNCED.value
    assert sync_doc["retryable_error"] is False
    assert sync_doc["next_retry_at"] is None


@pytest.mark.asyncio
async def test_run_drift_checks_marks_missing_external_task_orphaned() -> None:
    connection_id = ObjectId()
    sync_id = ObjectId()
    provider = _Provider()
    provider.client.get_task_error = httpx.HTTPStatusError(
        "missing",
        request=httpx.Request("GET", "https://api.aurinko.io/v1/task"),
        response=httpx.Response(404, json={"message": "missing"}),
    )
    service = _service(
        tasks=_Collection(),
        connections=_Collection(
            [
                {
                    "_id": connection_id,
                    "connection_status": CalendarConnectionStatus.ACTIVE.value,
                    "task_sync_enabled": True,
                    "task_sync_tasklist_id": "tasks-default",
                }
            ]
        ),
        syncs=_Collection(
            [
                {
                    "_id": sync_id,
                    "planner_task_id": str(ObjectId()),
                    "connection_id": str(connection_id),
                    "aurinko_task_id": "aurinko-task-missing",
                    "aurinko_tasklist_id": "tasks-default",
                    "sync_status": CalendarSyncStatusValue.SYNCED.value,
                    "last_drift_check_at": datetime.now(UTC) - timedelta(hours=2),
                }
            ]
        ),
        provider=provider,
    )

    checked = await service.run_drift_checks(limit=10)

    assert checked == 1
    assert provider.client.fetched == [
        {
            "account_token": f"token:{connection_id}",
            "tasklist_id": "tasks-default",
            "task_id": "aurinko-task-missing",
        }
    ]
    sync_doc = service.syncs_collection.docs[0]
    assert sync_doc["sync_status"] == CalendarSyncStatusValue.ORPHANED.value
    assert sync_doc["last_error_category"] == "provider_task_missing"
