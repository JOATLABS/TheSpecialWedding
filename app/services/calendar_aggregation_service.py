"""Aggregate canonical planner tasks with shared external calendar events."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Optional

from bson import ObjectId

from app.core.database import mongo
from app.models.calendar import VisibilityMode
from app.services.google_calendar_service import google_calendar_service


class CalendarAggregationService:
    """Build a shared calendar feed for planner owners and team members."""

    def __init__(self):
        self.tasks_collection = mongo.get_planner_tasks_collection()

    def _build_internal_query(
        self,
        *,
        owner_email: Optional[str],
        wedding_ids: Optional[list[str]],
        staff_ids: Optional[list[str]],
        start: datetime,
        end: datetime,
        source_types: Optional[list[str]],
        accessible_wedding_ids: Optional[list[str]],
    ) -> dict[str, Any]:
        query: dict[str, Any] = {
            "$or": [
                {"start_date": {"$gte": start, "$lte": end}},
                {"end_date": {"$gte": start, "$lte": end}},
                {
                    "start_date": {"$lt": start},
                    "end_date": {"$gte": end},
                },
            ]
        }

        owner_filters = []
        if owner_email:
            owner_filters.append({"owner_planner_email": owner_email})
            owner_filters.append({"planner_email": owner_email})
        if owner_filters:
            query["$and"] = [{"$or": owner_filters}]

        if accessible_wedding_ids is not None:
            query["wedding_id"] = {"$in": accessible_wedding_ids}
        if wedding_ids:
            query["wedding_id"] = {"$in": wedding_ids}
        if staff_ids:
            query["$or"] = query.get("$or", [])
            query["assigned_user_ids"] = {"$in": staff_ids}
        if source_types:
            schedule_item_types = []
            if "internal_meeting" in source_types:
                schedule_item_types.append("meeting")
            if "internal_task" in source_types:
                schedule_item_types.append("task")
            if schedule_item_types:
                query["schedule_item_type"] = {"$in": schedule_item_types}
        return query

    def _normalize_internal(self, task: dict) -> dict:
        schedule_item_type = task.get("schedule_item_type") or (
            "meeting" if task.get("category") == "meeting" else "task"
        )
        assigned_user_ids = task.get("assigned_user_ids", [])
        assigned_user_emails = task.get("assigned_user_emails", [])
        if not assigned_user_ids and task.get("owner_planner_id"):
            assigned_user_ids = [task.get("owner_planner_id")]
        if not assigned_user_emails and (
            task.get("owner_planner_email") or task.get("planner_email")
        ):
            assigned_user_emails = [
                task.get("owner_planner_email") or task.get("planner_email")
            ]
        return {
            "id": str(task["_id"]),
            "source_type": f"internal_{schedule_item_type}",
            "title": task.get("title"),
            "start_date": task.get("start_date"),
            "end_date": task.get("end_date"),
            "all_day": task.get("all_day", False),
            "wedding_id": task.get("wedding_id"),
            "owner_planner_email": task.get("owner_planner_email") or task.get("planner_email"),
            "assigned_user_ids": assigned_user_ids,
            "assigned_user_emails": assigned_user_emails,
            "visibility_mode": task.get("visibility_mode", VisibilityMode.DETAILS.value),
            "details": {
                "description": task.get("description"),
                "category": task.get("category"),
                "priority": task.get("priority"),
                "status": task.get("status"),
                "meeting_status": task.get("meeting_status"),
                "conference_url": task.get("conference_url"),
                "invite_delivery_mode": task.get("invite_delivery_mode"),
            },
        }

    def _normalize_external(self, event: dict, can_view_details: bool) -> dict:
        connection = event.get("_connection", {})
        details_visibility = connection.get("details_visibility", VisibilityMode.BUSY_ONLY.value)
        show_details = details_visibility == VisibilityMode.DETAILS.value and can_view_details
        start_info = event.get("start", {})
        end_info = event.get("end", {})
        return {
            "id": event.get("id"),
            "source_type": "external_google",
            "title": event.get("summary") if show_details else "Busy",
            "start_date": start_info.get("dateTime") or start_info.get("date"),
            "end_date": end_info.get("dateTime") or end_info.get("date"),
            "all_day": bool(start_info.get("date") and not start_info.get("dateTime")),
            "wedding_id": None,
            "owner_planner_email": connection.get("owner_planner_email"),
            "assigned_user_ids": [connection.get("user_id")] if connection.get("user_id") else [],
            "assigned_user_emails": [connection.get("user_email")] if connection.get("user_email") else [],
            "visibility_mode": details_visibility,
            "details": {
                "calendar_connection_id": connection.get("id"),
                "calendar_name": connection.get("calendar_name"),
                "provider_account_email": connection.get("provider_account_email"),
                "description": event.get("description") if show_details else None,
            },
        }

    async def build_shared_view(
        self,
        *,
        owner_id: str,
        owner_email: Optional[str],
        current_user_id: Optional[str],
        include_all_owner_connections: bool,
        can_view_details: bool,
        accessible_wedding_ids: Optional[list[str]],
        start: Optional[datetime],
        end: Optional[datetime],
        wedding_ids: Optional[list[str]] = None,
        staff_ids: Optional[list[str]] = None,
        source_types: Optional[list[str]] = None,
    ) -> list[dict]:
        """Build a single calendar feed of internal and external events."""
        start = start or datetime.now(UTC)
        end = end or (start + timedelta(days=30))

        query = self._build_internal_query(
            owner_email=owner_email,
            wedding_ids=wedding_ids,
            staff_ids=staff_ids,
            start=start,
            end=end,
            source_types=source_types,
            accessible_wedding_ids=accessible_wedding_ids,
        )
        internal_rows = (
            await self.tasks_collection.find(query).sort("start_date", 1).to_list(length=500)
        )
        internal_events = [self._normalize_internal(row) for row in internal_rows]

        external_events: list[dict] = []
        include_external = not source_types or "external_google" in source_types
        if include_external:
            connections = await google_calendar_service.list_connections(
                owner_id=owner_id,
                current_user_id=current_user_id,
                include_all_owner_connections=include_all_owner_connections,
            )
            for connection in connections:
                if not connection.get("is_shared_in_team_view") and connection.get("user_id") != current_user_id:
                    continue
                if staff_ids and connection.get("user_id") not in staff_ids:
                    continue
                events = await google_calendar_service.fetch_google_events_for_connection(
                    connection["id"],
                    time_min=start,
                    time_max=end,
                    max_results=200,
                )
                external_events.extend(
                    [self._normalize_external(event, can_view_details) for event in events]
                )

        combined = sorted(
            [*internal_events, *external_events],
            key=lambda row: row.get("start_date") or "",
        )
        return combined


calendar_aggregation_service = CalendarAggregationService()
