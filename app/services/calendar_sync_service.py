"""Resolve explicit calendar targets and maintain per-target sync mappings."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from bson import ObjectId
from fastapi import HTTPException
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.core.config import settings
from app.core.database import mongo
from app.models.calendar import CalendarSyncPolicy, ScheduleItemType
from app.models.calendar_connection import (
    CalendarSchedulerAccessMode,
    CalendarSchedulerRole,
    CalendarSyncTargetingMode,
)
from app.models.calendar_sync import CalendarSyncStatusValue
from app.services.calendar_audit_service import calendar_audit_service
from app.services.calendar_provider_service import calendar_provider_service


class CalendarSyncService:
    """Sync canonical planner_tasks records onto selected external calendars."""

    def __init__(self):
        self.connections_collection = mongo.get_calendar_connections_collection()
        self.syncs_collection = mongo.get_calendar_event_syncs_collection()
        self.tasks_collection = mongo.get_planner_tasks_collection()

    async def _get_connection_docs(self, query: dict) -> list[dict]:
        return await self.connections_collection.find(query).to_list(length=200)

    def _actor_can_schedule_on_connection(
        self,
        connection_doc: dict[str, Any],
        *,
        actor_user_id: str | None,
        actor_is_owner: bool,
        actor_role_scope: str | None = None,
    ) -> bool:
        if actor_is_owner:
            return True
        if not actor_user_id:
            return False

        scheduler_access_mode = str(
            connection_doc.get("scheduler_access_mode")
            or CalendarSchedulerAccessMode.WORKSPACE_DEFAULT.value
        )
        explicit_allowed_scheduler_user_ids = {
            str(value)
            for value in connection_doc.get("allowed_scheduler_user_ids", [])
            if value
        }
        owner_id = str(connection_doc.get("owner_planner_id") or "")
        connection_user_id = str(connection_doc.get("user_id") or "")

        base_allowed = False
        if scheduler_access_mode == CalendarSchedulerAccessMode.OWNER_ONLY.value:
            base_allowed = False
        elif (
            scheduler_access_mode
            == CalendarSchedulerAccessMode.OWNER_AND_CONNECTION_USER.value
        ):
            base_allowed = bool(
                connection_user_id and actor_user_id == connection_user_id
            )
        elif (
            scheduler_access_mode
            == CalendarSchedulerAccessMode.WORKSPACE_PERMITTED.value
        ):
            base_allowed = True
        else:
            owner_connection = bool(
                owner_id and connection_user_id and owner_id == connection_user_id
            )
            base_allowed = owner_connection or (
                bool(connection_user_id) and actor_user_id == connection_user_id
            )

        # Precedence is explicit: base access mode defines the default actor set,
        # user grants can widen that set, and role/item/wedding rules only narrow it.
        if not (base_allowed or actor_user_id in explicit_allowed_scheduler_user_ids):
            return False

        explicit_allowed_scheduler_roles = [
            str(value)
            for value in connection_doc.get("allowed_scheduler_roles", [])
            if value
        ]
        if explicit_allowed_scheduler_roles:
            effective_role = actor_role_scope or CalendarSchedulerRole.VIEWER.value
            if effective_role not in set(explicit_allowed_scheduler_roles):
                return False

        return True

    def _task_schedule_item_type(self, task: dict[str, Any]) -> str:
        raw_type = str(task.get("schedule_item_type") or "").strip()
        valid_types = {item.value for item in ScheduleItemType}
        if raw_type in valid_types:
            return raw_type
        if str(task.get("category") or "") == "meeting":
            return ScheduleItemType.MEETING.value
        return ScheduleItemType.TASK.value

    def _connection_allows_task(
        self,
        connection_doc: dict[str, Any],
        task: dict[str, Any],
    ) -> bool:
        allowed_schedule_item_types = {
            str(value)
            for value in connection_doc.get("allowed_schedule_item_types", [])
            if value
        }
        if allowed_schedule_item_types and (
            self._task_schedule_item_type(task) not in allowed_schedule_item_types
        ):
            return False

        allowed_wedding_ids = {
            str(value)
            for value in connection_doc.get("allowed_wedding_ids", [])
            if value
        }
        if allowed_wedding_ids:
            task_wedding_id = task.get("wedding_id")
            if not task_wedding_id:
                return False
            if str(task_wedding_id) not in allowed_wedding_ids:
                return False

        return True

    def _connection_allows_automatic_targeting(
        self,
        connection_doc: dict[str, Any],
    ) -> bool:
        targeting_mode = str(
            connection_doc.get("sync_targeting_mode")
            or CalendarSyncTargetingMode.AUTOMATIC_AND_MANUAL.value
        )
        return targeting_mode == CalendarSyncTargetingMode.AUTOMATIC_AND_MANUAL.value

    def _summarize_sync_docs(self, sync_docs: list[dict[str, Any]]) -> dict[str, Any]:
        status_counts = {
            CalendarSyncStatusValue.SYNCED.value: 0,
            CalendarSyncStatusValue.FAILED.value: 0,
            CalendarSyncStatusValue.ORPHANED.value: 0,
            CalendarSyncStatusValue.NOT_CONFIGURED.value: 0,
            CalendarSyncStatusValue.PENDING.value: 0,
        }
        primary_external_event_id: str | None = None
        last_sync_at: datetime | None = None

        for doc in sync_docs:
            status = str(
                doc.get("sync_status") or CalendarSyncStatusValue.PENDING.value
            )
            if status in status_counts:
                status_counts[status] += 1
            if not primary_external_event_id and doc.get("external_event_id"):
                primary_external_event_id = str(doc["external_event_id"])
            sync_time = doc.get("last_sync_at")
            if isinstance(sync_time, datetime) and (
                last_sync_at is None or sync_time > last_sync_at
            ):
                last_sync_at = sync_time

        return {
            "row_count": len(sync_docs),
            "synced_target_count": status_counts[CalendarSyncStatusValue.SYNCED.value],
            "failed_target_count": status_counts[CalendarSyncStatusValue.FAILED.value],
            "orphaned_target_count": status_counts[
                CalendarSyncStatusValue.ORPHANED.value
            ],
            "not_configured_target_count": status_counts[
                CalendarSyncStatusValue.NOT_CONFIGURED.value
            ],
            "pending_target_count": status_counts[
                CalendarSyncStatusValue.PENDING.value
            ],
            "has_synced_target": bool(
                status_counts[CalendarSyncStatusValue.SYNCED.value]
            ),
            "has_configured_target": any(
                doc.get("calendar_connection_id")
                and doc.get("sync_status")
                != CalendarSyncStatusValue.NOT_CONFIGURED.value
                for doc in sync_docs
            ),
            "primary_external_event_id": primary_external_event_id,
            "last_sync_at": last_sync_at,
        }

    def _sync_row_base(
        self,
        *,
        task: dict[str, Any],
        connection_doc: dict[str, Any],
        now: datetime,
    ) -> dict[str, Any]:
        return {
            "task_id": str(task["_id"]),
            "owner_planner_id": task.get("owner_planner_id"),
            "owner_planner_email": task.get("owner_planner_email")
            or task.get("planner_email"),
            "target_user_id": connection_doc.get("user_id"),
            "target_user_email": connection_doc.get("user_email"),
            "calendar_connection_id": str(connection_doc["_id"]),
            "provider": connection_doc.get("provider", "google"),
            "calendar_id": connection_doc.get("calendar_id"),
            "sync_direction": "outbound",
            "updated_at": now,
        }

    def _retry_backoff(self, retry_count: int) -> timedelta:
        capped_attempts = min(
            max(retry_count, 1), settings.CALENDAR_SYNC_RETRY_MAX_ATTEMPTS
        )
        seconds = settings.CALENDAR_SYNC_RETRY_INITIAL_BACKOFF_SECONDS * (
            2 ** (capped_attempts - 1)
        )
        max_seconds = settings.CALENDAR_SYNC_RETRY_INITIAL_BACKOFF_SECONDS * 32
        return timedelta(seconds=min(seconds, max_seconds))

    def _build_failure_state(
        self,
        *,
        existing_retry_count: int,
        classification: dict[str, Any],
        now: datetime,
    ) -> dict[str, Any]:
        retry_count = existing_retry_count + 1
        retryable = bool(classification.get("retryable", False)) and (
            retry_count <= settings.CALENDAR_SYNC_RETRY_MAX_ATTEMPTS
        )
        next_retry_at = now + self._retry_backoff(retry_count) if retryable else None
        return {
            "sync_status": CalendarSyncStatusValue.FAILED.value,
            "last_sync_at": None,
            "last_error": classification.get("error_message")
            or "Failed to sync to provider",
            "last_error_category": classification.get("error_category"),
            "retryable_error": retryable,
            "retry_count": retry_count,
            "last_retry_at": now,
            "next_retry_at": next_retry_at,
            "updated_at": now,
        }

    def _build_success_state(
        self,
        *,
        now: datetime,
        external_event_id: str | None,
        etag: str | None,
    ) -> dict[str, Any]:
        return {
            "external_event_id": external_event_id,
            "etag": etag,
            "sync_status": (
                CalendarSyncStatusValue.SYNCED.value
                if external_event_id
                else CalendarSyncStatusValue.FAILED.value
            ),
            "last_sync_at": now if external_event_id else None,
            "last_error": None if external_event_id else "Failed to sync to provider",
            "last_error_category": None,
            "retryable_error": False,
            "retry_count": 0,
            "last_retry_at": None,
            "next_retry_at": None,
            "last_drift_check_at": now if external_event_id else None,
            "updated_at": now,
        }

    def _coerce_provider_result(self, result: Any) -> dict[str, Any]:
        if isinstance(result, dict):
            return result
        return {
            "success": bool(result),
            "retryable": False,
            "error_category": None,
            "error_message": None if result else "Failed to sync to provider",
            "status_code": None,
        }

    async def _log_sync_failure(
        self,
        *,
        task: dict[str, Any],
        connection_doc: dict[str, Any] | None,
        classification: dict[str, Any],
    ) -> None:
        await calendar_audit_service.log(
            action="calendar_sync_failed",
            message=(
                f"Failed to sync {task.get('title') or 'schedule item'} to "
                f"{(connection_doc or {}).get('calendar_name') or 'external calendar'}"
            ),
            owner_planner_email=task.get("owner_planner_email")
            or task.get("planner_email"),
            actor_email=task.get("created_by_email")
            or task.get("owner_planner_email")
            or task.get("planner_email"),
            wedding_id=task.get("wedding_id"),
            metadata={
                "task_id": str(task.get("_id")),
                "calendar_connection_id": (
                    str(connection_doc.get("_id"))
                    if isinstance(connection_doc, dict)
                    else None
                ),
                "error_category": classification.get("error_category"),
                "retryable": classification.get("retryable", False),
                "status_code": classification.get("status_code"),
                "error_message": classification.get("error_message"),
            },
        )

    async def _claim_provider_create_slot(
        self,
        *,
        task: dict[str, Any],
        connection_doc: dict[str, Any],
        now: datetime,
    ) -> tuple[dict[str, Any] | None, str]:
        claim_token = uuid4().hex
        task_id = str(task["_id"])
        connection_id = str(connection_doc["_id"])
        stale_before = now - timedelta(minutes=5)
        base_doc = self._sync_row_base(
            task=task, connection_doc=connection_doc, now=now
        )

        try:
            claimed_doc = await self.syncs_collection.find_one_and_update(
                {
                    "task_id": task_id,
                    "calendar_connection_id": connection_id,
                    "$and": [
                        {
                            "$or": [
                                {"provider_create_claim_token": {"$exists": False}},
                                {"provider_create_claim_token": None},
                                {"provider_create_claimed_at": {"$lt": stale_before}},
                            ]
                        },
                        {
                            "$or": [
                                {"external_event_id": {"$exists": False}},
                                {"external_event_id": None},
                            ]
                        },
                    ],
                },
                {
                    "$set": {
                        **base_doc,
                        "sync_status": CalendarSyncStatusValue.PENDING.value,
                        "last_error": None,
                        "provider_create_claim_token": claim_token,
                        "provider_create_claimed_at": now,
                    },
                    "$setOnInsert": {"created_at": now},
                },
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )
        except DuplicateKeyError:
            claimed_doc = None

        if claimed_doc is None:
            existing_doc = await self.syncs_collection.find_one(
                {
                    "task_id": task_id,
                    "calendar_connection_id": connection_id,
                }
            )
            if isinstance(existing_doc, dict) and existing_doc.get("external_event_id"):
                return existing_doc, ""
            return None, ""
        return claimed_doc, claim_token

    async def resolve_sync_targets(
        self,
        task: dict,
        explicit_connection_ids: list[str] | None = None,
        *,
        actor_user_id: str | None = None,
        actor_is_owner: bool = False,
        actor_role_scope: str | None = None,
    ) -> list[dict]:
        """Resolve effective writable target connections for a canonical schedule item."""
        owner_id = task.get("owner_planner_id")
        assigned_user_ids = [
            value for value in task.get("assigned_user_ids", []) if value
        ]
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
        elif (
            policy == CalendarSyncPolicy.OWNER_AND_ASSIGNED.value
            or policy == CalendarSyncPolicy.CUSTOM.value
        ):
            allowed_user_ids = [
                value for value in [owner_id, *assigned_user_ids] if value
            ]

        base_query = {
            "owner_planner_id": owner_id,
            "user_id": {"$in": allowed_user_ids or ["__no_user__"]},
            "connection_status": "active",
            "sync_enabled": True,
            "is_writable": True,
        }
        owner_scope_connections = await self._get_connection_docs(base_query)
        allowed_connections = [
            doc
            for doc in owner_scope_connections
            if self._actor_can_schedule_on_connection(
                doc,
                actor_user_id=actor_user_id,
                actor_is_owner=actor_is_owner,
                actor_role_scope=actor_role_scope,
            )
            and self._connection_allows_task(doc, task)
        ]
        allowed_by_id = {str(doc["_id"]): doc for doc in allowed_connections}
        automatically_selectable_connections = [
            doc
            for doc in allowed_connections
            if self._connection_allows_automatic_targeting(doc)
        ]

        if effective_explicit_ids is not None:
            explicit_targets = [
                allowed_by_id[connection_id]
                for connection_id in effective_explicit_ids
                if connection_id in allowed_by_id
            ]
            # Explicit overrides fail closed. If the scheduler selected targets
            # that are no longer allowed by policy or permission, do not guess.
            return list({str(doc["_id"]): doc for doc in explicit_targets}.values())

        if policy == CalendarSyncPolicy.CUSTOM.value:
            return []

        selected_targets: list[dict] = []
        if assigned_user_ids and policy in {
            CalendarSyncPolicy.ASSIGNED_ONLY.value,
            CalendarSyncPolicy.OWNER_AND_ASSIGNED.value,
            CalendarSyncPolicy.CUSTOM.value,
        }:
            for assigned_user_id in assigned_user_ids:
                default_connection = next(
                    (
                        doc
                        for doc in automatically_selectable_connections
                        if doc.get("user_id") == assigned_user_id
                        and doc.get("is_default_write_target")
                    ),
                    None,
                )
                if default_connection:
                    selected_targets.append(default_connection)

        if selected_targets:
            return list({str(doc["_id"]): doc for doc in selected_targets}.values())

        if owner_id and policy in {
            CalendarSyncPolicy.OWNER_ONLY.value,
            CalendarSyncPolicy.OWNER_AND_ASSIGNED.value,
            CalendarSyncPolicy.CUSTOM.value,
        }:
            owner_default = next(
                (
                    doc
                    for doc in automatically_selectable_connections
                    if doc.get("user_id") == owner_id
                    and doc.get("is_default_write_target")
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
        actor_user_id: str | None = None,
        actor_is_owner: bool = False,
        actor_role_scope: str | None = None,
    ) -> list[dict]:
        """Create or update all required external sync mappings for a task."""
        task_id = str(task["_id"])
        now = datetime.now(UTC)
        existing_syncs = await self.syncs_collection.find({"task_id": task_id}).to_list(
            length=200
        )
        selected_connections = await self.resolve_sync_targets(
            task,
            explicit_connection_ids,
            actor_user_id=actor_user_id,
            actor_is_owner=actor_is_owner,
            actor_role_scope=actor_role_scope,
        )
        existing_by_connection_id = {
            sync_doc.get("calendar_connection_id"): sync_doc
            for sync_doc in existing_syncs
        }
        selected_connection_ids = {str(doc["_id"]) for doc in selected_connections}
        updated_syncs: list[dict] = []

        for sync_doc in existing_syncs:
            sync_connection_id = sync_doc.get("calendar_connection_id")
            if sync_connection_id and sync_connection_id not in selected_connection_ids:
                if sync_doc.get("external_event_id"):
                    delete_result = self._coerce_provider_result(
                        await calendar_provider_service.delete_event_for_connection(
                            sync_connection_id,
                            sync_doc["external_event_id"],
                        )
                    )
                    if not delete_result.get("success"):
                        failure_state = self._build_failure_state(
                            existing_retry_count=int(sync_doc.get("retry_count") or 0),
                            classification=delete_result,
                            now=now,
                        )
                        failure_state["last_error"] = (
                            "Failed to remove provider event for deselected calendar"
                        )
                        await self.syncs_collection.update_one(
                            {"_id": sync_doc["_id"]},
                            {
                                "$set": {
                                    **failure_state,
                                    "calendar_connection_id": sync_connection_id,
                                    "calendar_id": sync_doc.get("calendar_id"),
                                }
                            },
                        )
                        await self._log_sync_failure(
                            task=task,
                            connection_doc=None,
                            classification=delete_result,
                        )
                        continue
                await self.syncs_collection.update_one(
                    {"_id": sync_doc["_id"]},
                    {
                        "$set": {
                            "sync_status": CalendarSyncStatusValue.ORPHANED.value,
                            "last_error": None,
                            "last_error_category": None,
                            "retryable_error": False,
                            "next_retry_at": None,
                            "updated_at": now,
                        }
                    },
                )

        if not selected_connections:
            await self.syncs_collection.update_one(
                {
                    "task_id": task_id,
                    "sync_status": CalendarSyncStatusValue.NOT_CONFIGURED.value,
                },
                {
                    "$set": {
                        "task_id": task_id,
                        "owner_planner_id": task.get("owner_planner_id"),
                        "owner_planner_email": task.get("owner_planner_email")
                        or task.get("planner_email"),
                        "sync_status": CalendarSyncStatusValue.NOT_CONFIGURED.value,
                        "last_error": None,
                        "last_error_category": None,
                        "retryable_error": False,
                        "retry_count": 0,
                        "next_retry_at": None,
                        "last_retry_at": None,
                        "updated_at": now,
                    },
                    "$setOnInsert": {"created_at": now},
                },
                upsert=True,
            )
            return await self.get_sync_status(task_id)

        await self.syncs_collection.delete_many(
            {
                "task_id": task_id,
                "sync_status": CalendarSyncStatusValue.NOT_CONFIGURED.value,
            }
        )

        for connection_doc in selected_connections:
            connection_id = str(connection_doc["_id"])
            existing = existing_by_connection_id.get(connection_id)
            if existing and existing.get("external_event_id"):
                provider_result = self._coerce_provider_result(
                    await calendar_provider_service.update_event_for_connection(
                        connection_id,
                        existing["external_event_id"],
                        task,
                        attendee_emails=attendee_emails,
                    )
                )
                success = bool(provider_result.get("success"))
                external_event_id = provider_result.get(
                    "external_event_id"
                ) or existing.get("external_event_id")
                etag = provider_result.get("etag") or existing.get("etag")
            else:
                claimed_doc, claim_token = await self._claim_provider_create_slot(
                    task=task,
                    connection_doc=connection_doc,
                    now=now,
                )
                if claimed_doc is None:
                    continue
                if claimed_doc.get("external_event_id"):
                    provider_result = self._coerce_provider_result(
                        await calendar_provider_service.update_event_for_connection(
                            connection_id,
                            claimed_doc["external_event_id"],
                            task,
                            attendee_emails=attendee_emails,
                        )
                    )
                    success = bool(provider_result.get("success"))
                    external_event_id = claimed_doc.get("external_event_id")
                    etag = provider_result.get("etag") or claimed_doc.get("etag")
                    existing = claimed_doc
                else:
                    provider_result = self._coerce_provider_result(
                        await calendar_provider_service.create_event_for_connection(
                            connection_id,
                            task,
                            attendee_emails=attendee_emails,
                        )
                    )
                    success = bool(provider_result.get("success"))
                    external_event_id = provider_result.get("external_event_id")
                    etag = provider_result.get("etag")
                    create_state = (
                        self._build_success_state(
                            now=now,
                            external_event_id=external_event_id,
                            etag=etag,
                        )
                        if success
                        else self._build_failure_state(
                            existing_retry_count=int(
                                claimed_doc.get("retry_count") or 0
                            ),
                            classification=provider_result,
                            now=now,
                        )
                    )
                    await self.syncs_collection.update_one(
                        {
                            "task_id": task_id,
                            "calendar_connection_id": connection_id,
                            "provider_create_claim_token": claim_token,
                        },
                        {
                            "$set": {
                                **self._sync_row_base(
                                    task=task,
                                    connection_doc=connection_doc,
                                    now=now,
                                ),
                                **create_state,
                            },
                            "$unset": {
                                "provider_create_claim_token": "",
                                "provider_create_claimed_at": "",
                            },
                            "$setOnInsert": {"created_at": now},
                        },
                        upsert=True,
                    )
                    existing_by_connection_id[connection_id] = (
                        await self.syncs_collection.find_one(
                            {
                                "task_id": task_id,
                                "calendar_connection_id": connection_id,
                            }
                        )
                        or {}
                    )
                    if not success:
                        await self._log_sync_failure(
                            task=task,
                            connection_doc=connection_doc,
                            classification=provider_result,
                        )
                    continue

            sync_state = (
                self._build_success_state(
                    now=now,
                    external_event_id=external_event_id,
                    etag=etag,
                )
                if success
                else self._build_failure_state(
                    existing_retry_count=int((existing or {}).get("retry_count") or 0),
                    classification=provider_result,
                    now=now,
                )
            )
            await self.syncs_collection.update_one(
                {"task_id": task_id, "calendar_connection_id": connection_id},
                {
                    "$set": {
                        "task_id": task_id,
                        "owner_planner_id": task.get("owner_planner_id"),
                        "owner_planner_email": task.get("owner_planner_email")
                        or task.get("planner_email"),
                        "target_user_id": connection_doc.get("user_id"),
                        "target_user_email": connection_doc.get("user_email"),
                        "calendar_connection_id": connection_id,
                        "provider": connection_doc.get("provider", "google"),
                        "calendar_id": connection_doc.get("calendar_id"),
                        "sync_direction": "outbound",
                        **sync_state,
                    },
                    "$unset": {
                        "provider_create_claim_token": "",
                        "provider_create_claimed_at": "",
                    },
                    "$setOnInsert": {"created_at": now},
                },
                upsert=True,
            )
            if not success:
                await self._log_sync_failure(
                    task=task,
                    connection_doc=connection_doc,
                    classification=provider_result,
                )

        updated_syncs = await self.get_sync_status(task_id)
        return updated_syncs

    async def delete_schedule_item_syncs(self, task_id: str) -> None:
        """Delete all external event projections and local mapping rows."""
        sync_docs = await self.syncs_collection.find({"task_id": task_id}).to_list(
            length=200
        )
        failed_deletions: list[str] = []
        for sync_doc in sync_docs:
            connection_id = sync_doc.get("calendar_connection_id")
            external_event_id = sync_doc.get("external_event_id")
            if connection_id and external_event_id:
                delete_result = self._coerce_provider_result(
                    await calendar_provider_service.delete_event_for_connection(
                        connection_id,
                        external_event_id,
                    )
                )
                if not delete_result.get("success"):
                    await self.syncs_collection.update_one(
                        {"_id": sync_doc["_id"]},
                        {
                            "$set": self._build_failure_state(
                                existing_retry_count=int(
                                    sync_doc.get("retry_count") or 0
                                ),
                                classification=delete_result,
                                now=datetime.now(UTC),
                            )
                        },
                    )
                    failed_deletions.append(
                        str(sync_doc.get("_id") or external_event_id)
                    )
        if failed_deletions:
            raise HTTPException(
                status_code=502,
                detail="Failed to delete one or more external calendar events. Internal record was preserved.",
            )
        await self.syncs_collection.delete_many({"task_id": task_id})

    async def process_due_retries(self, *, limit: int) -> dict[str, int]:
        """Retry transient per-target sync failures with capped backoff."""
        now = datetime.now(UTC)
        due_rows = (
            await self.syncs_collection.find(
                {
                    "sync_status": CalendarSyncStatusValue.FAILED.value,
                    "retryable_error": True,
                    "next_retry_at": {"$lte": now},
                    "calendar_connection_id": {"$exists": True, "$ne": None},
                }
            )
            .sort("next_retry_at", 1)
            .limit(limit)
            .to_list(length=limit)
        )
        processed = 0
        succeeded = 0
        failed = 0
        for sync_doc in due_rows:
            processed += 1
            if await self._retry_sync_row(sync_doc):
                succeeded += 1
            else:
                failed += 1
        return {"processed": processed, "succeeded": succeeded, "failed": failed}

    async def _retry_sync_row(self, sync_doc: dict[str, Any]) -> bool:
        task_id = sync_doc.get("task_id")
        if not task_id:
            return False
        try:
            task_oid = ObjectId(task_id)
        except Exception:
            task_oid = task_id
        task = await self.tasks_collection.find_one({"_id": task_oid})
        if not isinstance(task, dict):
            await self.syncs_collection.update_one(
                {"_id": sync_doc["_id"]},
                {
                    "$set": {
                        "sync_status": CalendarSyncStatusValue.ORPHANED.value,
                        "last_error": "Canonical schedule item no longer exists",
                        "last_error_category": "missing_task",
                        "retryable_error": False,
                        "next_retry_at": None,
                        "updated_at": datetime.now(UTC),
                    }
                },
            )
            return False

        selected = await self.resolve_sync_targets(task, actor_is_owner=True)
        selected_by_id = {str(doc["_id"]): doc for doc in selected}
        connection_id = sync_doc.get("calendar_connection_id")
        if connection_id not in selected_by_id:
            await self.syncs_collection.update_one(
                {"_id": sync_doc["_id"]},
                {
                    "$set": {
                        "sync_status": CalendarSyncStatusValue.ORPHANED.value,
                        "last_error": "Retry target is no longer selected by current sync policy",
                        "last_error_category": "deselected_target",
                        "retryable_error": False,
                        "next_retry_at": None,
                        "updated_at": datetime.now(UTC),
                    }
                },
            )
            return False

        await calendar_audit_service.log(
            action="calendar_sync_retried",
            message=f"Retrying calendar sync for {task.get('title') or 'schedule item'}",
            owner_planner_email=task.get("owner_planner_email")
            or task.get("planner_email"),
            actor_email=task.get("owner_planner_email") or task.get("planner_email"),
            wedding_id=task.get("wedding_id"),
            metadata={
                "task_id": task_id,
                "calendar_connection_id": connection_id,
                "retry_count": int(sync_doc.get("retry_count") or 0),
            },
        )

        await self.sync_schedule_item(
            task,
            explicit_connection_ids=[connection_id],
            actor_is_owner=True,
        )
        refreshed = await self.syncs_collection.find_one({"_id": sync_doc["_id"]})
        return bool(
            isinstance(refreshed, dict)
            and refreshed.get("sync_status") == CalendarSyncStatusValue.SYNCED.value
        )

    async def run_drift_checks(self, *, limit: int) -> int:
        """Check synced rows for missing provider events or lost provider access."""
        now = datetime.now(UTC)
        cutoff = now - timedelta(minutes=settings.CALENDAR_DRIFT_CHECK_INTERVAL_MINUTES)
        due_rows = (
            await self.syncs_collection.find(
                {
                    "sync_status": CalendarSyncStatusValue.SYNCED.value,
                    "calendar_connection_id": {"$exists": True, "$ne": None},
                    "$or": [
                        {"last_drift_check_at": {"$exists": False}},
                        {"last_drift_check_at": None},
                        {"last_drift_check_at": {"$lt": cutoff}},
                    ],
                }
            )
            .sort("last_drift_check_at", 1)
            .limit(limit)
            .to_list(length=limit)
        )
        checked = 0
        for sync_doc in due_rows:
            connection_id = sync_doc.get("calendar_connection_id")
            external_event_id = sync_doc.get("external_event_id")
            if not connection_id or not external_event_id:
                continue
            checked += 1
            result = await calendar_provider_service.get_event_for_connection(
                connection_id,
                external_event_id,
            )
            if result.get("success"):
                await self.syncs_collection.update_one(
                    {"_id": sync_doc["_id"]},
                    {
                        "$set": {
                            "last_drift_check_at": now,
                            "last_error": None,
                            "last_error_category": None,
                            "updated_at": now,
                        }
                    },
                )
                continue

            error_category = result.get("error_category")
            if error_category == "not_found":
                await self.syncs_collection.update_one(
                    {"_id": sync_doc["_id"]},
                    {
                        "$set": {
                            "sync_status": CalendarSyncStatusValue.ORPHANED.value,
                            "last_error": "Provider event no longer exists",
                            "last_error_category": "provider_event_missing",
                            "retryable_error": False,
                            "next_retry_at": None,
                            "last_drift_check_at": now,
                            "updated_at": now,
                        }
                    },
                )
            else:
                await self.syncs_collection.update_one(
                    {"_id": sync_doc["_id"]},
                    {
                        "$set": {
                            **self._build_failure_state(
                                existing_retry_count=int(
                                    sync_doc.get("retry_count") or 0
                                ),
                                classification=result,
                                now=now,
                            ),
                            "last_drift_check_at": now,
                        }
                    },
                )
        return checked

    async def get_sync_status(self, task_id: str) -> list[dict]:
        """List per-target sync rows for a canonical schedule item."""
        docs = await self.syncs_collection.find({"task_id": task_id}).to_list(
            length=200
        )
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
                    "last_error_category": doc.get("last_error_category"),
                    "retryable_error": doc.get("retryable_error", False),
                    "retry_count": doc.get("retry_count", 0),
                    "next_retry_at": doc.get("next_retry_at"),
                    "last_retry_at": doc.get("last_retry_at"),
                    "last_drift_check_at": doc.get("last_drift_check_at"),
                    "updated_at": doc.get("updated_at"),
                }
            )
        return result

    async def get_sync_summary(self, task_id: str) -> dict[str, Any]:
        """Summarize sync rows for one canonical schedule item."""
        sync_docs = await self.syncs_collection.find({"task_id": task_id}).to_list(
            length=200
        )
        return self._summarize_sync_docs(sync_docs)

    async def get_sync_summary_map(
        self, task_ids: list[str]
    ) -> dict[str, dict[str, Any]]:
        """Load sync summaries for multiple schedule items in one query."""
        normalized_ids = list(
            dict.fromkeys(str(task_id) for task_id in task_ids if task_id)
        )
        if not normalized_ids:
            return {}

        sync_docs = await self.syncs_collection.find(
            {"task_id": {"$in": normalized_ids}}
        ).to_list(length=5000)
        grouped: dict[str, list[dict[str, Any]]] = {
            task_id: [] for task_id in normalized_ids
        }
        for doc in sync_docs:
            task_id = str(doc.get("task_id") or "")
            if not task_id:
                continue
            grouped.setdefault(task_id, []).append(doc)
        return {
            task_id: self._summarize_sync_docs(grouped.get(task_id, []))
            for task_id in normalized_ids
        }


calendar_sync_service = CalendarSyncService()
