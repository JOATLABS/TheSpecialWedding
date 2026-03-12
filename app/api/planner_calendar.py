"""Calendar and task management API endpoints for wedding planners."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, UTC
from typing import List, Optional, Any

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from app.core.database import mongo
from app.dependencies.auth_extended import (
    get_current_user_extended,
    ExtendedAuthUser,
    require_wedding_planner,
    enforce_team_permission,
)
from app.utils.query_validation import (
    validated_page,
    validated_limit_extended,
    validated_string_filter,
    validated_status_filter,
    calculate_pagination_params
)
from app.models.calendar import (
    CalendarEventCreate,
    CalendarEventUpdate,
    CalendarSyncStatus,
    TaskStatus,
    TaskPriority,
)
from app.services.google_calendar_service import google_calendar_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Response Models
# ============================================================================

class TaskResponse(BaseModel):
    """Response model for a planner task."""
    id: str
    planner_email: str
    wedding_id: Optional[str] = None
    wedding_name: Optional[str] = None
    title: str
    description: Optional[str] = None
    category: str
    priority: str
    status: str
    start_date: str
    end_date: Optional[str] = None
    all_day: bool
    due_date: Optional[str] = None
    reminder_minutes: Optional[int] = None
    google_event_id: Optional[str] = None
    synced_to_google: bool
    is_recurring: bool
    recurrence_rule: Optional[str] = None
    color: Optional[str] = None
    notes: Optional[str] = None
    created_at: str
    updated_at: str
    completed_at: Optional[str] = None


class TaskListResponse(BaseModel):
    """Response model for list of tasks."""
    tasks: List[TaskResponse]
    total: int
    page: int
    page_size: int


class GoogleAuthUrlResponse(BaseModel):
    """Response for Google OAuth authorization URL."""
    auth_url: str
    message: str


class GoogleCallbackResponse(BaseModel):
    """Response after Google OAuth callback."""
    connected: bool
    calendar_id: Optional[str] = None
    message: str


# ============================================================================
# Helper Functions
# ============================================================================

def _isoformat(value: Optional[datetime | str]) -> Optional[str]:
    """Convert datetime to ISO format string."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


async def _get_wedding_name(wedding_id: Optional[str]) -> Optional[str]:
    """Get wedding couple names by ID."""
    if not wedding_id:
        return None
    try:
        oid = ObjectId(wedding_id) if ObjectId.is_valid(wedding_id) else wedding_id
        wedding = await mongo.get_weddings_collection().find_one({"_id": oid})
        return wedding.get("couple_names") if wedding else None
    except Exception as e:
        logger.debug(f"Failed to get wedding name for {wedding_id}: {e}")
        return None


def _serialize_task(task: dict, wedding_name: Optional[str] = None) -> TaskResponse:
    """Serialize a task document to response model."""
    return TaskResponse(
        id=str(task.get("_id")),
        planner_email=task.get("planner_email", ""),
        wedding_id=str(task.get("wedding_id")) if task.get("wedding_id") else None,
        wedding_name=wedding_name,
        title=task.get("title", ""),
        description=task.get("description"),
        category=task.get("category", "other"),
        priority=task.get("priority", "medium"),
        status=task.get("status", "pending"),
        start_date=_isoformat(task.get("start_date")) or "",
        end_date=_isoformat(task.get("end_date")),
        all_day=task.get("all_day", False),
        due_date=_isoformat(task.get("due_date")),
        reminder_minutes=task.get("reminder_minutes"),
        google_event_id=task.get("google_event_id"),
        synced_to_google=task.get("synced_to_google", False),
        is_recurring=task.get("is_recurring", False),
        recurrence_rule=task.get("recurrence_rule"),
        color=task.get("color"),
        notes=task.get("notes"),
        created_at=_isoformat(task.get("created_at")) or "",
        updated_at=_isoformat(task.get("updated_at")) or "",
        completed_at=_isoformat(task.get("completed_at")),
    )


# ============================================================================
# Google Calendar OAuth Endpoints
# ============================================================================

@router.get(
    "/planner/calendar/google/connect",
    tags=["Planner Calendar"],
    response_model=GoogleAuthUrlResponse,
)
async def get_google_auth_url(
    current_user: ExtendedAuthUser = Depends(require_wedding_planner),
) -> GoogleAuthUrlResponse:
    """
    Get Google OAuth authorization URL to connect Google Calendar.

    Redirects the user to Google's consent screen to authorize
    calendar access. After consent, user is redirected to the callback URL.
    """
    auth_url = google_calendar_service.get_authorization_url(current_user.email)

    return GoogleAuthUrlResponse(
        auth_url=auth_url,
        message="Redirect user to auth_url to connect Google Calendar",
    )


@router.get(
    "/planner/calendar/google/callback",
    tags=["Planner Calendar"],
    response_model=GoogleCallbackResponse,
)
async def google_oauth_callback(
    code: str = Query(..., description="Authorization code from Google"),
    state: str = Query(..., description="State parameter containing user email"),
) -> GoogleCallbackResponse:
    """
    Handle Google OAuth callback after user grants consent.

    This endpoint is called by Google after user authorizes access.
    The authorization code is exchanged for access/refresh tokens.
    """
    result = await google_calendar_service.handle_oauth_callback(code, state)

    return GoogleCallbackResponse(
        connected=result.get("connected", False),
        calendar_id=result.get("calendar_id"),
        message=result.get("message", ""),
    )


@router.get(
    "/planner/calendar/google/status",
    tags=["Planner Calendar"],
    response_model=CalendarSyncStatus,
)
async def get_google_calendar_status(
    current_user: ExtendedAuthUser = Depends(require_wedding_planner),
) -> CalendarSyncStatus:
    """
    Check if Google Calendar is connected for the current user.

    Returns connection status, last sync time, and number of synced events.
    """
    status = await google_calendar_service.get_connection_status(current_user.email)

    return CalendarSyncStatus(
        connected=status.get("connected", False),
        calendar_id=status.get("calendar_id"),
        last_sync=status.get("last_sync"),
        sync_enabled=status.get("sync_enabled", False),
        events_synced=status.get("events_synced", 0),
    )


@router.delete(
    "/planner/calendar/google/disconnect",
    tags=["Planner Calendar"],
)
async def disconnect_google_calendar(
    current_user: ExtendedAuthUser = Depends(require_wedding_planner),
) -> dict:
    """
    Disconnect Google Calendar for the current user.

    Removes stored OAuth tokens. Tasks are preserved but sync is disabled.
    """
    enforce_team_permission(current_user, "manage_calendar")
    result = await google_calendar_service.disconnect(current_user.email)
    return result


@router.get(
    "/planner/calendar/google/events",
    tags=["Planner Calendar"],
)
async def fetch_google_events(
    current_user: ExtendedAuthUser = Depends(require_wedding_planner),
    days_ahead: int = Query(default=30, ge=1, le=365, description="Days ahead to fetch"),
) -> List[dict]:
    """
    Fetch events from connected Google Calendar.

    Returns events from now until the specified number of days ahead.
    """
    time_min = datetime.now(UTC)
    time_max = time_min + timedelta(days=days_ahead)

    events = await google_calendar_service.fetch_google_events(
        current_user.email,
        time_min=time_min,
        time_max=time_max,
    )

    return events


# ============================================================================
# Task/Event CRUD Endpoints
# ============================================================================

@router.post(
    "/planner/calendar/tasks",
    tags=["Planner Calendar"],
    response_model=TaskResponse,
)
async def create_task(
    task_data: CalendarEventCreate,
    current_user: ExtendedAuthUser = Depends(require_wedding_planner),
) -> TaskResponse:
    """
    Create a new task/event for the planner's calendar.

    If Google Calendar is connected and sync_to_google is True,
    the event will also be created in Google Calendar.
    """
    enforce_team_permission(current_user, "manage_calendar")
    tasks_collection = mongo.get_planner_tasks_collection()

    now = datetime.now(UTC)

    # Build task document
    task_doc = {
        "planner_email": current_user.email,
        "wedding_id": task_data.wedding_id,
        "title": task_data.title,
        "description": task_data.description,
        "category": task_data.category,
        "priority": task_data.priority,
        "status": "pending",
        "start_date": task_data.start_date,
        "end_date": task_data.end_date or task_data.start_date,
        "all_day": task_data.all_day,
        "due_date": task_data.due_date,
        "reminder_minutes": task_data.reminder_minutes,
        "is_recurring": task_data.is_recurring,
        "recurrence_rule": task_data.recurrence_rule,
        "color": task_data.color,
        "notes": task_data.notes,
        "synced_to_google": False,
        "google_event_id": None,
        "last_google_sync": None,
        "attachments": [],
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
    }

    result = await tasks_collection.insert_one(task_doc)
    task_doc["_id"] = result.inserted_id

    # Sync to Google Calendar if requested and connected
    if task_data.sync_to_google:
        status = await google_calendar_service.get_connection_status(current_user.email)
        if status.get("connected"):
            google_event_id = await google_calendar_service.create_google_event(
                current_user.email,
                task_doc,
            )
            if google_event_id:
                await tasks_collection.update_one(
                    {"_id": result.inserted_id},
                    {
                        "$set": {
                            "google_event_id": google_event_id,
                            "synced_to_google": True,
                            "last_google_sync": now,
                        }
                    },
                )
                task_doc["google_event_id"] = google_event_id
                task_doc["synced_to_google"] = True

    wedding_name = await _get_wedding_name(task_data.wedding_id)

    logger.info(f"Created task {result.inserted_id} for planner {current_user.email}")

    return _serialize_task(task_doc, wedding_name)


@router.get(
    "/planner/calendar/tasks",
    tags=["Planner Calendar"],
    response_model=TaskListResponse,
)
async def list_tasks(
    current_user: ExtendedAuthUser = Depends(require_wedding_planner),
    wedding_id: Optional[str] = Query(None, description="Filter by wedding ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    category: Optional[str] = Query(None, description="Filter by category"),
    start_date: Optional[datetime] = Query(None, description="Filter tasks after this date"),
    end_date: Optional[datetime] = Query(None, description="Filter tasks before this date"),
    page: int = Query(default=1, ge=1, le=10000, description="Page number"),
    page_size: int = Query(default=50, ge=1, le=200, description="Items per page"),
) -> TaskListResponse:
    """
    List all tasks for the current planner.

    Supports filtering by wedding, status, category, and date range.
    Results are sorted by start_date ascending.
    """
    tasks_collection = mongo.get_planner_tasks_collection()

    # Validate filter parameters
    wedding_id = validated_string_filter(wedding_id, max_length=100)
    status = validated_status_filter(status, ['pending', 'in_progress', 'completed', 'on_hold'])
    category = validated_string_filter(category, max_length=50)

    # Build query
    query: dict[str, Any] = {"planner_email": current_user.email}

    if wedding_id:
        query["wedding_id"] = wedding_id
    if status:
        query["status"] = status
    if category:
        query["category"] = category
    if start_date:
        query["start_date"] = {"$gte": start_date}
    if end_date:
        if "start_date" in query:
            query["start_date"]["$lte"] = end_date
        else:
            query["start_date"] = {"$lte": end_date}

    # Get total count
    total = await tasks_collection.count_documents(query)

    # Get paginated tasks
    skip, limit = calculate_pagination_params(page, page_size)
    cursor = tasks_collection.find(query).sort("start_date", 1).skip(skip).limit(limit)
    tasks = await cursor.to_list(length=page_size)

    # Get wedding names for all tasks
    wedding_ids = set(t.get("wedding_id") for t in tasks if t.get("wedding_id"))
    wedding_names: dict[str, str] = {}

    if wedding_ids:
        weddings_collection = mongo.get_weddings_collection()
        for wid in wedding_ids:
            try:
                oid = ObjectId(wid) if ObjectId.is_valid(wid) else wid
                wedding = await weddings_collection.find_one({"_id": oid})
                if wedding:
                    wedding_names[wid] = wedding.get("couple_names", "")
            except Exception:
                pass

    serialized_tasks = [
        _serialize_task(t, wedding_names.get(t.get("wedding_id")))
        for t in tasks
    ]

    return TaskListResponse(
        tasks=serialized_tasks,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/planner/calendar/tasks/{task_id}",
    tags=["Planner Calendar"],
    response_model=TaskResponse,
)
async def get_task(
    task_id: str,
    current_user: ExtendedAuthUser = Depends(require_wedding_planner),
) -> TaskResponse:
    """
    Get a specific task by ID.
    """
    tasks_collection = mongo.get_planner_tasks_collection()

    try:
        oid = ObjectId(task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID format")

    task = await tasks_collection.find_one({
        "_id": oid,
        "planner_email": current_user.email,
    })

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    wedding_name = await _get_wedding_name(task.get("wedding_id"))

    return _serialize_task(task, wedding_name)


@router.patch(
    "/planner/calendar/tasks/{task_id}",
    tags=["Planner Calendar"],
    response_model=TaskResponse,
)
async def update_task(
    task_id: str,
    updates: CalendarEventUpdate,
    current_user: ExtendedAuthUser = Depends(require_wedding_planner),
) -> TaskResponse:
    """
    Update an existing task.

    If the task is synced to Google Calendar, the Google event
    will also be updated.
    """
    enforce_team_permission(current_user, "manage_calendar")
    tasks_collection = mongo.get_planner_tasks_collection()

    try:
        oid = ObjectId(task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID format")

    # Get existing task
    task = await tasks_collection.find_one({
        "_id": oid,
        "planner_email": current_user.email,
    })

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Build update document
    update_doc: dict[str, Any] = {"updated_at": datetime.now(UTC)}

    update_fields = updates.model_dump(exclude_unset=True)
    for field, value in update_fields.items():
        if value is not None:
            update_doc[field] = value

    # Handle status change to completed
    if updates.status == "completed" and task.get("status") != "completed":
        update_doc["completed_at"] = datetime.now(UTC)
    elif updates.status and updates.status != "completed":
        update_doc["completed_at"] = None

    await tasks_collection.update_one({"_id": oid}, {"$set": update_doc})

    # Sync to Google Calendar if connected and task was synced
    if task.get("synced_to_google") and task.get("google_event_id"):
        await google_calendar_service.update_google_event(
            current_user.email,
            task["google_event_id"],
            {**task, **update_doc},
        )

    # Fetch updated task
    updated_task = await tasks_collection.find_one({"_id": oid})
    wedding_name = await _get_wedding_name(updated_task.get("wedding_id"))

    logger.info(f"Updated task {task_id} for planner {current_user.email}")

    return _serialize_task(updated_task, wedding_name)


@router.delete(
    "/planner/calendar/tasks/{task_id}",
    tags=["Planner Calendar"],
)
async def delete_task(
    task_id: str,
    current_user: ExtendedAuthUser = Depends(require_wedding_planner),
) -> dict:
    """
    Delete a task.

    If the task is synced to Google Calendar, the Google event
    will also be deleted.
    """
    enforce_team_permission(current_user, "manage_calendar")
    tasks_collection = mongo.get_planner_tasks_collection()

    try:
        oid = ObjectId(task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID format")

    # Get existing task
    task = await tasks_collection.find_one({
        "_id": oid,
        "planner_email": current_user.email,
    })

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Delete from Google Calendar if synced
    if task.get("synced_to_google") and task.get("google_event_id"):
        await google_calendar_service.delete_google_event(
            current_user.email,
            task["google_event_id"],
        )

    await tasks_collection.delete_one({"_id": oid})

    logger.info(f"Deleted task {task_id} for planner {current_user.email}")

    return {"deleted": True, "task_id": task_id}


@router.post(
    "/planner/calendar/tasks/{task_id}/sync",
    tags=["Planner Calendar"],
    response_model=TaskResponse,
)
async def sync_task_to_google(
    task_id: str,
    current_user: ExtendedAuthUser = Depends(require_wedding_planner),
) -> TaskResponse:
    """
    Manually sync a specific task to Google Calendar.

    Creates the event in Google Calendar if not already synced,
    or updates it if already synced.
    """
    enforce_team_permission(current_user, "manage_calendar")
    # Check if Google Calendar is connected
    status = await google_calendar_service.get_connection_status(current_user.email)
    if not status.get("connected"):
        raise HTTPException(
            status_code=400,
            detail="Google Calendar not connected. Please connect first.",
        )

    tasks_collection = mongo.get_planner_tasks_collection()

    try:
        oid = ObjectId(task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID format")

    task = await tasks_collection.find_one({
        "_id": oid,
        "planner_email": current_user.email,
    })

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Sync to Google
    success = await google_calendar_service.sync_task_to_google(
        current_user.email,
        task_id,
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to sync task to Google Calendar")

    # Fetch updated task
    updated_task = await tasks_collection.find_one({"_id": oid})
    wedding_name = await _get_wedding_name(updated_task.get("wedding_id"))

    return _serialize_task(updated_task, wedding_name)


# ============================================================================
# Bulk Operations
# ============================================================================

@router.patch(
    "/planner/calendar/tasks/bulk/status",
    tags=["Planner Calendar"],
)
async def bulk_update_task_status(
    task_ids: List[str],
    status: str = Query(..., description="New status for all tasks"),
    current_user: ExtendedAuthUser = Depends(require_wedding_planner),
) -> dict:
    """
    Update status for multiple tasks at once.
    """
    enforce_team_permission(current_user, "manage_calendar")
    if status not in ["pending", "in_progress", "completed", "cancelled"]:
        raise HTTPException(status_code=400, detail="Invalid status value")

    tasks_collection = mongo.get_planner_tasks_collection()

    # Convert IDs
    oids = []
    for tid in task_ids:
        try:
            oids.append(ObjectId(tid))
        except Exception:
            pass

    if not oids:
        raise HTTPException(status_code=400, detail="No valid task IDs provided")

    update_doc: dict[str, Any] = {
        "status": status,
        "updated_at": datetime.now(UTC),
    }

    if status == "completed":
        update_doc["completed_at"] = datetime.now(UTC)
    else:
        update_doc["completed_at"] = None

    result = await tasks_collection.update_many(
        {
            "_id": {"$in": oids},
            "planner_email": current_user.email,
        },
        {"$set": update_doc},
    )

    return {
        "updated_count": result.modified_count,
        "status": status,
    }


# ============================================================================
# Calendar View Helpers
# ============================================================================

@router.get(
    "/planner/calendar/month/{year}/{month}",
    tags=["Planner Calendar"],
)
async def get_month_tasks(
    year: int,
    month: int,
    current_user: ExtendedAuthUser = Depends(require_wedding_planner),
) -> List[TaskResponse]:
    """
    Get all tasks for a specific month.

    Useful for calendar month view rendering.
    """
    if not (1 <= month <= 12):
        raise HTTPException(status_code=400, detail="Invalid month")
    if not (2000 <= year <= 2100):
        raise HTTPException(status_code=400, detail="Invalid year")

    tasks_collection = mongo.get_planner_tasks_collection()

    # Calculate month boundaries
    start_of_month = datetime(year, month, 1, tzinfo=UTC)
    if month == 12:
        end_of_month = datetime(year + 1, 1, 1, tzinfo=UTC)
    else:
        end_of_month = datetime(year, month + 1, 1, tzinfo=UTC)

    query = {
        "planner_email": current_user.email,
        "$or": [
            # Tasks that start in this month
            {"start_date": {"$gte": start_of_month, "$lt": end_of_month}},
            # Tasks that end in this month
            {"end_date": {"$gte": start_of_month, "$lt": end_of_month}},
            # Tasks that span this month
            {
                "start_date": {"$lt": start_of_month},
                "end_date": {"$gte": end_of_month},
            },
        ],
    }

    tasks = await tasks_collection.find(query).sort("start_date", 1).to_list(length=500)

    # Get wedding names
    wedding_ids = set(t.get("wedding_id") for t in tasks if t.get("wedding_id"))
    wedding_names: dict[str, str] = {}

    if wedding_ids:
        weddings_collection = mongo.get_weddings_collection()
        for wid in wedding_ids:
            try:
                oid = ObjectId(wid) if ObjectId.is_valid(wid) else wid
                wedding = await weddings_collection.find_one({"_id": oid})
                if wedding:
                    wedding_names[wid] = wedding.get("couple_names", "")
            except Exception:
                pass

    return [
        _serialize_task(t, wedding_names.get(t.get("wedding_id")))
        for t in tasks
    ]


@router.get(
    "/planner/calendar/upcoming",
    tags=["Planner Calendar"],
)
async def get_upcoming_tasks(
    current_user: ExtendedAuthUser = Depends(require_wedding_planner),
    days: int = Query(default=7, ge=1, le=90, description="Days ahead to fetch"),
    limit: int = Query(default=20, ge=1, le=100, description="Maximum tasks to return"),
) -> List[TaskResponse]:
    """
    Get upcoming tasks for the next N days.

    Useful for dashboard widgets and quick overviews.
    """
    tasks_collection = mongo.get_planner_tasks_collection()

    now = datetime.now(UTC)
    end_date = now + timedelta(days=days)

    query = {
        "planner_email": current_user.email,
        "status": {"$ne": "completed"},
        "start_date": {"$gte": now, "$lte": end_date},
    }

    tasks = await tasks_collection.find(query).sort("start_date", 1).limit(limit).to_list(length=limit)

    # Get wedding names
    wedding_ids = set(t.get("wedding_id") for t in tasks if t.get("wedding_id"))
    wedding_names: dict[str, str] = {}

    if wedding_ids:
        weddings_collection = mongo.get_weddings_collection()
        for wid in wedding_ids:
            try:
                oid = ObjectId(wid) if ObjectId.is_valid(wid) else wid
                wedding = await weddings_collection.find_one({"_id": oid})
                if wedding:
                    wedding_names[wid] = wedding.get("couple_names", "")
            except Exception:
                pass

    return [
        _serialize_task(t, wedding_names.get(t.get("wedding_id")))
        for t in tasks
    ]
