"""Unit tests for Aurinko task mirroring.

These tests keep the service contracts local: no Mongo, no Aurinko network.
They pin owner-scoped connection selection, outbound task payload shape, and
delete/orphan lifecycle behavior.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

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

    async def to_list(self, length: int | None = None) -> list[dict[str, Any]]:
        return self.docs[:length] if length is not None else self.docs


class _Collection:
    def __init__(self, docs: list[dict[str, Any]] | None = None) -> None:
        self.docs = docs or []
        self.updates: list[tuple[dict[str, Any], dict[str, Any], bool]] = []

    def _matches(self, doc: dict[str, Any], query: dict[str, Any]) -> bool:
        for key, expected in query.items():
            actual = doc.get(key)
            if isinstance(expected, dict):
                if "$nin" in expected and actual in expected["$nin"]:
                    return False
                if "$ne" in expected and actual == expected["$ne"]:
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


class _Provider:
    def __init__(self) -> None:
        self.client = _TaskClient()

    async def _account_token_for_connection(self, connection: dict[str, Any]) -> str:
        return f"token:{connection['_id']}"


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
