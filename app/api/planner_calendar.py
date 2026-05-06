"""Calendar and task management API endpoints for wedding planners."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any, List, Optional
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.cache import cache
from app.core.database import mongo
from app.dependencies.auth_extended import (
    ExtendedAuthUser,
    can_view_calendar_details,
    check_wedding_access,
    get_accessible_calendar_scope,
    get_calendar_owner_identity,
    require_calendar_access,
    require_calendar_permission,
    resolve_owner_scoped_user_assignments,
)
from app.models.calendar import (
    CalendarEventCreate,
    CalendarEventUpdate,
    CalendarSyncPolicy,
    CalendarSyncStatus,
    ExternalConflictStatus,
    InviteDeliveryMode,
    MeetingLifecycleStatus,
    ScheduleItemType,
    VisibilityMode,
)
from app.models.calendar_connection import CalendarConnectionUpdateRequest
from app.models.calendar_sync import CalendarSyncStatusValue
from app.services.calendar_aggregation_service import calendar_aggregation_service
from app.services.calendar_audit_service import calendar_audit_service
from app.services.calendar_idempotency_service import calendar_idempotency_service
from app.services.calendar_job_service import calendar_job_service
from app.services.calendar_sync_service import calendar_sync_service
from app.services.calendar_provider_service import calendar_provider_service
from app.utils.query_validation import (
    calculate_pagination_params,
    validated_status_filter,
    validated_string_filter,
)
from app.utils.planner_ownership import list_wedding_ids_for_owner

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Response Models
# ============================================================================


class TaskSyncSummaryResponse(BaseModel):
    """Compatibility summary derived from per-target sync rows."""

    row_count: int = 0
    synced_target_count: int = 0
    failed_target_count: int = 0
    orphaned_target_count: int = 0
    not_configured_target_count: int = 0
    pending_target_count: int = 0
    has_synced_target: bool = False
    has_configured_target: bool = False
    primary_external_event_id: Optional[str] = None
    last_sync_at: Optional[str] = None


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
    external_sync_requested: bool = False
    is_recurring: bool
    recurrence_rule: Optional[str] = None
    color: Optional[str] = None
    notes: Optional[str] = None
    owner_planner_id: Optional[str] = None
    owner_planner_email: Optional[str] = None
    created_by_user_id: Optional[str] = None
    created_by_email: Optional[str] = None
    assigned_user_ids: list[str] = Field(default_factory=list)
    assigned_user_emails: list[str] = Field(default_factory=list)
    schedule_item_type: Optional[str] = None
    visibility_mode: Optional[str] = None
    calendar_sync_policy: Optional[str] = None
    sync_target_override_enabled: bool = False
    sync_target_connection_ids: list[str] = Field(default_factory=list)
    timezone: Optional[str] = None
    couple_attendee_emails: list[str] = Field(default_factory=list)
    conference_provider: Optional[str] = None
    conference_url: Optional[str] = None
    invite_delivery_mode: Optional[str] = None
    meeting_status: Optional[str] = None
    created_at: str
    updated_at: str
    version: int = 1
    completed_at: Optional[str] = None
    sync_status_summary: Optional[TaskSyncSummaryResponse] = None


class TaskListResponse(BaseModel):
    """Response model for list of tasks."""

    tasks: List[TaskResponse]
    total: int
    page: int
    page_size: int


class CalendarAuthUrlResponse(BaseModel):
    """Response carrying the calendar aggregator hosted-auth URL."""

    auth_url: str
    message: str


class CalendarCallbackResponse(BaseModel):
    """Response after the calendar aggregator OAuth callback completes."""

    connected: bool
    calendar_id: Optional[str] = None
    message: str


class CalendarConnectionResponse(BaseModel):
    """Serialized external calendar connection."""

    id: str
    owner_planner_id: Optional[str] = None
    owner_planner_email: Optional[str] = None
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    provider: str
    provider_account_email: Optional[str] = None
    provider_account_name: Optional[str] = None
    calendar_id: Optional[str] = None
    calendar_name: Optional[str] = None
    access_role: Optional[str] = None
    is_writable: bool = False
    is_primary: bool = False
    is_default_write_target: bool = False
    scheduler_access_mode: str
    sync_targeting_mode: str
    allowed_scheduler_user_ids: list[str] = Field(default_factory=list)
    allowed_scheduler_roles: list[str] = Field(default_factory=list)
    allowed_schedule_item_types: list[str] = Field(default_factory=list)
    allowed_wedding_ids: list[str] = Field(default_factory=list)
    is_shared_in_team_view: bool = False
    details_visibility: str = VisibilityMode.BUSY_ONLY.value
    sync_enabled: bool = False
    connection_status: str
    token_expiry: Optional[datetime] = None
    last_sync_at: Optional[datetime] = None
    last_healthcheck_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SharedCalendarEventResponse(BaseModel):
    """Unified event shape for the shared planner calendar view."""

    id: str
    source_type: str
    title: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    all_day: bool = False
    wedding_id: Optional[str] = None
    owner_planner_email: Optional[str] = None
    assigned_user_ids: list[str] = Field(default_factory=list)
    assigned_user_emails: list[str] = Field(default_factory=list)
    visibility_mode: str = VisibilityMode.DETAILS.value
    details: dict[str, Any] = Field(default_factory=dict)


class MeetingUpsertResponse(BaseModel):
    """Response payload for create/update meeting endpoints."""

    meeting: dict[str, Any]
    sync_status: list[dict[str, Any]] = Field(default_factory=list)
    invite_status: list[dict[str, Any]] = Field(default_factory=list)


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


def _optional_str(value: Any) -> Optional[str]:
    """Return string values as-is and coerce simple scalar IDs to strings."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (int, ObjectId)):
        return str(value)
    return None


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


def _serialize_task_sync_summary(summary: dict[str, Any]) -> TaskSyncSummaryResponse:
    return TaskSyncSummaryResponse(
        row_count=int(summary.get("row_count") or 0),
        synced_target_count=int(summary.get("synced_target_count") or 0),
        failed_target_count=int(summary.get("failed_target_count") or 0),
        orphaned_target_count=int(summary.get("orphaned_target_count") or 0),
        not_configured_target_count=int(
            summary.get("not_configured_target_count") or 0
        ),
        pending_target_count=int(summary.get("pending_target_count") or 0),
        has_synced_target=bool(summary.get("has_synced_target", False)),
        has_configured_target=bool(summary.get("has_configured_target", False)),
        primary_external_event_id=summary.get("primary_external_event_id"),
        last_sync_at=_isoformat(summary.get("last_sync_at")),
    )


def _serialize_task(
    task: dict,
    wedding_name: Optional[str] = None,
    sync_summary: Optional[dict[str, Any]] = None,
) -> TaskResponse:
    """Serialize a task document to response model."""
    summary = _serialize_task_sync_summary(sync_summary or {})
    external_sync_requested = bool(
        task.get(
            "external_sync_requested",
            task.get("schedule_item_type") == ScheduleItemType.MEETING.value,
        )
    )
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
        external_sync_requested=external_sync_requested,
        is_recurring=task.get("is_recurring", False),
        recurrence_rule=task.get("recurrence_rule"),
        color=task.get("color"),
        notes=task.get("notes"),
        owner_planner_id=task.get("owner_planner_id"),
        owner_planner_email=task.get("owner_planner_email"),
        created_by_user_id=task.get("created_by_user_id"),
        created_by_email=task.get("created_by_email"),
        assigned_user_ids=task.get("assigned_user_ids", []),
        assigned_user_emails=task.get("assigned_user_emails", []),
        schedule_item_type=task.get("schedule_item_type"),
        visibility_mode=task.get("visibility_mode"),
        calendar_sync_policy=task.get("calendar_sync_policy"),
        sync_target_override_enabled=task.get("sync_target_override_enabled", False),
        sync_target_connection_ids=task.get("sync_target_connection_ids", []),
        timezone=task.get("timezone"),
        couple_attendee_emails=task.get("couple_attendee_emails", []),
        conference_provider=task.get("conference_provider"),
        conference_url=task.get("conference_url"),
        invite_delivery_mode=task.get("invite_delivery_mode"),
        meeting_status=task.get("meeting_status"),
        created_at=_isoformat(task.get("created_at")) or "",
        updated_at=_isoformat(task.get("updated_at")) or "",
        version=int(task.get("version") or 1),
        completed_at=_isoformat(task.get("completed_at")),
        sync_status_summary=summary,
    )


async def _load_task_sync_summary_map(
    tasks: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    task_ids = [str(task["_id"]) for task in tasks if task.get("_id")]
    return await calendar_sync_service.get_sync_summary_map(task_ids)


def _require_document(document: Any, detail: str) -> dict[str, Any]:
    """Narrow Mongo results to the dict payloads expected by this module."""
    if not isinstance(document, dict):
        raise HTTPException(status_code=404, detail=detail)
    return document


def _calendar_owner_email(current_user: ExtendedAuthUser) -> str:
    context = get_calendar_owner_identity(current_user)
    return str(context.get("owner_email") or current_user.email)


def _calendar_user_id(current_user: ExtendedAuthUser) -> Optional[str]:
    context = get_calendar_owner_identity(current_user)
    user_id = context.get("user_id")
    return str(user_id) if user_id else None


def _calendar_actor_role_scope(current_user: ExtendedAuthUser) -> str:
    if current_user.is_root_admin or current_user.is_wedding_planner:
        return "owner"
    return str(getattr(current_user, "team_role", None) or "viewer")


async def _resolve_owner_scoped_wedding_ids(
    owner_id: Optional[str],
    owner_email: Optional[str],
    wedding_ids: list[str],
) -> list[str]:
    requested_ids = list(dict.fromkeys(str(value) for value in wedding_ids if value))
    if not requested_ids:
        return []

    owned_ids = await list_wedding_ids_for_owner(
        planner_id=owner_id,
        planner_email=owner_email,
        accessible_wedding_ids=requested_ids,
    )
    if len(set(owned_ids)) != len(set(requested_ids)):
        raise HTTPException(
            status_code=400,
            detail="Calendar connection wedding scope must stay inside the planner owner workspace.",
        )
    return requested_ids


def _connection_matches_owner_scope(
    connection_doc: dict[str, Any],
    current_user: ExtendedAuthUser,
) -> bool:
    """Ensure a connection row belongs to the current planner-business scope."""
    if current_user.is_root_admin:
        return True

    context = get_calendar_owner_identity(current_user)
    owner_id = context.get("owner_id")
    owner_email = context.get("owner_email")
    connection_owner_id = connection_doc.get("owner_planner_id")
    connection_owner_email = connection_doc.get("owner_planner_email")

    if owner_id and connection_owner_id:
        return str(owner_id) == str(connection_owner_id)
    if owner_email and connection_owner_email:
        return str(owner_email) == str(connection_owner_email)
    return False


def _can_send_meeting_invites(current_user: ExtendedAuthUser) -> bool:
    """Whether the actor may send outbound couple meeting invites."""
    if current_user.is_root_admin or current_user.is_wedding_planner:
        return True
    return bool(
        current_user.team_permissions
        and current_user.team_permissions.get("send_meeting_invites", False)
    )


def _coerce_event_datetime(value: Any) -> Optional[datetime]:
    """Normalize serialized event timestamps into aware datetimes for availability math."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)

    raw = str(value)
    if "T" not in raw:
        return datetime.fromisoformat(raw).replace(tzinfo=UTC)

    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _build_task_scope_query(current_user: ExtendedAuthUser) -> dict[str, Any]:
    owner_email = _calendar_owner_email(current_user)
    owner_scope = {
        "$or": [
            {"owner_planner_email": owner_email},
            {"planner_email": owner_email},
        ]
    }

    if (
        not current_user.is_team_member
        or current_user.team_wedding_access != "assigned"
    ):
        return owner_scope

    accessible_wedding_ids = current_user.team_assigned_wedding_ids or []
    actor_user_id = _calendar_user_id(current_user)
    access_filters: list[dict[str, Any]] = [
        {"wedding_id": {"$in": accessible_wedding_ids}}
    ]
    if actor_user_id:
        access_filters.extend(
            [
                {"assigned_user_ids": actor_user_id},
                {"created_by_user_id": actor_user_id},
            ]
        )

    return {
        "$and": [
            owner_scope,
            {"$or": access_filters},
        ]
    }


async def _resolve_user_emails(user_ids: list[str]) -> list[str]:
    """Resolve internal user ids to emails for denormalized task storage."""
    if not user_ids:
        return []
    resolved: list[str] = []
    users_collection = mongo.get_users_collection()
    for user_id in user_ids:
        try:
            oid = ObjectId(user_id) if ObjectId.is_valid(user_id) else user_id
            user_doc = await users_collection.find_one({"_id": oid}, {"email": 1})
            if user_doc and user_doc.get("email"):
                resolved.append(user_doc["email"])
        except Exception:
            continue
    return resolved


async def _resolve_couple_attendee_emails(
    wedding_id: Optional[str],
    requested_emails: Optional[list[str]] = None,
) -> list[str]:
    """Use explicit couple attendee emails, falling back to wedding couple accounts."""
    normalized = [email for email in (requested_emails or []) if email]
    if normalized:
        return normalized
    if not wedding_id:
        return []
    cursor = mongo.db["couple_users"].find({"wedding_id": wedding_id}, {"email": 1})
    emails: list[str] = []
    async for couple_doc in cursor:
        if couple_doc.get("email"):
            emails.append(couple_doc["email"])
    return emails


def _build_scoped_meeting_query(
    current_user: ExtendedAuthUser,
    meeting_id: ObjectId,
) -> dict[str, Any]:
    """Build a scoped lookup query for canonical meetings."""
    return {
        "$and": [
            {"_id": meeting_id},
            {"$or": [{"schedule_item_type": "meeting"}, {"category": "meeting"}]},
            _build_task_scope_query(current_user),
        ]
    }


async def _get_scoped_meeting(
    meeting_id: ObjectId,
    current_user: ExtendedAuthUser,
    *,
    detail: str = "Meeting not found",
) -> dict[str, Any]:
    """Load a meeting while enforcing planner-owner and wedding/team scope."""
    task = await mongo.get_planner_tasks_collection().find_one(
        _build_scoped_meeting_query(current_user, meeting_id)
    )
    return _require_document(task, detail)


def _serialize_shared_event(row: dict) -> SharedCalendarEventResponse:
    """Convert aggregation rows to the shared calendar response model."""
    return SharedCalendarEventResponse(
        id=str(row.get("id")),
        source_type=row.get("source_type", "internal_task"),
        title=row.get("title"),
        start_date=_isoformat(row.get("start_date")),
        end_date=_isoformat(row.get("end_date")),
        all_day=row.get("all_day", False),
        wedding_id=row.get("wedding_id"),
        owner_planner_email=row.get("owner_planner_email"),
        assigned_user_ids=row.get("assigned_user_ids", []),
        assigned_user_emails=row.get("assigned_user_emails", []),
        visibility_mode=row.get("visibility_mode", VisibilityMode.DETAILS.value),
        details=row.get("details", {}),
    )


def _serialize_meeting_payload(task: dict) -> dict[str, Any]:
    """Shared meeting serializer for planner-side responses."""
    return {
        "id": str(task.get("_id")),
        "title": task.get("title"),
        "description": task.get("description"),
        "wedding_id": task.get("wedding_id"),
        "start_date": _isoformat(task.get("start_date")),
        "end_date": _isoformat(task.get("end_date")),
        "all_day": task.get("all_day", False),
        "schedule_item_type": task.get(
            "schedule_item_type", ScheduleItemType.MEETING.value
        ),
        "meeting_status": task.get("meeting_status"),
        "timezone": task.get("timezone"),
        "assigned_user_ids": task.get("assigned_user_ids", []),
        "assigned_user_emails": task.get("assigned_user_emails", []),
        "couple_attendee_emails": task.get("couple_attendee_emails", []),
        "calendar_sync_policy": task.get("calendar_sync_policy"),
        "external_sync_requested": bool(task.get("external_sync_requested", True)),
        "sync_target_override_enabled": task.get("sync_target_override_enabled", False),
        "sync_target_connection_ids": task.get("sync_target_connection_ids", []),
        "invite_delivery_mode": task.get("invite_delivery_mode"),
        "conference_provider": task.get("conference_provider"),
        "conference_url": task.get("conference_url"),
        "created_by_email": task.get("created_by_email"),
        "owner_planner_email": task.get("owner_planner_email")
        or task.get("planner_email"),
        "status": task.get("status"),
        "updated_at": _isoformat(task.get("updated_at")),
        "version": int(task.get("version") or 1),
    }


def _meeting_invite_content_changed(update_fields: dict[str, Any]) -> bool:
    """Whether a meeting edit should trigger an outward ICS update."""
    return bool(
        {
            "all_day",
            "conference_provider",
            "conference_url",
            "description",
            "end_date",
            "is_recurring",
            "recurrence_rule",
            "start_date",
            "timezone",
            "title",
            "wedding_id",
        }
        & set(update_fields.keys())
    )


def _require_idempotency_key(idempotency_key: Optional[str]) -> str:
    if not idempotency_key:
        raise HTTPException(
            status_code=400,
            detail="Idempotency-Key header is required for meeting mutations",
        )
    return idempotency_key


def _build_meeting_idempotency_scope(action: str, identifier: str) -> str:
    return f"planner_calendar:{action}:{identifier}"


async def _begin_meeting_idempotency(
    *,
    scope_key: str,
    idempotency_key: Optional[str],
    action: str,
    payload: dict[str, Any],
) -> tuple[str, Optional[dict[str, Any]]]:
    key = _require_idempotency_key(idempotency_key)
    resolution = await calendar_idempotency_service.begin(
        scope_key=scope_key,
        idempotency_key=key,
        request_hash=calendar_idempotency_service.build_request_hash(
            action=action,
            payload=payload,
        ),
    )
    if resolution.state == "replay":
        return key, resolution.response_payload
    if resolution.state == "conflict":
        raise HTTPException(
            status_code=409,
            detail="Idempotency key was already used for a different meeting request",
        )
    if resolution.state == "in_progress":
        raise HTTPException(
            status_code=409,
            detail="A matching meeting request is already being processed",
        )
    return key, None


async def _complete_meeting_idempotency(
    *,
    scope_key: str,
    idempotency_key: str,
    payload: dict[str, Any],
) -> None:
    await calendar_idempotency_service.complete(
        scope_key=scope_key,
        idempotency_key=idempotency_key,
        response_payload=payload,
        response_status_code=200,
    )


async def _fail_meeting_idempotency(
    *,
    scope_key: str,
    idempotency_key: str,
    detail: str,
) -> None:
    await calendar_idempotency_service.fail(
        scope_key=scope_key,
        idempotency_key=idempotency_key,
        error_detail=detail,
    )


@asynccontextmanager
async def _meeting_mutation_lock(meeting_id: str):
    lock_value = uuid4().hex
    lock_key = f"calendar_meeting_lock:{meeting_id}"
    acquired = await cache.acquire_lock(lock_key, lock_value, expire=60)
    if acquired is False:
        raise HTTPException(
            status_code=409,
            detail="This meeting is currently being changed by another request. Try again.",
        )
    try:
        yield
    finally:
        if acquired:
            await cache.release_lock(lock_key, lock_value)


# ============================================================================
# Calendar Aggregator OAuth Endpoints (Aurinko)
# ============================================================================


@router.get(
    "/planner/calendar/provider/connect",
    tags=["Planner Calendar"],
    response_model=CalendarAuthUrlResponse,
)
async def get_calendar_auth_url(
    current_user: ExtendedAuthUser = Depends(
        require_calendar_permission("connect_personal_calendar")
    ),
) -> CalendarAuthUrlResponse:
    """Generate the calendar aggregator hosted-auth URL for the current user."""
    context = get_calendar_owner_identity(current_user)
    auth_url = await calendar_provider_service.get_authorization_url(
        user_id=context.get("user_id") or "",
        user_email=context.get("user_email") or current_user.email,
        owner_id=context.get("owner_id") or context.get("user_id") or "",
        owner_email=context.get("owner_email") or current_user.email,
    )

    return CalendarAuthUrlResponse(
        auth_url=auth_url,
        message="Redirect the user to auth_url to connect a calendar account",
    )


@router.get(
    "/planner/calendar/provider/callback",
    tags=["Planner Calendar"],
    response_model=CalendarCallbackResponse,
)
async def calendar_oauth_callback(
    code: str = Query(..., description="Authorization code from the calendar aggregator"),
    state: str = Query(..., description="Signed state parameter from the connect step"),
    current_user: ExtendedAuthUser = Depends(
        require_calendar_permission("connect_personal_calendar")
    ),
) -> CalendarCallbackResponse:
    """Handle the calendar aggregator OAuth callback after the user grants consent."""
    context = get_calendar_owner_identity(current_user)
    result = await calendar_provider_service.handle_oauth_callback(
        code=code,
        state=state,
        current_user_context={
            "user_id": context.get("user_id"),
            "user_email": context.get("user_email"),
        },
    )

    return CalendarCallbackResponse(
        connected=result.get("connected", False),
        calendar_id=result.get("calendar_id"),
        message=result.get("message", ""),
    )


@router.get(
    "/planner/calendar/provider/status",
    tags=["Planner Calendar"],
    response_model=CalendarSyncStatus,
)
async def get_calendar_status(
    current_user: ExtendedAuthUser = Depends(require_calendar_access),
) -> CalendarSyncStatus:
    """Return the connection status for the current user's calendar account."""
    status = await calendar_provider_service.get_connection_status(current_user.email)

    return CalendarSyncStatus(
        connected=status.get("connected", False),
        calendar_id=status.get("calendar_id"),
        last_sync=status.get("last_sync"),
        sync_enabled=status.get("sync_enabled", False),
        events_synced=status.get("events_synced", 0),
    )


@router.delete(
    "/planner/calendar/provider/disconnect",
    tags=["Planner Calendar"],
)
async def disconnect_calendar(
    current_user: ExtendedAuthUser = Depends(
        require_calendar_permission("connect_personal_calendar")
    ),
) -> dict:
    """Disconnect every calendar connection for the current user."""
    result = await calendar_provider_service.disconnect(current_user.email)
    return result


@router.get(
    "/planner/calendar/provider/events",
    tags=["Planner Calendar"],
)
async def fetch_calendar_events(
    current_user: ExtendedAuthUser = Depends(require_calendar_access),
    days_ahead: int = Query(
        default=30, ge=1, le=365, description="Days ahead to fetch"
    ),
) -> List[dict]:
    """Fetch events from the user's default writable calendar via Aurinko."""
    time_min = datetime.now(UTC)
    time_max = time_min + timedelta(days=days_ahead)

    events = await calendar_provider_service.fetch_external_events(
        current_user.email,
        time_min=time_min,
        time_max=time_max,
    )

    return events


@router.get(
    "/planner/calendar/connections",
    tags=["Planner Calendar"],
    response_model=list[CalendarConnectionResponse],
)
async def list_calendar_connections(
    current_user: ExtendedAuthUser = Depends(require_calendar_access),
) -> list[CalendarConnectionResponse]:
    """List visible external calendar connections in the planner owner scope."""
    scope = get_accessible_calendar_scope(current_user)
    connections = await calendar_provider_service.list_connections(
        owner_id=str(scope.get("owner_id") or ""),
        current_user_id=get_calendar_owner_identity(current_user).get("user_id"),
        include_all_owner_connections=bool(scope.get("is_owner")),
    )
    return [CalendarConnectionResponse(**connection) for connection in connections]


@router.post(
    "/planner/calendar/connections/provider/connect",
    tags=["Planner Calendar"],
    response_model=CalendarAuthUrlResponse,
)
async def get_calendar_connection_auth_url(
    current_user: ExtendedAuthUser = Depends(
        require_calendar_permission("connect_personal_calendar")
    ),
) -> CalendarAuthUrlResponse:
    """Connection-aware alias for the calendar aggregator connect flow."""
    return await get_calendar_auth_url(current_user=current_user)


@router.get(
    "/planner/calendar/connections/provider/callback",
    tags=["Planner Calendar"],
    response_model=CalendarCallbackResponse,
)
async def calendar_connection_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    current_user: ExtendedAuthUser = Depends(
        require_calendar_permission("connect_personal_calendar")
    ),
) -> CalendarCallbackResponse:
    """Connection-aware alias for the calendar aggregator OAuth callback."""
    return await calendar_oauth_callback(
        code=code, state=state, current_user=current_user
    )


@router.patch(
    "/planner/calendar/connections/{connection_id}",
    tags=["Planner Calendar"],
    response_model=CalendarConnectionResponse,
)
async def update_calendar_connection(
    connection_id: str,
    body: CalendarConnectionUpdateRequest,
    current_user: ExtendedAuthUser = Depends(require_calendar_access),
) -> CalendarConnectionResponse:
    """Update mutable connection settings for a calendar row."""
    connection_doc = await calendar_provider_service.get_connection_doc(connection_id)
    current_context = get_calendar_owner_identity(current_user)
    is_owner = current_user.is_root_admin or current_user.is_wedding_planner
    is_connection_owner = connection_doc.get("user_id") == current_context.get(
        "user_id"
    )
    can_manage_all = bool(
        current_user.team_permissions
        and current_user.team_permissions.get("manage_calendar_connections", False)
    )

    updates = body.model_dump(exclude_none=True)
    if not _connection_matches_owner_scope(connection_doc, current_user):
        raise HTTPException(
            status_code=403, detail="Cannot manage this calendar connection"
        )

    if not (is_owner or can_manage_all or is_connection_owner):
        raise HTTPException(
            status_code=403, detail="Cannot manage this calendar connection"
        )

    if not (is_owner or can_manage_all):
        restricted_fields = {
            "scheduler_access_mode",
            "sync_targeting_mode",
            "allowed_scheduler_user_ids",
            "allowed_scheduler_roles",
            "allowed_schedule_item_types",
            "allowed_wedding_ids",
            "is_shared_in_team_view",
            "details_visibility",
        }
        if restricted_fields.intersection(updates.keys()):
            raise HTTPException(
                status_code=403,
                detail="Only planner owners can change team-sharing visibility",
            )

    if "allowed_scheduler_user_ids" in updates:
        resolved_ids, _ = await resolve_owner_scoped_user_assignments(
            connection_doc.get("owner_planner_id"),
            connection_doc.get("owner_planner_email"),
            updates["allowed_scheduler_user_ids"],
        )
        updates["allowed_scheduler_user_ids"] = resolved_ids
    if "allowed_wedding_ids" in updates:
        updates["allowed_wedding_ids"] = await _resolve_owner_scoped_wedding_ids(
            connection_doc.get("owner_planner_id"),
            connection_doc.get("owner_planner_email"),
            updates["allowed_wedding_ids"],
        )

    updated = await calendar_provider_service.update_connection(
        connection_id,
        updates,
        actor_email=current_user.email,
        actor_role=current_user.role,
    )
    return CalendarConnectionResponse(**updated)


@router.delete(
    "/planner/calendar/connections/{connection_id}",
    tags=["Planner Calendar"],
)
async def delete_calendar_connection(
    connection_id: str,
    current_user: ExtendedAuthUser = Depends(require_calendar_access),
) -> dict:
    """Disconnect one calendar connection, revoking provider access when appropriate."""
    connection_doc = await calendar_provider_service.get_connection_doc(connection_id)
    current_context = get_calendar_owner_identity(current_user)
    is_owner = current_user.is_root_admin or current_user.is_wedding_planner
    can_manage_all = bool(
        current_user.team_permissions
        and current_user.team_permissions.get("manage_calendar_connections", False)
    )
    if not _connection_matches_owner_scope(connection_doc, current_user):
        raise HTTPException(
            status_code=403, detail="Cannot disconnect this calendar connection"
        )
    if not (
        is_owner
        or can_manage_all
        or connection_doc.get("user_id") == current_context.get("user_id")
    ):
        raise HTTPException(
            status_code=403, detail="Cannot disconnect this calendar connection"
        )
    return await calendar_provider_service.disconnect_connection(
        connection_id,
        actor_email=current_user.email,
        actor_role=current_user.role,
    )


@router.post(
    "/planner/calendar/connections/{connection_id}/healthcheck",
    tags=["Planner Calendar"],
    response_model=CalendarConnectionResponse,
)
async def healthcheck_calendar_connection(
    connection_id: str,
    current_user: ExtendedAuthUser = Depends(require_calendar_access),
) -> CalendarConnectionResponse:
    """Validate a connection against the calendar aggregator and return updated health metadata."""
    connection_doc = await calendar_provider_service.get_connection_doc(connection_id)
    current_context = get_calendar_owner_identity(current_user)
    can_manage_all = bool(
        current_user.team_permissions
        and current_user.team_permissions.get("manage_calendar_connections", False)
    )
    if not _connection_matches_owner_scope(connection_doc, current_user):
        raise HTTPException(
            status_code=403, detail="Cannot healthcheck this calendar connection"
        )
    if not (
        current_user.is_root_admin
        or current_user.is_wedding_planner
        or can_manage_all
        or connection_doc.get("user_id") == current_context.get("user_id")
    ):
        raise HTTPException(
            status_code=403, detail="Cannot healthcheck this calendar connection"
        )
    result = await calendar_provider_service.healthcheck_connection(connection_id)
    return CalendarConnectionResponse(**result)


@router.get(
    "/planner/calendar/view",
    tags=["Planner Calendar"],
    response_model=list[SharedCalendarEventResponse],
)
async def get_shared_calendar_view(
    current_user: ExtendedAuthUser = Depends(require_calendar_access),
    start: Optional[datetime] = Query(None),
    end: Optional[datetime] = Query(None),
    wedding_ids: Optional[List[str]] = Query(None),
    staff_ids: Optional[List[str]] = Query(None),
    source_types: Optional[List[str]] = Query(None),
) -> list[SharedCalendarEventResponse]:
    """Return a unified internal plus external shared calendar feed."""
    scope = get_accessible_calendar_scope(current_user)
    context = get_calendar_owner_identity(current_user)
    events = await calendar_aggregation_service.build_shared_view(
        owner_id=str(scope.get("owner_id") or ""),
        owner_email=str(scope.get("owner_email") or ""),
        current_user_id=context.get("user_id"),
        include_all_owner_connections=bool(scope.get("is_owner")),
        can_view_details=can_view_calendar_details(current_user),
        accessible_wedding_ids=scope.get("accessible_wedding_ids"),
        start=start,
        end=end,
        wedding_ids=wedding_ids,
        staff_ids=staff_ids,
        source_types=source_types,
    )
    return [_serialize_shared_event(event) for event in events]


@router.get("/planner/calendar/availability", tags=["Planner Calendar"])
async def get_staff_availability(
    current_user: ExtendedAuthUser = Depends(
        require_calendar_permission("view_team_availability")
    ),
    staff_ids: List[str] = Query(...),
    start: datetime = Query(...),
    end: datetime = Query(...),
) -> dict:
    """Return busy blocks plus naive available windows for selected staff."""
    scope = get_accessible_calendar_scope(current_user)
    context = get_calendar_owner_identity(current_user)
    events = await calendar_aggregation_service.build_shared_view(
        owner_id=str(scope.get("owner_id") or ""),
        owner_email=str(scope.get("owner_email") or ""),
        current_user_id=context.get("user_id"),
        include_all_owner_connections=bool(scope.get("is_owner")),
        can_view_details=can_view_calendar_details(current_user),
        accessible_wedding_ids=scope.get("accessible_wedding_ids"),
        start=start,
        end=end,
        staff_ids=staff_ids,
    )
    busy_events = [
        event
        for event in events
        if set(event.get("assigned_user_ids", [])) & set(staff_ids)
    ]
    busy_ranges = []
    for event in busy_events:
        event_start = _coerce_event_datetime(event.get("start_date"))
        event_end = _coerce_event_datetime(event.get("end_date"))
        if event_start and event_end:
            busy_ranges.append((event_start, event_end))
    busy_ranges.sort(key=lambda row: row[0])

    available_windows = []
    cursor = start
    for busy_start, busy_end in busy_ranges:
        if busy_start > cursor:
            available_windows.append(
                {
                    "start": cursor.isoformat(),
                    "end": busy_start.isoformat(),
                }
            )
        if busy_end > cursor:
            cursor = busy_end
    if cursor < end:
        available_windows.append({"start": cursor.isoformat(), "end": end.isoformat()})

    return {
        "staff_ids": staff_ids,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "busy_events": [_serialize_shared_event(event) for event in busy_events],
        "available_windows": available_windows,
    }


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
    current_user: ExtendedAuthUser = Depends(
        require_calendar_permission("manage_calendar_tasks")
    ),
) -> TaskResponse:
    """
    Create a new task/event for the planner's calendar.
    """
    tasks_collection = mongo.get_planner_tasks_collection()

    now = datetime.now(UTC)
    owner_context = get_calendar_owner_identity(current_user)
    owner_email = _calendar_owner_email(current_user)
    external_sync_requested = bool(
        task_data.external_sync_requested
        if task_data.external_sync_requested is not None
        else task_data.schedule_item_type == ScheduleItemType.MEETING.value
    )
    assigned_user_ids = task_data.assigned_user_ids
    assigned_user_emails = task_data.assigned_user_emails
    if assigned_user_ids:
        (
            assigned_user_ids,
            assigned_user_emails,
        ) = await resolve_owner_scoped_user_assignments(
            owner_context.get("owner_id"),
            owner_context.get("owner_email"),
            assigned_user_ids,
        )

    # Build task document
    task_doc = {
        "planner_email": owner_email,
        "owner_planner_id": owner_context.get("owner_id"),
        "owner_planner_email": owner_email,
        "created_by_user_id": owner_context.get("user_id"),
        "created_by_email": current_user.email,
        "assigned_user_ids": assigned_user_ids,
        "assigned_user_emails": assigned_user_emails,
        "wedding_id": task_data.wedding_id,
        "title": task_data.title,
        "description": task_data.description,
        "category": task_data.category,
        "priority": task_data.priority,
        "status": "pending",
        "schedule_item_type": task_data.schedule_item_type,
        "visibility_mode": task_data.visibility_mode,
        "calendar_sync_policy": task_data.calendar_sync_policy,
        "external_sync_requested": external_sync_requested,
        "start_date": task_data.start_date,
        "end_date": task_data.end_date or task_data.start_date,
        "all_day": task_data.all_day,
        "due_date": task_data.due_date,
        "timezone": task_data.timezone,
        "couple_attendee_emails": task_data.couple_attendee_emails,
        "external_attendees": [],
        "conference_provider": task_data.conference_provider,
        "conference_url": task_data.conference_url,
        "invite_delivery_mode": task_data.invite_delivery_mode,
        "meeting_status": task_data.meeting_status,
        "reminder_minutes": task_data.reminder_minutes,
        "is_recurring": task_data.is_recurring,
        "recurrence_rule": task_data.recurrence_rule,
        "color": task_data.color,
        "notes": task_data.notes,
        "attachments": [],
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
    }

    result = await tasks_collection.insert_one(task_doc)
    task_doc["_id"] = result.inserted_id

    # Sync to Google Calendar if requested and connected
    if external_sync_requested:
        await calendar_sync_service.sync_schedule_item(
            task_doc,
            actor_user_id=_calendar_user_id(current_user),
            actor_is_owner=bool(
                current_user.is_root_admin or current_user.is_wedding_planner
            ),
            actor_role_scope=_calendar_actor_role_scope(current_user),
        )

    wedding_name = await _get_wedding_name(task_data.wedding_id)
    sync_summary = await calendar_sync_service.get_sync_summary(str(result.inserted_id))

    logger.info(f"Created task {result.inserted_id} for planner {current_user.email}")

    return _serialize_task(task_doc, wedding_name, sync_summary)


@router.get(
    "/planner/calendar/tasks",
    tags=["Planner Calendar"],
    response_model=TaskListResponse,
)
async def list_tasks(
    current_user: ExtendedAuthUser = Depends(require_calendar_access),
    wedding_id: Optional[str] = Query(None, description="Filter by wedding ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    category: Optional[str] = Query(None, description="Filter by category"),
    start_date: Optional[datetime] = Query(
        None, description="Filter tasks after this date"
    ),
    end_date: Optional[datetime] = Query(
        None, description="Filter tasks before this date"
    ),
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
    status = validated_status_filter(
        status, ["pending", "in_progress", "completed", "cancelled"]
    )
    category = validated_string_filter(category, max_length=50)

    # Build query
    query: dict[str, Any] = _build_task_scope_query(current_user)

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

    sync_summary_map = await _load_task_sync_summary_map(tasks)

    serialized_tasks = [
        _serialize_task(
            t,
            wedding_names.get(t.get("wedding_id")),
            sync_summary_map.get(str(t.get("_id")), {}),
        )
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
    current_user: ExtendedAuthUser = Depends(require_calendar_access),
) -> TaskResponse:
    """
    Get a specific task by ID.
    """
    tasks_collection = mongo.get_planner_tasks_collection()

    try:
        oid = ObjectId(task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID format")

    task = await tasks_collection.find_one(
        {"$and": [{"_id": oid}, _build_task_scope_query(current_user)]}
    )
    task = _require_document(task, "Task not found")

    wedding_name = await _get_wedding_name(task.get("wedding_id"))
    sync_summary = await calendar_sync_service.get_sync_summary(task_id)

    return _serialize_task(task, wedding_name, sync_summary)


@router.patch(
    "/planner/calendar/tasks/{task_id}",
    tags=["Planner Calendar"],
    response_model=TaskResponse,
)
async def update_task(
    task_id: str,
    updates: CalendarEventUpdate,
    current_user: ExtendedAuthUser = Depends(
        require_calendar_permission("manage_calendar_tasks")
    ),
) -> TaskResponse:
    """
    Update an existing task.
    """
    tasks_collection = mongo.get_planner_tasks_collection()

    try:
        oid = ObjectId(task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID format")

    # Get existing task
    task = await tasks_collection.find_one(
        {"$and": [{"_id": oid}, _build_task_scope_query(current_user)]}
    )
    task = _require_document(task, "Task not found")

    # Build update document
    update_doc: dict[str, Any] = {"updated_at": datetime.now(UTC)}

    update_fields = updates.model_dump(exclude_unset=True)
    owner_context = get_calendar_owner_identity(current_user)
    requested_sync_state = None
    if update_fields.get("external_sync_requested") is not None:
        requested_sync_state = bool(update_fields.pop("external_sync_requested"))
    if requested_sync_state is not None:
        update_doc["external_sync_requested"] = requested_sync_state
    if (
        "assigned_user_ids" in update_fields
        and update_fields["assigned_user_ids"] is not None
    ):
        resolved_ids, resolved_emails = await resolve_owner_scoped_user_assignments(
            owner_context.get("owner_id"),
            owner_context.get("owner_email"),
            update_fields["assigned_user_ids"],
        )
        update_fields["assigned_user_ids"] = resolved_ids
        update_fields["assigned_user_emails"] = resolved_emails
    for field, value in update_fields.items():
        if value is not None:
            update_doc[field] = value

    # Handle status change to completed
    if updates.status == "completed" and task.get("status") != "completed":
        update_doc["completed_at"] = datetime.now(UTC)
    elif updates.status and updates.status != "completed":
        update_doc["completed_at"] = None

    existing_sync_summary = await calendar_sync_service.get_sync_summary(task_id)
    updated_task_doc = {**task, **update_doc, "_id": oid}

    await tasks_collection.update_one({"_id": oid}, {"$set": update_doc})

    if requested_sync_state is False and existing_sync_summary.get("row_count"):
        await calendar_sync_service.delete_schedule_item_syncs(task_id)
    elif updated_task_doc.get("external_sync_requested") or existing_sync_summary.get(
        "row_count"
    ):
        await calendar_sync_service.sync_schedule_item(
            updated_task_doc,
            actor_user_id=_calendar_user_id(current_user),
            actor_is_owner=bool(
                current_user.is_root_admin or current_user.is_wedding_planner
            ),
            actor_role_scope=_calendar_actor_role_scope(current_user),
        )

    # Fetch updated task
    updated_task = await tasks_collection.find_one({"_id": oid})
    updated_task = _require_document(updated_task, "Task not found after update")
    wedding_name = await _get_wedding_name(updated_task.get("wedding_id"))
    sync_summary = await calendar_sync_service.get_sync_summary(task_id)

    logger.info(f"Updated task {task_id} for planner {current_user.email}")

    return _serialize_task(updated_task, wedding_name, sync_summary)


@router.delete(
    "/planner/calendar/tasks/{task_id}",
    tags=["Planner Calendar"],
)
async def delete_task(
    task_id: str,
    current_user: ExtendedAuthUser = Depends(
        require_calendar_permission("manage_calendar_tasks")
    ),
) -> dict:
    """
    Delete a task.

    If the task is synced to Google Calendar, the Google event
    will also be deleted.
    """
    tasks_collection = mongo.get_planner_tasks_collection()

    try:
        oid = ObjectId(task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID format")

    # Get existing task
    task = await tasks_collection.find_one(
        {"$and": [{"_id": oid}, _build_task_scope_query(current_user)]}
    )
    task = _require_document(task, "Task not found")

    # Delete from Google Calendar if synced
    await calendar_sync_service.delete_schedule_item_syncs(task_id)

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
    current_user: ExtendedAuthUser = Depends(
        require_calendar_permission("sync_calendar_tasks")
    ),
) -> TaskResponse:
    """
    Manually sync a specific task to Google Calendar.

    Creates the event in Google Calendar if not already synced,
    or updates it if already synced.
    """
    tasks_collection = mongo.get_planner_tasks_collection()

    try:
        oid = ObjectId(task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID format")

    task = await tasks_collection.find_one(
        {"$and": [{"_id": oid}, _build_task_scope_query(current_user)]}
    )
    task = _require_document(task, "Task not found")

    await tasks_collection.update_one(
        {"_id": oid},
        {
            "$set": {
                "external_sync_requested": True,
                "updated_at": datetime.now(UTC),
            }
        },
    )
    task["external_sync_requested"] = True

    sync_status = await calendar_sync_service.sync_schedule_item(
        task,
        actor_user_id=_calendar_user_id(current_user),
        actor_is_owner=bool(
            current_user.is_root_admin or current_user.is_wedding_planner
        ),
        actor_role_scope=_calendar_actor_role_scope(current_user),
    )
    successful_sync = next(
        (
            item
            for item in sync_status
            if item.get("sync_status") == CalendarSyncStatusValue.SYNCED.value
            and item.get("external_event_id")
        ),
        None,
    )

    if not successful_sync:
        raise HTTPException(
            status_code=400,
            detail="No eligible writable calendar target is currently available for this task.",
        )

    # Fetch updated task
    updated_task = await tasks_collection.find_one({"_id": oid})
    updated_task = _require_document(updated_task, "Task not found after sync")
    wedding_name = await _get_wedding_name(updated_task.get("wedding_id"))
    sync_summary = await calendar_sync_service.get_sync_summary(task_id)

    return _serialize_task(updated_task, wedding_name, sync_summary)


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
    current_user: ExtendedAuthUser = Depends(
        require_calendar_permission("manage_calendar_tasks")
    ),
) -> dict:
    """
    Update status for multiple tasks at once.
    """
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
            **_build_task_scope_query(current_user),
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
    current_user: ExtendedAuthUser = Depends(require_calendar_access),
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
        "$and": [
            _build_task_scope_query(current_user),
            {
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
                ]
            },
        ]
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
    sync_summary_map = await _load_task_sync_summary_map(tasks)

    return [
        _serialize_task(
            t,
            wedding_names.get(t.get("wedding_id")),
            sync_summary_map.get(str(t.get("_id")), {}),
        )
        for t in tasks
    ]


@router.get(
    "/planner/calendar/upcoming",
    tags=["Planner Calendar"],
)
async def get_upcoming_tasks(
    current_user: ExtendedAuthUser = Depends(require_calendar_access),
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
        "$and": [
            _build_task_scope_query(current_user),
            {
                "status": {"$ne": "completed"},
                "start_date": {"$gte": now, "$lte": end_date},
            },
        ]
    }

    tasks = (
        await tasks_collection.find(query)
        .sort("start_date", 1)
        .limit(limit)
        .to_list(length=limit)
    )

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
    sync_summary_map = await _load_task_sync_summary_map(tasks)

    return [
        _serialize_task(
            t,
            wedding_names.get(t.get("wedding_id")),
            sync_summary_map.get(str(t.get("_id")), {}),
        )
        for t in tasks
    ]


# ============================================================================
# Shared Meeting Endpoints
# ============================================================================


@router.post(
    "/planner/calendar/meetings",
    tags=["Planner Calendar"],
    response_model=MeetingUpsertResponse,
)
async def create_meeting(
    data: CalendarEventCreate,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    current_user: ExtendedAuthUser = Depends(
        require_calendar_permission("schedule_meetings")
    ),
) -> MeetingUpsertResponse:
    """Create a canonical meeting inside planner_tasks and sync projections explicitly."""
    if data.wedding_id and not await check_wedding_access(
        current_user, data.wedding_id
    ):
        raise HTTPException(
            status_code=403, detail="You don't have access to this wedding"
        )

    owner_context = get_calendar_owner_identity(current_user)
    scope_key = _build_meeting_idempotency_scope(
        "create_meeting",
        str(
            owner_context.get("owner_id")
            or owner_context.get("user_id")
            or current_user.email
        ),
    )
    idempotency_key_value, replay_payload = await _begin_meeting_idempotency(
        scope_key=scope_key,
        idempotency_key=idempotency_key,
        action="create_meeting",
        payload=data.model_dump(mode="json"),
    )
    if replay_payload:
        return MeetingUpsertResponse(**replay_payload)

    assigned_user_ids = data.assigned_user_ids or []
    assigned_user_emails = data.assigned_user_emails or []
    if assigned_user_ids:
        (
            assigned_user_ids,
            assigned_user_emails,
        ) = await resolve_owner_scoped_user_assignments(
            owner_context.get("owner_id"),
            owner_context.get("owner_email"),
            assigned_user_ids,
        )
    couple_attendee_emails = await _resolve_couple_attendee_emails(
        data.wedding_id,
        data.couple_attendee_emails,
    )
    sync_policy = data.calendar_sync_policy or (
        CalendarSyncPolicy.ASSIGNED_ONLY.value
        if assigned_user_ids
        else CalendarSyncPolicy.OWNER_ONLY.value
    )
    can_send_invites = _can_send_meeting_invites(current_user)
    if (
        data.invite_delivery_mode == InviteDeliveryMode.EMAIL_ICS.value
        and not can_send_invites
    ):
        raise HTTPException(
            status_code=403,
            detail="You do not have the 'send meeting invites' permission.",
        )
    invite_mode = (
        data.invite_delivery_mode
        if data.invite_delivery_mode != InviteDeliveryMode.NONE.value
        else (
            InviteDeliveryMode.EMAIL_ICS.value
            if couple_attendee_emails and can_send_invites
            else InviteDeliveryMode.PORTAL_ONLY.value
        )
    )
    now = datetime.now(UTC)
    task_doc = {
        "planner_email": owner_context.get("owner_email") or current_user.email,
        "owner_planner_id": owner_context.get("owner_id"),
        "owner_planner_email": owner_context.get("owner_email") or current_user.email,
        "created_by_user_id": owner_context.get("user_id"),
        "created_by_email": current_user.email,
        "assigned_user_ids": assigned_user_ids,
        "assigned_user_emails": assigned_user_emails,
        "wedding_id": data.wedding_id,
        "title": data.title,
        "description": data.description,
        "category": "meeting",
        "priority": data.priority,
        "status": "pending",
        "schedule_item_type": ScheduleItemType.MEETING.value,
        "visibility_mode": data.visibility_mode,
        "calendar_sync_policy": sync_policy,
        "external_sync_requested": True,
        "sync_target_override_enabled": data.sync_target_override_enabled,
        "sync_target_connection_ids": (
            data.sync_target_connection_ids if data.sync_target_override_enabled else []
        ),
        "start_date": data.start_date,
        "end_date": data.end_date or data.start_date,
        "all_day": data.all_day,
        "due_date": data.due_date,
        "timezone": data.timezone,
        "couple_attendee_emails": couple_attendee_emails,
        "external_attendees": [],
        "conference_provider": data.conference_provider,
        "conference_url": data.conference_url,
        "invite_delivery_mode": invite_mode,
        "meeting_status": MeetingLifecycleStatus.SCHEDULED.value,
        "reminder_minutes": data.reminder_minutes,
        "is_recurring": data.is_recurring,
        "recurrence_rule": data.recurrence_rule if data.is_recurring else None,
        "color": data.color,
        "notes": data.notes,
        "attachments": [],
        "created_at": now,
        "updated_at": now,
        "version": 1,
        "completed_at": None,
    }
    try:
        result = await mongo.get_planner_tasks_collection().insert_one(task_doc)
        task_doc["_id"] = result.inserted_id

        sync_status = await calendar_sync_service.sync_schedule_item(
            task_doc,
            explicit_connection_ids=(
                data.sync_target_connection_ids
                if data.sync_target_override_enabled
                else None
            ),
            actor_user_id=_calendar_user_id(current_user),
            actor_is_owner=bool(
                current_user.is_root_admin or current_user.is_wedding_planner
            ),
            actor_role_scope=_calendar_actor_role_scope(current_user),
        )

        invite_status: list[dict[str, Any]] = []
        if (
            invite_mode == InviteDeliveryMode.EMAIL_ICS.value
            and can_send_invites
            and couple_attendee_emails
        ):
            try:
                invite_status = await calendar_job_service.enqueue_invite_job(
                    task_doc,
                    method="REQUEST",
                    reason="meeting_created",
                )
            except Exception as exc:
                logger.error(
                    "Failed to enqueue meeting invite job for %s: %s",
                    result.inserted_id,
                    exc,
                )
                invite_status = [
                    {
                        "success": False,
                        "status": "queue_failed",
                        "error": "Failed to queue invite delivery",
                    }
                ]

        await calendar_audit_service.log(
            action="calendar_meeting_scheduled",
            message=f"Scheduled meeting {task_doc.get('title')}",
            owner_planner_email=_optional_str(task_doc.get("owner_planner_email"))
            or _optional_str(task_doc.get("planner_email")),
            actor_email=current_user.email,
            actor_role=current_user.role,
            wedding_id=_optional_str(task_doc.get("wedding_id")),
            metadata={
                "task_id": str(task_doc.get("_id")),
                "assigned_user_ids": task_doc.get("assigned_user_ids", []),
                "calendar_sync_policy": task_doc.get("calendar_sync_policy"),
                "invite_delivery_mode": task_doc.get("invite_delivery_mode"),
            },
        )

        response = MeetingUpsertResponse(
            meeting=_serialize_meeting_payload(task_doc),
            sync_status=sync_status,
            invite_status=invite_status,
        )
        await _complete_meeting_idempotency(
            scope_key=scope_key,
            idempotency_key=idempotency_key_value,
            payload=response.model_dump(mode="json"),
        )
        return response
    except Exception as exc:
        await _fail_meeting_idempotency(
            scope_key=scope_key,
            idempotency_key=idempotency_key_value,
            detail=str(exc),
        )
        raise


@router.patch(
    "/planner/calendar/meetings/{meeting_id}",
    tags=["Planner Calendar"],
    response_model=MeetingUpsertResponse,
)
async def update_meeting(
    meeting_id: str,
    updates: CalendarEventUpdate,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    current_user: ExtendedAuthUser = Depends(
        require_calendar_permission("edit_meetings")
    ),
) -> MeetingUpsertResponse:
    """Update a canonical meeting and re-sync its external projections."""
    try:
        oid = ObjectId(meeting_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid meeting ID format")

    if updates.expected_version is None:
        raise HTTPException(
            status_code=428,
            detail="expected_version is required when updating a meeting",
        )

    scope_key = _build_meeting_idempotency_scope("update_meeting", meeting_id)
    update_payload = updates.model_dump(mode="json", exclude_unset=True)
    idempotency_key_value, replay_payload = await _begin_meeting_idempotency(
        scope_key=scope_key,
        idempotency_key=idempotency_key,
        action="update_meeting",
        payload={"meeting_id": meeting_id, **update_payload},
    )
    if replay_payload:
        return MeetingUpsertResponse(**replay_payload)

    tasks_collection = mongo.get_planner_tasks_collection()
    async with _meeting_mutation_lock(meeting_id):
        task = await _get_scoped_meeting(oid, current_user)
        if task.get("wedding_id") and not await check_wedding_access(
            current_user, task["wedding_id"]
        ):
            raise HTTPException(
                status_code=403, detail="You don't have access to this wedding"
            )

        expected_version = updates.expected_version
        if int(task.get("version") or 1) != expected_version:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "This meeting was changed by another user. Refresh and try again.",
                    "current_version": int(task.get("version") or 1),
                },
            )

        update_doc: dict[str, Any] = {"updated_at": datetime.now(UTC)}
        update_fields = updates.model_dump(exclude_unset=True)
        update_fields.pop("expected_version", None)
        update_doc["external_sync_requested"] = True
        if update_fields.get(
            "invite_delivery_mode"
        ) == InviteDeliveryMode.EMAIL_ICS.value and not _can_send_meeting_invites(
            current_user
        ):
            raise HTTPException(
                status_code=403,
                detail="You do not have the 'send meeting invites' permission.",
            )
        if "wedding_id" in update_fields and update_fields["wedding_id"] is not None:
            if not await check_wedding_access(
                current_user, update_fields["wedding_id"]
            ):
                raise HTTPException(
                    status_code=403, detail="You don't have access to this wedding"
                )
        if (
            "assigned_user_ids" in update_fields
            and update_fields["assigned_user_ids"] is not None
        ):
            resolved_ids, resolved_emails = await resolve_owner_scoped_user_assignments(
                task.get("owner_planner_id"),
                task.get("owner_planner_email") or task.get("planner_email"),
                update_fields["assigned_user_ids"],
            )
            update_doc["assigned_user_ids"] = resolved_ids
            update_doc["assigned_user_emails"] = resolved_emails
        if (
            "couple_attendee_emails" in update_fields
            and update_fields["couple_attendee_emails"] is not None
        ):
            update_doc[
                "couple_attendee_emails"
            ] = await _resolve_couple_attendee_emails(
                update_fields.get("wedding_id") or task.get("wedding_id"),
                update_fields["couple_attendee_emails"],
            )
        for key, value in update_fields.items():
            if key in {"assigned_user_ids", "couple_attendee_emails"}:
                continue
            if value is not None:
                update_doc[key] = value
        if update_fields.get("sync_target_override_enabled") is False:
            update_doc["sync_target_connection_ids"] = []
        if (
            _meeting_invite_content_changed(update_fields)
            and update_fields.get("meeting_status") is None
        ):
            update_doc["meeting_status"] = MeetingLifecycleStatus.RESCHEDULED.value

        try:
            update_result = await tasks_collection.update_one(
                {"_id": oid, "version": expected_version},
                {"$set": update_doc, "$inc": {"version": 1}},
            )
            if update_result.matched_count == 0:
                fresh_task = await _get_scoped_meeting(oid, current_user)
                raise HTTPException(
                    status_code=409,
                    detail={
                        "message": "This meeting was changed by another user. Refresh and try again.",
                        "current_version": int(fresh_task.get("version") or 1),
                    },
                )

            updated_task = await tasks_collection.find_one({"_id": oid})
            updated_task = _require_document(
                updated_task, "Meeting not found after update"
            )
            sync_status = await calendar_sync_service.sync_schedule_item(
                updated_task,
                explicit_connection_ids=(
                    update_fields.get("sync_target_connection_ids")
                    if update_fields.get("sync_target_override_enabled") is True
                    else (
                        []
                        if update_fields.get("sync_target_override_enabled") is False
                        else None
                    )
                ),
                actor_user_id=_calendar_user_id(current_user),
                actor_is_owner=bool(
                    current_user.is_root_admin or current_user.is_wedding_planner
                ),
                actor_role_scope=_calendar_actor_role_scope(current_user),
            )

            invite_status: list[dict[str, Any]] = []
            previous_recipients = {
                email for email in task.get("couple_attendee_emails", []) if email
            }
            current_recipients = {
                email
                for email in updated_task.get("couple_attendee_emails", [])
                if email
            }
            previous_invite_mode = task.get("invite_delivery_mode")
            current_invite_mode = updated_task.get("invite_delivery_mode")

            if previous_invite_mode == InviteDeliveryMode.EMAIL_ICS.value:
                removed_recipients = (
                    previous_recipients
                    if current_invite_mode != InviteDeliveryMode.EMAIL_ICS.value
                    else previous_recipients - current_recipients
                )
                if removed_recipients:
                    cancellation_task = {
                        **task,
                        "updated_at": updated_task.get("updated_at")
                        or datetime.now(UTC),
                        "meeting_status": MeetingLifecycleStatus.CANCELLED.value,
                    }
                    try:
                        invite_status.extend(
                            await calendar_job_service.enqueue_invite_job(
                                cancellation_task,
                                method="CANCEL",
                                recipient_emails=sorted(removed_recipients),
                                reason="meeting_updated_remove_recipient",
                            )
                        )
                    except Exception as exc:
                        logger.error(
                            "Failed to enqueue recipient removal cancellations for %s: %s",
                            meeting_id,
                            exc,
                        )
                        invite_status.append(
                            {
                                "success": False,
                                "status": "queue_failed",
                                "error": "Failed to queue cancellation invite delivery",
                            }
                        )

            should_send_updated_invites = (
                current_invite_mode == InviteDeliveryMode.EMAIL_ICS.value
                and bool(current_recipients)
                and (
                    previous_invite_mode != InviteDeliveryMode.EMAIL_ICS.value
                    or bool(current_recipients - previous_recipients)
                    or _meeting_invite_content_changed(update_fields)
                )
            )
            if should_send_updated_invites:
                try:
                    invite_status.extend(
                        await calendar_job_service.enqueue_invite_job(
                            updated_task,
                            method="REQUEST",
                            reason="meeting_updated",
                        )
                    )
                except Exception as exc:
                    logger.error(
                        "Failed to enqueue updated invites for %s: %s",
                        meeting_id,
                        exc,
                    )
                    invite_status.append(
                        {
                            "success": False,
                            "status": "queue_failed",
                            "error": "Failed to queue invite delivery",
                        }
                    )

            await calendar_audit_service.log(
                action="calendar_meeting_rescheduled",
                message=f"Updated meeting {updated_task.get('title')}",
                owner_planner_email=_optional_str(
                    updated_task.get("owner_planner_email")
                )
                or _optional_str(updated_task.get("planner_email")),
                actor_email=current_user.email,
                actor_role=current_user.role,
                wedding_id=_optional_str(updated_task.get("wedding_id")),
                metadata={
                    "task_id": meeting_id,
                    "previous_version": expected_version,
                    "current_version": int(updated_task.get("version") or 1),
                    "updated_fields": sorted(update_fields.keys()),
                },
            )

            response = MeetingUpsertResponse(
                meeting=_serialize_meeting_payload(updated_task),
                sync_status=sync_status,
                invite_status=invite_status,
            )
            await _complete_meeting_idempotency(
                scope_key=scope_key,
                idempotency_key=idempotency_key_value,
                payload=response.model_dump(mode="json"),
            )
            return response
        except Exception as exc:
            await _fail_meeting_idempotency(
                scope_key=scope_key,
                idempotency_key=idempotency_key_value,
                detail=str(exc),
            )
            raise


@router.delete(
    "/planner/calendar/meetings/{meeting_id}",
    tags=["Planner Calendar"],
)
async def delete_meeting(
    meeting_id: str,
    expected_version: int = Query(..., ge=1),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    current_user: ExtendedAuthUser = Depends(
        require_calendar_permission("cancel_meetings")
    ),
) -> dict:
    """Delete a canonical meeting and all external projections."""
    try:
        oid = ObjectId(meeting_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid meeting ID format")

    scope_key = _build_meeting_idempotency_scope("delete_meeting", meeting_id)
    idempotency_key_value, replay_payload = await _begin_meeting_idempotency(
        scope_key=scope_key,
        idempotency_key=idempotency_key,
        action="delete_meeting",
        payload={"meeting_id": meeting_id, "expected_version": expected_version},
    )
    if replay_payload:
        return replay_payload

    tasks_collection = mongo.get_planner_tasks_collection()
    async with _meeting_mutation_lock(meeting_id):
        task = await _get_scoped_meeting(oid, current_user)
        if task.get("wedding_id") and not await check_wedding_access(
            current_user, task["wedding_id"]
        ):
            raise HTTPException(
                status_code=403, detail="You don't have access to this wedding"
            )
        if int(task.get("version") or 1) != expected_version:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "This meeting was changed by another user. Refresh and try again.",
                    "current_version": int(task.get("version") or 1),
                },
            )

        try:
            await calendar_sync_service.delete_schedule_item_syncs(meeting_id)
            invite_status: list[dict[str, Any]] = []
            if task.get(
                "invite_delivery_mode"
            ) == InviteDeliveryMode.EMAIL_ICS.value and task.get(
                "couple_attendee_emails"
            ):
                cancellation_task = {
                    **task,
                    "updated_at": datetime.now(UTC),
                    "meeting_status": MeetingLifecycleStatus.CANCELLED.value,
                }
                try:
                    invite_status = await calendar_job_service.enqueue_invite_job(
                        cancellation_task,
                        method="CANCEL",
                        reason="meeting_cancelled",
                    )
                except Exception as exc:
                    logger.error(
                        "Failed to enqueue cancellation invites for %s: %s",
                        meeting_id,
                        exc,
                    )
                    invite_status = [
                        {
                            "success": False,
                            "status": "queue_failed",
                            "error": "Failed to queue cancellation invite delivery",
                        }
                    ]

            delete_result = await tasks_collection.delete_one(
                {"_id": oid, "version": expected_version}
            )
            if delete_result.deleted_count == 0:
                fresh_task = await _get_scoped_meeting(oid, current_user)
                raise HTTPException(
                    status_code=409,
                    detail={
                        "message": "This meeting was changed by another user. Refresh and try again.",
                        "current_version": int(fresh_task.get("version") or 1),
                    },
                )

            await calendar_audit_service.log(
                action="calendar_meeting_cancelled",
                message=f"Cancelled meeting {task.get('title')}",
                owner_planner_email=_optional_str(task.get("owner_planner_email"))
                or _optional_str(task.get("planner_email")),
                actor_email=current_user.email,
                actor_role=current_user.role,
                wedding_id=_optional_str(task.get("wedding_id")),
                metadata={
                    "task_id": meeting_id,
                    "previous_version": expected_version,
                },
            )
            response_payload = {
                "deleted": True,
                "meeting_id": meeting_id,
                "invite_status": invite_status,
            }
            await _complete_meeting_idempotency(
                scope_key=scope_key,
                idempotency_key=idempotency_key_value,
                payload=response_payload,
            )
            return response_payload
        except Exception as exc:
            await _fail_meeting_idempotency(
                scope_key=scope_key,
                idempotency_key=idempotency_key_value,
                detail=str(exc),
            )
            raise


@router.post(
    "/planner/calendar/meetings/{meeting_id}/send-invites",
    tags=["Planner Calendar"],
)
async def send_meeting_invites(
    meeting_id: str,
    current_user: ExtendedAuthUser = Depends(
        require_calendar_permission("send_meeting_invites")
    ),
) -> dict:
    """Send or resend ICS email invites for a meeting."""
    try:
        oid = ObjectId(meeting_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid meeting ID format")
    task = await _get_scoped_meeting(oid, current_user)
    if task.get("wedding_id") and not await check_wedding_access(
        current_user, task["wedding_id"]
    ):
        raise HTTPException(
            status_code=403, detail="You don't have access to this wedding"
        )
    invites = await calendar_job_service.enqueue_invite_job(
        task,
        method="REQUEST",
        reason="manual_resend",
    )
    return {"meeting_id": meeting_id, "invite_status": invites}


@router.post(
    "/planner/calendar/meetings/{meeting_id}/sync",
    tags=["Planner Calendar"],
)
async def sync_meeting(
    meeting_id: str,
    current_user: ExtendedAuthUser = Depends(
        require_calendar_permission("edit_meetings")
    ),
) -> dict:
    """Force a re-sync of all eligible external targets for a canonical meeting."""
    try:
        oid = ObjectId(meeting_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid meeting ID format")
    task = await _get_scoped_meeting(oid, current_user)
    await mongo.get_planner_tasks_collection().update_one(
        {"_id": oid},
        {
            "$set": {
                "external_sync_requested": True,
                "updated_at": datetime.now(UTC),
            }
        },
    )
    task["external_sync_requested"] = True
    sync_status = await calendar_sync_service.sync_schedule_item(
        task,
        actor_user_id=_calendar_user_id(current_user),
        actor_is_owner=bool(
            current_user.is_root_admin or current_user.is_wedding_planner
        ),
        actor_role_scope=_calendar_actor_role_scope(current_user),
    )
    return {"meeting_id": meeting_id, "sync_status": sync_status}


@router.get(
    "/planner/calendar/meetings/{meeting_id}/sync-status",
    tags=["Planner Calendar"],
)
async def get_meeting_sync_status(
    meeting_id: str,
    current_user: ExtendedAuthUser = Depends(require_calendar_access),
) -> dict:
    """Return per-target sync rows for a canonical meeting."""
    try:
        oid = ObjectId(meeting_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid meeting ID format")
    task = await _get_scoped_meeting(oid, current_user)
    if task.get("wedding_id") and not await check_wedding_access(
        current_user, task["wedding_id"]
    ):
        raise HTTPException(
            status_code=403, detail="You don't have access to this wedding"
        )
    return {
        "meeting_id": meeting_id,
        "sync_status": await calendar_sync_service.get_sync_status(meeting_id),
    }


@router.post(
    "/planner/calendar/meetings/{meeting_id}/external-change/accept",
    tags=["Planner Calendar"],
)
async def accept_meeting_external_change(
    meeting_id: str,
    current_user: ExtendedAuthUser = Depends(
        require_calendar_permission("edit_meetings")
    ),
) -> dict:
    """Accept an externally detected change: copy ``external_*`` snapshot fields
    onto canonical fields and reschedule ICS to attendees."""
    try:
        oid = ObjectId(meeting_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid meeting ID format")
    task = await _get_scoped_meeting(oid, current_user)
    now = datetime.now(UTC)

    canonical_updates: dict[str, Any] = {
        "external_conflict_status": ExternalConflictStatus.NONE.value,
        "external_conflict_source": None,
        "external_conflict_detected_at": None,
        "updated_at": now,
        "meeting_status": MeetingLifecycleStatus.RESCHEDULED.value,
    }
    if task.get("external_start_date"):
        canonical_updates["start_date"] = task["external_start_date"]
    if task.get("external_end_date"):
        canonical_updates["end_date"] = task["external_end_date"]
    if task.get("external_title"):
        canonical_updates["title"] = task["external_title"]
    if task.get("external_description") is not None:
        canonical_updates["description"] = task["external_description"]

    await mongo.get_planner_tasks_collection().update_one(
        {"_id": oid}, {"$set": canonical_updates}
    )
    refreshed_task = await _get_scoped_meeting(oid, current_user)
    invite_status: list[dict[str, Any]] = []
    if (
        refreshed_task.get("invite_delivery_mode") == InviteDeliveryMode.EMAIL_ICS.value
        and refreshed_task.get("couple_attendee_emails")
    ):
        invite_status = await calendar_job_service.enqueue_invite_job(
            refreshed_task,
            method="REQUEST",
            reason="external_change_accepted",
        )
    return {
        "meeting_id": meeting_id,
        "external_conflict_status": ExternalConflictStatus.NONE.value,
        "invite_status": invite_status,
    }


@router.post(
    "/planner/calendar/meetings/{meeting_id}/external-change/reject",
    tags=["Planner Calendar"],
)
async def reject_meeting_external_change(
    meeting_id: str,
    current_user: ExtendedAuthUser = Depends(
        require_calendar_permission("edit_meetings")
    ),
) -> dict:
    """Reject an externally detected change: leave canonical fields untouched
    and re-sync canonical state back onto external calendars."""
    try:
        oid = ObjectId(meeting_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid meeting ID format")
    task = await _get_scoped_meeting(oid, current_user)
    now = datetime.now(UTC)

    await mongo.get_planner_tasks_collection().update_one(
        {"_id": oid},
        {
            "$set": {
                "external_conflict_status": ExternalConflictStatus.NONE.value,
                "external_conflict_source": None,
                "external_conflict_detected_at": None,
                "external_sync_requested": True,
                "updated_at": now,
            }
        },
    )
    task["external_sync_requested"] = True
    sync_status = await calendar_sync_service.sync_schedule_item(
        task,
        actor_user_id=_calendar_user_id(current_user),
        actor_is_owner=bool(
            current_user.is_root_admin or current_user.is_wedding_planner
        ),
        actor_role_scope=_calendar_actor_role_scope(current_user),
    )
    return {
        "meeting_id": meeting_id,
        "external_conflict_status": ExternalConflictStatus.NONE.value,
        "sync_status": sync_status,
    }
