"""Vendor dashboard aggregation and task management service."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from bson import ObjectId
from fastapi import HTTPException

from app.core.database import mongo


def _isoformat(value: datetime | str | None) -> str | None:
    """Convert datetime-like values to ISO-8601 strings."""

    if value is None:
        return None

    if isinstance(value, str):
        return value

    if isinstance(value, datetime):
        return value.isoformat()

    return str(value)


class VendorDashboardService:
    """Aggregate vendor specific data for the dashboard experience."""

    VALID_STATUSES = {"pending", "in_progress", "completed"}

    def __init__(self) -> None:
        self.vendors = mongo.get_vendors_collection()
        self.weddings = mongo.get_weddings_collection()
        self.checklist = mongo.get_wedding_checklist_collection()
        self.vendor_forms = mongo.db["vendor_forms"]
        self.vendor_submissions = mongo.db["vendor_submissions"]

    def resolve_vendor_scope(
        self,
        *,
        vendor_email: str,
        assigned_wedding_ids: Sequence[str] | None = None,
    ) -> dict[str, list[str]]:
        """Return vendor and wedding identifiers associated with the account."""

        vendor_ids: list[str] = []
        wedding_ids = set(str(w_id) for w_id in assigned_wedding_ids or [])

        for record in self.vendors.find({"email": vendor_email}):
            record_id = record.get("_id")
            if record_id:
                vendor_ids.append(str(record_id))

            wedding_id = record.get("wedding_id")
            if wedding_id:
                wedding_ids.add(str(wedding_id))

        return {"vendor_ids": vendor_ids, "wedding_ids": list(wedding_ids)}

    def _build_wedding_snapshot(
        self, wedding_ids: Sequence[str]
    ) -> dict[str, dict[str, str]]:
        """Fetch minimal wedding metadata for display."""

        if not wedding_ids:
            return {}

        query_ids = [
            ObjectId(w_id) if ObjectId.is_valid(w_id) else w_id for w_id in wedding_ids
        ]
        snapshot: dict[str, dict[str, str]] = {}

        for wedding in self.weddings.find({"_id": {"$in": query_ids}}):
            key = str(wedding.get("_id"))
            snapshot[key] = {
                "name": wedding.get("couple_names")
                or wedding.get("couple_name", "Wedding"),
                "date": _isoformat(wedding.get("date")),
                "status": wedding.get("status", "active"),
                "location": wedding.get("location") or wedding.get("venue", ""),
            }

        return snapshot

    def _serialize_task(
        self, task: dict, wedding_map: dict[str, dict[str, str]]
    ) -> dict:
        wedding_id = (
            str(task.get("wedding_id")) if task.get("wedding_id") is not None else ""
        )
        wedding = wedding_map.get(wedding_id, {})

        return {
            "id": str(task.get("_id")),
            "wedding_id": wedding_id,
            "wedding_name": wedding.get("name", ""),
            "category": task.get("category", ""),
            "task": task.get("task", ""),
            "status": task.get("status", "pending"),
            "due_date": _isoformat(task.get("due_date")),
            "notes": task.get("notes"),
            "updated_at": _isoformat(task.get("updated_at")),
        }

    def _serialize_form(
        self,
        form: dict,
        submissions: dict[str, dict],
        wedding_map: dict[str, dict[str, str]],
    ) -> dict:
        form_id = str(form.get("_id"))
        wedding_id = (
            str(form.get("wedding_id")) if form.get("wedding_id") is not None else ""
        )
        wedding = wedding_map.get(wedding_id, {})
        submission = submissions.get(form_id)

        return {
            "id": form_id,
            "form_name": form.get("form_name", "Vendor Form"),
            "status": form.get("status", "draft"),
            "vendor_type": form.get("vendor_type", ""),
            "sent_at": _isoformat(form.get("sent_at")),
            "submitted_at": _isoformat(form.get("submitted_at")),
            "wedding_id": wedding_id,
            "wedding_name": wedding.get("name", ""),
            "fields_count": len(form.get("fields", [])),
            "access_token": form.get("access_token"),
            "latest_submission_id": submission.get("_id") if submission else None,
        }

    def get_dashboard(
        self,
        *,
        vendor_email: str,
        assigned_wedding_ids: Sequence[str] | None = None,
    ) -> dict:
        """Compile dashboard data for the vendor experience."""

        associations = self.resolve_vendor_scope(
            vendor_email=vendor_email,
            assigned_wedding_ids=assigned_wedding_ids,
        )

        vendor_ids = associations["vendor_ids"]
        wedding_ids = associations["wedding_ids"]

        wedding_map = self._build_wedding_snapshot(wedding_ids)

        task_filters: list[dict] = []
        if vendor_ids:
            task_filters.append({"assigned_vendor_id": {"$in": vendor_ids}})
        task_filters.append({"assigned_vendor_email": vendor_email})

        checklist_query: dict = {}
        if task_filters:
            checklist_query["$or"] = task_filters
        if wedding_ids:
            checklist_query["wedding_id"] = {"$in": wedding_ids}

        raw_tasks = list(self.checklist.find(checklist_query))
        serialized_tasks = [
            self._serialize_task(task, wedding_map) for task in raw_tasks
        ]

        serialized_tasks.sort(
            key=lambda task: (
                0 if task["status"] != "completed" else 1,
                task["due_date"] or "9999-12-31",
            )
        )

        form_query = {"vendor_email": vendor_email}
        if wedding_ids:
            form_query["wedding_id"] = {"$in": wedding_ids}

        raw_forms = list(self.vendor_forms.find(form_query))
        submission_map: dict[str, dict] = {}

        if raw_forms:
            form_ids = [str(form.get("_id")) for form in raw_forms]
            submissions = self.vendor_submissions.find({"form_id": {"$in": form_ids}})
            for submission in submissions:
                submission_map[str(submission.get("form_id"))] = {
                    "_id": str(submission.get("_id")),
                    "submitted_at": _isoformat(submission.get("submitted_at")),
                }

        serialized_forms = [
            self._serialize_form(form, submission_map, wedding_map)
            for form in raw_forms
        ]

        pending_forms = [
            form for form in serialized_forms if form["status"] != "submitted"
        ]
        completed_forms = [
            form for form in serialized_forms if form["status"] == "submitted"
        ]

        total_tasks = len(serialized_tasks)
        completed_tasks = sum(
            1 for task in serialized_tasks if task["status"] == "completed"
        )

        wedding_cards = []
        for wedding_id, metadata in wedding_map.items():
            wedding_tasks = [
                task for task in serialized_tasks if task["wedding_id"] == wedding_id
            ]
            wedding_cards.append(
                {
                    "id": wedding_id,
                    "name": metadata.get("name", "Wedding"),
                    "date": metadata.get("date"),
                    "status": metadata.get("status", "active"),
                    "location": metadata.get("location"),
                    "tasks_total": len(wedding_tasks),
                    "tasks_completed": sum(
                        1 for task in wedding_tasks if task["status"] == "completed"
                    ),
                }
            )

        return {
            "profile": {
                "email": vendor_email,
                "wedding_count": len(wedding_map),
                "services": sorted(
                    {
                        form.get("vendor_type")
                        for form in raw_forms
                        if form.get("vendor_type")
                    }
                ),
            },
            "stats": {
                "total_tasks": total_tasks,
                "completed_tasks": completed_tasks,
                "open_tasks": total_tasks - completed_tasks,
                "pending_forms": len(pending_forms),
                "completed_forms": len(completed_forms),
            },
            "weddings": wedding_cards,
            "tasks": serialized_tasks,
            "forms": {
                "pending": pending_forms,
                "completed": completed_forms,
            },
        }

    def update_task_status(
        self,
        *,
        task_id: str,
        new_status: str,
        actor_email: str,
        allowed_vendor_ids: Sequence[str],
        allowed_wedding_ids: Sequence[str],
        bypass_permission: bool = False,
    ) -> dict:
        """Update a vendor task status ensuring ownership checks."""

        if new_status not in self.VALID_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status value")

        try:
            object_id = ObjectId(task_id)
        except Exception as exc:  # pragma: no cover - defensive guard
            raise HTTPException(
                status_code=400, detail="Invalid task identifier"
            ) from exc

        task = self.checklist.find_one({"_id": object_id})
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        if not bypass_permission:
            assigned_vendor_id = (
                str(task.get("assigned_vendor_id"))
                if task.get("assigned_vendor_id")
                else None
            )
            assigned_email = task.get("assigned_vendor_email")
            wedding_id = str(task.get("wedding_id")) if task.get("wedding_id") else None

            owns_task = False
            if assigned_vendor_id and assigned_vendor_id in allowed_vendor_ids:
                owns_task = True
            if assigned_email and assigned_email.lower() == actor_email.lower():
                owns_task = True
            if wedding_id and wedding_id in allowed_wedding_ids:
                owns_task = True

            if not owns_task:
                raise HTTPException(
                    status_code=403, detail="You are not assigned to this task"
                )

        update_payload = {
            "status": new_status,
            "updated_at": datetime.now(UTC),
            "updated_by": actor_email,
        }

        self.checklist.update_one({"_id": object_id}, {"$set": update_payload})

        task.update(update_payload)
        wedding_map = self._build_wedding_snapshot([str(task.get("wedding_id"))])
        return self._serialize_task(task, wedding_map)
