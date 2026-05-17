"""Bidirectional sync between planner_tasks and Aurinko task lists."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Optional

from bson import ObjectId
from fastapi import HTTPException

from app.core.database import mongo
from app.models.calendar import ScheduleItemType
from app.models.calendar_connection import CalendarConnectionStatus
from app.models.calendar_sync import CalendarSyncDirection, CalendarSyncStatusValue
from app.services.calendar_provider_service import (
    _redact_sensitive,
    calendar_provider_service,
)

logger = logging.getLogger(__name__)


class AurinkoTasksSyncService:
    """Mirror ordinary planner tasks into a configured Aurinko task list."""

    def __init__(self) -> None:
        self.tasks_collection = mongo.get_planner_tasks_collection()
        self.connections_collection = mongo.get_calendar_connections_collection()
        self.syncs_collection = mongo.get_task_sync_records_collection()
        self.provider = calendar_provider_service

    def _coerce_task_oid(self, planner_task_id: str) -> ObjectId:
        try:
            return ObjectId(planner_task_id)
        except Exception as exc:
            raise HTTPException(
                status_code=400, detail="Invalid task ID format"
            ) from exc

    def _is_syncable_task(self, task: dict[str, Any]) -> bool:
        return (
            task.get("schedule_item_type", ScheduleItemType.TASK.value)
            != ScheduleItemType.MEETING.value
        )

    def _status_to_aurinko(self, status: Any) -> str:
        if status == "completed":
            return "completed"
        return "notStarted"

    def _status_from_aurinko(self, status: Any, completed: Any = None) -> str:
        normalized = str(status or "").lower()
        if normalized in {"completed", "complete"} or completed:
            return "completed"
        if normalized in {"inprogress", "in_progress"}:
            return "in_progress"
        return "pending"

    def _importance_to_aurinko(self, priority: Any) -> str:
        normalized = str(priority or "medium").lower()
        if normalized in {"urgent", "high"}:
            return "high"
        if normalized == "low":
            return "low"
        return "normal"

    def _build_external_body(self, task: dict[str, Any]) -> dict[str, Any]:
        body: dict[str, Any] = {
            "title": task.get("title") or "Untitled task",
            "notes": task.get("notes") or task.get("description") or "",
            "status": self._status_to_aurinko(task.get("status")),
            "importance": self._importance_to_aurinko(task.get("priority")),
        }
        due = task.get("due_date") or task.get("end_date") or task.get("start_date")
        if isinstance(due, datetime):
            body["due"] = due.isoformat()
        elif due:
            body["due"] = str(due)
        start = task.get("start_date")
        if isinstance(start, datetime):
            body["startDateTime"] = start.isoformat()
        elif start:
            body["startDateTime"] = str(start)
        return body

    def _external_id(self, payload: dict[str, Any]) -> Optional[str]:
        value = payload.get("id") or payload.get("taskId")
        return str(value) if value else None

    def _external_etag(self, payload: dict[str, Any]) -> Optional[str]:
        value = payload.get("etag") or payload.get("changeKey")
        return str(value) if value else None

    def _account_tasklist_key(self, connection: dict[str, Any]) -> tuple[str, str]:
        account_key = str(connection.get("aurinko_account_id") or "").strip()
        if not account_key:
            account_key = "|".join(
                [
                    str(connection.get("user_id") or ""),
                    str(connection.get("provider") or ""),
                    str(connection.get("provider_account_email") or ""),
                ]
            )
        tasklist_id = str(connection.get("task_sync_tasklist_id") or "").strip()
        return account_key, tasklist_id

    def _dedupe_account_tasklist_connections(
        self, connections: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Return one enabled row per connected account/task-list resource.

        Older picker submissions stored the same account-scoped task list on
        every picked calendar row. Prefer the default-write row when repairing
        that legacy shape in memory.
        """
        sorted_connections = sorted(
            connections,
            key=lambda row: (
                not bool(row.get("is_default_write_target")),
                str(row.get("calendar_name") or row.get("_id") or ""),
            ),
        )
        seen: set[tuple[str, str]] = set()
        deduped: list[dict[str, Any]] = []
        for connection in sorted_connections:
            key = self._account_tasklist_key(connection)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(connection)
        return deduped

    async def _eligible_connections(
        self,
        task: dict[str, Any],
        connection_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {
            "connection_status": CalendarConnectionStatus.ACTIVE.value,
            "task_sync_enabled": True,
            "task_sync_tasklist_id": {"$nin": [None, ""]},
        }
        if task.get("owner_planner_id"):
            query["owner_planner_id"] = str(task.get("owner_planner_id"))
        else:
            query["owner_planner_email"] = task.get("owner_planner_email") or task.get(
                "planner_email"
            )
        if connection_id:
            query["_id"] = ObjectId(connection_id)
        connections = await self.connections_collection.find(query).to_list(length=100)
        return self._dedupe_account_tasklist_connections(connections)

    async def mirror_planner_task_to_aurinko(
        self,
        planner_task_id: str,
        connection_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        task = await self.tasks_collection.find_one(
            {"_id": self._coerce_task_oid(planner_task_id)}
        )
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        if not self._is_syncable_task(task):
            return []

        connections = await self._eligible_connections(task, connection_id)
        if not connections:
            await self.syncs_collection.update_one(
                {"planner_task_id": planner_task_id, "connection_id": connection_id},
                {
                    "$set": {
                        "planner_task_id": planner_task_id,
                        "connection_id": connection_id,
                        "owner_planner_id": task.get("owner_planner_id"),
                        "owner_planner_email": task.get("owner_planner_email")
                        or task.get("planner_email"),
                        "sync_status": CalendarSyncStatusValue.NOT_CONFIGURED.value,
                        "last_error": "No task-sync-enabled connection is available",
                        "updated_at": datetime.now(UTC),
                    },
                    "$setOnInsert": {"created_at": datetime.now(UTC)},
                },
                upsert=True,
            )
            return []

        results: list[dict[str, Any]] = []
        body = self._build_external_body(task)
        now = datetime.now(UTC)
        for connection in connections:
            cid = str(connection["_id"])
            token = await self.provider._account_token_for_connection(connection)
            tasklist_id = str(connection.get("task_sync_tasklist_id") or "")
            if not token or not tasklist_id:
                continue
            sync_doc = await self.syncs_collection.find_one(
                {"planner_task_id": planner_task_id, "connection_id": cid}
            )
            try:
                if sync_doc and sync_doc.get("aurinko_task_id"):
                    payload = await self.provider.client.update_task(
                        account_token=token,
                        tasklist_id=tasklist_id,
                        task_id=str(sync_doc["aurinko_task_id"]),
                        body=body,
                        etag=sync_doc.get("last_external_etag"),
                    )
                    aurinko_task_id = str(sync_doc["aurinko_task_id"])
                else:
                    payload = await self.provider.client.create_task(
                        account_token=token,
                        tasklist_id=tasklist_id,
                        body=body,
                    )
                    aurinko_task_id = self._external_id(payload)
                if not aurinko_task_id:
                    raise RuntimeError("Aurinko task response did not include an id")
                etag = self._external_etag(payload)
                await self.syncs_collection.update_one(
                    {"planner_task_id": planner_task_id, "connection_id": cid},
                    {
                        "$set": {
                            "planner_task_id": planner_task_id,
                            "owner_planner_id": task.get("owner_planner_id"),
                            "owner_planner_email": task.get("owner_planner_email")
                            or task.get("planner_email"),
                            "target_user_id": connection.get("user_id"),
                            "target_user_email": connection.get("user_email"),
                            "connection_id": cid,
                            "provider": connection.get("provider"),
                            "aurinko_task_id": aurinko_task_id,
                            "aurinko_tasklist_id": tasklist_id,
                            "sync_direction": CalendarSyncDirection.BIDIRECTIONAL.value,
                            "sync_status": CalendarSyncStatusValue.SYNCED.value,
                            "last_external_etag": etag,
                            "last_sync_at": now,
                            "last_error": None,
                            "updated_at": now,
                        },
                        "$setOnInsert": {"created_at": now},
                    },
                    upsert=True,
                )
                results.append(
                    {
                        "connection_id": cid,
                        "aurinko_task_id": aurinko_task_id,
                        "sync_status": CalendarSyncStatusValue.SYNCED.value,
                    }
                )
            except Exception as exc:
                logger.warning(
                    "Aurinko task mirror failed for planner task %s on connection %s: %s",
                    planner_task_id,
                    cid,
                    _redact_sensitive(exc),
                )
                await self.syncs_collection.update_one(
                    {"planner_task_id": planner_task_id, "connection_id": cid},
                    {
                        "$set": {
                            "planner_task_id": planner_task_id,
                            "owner_planner_id": task.get("owner_planner_id"),
                            "owner_planner_email": task.get("owner_planner_email")
                            or task.get("planner_email"),
                            "connection_id": cid,
                            "sync_status": CalendarSyncStatusValue.FAILED.value,
                            "last_error": _redact_sensitive(exc),
                            "updated_at": now,
                        },
                        "$setOnInsert": {"created_at": now},
                    },
                    upsert=True,
                )
        return results

    async def unmirror_planner_task(
        self,
        planner_task_id: str,
        connection_id: Optional[str] = None,
    ) -> None:
        query: dict[str, Any] = {"planner_task_id": planner_task_id}
        if connection_id:
            query["connection_id"] = connection_id
        sync_rows = await self.syncs_collection.find(query).to_list(length=100)
        now = datetime.now(UTC)
        for sync_doc in sync_rows:
            cid = sync_doc.get("connection_id")
            connection = None
            if ObjectId.is_valid(str(cid)):
                connection = await self.connections_collection.find_one(
                    {"_id": ObjectId(str(cid))}
                )
            if connection and sync_doc.get("aurinko_task_id"):
                token = await self.provider._account_token_for_connection(connection)
                tasklist_id = sync_doc.get("aurinko_tasklist_id") or connection.get(
                    "task_sync_tasklist_id"
                )
                if token and tasklist_id:
                    try:
                        await self.provider.client.delete_task(
                            account_token=token,
                            tasklist_id=str(tasklist_id),
                            task_id=str(sync_doc["aurinko_task_id"]),
                        )
                    except Exception as exc:
                        logger.warning(
                            "Aurinko task delete failed for sync %s: %s",
                            sync_doc.get("_id"),
                            _redact_sensitive(exc),
                        )
                        await self.syncs_collection.update_one(
                            {"_id": sync_doc["_id"]},
                            {
                                "$set": {
                                    "sync_status": CalendarSyncStatusValue.FAILED.value,
                                    "last_error": _redact_sensitive(exc),
                                    "updated_at": now,
                                }
                            },
                        )
                        raise HTTPException(
                            status_code=502,
                            detail=(
                                "Could not delete the synced external task. "
                                "The internal task was preserved."
                            ),
                        ) from exc
            await self.syncs_collection.update_one(
                {"_id": sync_doc["_id"]},
                {
                    "$set": {
                        "sync_status": CalendarSyncStatusValue.ORPHANED.value,
                        "last_error": "Internal planner task removed or sync disabled",
                        "updated_at": now,
                    }
                },
            )

    async def apply_external_task_change(
        self,
        *,
        connection_id: str,
        aurinko_task_id: str,
        change_type: str,
        snapshot: Optional[dict[str, Any]] = None,
    ) -> None:
        sync_doc = await self.syncs_collection.find_one(
            {"connection_id": connection_id, "aurinko_task_id": aurinko_task_id}
        )
        connection = await self.connections_collection.find_one(
            {"_id": ObjectId(connection_id)}
        )
        if not connection:
            return
        now = datetime.now(UTC)
        if change_type == "deleted":
            if sync_doc and ObjectId.is_valid(str(sync_doc.get("planner_task_id"))):
                await self.tasks_collection.update_one(
                    {"_id": ObjectId(str(sync_doc["planner_task_id"]))},
                    {"$set": {"status": "cancelled", "updated_at": now}},
                )
                await self.syncs_collection.update_one(
                    {"_id": sync_doc["_id"]},
                    {
                        "$set": {
                            "sync_status": CalendarSyncStatusValue.ORPHANED.value,
                            "last_error": "External task deleted",
                            "updated_at": now,
                        }
                    },
                )
            return
        if not snapshot:
            return

        task_update = {
            "title": snapshot.get("title")
            or snapshot.get("subject")
            or "Untitled task",
            "notes": snapshot.get("notes") or snapshot.get("description"),
            "status": self._status_from_aurinko(
                snapshot.get("status"), snapshot.get("completed")
            ),
            "external_sync_requested": True,
            "external_source_type": "aurinko_task",
            "external_last_modified_at": now,
            "updated_at": now,
        }
        if snapshot.get("due"):
            try:
                task_update["due_date"] = datetime.fromisoformat(
                    str(snapshot["due"]).replace("Z", "+00:00")
                )
            except ValueError:
                pass

        if sync_doc and ObjectId.is_valid(str(sync_doc.get("planner_task_id"))):
            planner_task_id = str(sync_doc["planner_task_id"])
            await self.tasks_collection.update_one(
                {"_id": ObjectId(planner_task_id)}, {"$set": task_update}
            )
        else:
            insert_doc = {
                **task_update,
                "planner_email": connection.get("owner_planner_email"),
                "owner_planner_id": connection.get("owner_planner_id"),
                "owner_planner_email": connection.get("owner_planner_email"),
                "created_by_user_id": connection.get("user_id"),
                "created_by_email": connection.get("user_email"),
                "assigned_user_ids": [],
                "assigned_user_emails": [],
                "wedding_id": None,
                "description": snapshot.get("notes") or snapshot.get("description"),
                "category": "other",
                "priority": "medium",
                "schedule_item_type": ScheduleItemType.TASK.value,
                "visibility_mode": "details",
                "calendar_sync_policy": "owner_only",
                "sync_target_connection_ids": [],
                "all_day": False,
                "is_recurring": False,
                "created_at": now,
                "completed_at": now if task_update["status"] == "completed" else None,
            }
            if snapshot.get("startDateTime"):
                try:
                    insert_doc["start_date"] = datetime.fromisoformat(
                        str(snapshot["startDateTime"]).replace("Z", "+00:00")
                    )
                except ValueError:
                    insert_doc["start_date"] = now
            else:
                insert_doc["start_date"] = now
            insert_doc["end_date"] = insert_doc["start_date"]
            result = await self.tasks_collection.insert_one(insert_doc)
            planner_task_id = str(result.inserted_id)

        await self.syncs_collection.update_one(
            {"connection_id": connection_id, "aurinko_task_id": aurinko_task_id},
            {
                "$set": {
                    "planner_task_id": planner_task_id,
                    "connection_id": connection_id,
                    "owner_planner_id": connection.get("owner_planner_id"),
                    "owner_planner_email": connection.get("owner_planner_email"),
                    "target_user_id": connection.get("user_id"),
                    "target_user_email": connection.get("user_email"),
                    "provider": connection.get("provider"),
                    "aurinko_task_id": aurinko_task_id,
                    "aurinko_tasklist_id": connection.get("task_sync_tasklist_id"),
                    "sync_direction": CalendarSyncDirection.BIDIRECTIONAL.value,
                    "sync_status": CalendarSyncStatusValue.SYNCED.value,
                    "last_external_etag": self._external_etag(snapshot),
                    "last_sync_at": now,
                    "last_error": None,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )

    async def process_external_task_change_async(
        self,
        *,
        aurinko_account_id: str,
        aurinko_tasklist_id: str,
        aurinko_task_id: str,
        change_type: str,
    ) -> None:
        connections = await self.connections_collection.find(
            {
                "aurinko_account_id": aurinko_account_id,
                "task_sync_tasklist_id": aurinko_tasklist_id,
                "task_sync_enabled": True,
            }
        ).to_list(length=100)
        eligible = self._dedupe_account_tasklist_connections(connections)
        connection = eligible[0] if eligible else None
        if not connection:
            return
        snapshot = None
        if change_type != "deleted":
            token = await self.provider._account_token_for_connection(connection)
            if token:
                snapshot = await self.provider.client.get_task(
                    account_token=token,
                    tasklist_id=aurinko_tasklist_id,
                    task_id=aurinko_task_id,
                )
        await self.apply_external_task_change(
            connection_id=str(connection["_id"]),
            aurinko_task_id=aurinko_task_id,
            change_type=change_type,
            snapshot=snapshot,
        )


aurinko_tasks_sync_service = AurinkoTasksSyncService()
