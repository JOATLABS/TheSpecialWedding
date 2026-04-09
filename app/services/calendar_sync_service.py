"""Resolve explicit calendar targets and maintain per-target sync mappings."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Dict, List

from fastapi import HTTPException

from app.core.database import mongo
from app.models.calendar import CalendarSyncPolicy
from app.models.calendar_sync import CalendarSyncStatusValue
from app.services.google_calendar_service import google_calendar_service


class CalendarSyncService:
    """Sync canonical planner_tasks records onto selected external calendars."""

    def __init__(self):
        self.connections_collection = mongo.get_calendar_connections_collection()
        self.syncs_collection = mongo.get_calendar_event_syncs_collection()
        self.tasks_collection = mongo.get_planner_tasks_collection()

    async def _get_connection_docs(self, query: dict) -> list[dict]:
        return await self.connections_collection.find(query).to_list(length=200)

    async def resolve_sync_targets(
        self,
        task: dict,
        explicit_connection_ids: list[str] | None = None,
    ) -> list[dict]:
        """Resolve effective writable target connections for a canonical schedule item."""
        owner_id = task.get("owner_planner_id")
        assigned_user_ids = [value for value in task.get("assigned_user_ids", []) if value]
        policy = task.get("calendar_sync_policy") or CalendarSyncPolicy.OWNER_ONLY.value
        override_enabled = bool(task.get("sync_target_override_enabled"))
        effective_explicit_ids = explicit_connection_ids
        if effective_explicit_ids is None and override_enabled:
            effective_explicit_ids = [
                value for value in task.get("sync_target_connection_ids", []) if value
            ]

        allowed_user_ids: list[str] = []
        if policy == CalendarSyncPolicy.OWNER_ONLY.value:
            allowed_user_ids = [owner_id] if owner_id else []
        elif policy == CalendarSyncPolicy.ASSIGNED_ONLY.value:
            allowed_user_ids = assigned_user_ids
        elif policy == CalendarSyncPolicy.OWNER_AND_ASSIGNED.value:
            allowed_user_ids = [value for value in [owner_id, *assigned_user_ids] if value]
        elif policy == CalendarSyncPolicy.CUSTOM.value:
            allowed_user_ids = [value for value in [owner_id, *assigned_user_ids] if value]

        base_query = {
            "owner_planner_id": owner_id,
            "user_id": {"$in": allowed_user_ids or ["__no_user__"]},
            "connection_status": "active",
            "sync_enabled": True,
            "is_writable": True,
        }
        allowed_connections = await self._get_connection_docs(base_query)
        allowed_by_id = {str(doc["_id"]): doc for doc in allowed_connections}

        if effective_explicit_ids is not None:
            explicit_targets = [
                allowed_by_id[connection_id]
                for connection_id in effective_explicit_ids
                if connection_id in allowed_by_id
            ]
            # Explicit overrides fail closed. If the scheduler selected targets
            # that are no longer allowed by policy or permission, do not guess.
            return explicit_targets

        if policy == CalendarSyncPolicy.CUSTOM.value:
            return []

        selected_targets: list[dict] = []
        if (
            assigned_user_ids
            and policy
            in {
                CalendarSyncPolicy.ASSIGNED_ONLY.value,
                CalendarSyncPolicy.OWNER_AND_ASSIGNED.value,
                CalendarSyncPolicy.CUSTOM.value,
            }
        ):
            for assigned_user_id in assigned_user_ids:
                default_connection = next(
                    (
                        doc
                        for doc in allowed_connections
                        if doc.get("user_id") == assigned_user_id
                        and doc.get("is_default_write_target")
                    ),
                    None,
                )
                if default_connection:
                    selected_targets.append(default_connection)

        if selected_targets:
            return selected_targets

        if owner_id and policy in {
            CalendarSyncPolicy.OWNER_ONLY.value,
            CalendarSyncPolicy.OWNER_AND_ASSIGNED.value,
            CalendarSyncPolicy.CUSTOM.value,
        }:
            owner_default = next(
                (
                    doc
                    for doc in allowed_connections
                    if doc.get("user_id") == owner_id and doc.get("is_default_write_target")
                ),
                None,
            )
            if owner_default:
                return [owner_default]

        return []

    async def sync_schedule_item(
        self,
        task: dict,
        *,
        explicit_connection_ids: list[str] | None = None,
        attendee_emails: list[str] | None = None,
    ) -> list[dict]:
        """Create or update all required external sync mappings for a task."""
        task_id = str(task["_id"])
        now = datetime.now(UTC)
        existing_syncs = await self.syncs_collection.find({"task_id": task_id}).to_list(length=200)
        selected_connections = await self.resolve_sync_targets(task, explicit_connection_ids)
        selected_connection_ids = {str(doc["_id"]) for doc in selected_connections}
        updated_syncs: list[dict] = []

        for sync_doc in existing_syncs:
            sync_connection_id = sync_doc.get("calendar_connection_id")
            if sync_connection_id and sync_connection_id not in selected_connection_ids:
                if sync_doc.get("external_event_id"):
                    await google_calendar_service.delete_google_event_for_connection(
                        sync_connection_id,
                        sync_doc["external_event_id"],
                    )
                await self.syncs_collection.update_one(
                    {"_id": sync_doc["_id"]},
                    {
                        "$set": {
                            "sync_status": CalendarSyncStatusValue.ORPHANED.value,
                            "updated_at": now,
                        }
                    },
                )

        if not selected_connections:
            await self.syncs_collection.update_one(
                {"task_id": task_id, "sync_status": CalendarSyncStatusValue.NOT_CONFIGURED.value},
                {
                    "$set": {
                        "task_id": task_id,
                        "owner_planner_id": task.get("owner_planner_id"),
                        "owner_planner_email": task.get("owner_planner_email") or task.get("planner_email"),
                        "sync_status": CalendarSyncStatusValue.NOT_CONFIGURED.value,
                        "updated_at": now,
                    },
                    "$setOnInsert": {"created_at": now},
                },
                upsert=True,
            )
            return await self.get_sync_status(task_id)

        await self.syncs_collection.delete_many(
            {"task_id": task_id, "sync_status": CalendarSyncStatusValue.NOT_CONFIGURED.value}
        )

        for connection_doc in selected_connections:
            connection_id = str(connection_doc["_id"])
            existing = next(
                (
                    sync_doc
                    for sync_doc in existing_syncs
                    if sync_doc.get("calendar_connection_id") == connection_id
                ),
                None,
            )
            if existing and existing.get("external_event_id"):
                success = await google_calendar_service.update_google_event_for_connection(
                    connection_id,
                    existing["external_event_id"],
                    task,
                    attendee_emails=attendee_emails,
                )
                external_event_id = existing.get("external_event_id")
                etag = existing.get("etag")
            else:
                result = await google_calendar_service.create_google_event_for_connection(
                    connection_id,
                    task,
                    attendee_emails=attendee_emails,
                )
                success = bool(result)
                external_event_id = result.get("id") if result else None
                etag = result.get("etag") if result else None

            sync_status = (
                CalendarSyncStatusValue.SYNCED.value
                if success and external_event_id
                else CalendarSyncStatusValue.FAILED.value
            )
            await self.syncs_collection.update_one(
                {"task_id": task_id, "calendar_connection_id": connection_id},
                {
                    "$set": {
                        "task_id": task_id,
                        "owner_planner_id": task.get("owner_planner_id"),
                        "owner_planner_email": task.get("owner_planner_email") or task.get("planner_email"),
                        "target_user_id": connection_doc.get("user_id"),
                        "target_user_email": connection_doc.get("user_email"),
                        "calendar_connection_id": connection_id,
                        "provider": connection_doc.get("provider", "google"),
                        "calendar_id": connection_doc.get("calendar_id"),
                        "external_event_id": external_event_id,
                        "sync_direction": "outbound",
                        "sync_status": sync_status,
                        "last_sync_at": now if success else None,
                        "last_error": None if success else "Failed to sync to provider",
                        "etag": etag,
                        "updated_at": now,
                    },
                    "$setOnInsert": {"created_at": now},
                },
                upsert=True,
            )

        updated_syncs = await self.get_sync_status(task_id)
        return updated_syncs

    async def delete_schedule_item_syncs(self, task_id: str) -> None:
        """Delete all external event projections and local mapping rows."""
        sync_docs = await self.syncs_collection.find({"task_id": task_id}).to_list(length=200)
        failed_deletions: list[str] = []
        for sync_doc in sync_docs:
            connection_id = sync_doc.get("calendar_connection_id")
            external_event_id = sync_doc.get("external_event_id")
            if connection_id and external_event_id:
                deleted = await google_calendar_service.delete_google_event_for_connection(
                    connection_id,
                    external_event_id,
                )
                if not deleted:
                    failed_deletions.append(str(sync_doc.get("_id") or external_event_id))
        if failed_deletions:
            raise HTTPException(
                status_code=502,
                detail="Failed to delete one or more external calendar events. Internal record was preserved.",
            )
        await self.syncs_collection.delete_many({"task_id": task_id})

    async def get_sync_status(self, task_id: str) -> list[dict]:
        """List per-target sync rows for a canonical schedule item."""
        docs = await self.syncs_collection.find({"task_id": task_id}).to_list(length=200)
        result = []
        for doc in docs:
            result.append(
                {
                    "id": str(doc["_id"]),
                    "task_id": doc.get("task_id"),
                    "target_user_id": doc.get("target_user_id"),
                    "target_user_email": doc.get("target_user_email"),
                    "calendar_connection_id": doc.get("calendar_connection_id"),
                    "provider": doc.get("provider"),
                    "calendar_id": doc.get("calendar_id"),
                    "external_event_id": doc.get("external_event_id"),
                    "sync_status": doc.get("sync_status"),
                    "last_sync_at": doc.get("last_sync_at"),
                    "last_error": doc.get("last_error"),
                    "updated_at": doc.get("updated_at"),
                }
            )
        return result


calendar_sync_service = CalendarSyncService()
