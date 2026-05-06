"""
Couple Portal API Routes

Endpoints for the couple's dashboard portal.
Includes couple-facing endpoints (require couple auth) and planner-facing
management endpoints (require planner auth).

Sprint 1: Dashboard, events, forms, updates
Sprint 2: Order-of-events CRUD, collaborative notes, contract review
Sprint 3: Couple↔planner messaging, planner notification center
Sprint 4: Wedding archival, custom form templates, error handling
Sprint 5: Note replies, meeting scheduling
Sprint 6: Registry CRUD, FAQ CRUD, QR code, push notifications
"""

import copy
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.core.database import mongo
from app.dependencies.auth_extended import (
    ExtendedAuthUser,
    check_wedding_access,
    enforce_team_permission,
    get_accessible_wedding_ids,
    require_team_or_planner,
)
from app.dependencies.couple_auth import require_couple_auth
from app.services.couple_lifecycle_service import couple_lifecycle_service
from app.services.couple_portal_service import couple_portal_service
from app.services.guest_export_service import guest_export_service
from app.services.sse_manager import sse_manager
from app.services.web_push_service import web_push_service
from app.utils.couple_archived_read_model import (
    build_archived_guest_stats,
    get_archived_faqs,
    get_archived_registries,
    get_archived_wedding_record,
)
from app.utils.best_effort_task import best_effort
from app.utils.couple_identity import (
    build_couple_principal_key,
    get_couple_display_name,
    get_couple_record_id,
    list_couple_identity_keys,
)
from app.utils.couple_realtime import couple_sse_channel
from app.utils.id_utils import to_str_id
from app.utils.messaging_roles import (
    SENDER_ROLE_COUPLE,
    SENDER_ROLE_PLANNER,
)
from app.utils.planner_ownership import (
    build_team_owner_query,
    list_wedding_ids_for_owner,
    normalize_planner_email,
    normalize_wedding_query_id,
    resolve_wedding_owner_identity,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _enforce_manage_couple_portal(current_user: ExtendedAuthUser) -> None:
    """Require explicit couple-portal management access for team members."""
    enforce_team_permission(current_user, "manage_couple_portal")


def _enforce_message_couples(current_user: ExtendedAuthUser) -> None:
    """Require explicit couple-messaging access for team members."""
    enforce_team_permission(current_user, "message_couples")


async def _resolve_couple_planner_email(
    couple: dict, wedding: Optional[dict] = None
) -> Optional[str]:
    """Resolve planner contact from canonical wedding ownership only."""
    if wedding is None and couple.get("wedding_id"):
        wedding = await mongo.get_weddings_collection().find_one(
            {"_id": normalize_wedding_query_id(couple["wedding_id"])},
            {"assigned_planner_id": 1, "assigned_planner_email": 1},
        )

    owner_identity = await resolve_wedding_owner_identity(wedding)
    return owner_identity.get("planner_email")


async def _resolve_custom_template_owner_scope(
    current_user: ExtendedAuthUser,
) -> dict[str, Any]:
    """Resolve canonical owner scope and migrate legacy team-scoped templates."""
    owner_email = normalize_planner_email(
        current_user.team_owner_email
        if current_user.is_team_member
        else current_user.email
    )
    legacy_emails = {
        email
        for email in (
            owner_email,
            normalize_planner_email(current_user.email),
        )
        if email
    }

    owner_id = (
        current_user.parent_planner_id
        if current_user.is_team_member
        else current_user.user_data.get("_id")
    )
    team_query = build_team_owner_query(owner_id, owner_email)
    if team_query:
        team_members = (
            await mongo.db["team_members"]
            .find(
                team_query,
                {"email": 1},
            )
            .to_list(length=None)
        )
        legacy_emails.update(
            email
            for member in team_members
            if member.get("email")
            for email in [normalize_planner_email(member.get("email"))]
            if email
        )

    if owner_email and legacy_emails:
        migration_emails = [email for email in legacy_emails if email != owner_email]
        if migration_emails:
            await mongo.db["custom_form_templates"].update_many(
                {"planner_email": {"$in": migration_emails}},
                {"$set": {"planner_email": owner_email}},
            )

    return {
        "owner_email": owner_email,
    }


# Auth dependency: use require_couple_auth from app.dependencies.couple_auth


# ============================================================================
# DASHBOARD ENDPOINTS
# ============================================================================


def _isoformat_or_none(value: Any) -> Optional[str]:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        return value
    return None


def _default_archived_memories_summary() -> dict[str, Any]:
    return {
        "pending_count": 0,
        "kept_count": 0,
        "rejected_count": 0,
        "processing_videos": 0,
        "enabled": False,
        "link_status": "closed",
        "upload_closes_at": None,
        "storage_ready": False,
        "stream_configured": False,
    }


def _build_archived_dashboard_fallback(
    archive: dict[str, Any], couple_email: str
) -> dict[str, Any]:
    """Return a dashboard-shaped archived payload when the live dashboard is unavailable."""
    wedding_snapshot = archive.get("wedding") or {}
    forms = archive.get("forms") or []
    submissions = archive.get("form_submissions") or []
    updates = archive.get("updates") or []
    budget_doc = archive.get("budget") or {}

    submission_map: dict[str, dict[str, Any]] = {}
    for submission in submissions:
        if submission.get("submitted_by") != couple_email:
            continue
        form_id = str(submission.get("form_id"))
        if form_id and form_id not in submission_map:
            submission_map[form_id] = submission

    archived_forms: list[dict[str, Any]] = []
    for form in forms:
        if not (
            form.get("shared_with_couple")
            or form.get("target_audience") == "couple"
            or form.get("couple_email") == couple_email
        ):
            continue

        form_id = str(form.get("_id"))
        submission = submission_map.get(form_id)
        archived_forms.append(
            {
                "id": form_id,
                "title": form.get("title"),
                "description": form.get("description"),
                "status": "submitted" if submission else "pending",
                "submitted_at": _isoformat_or_none(
                    submission.get("submitted_at") if submission else None
                ),
                "created_at": _isoformat_or_none(form.get("created_at")),
            }
        )

    archived_updates = [
        {
            "id": str(update.get("_id")),
            "type": update.get("type", "update"),
            "title": update.get("title"),
            "content": update.get("content"),
            "category": update.get("category"),
            "attachments": update.get("attachments", []),
            "is_milestone": update.get("is_milestone", False),
            "created_at": _isoformat_or_none(update.get("created_at")),
            "created_by": update.get("created_by_name"),
        }
        for update in updates
    ]

    total_budget = budget_doc.get("total_budget") or 0
    total_spent = budget_doc.get("total_spent") or budget_doc.get("spent_total") or 0
    remaining = budget_doc.get("remaining")
    if remaining is None:
        remaining = max(total_budget - total_spent, 0)

    wedding_id = archive.get("original_wedding_id") or wedding_snapshot.get("_id")
    wedding_events = wedding_snapshot.get("events", []) or []

    return {
        "wedding": {
            "id": str(wedding_id) if wedding_id is not None else "",
            "couple_names": wedding_snapshot.get("couple_names"),
            "date": wedding_snapshot.get("date"),
            "timezone": wedding_snapshot.get("timezone", "America/Chicago"),
            "venue": wedding_snapshot.get("venue"),
            "cultural_style": wedding_snapshot.get("cultural_style"),
            "theme_config": wedding_snapshot.get("theme_config"),
            "events": [
                {
                    "type": event.get("type"),
                    "custom_type_label": event.get("custom_type_label"),
                    "date": event.get("date"),
                    "details": event.get("details"),
                    "order_of_events": event.get("order_of_events", []),
                    "event_notes": event.get("event_notes", []),
                }
                for event in wedding_events
            ],
            "registries": wedding_snapshot.get("registries", []),
            "faqs": wedding_snapshot.get("faqs", []),
        },
        "planner": (
            {
                "name": None,
                "company": None,
                "email": archive.get("planner_email"),
                "phone": None,
                "profile_image_url": None,
            }
            if archive.get("planner_email")
            else None
        ),
        "guest_stats": build_archived_guest_stats(archive),
        "budget_summary": {
            "total_budget": total_budget,
            "total_spent": total_spent,
            "remaining": remaining,
        },
        "contract": None,
        "forms": archived_forms,
        "updates": archived_updates,
        "memories_summary": _default_archived_memories_summary(),
    }


@router.get("/couple/portal/dashboard", tags=["Couple Portal"])
async def get_dashboard(couple: dict = Depends(require_couple_auth)):
    """Get the couple's portal dashboard with all data."""

    wedding_id = couple.get("wedding_id")
    if not wedding_id:
        raise HTTPException(status_code=404, detail="No wedding linked to this account")

    archive = None
    if couple.get("wedding_archived"):
        archive = await get_archived_wedding_record(wedding_id)

    dashboard = await couple_portal_service.get_portal_dashboard(
        wedding_id, couple["email"]
    )
    if not dashboard and archive:
        dashboard = _build_archived_dashboard_fallback(archive, couple["email"])

    if not dashboard:
        raise HTTPException(status_code=404, detail="Wedding data not found")

    if couple.get("wedding_archived"):
        return {
            "archived": True,
            **dashboard,
            "archived_at": (
                _isoformat_or_none(archive.get("archived_at"))
                if archive
                else _isoformat_or_none(couple.get("archived_at"))
            ),
            "message": "This wedding has been completed and archived. You can still view your wedding details.",
        }

    return {"archived": False, **dashboard}


@router.get("/couple/portal/events", tags=["Couple Portal"])
async def get_events(couple: dict = Depends(require_couple_auth)):
    """Get wedding events/timeline."""
    wedding = await mongo.get_weddings_collection().find_one(
        {"_id": couple["wedding_id"]},
        {"events": 1, "date": 1, "timezone": 1},
    )
    if not wedding:
        raise HTTPException(status_code=404, detail="Wedding not found")

    return {
        "events": [
            {
                "type": e.get("type"),
                "date": e.get("date"),
                "details": e.get("details"),
                "order_of_events": e.get("order_of_events", []),
                "event_notes": e.get("event_notes", []),
            }
            for e in wedding.get("events", [])
        ],
        "wedding_date": wedding.get("date"),
        "timezone": wedding.get("timezone", "America/Chicago"),
    }


@router.get("/couple/portal/updates", tags=["Couple Portal"])
async def get_updates(
    couple: dict = Depends(require_couple_auth),
    limit: int = Query(20, ge=1, le=100),
    skip: int = Query(0, ge=0),
):
    """Get planner updates for the couple."""

    updates = []
    async for update in (
        mongo.db["couple_updates"]
        .find({"wedding_id": couple["wedding_id"]})
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    ):
        updates.append(
            {
                "id": str(update["_id"]),
                "type": update.get("type", "update"),
                "title": update.get("title"),
                "content": update.get("content"),
                "category": update.get("category"),
                "attachments": update.get("attachments", []),
                "is_milestone": update.get("is_milestone", False),
                "created_at": (
                    update.get("created_at").isoformat()
                    if update.get("created_at")
                    else None
                ),
                "created_by": update.get("created_by_name"),
            }
        )

    return {"updates": updates, "count": len(updates)}


# ============================================================================
# FORM SUBMISSION
# ============================================================================


class FormSubmissionRequest(BaseModel):
    """Couple submits a form response."""

    form_id: str = Field(...)
    responses: dict = Field(..., description="Form field responses keyed by field_id")


def _parse_couple_form_id(form_id: str) -> ObjectId:
    """Parse a couple-facing form id into an ObjectId with a stable client error."""
    try:
        return ObjectId(form_id)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=400, detail="Invalid form ID format")


def _build_couple_shared_form_query(form_object_id: ObjectId, couple: dict) -> dict:
    """Return the canonical visibility query for a couple-facing form."""
    return {
        "_id": form_object_id,
        "wedding_id": couple["wedding_id"],
        "$or": [
            {"shared_with_couple": True},
            {"target_audience": "couple"},
            {"couple_email": couple["email"]},
        ],
    }


@router.post("/couple/portal/forms/submit", tags=["Couple Portal"])
async def submit_form(
    data: FormSubmissionRequest, couple: dict = Depends(require_couple_auth)
):
    """Couple submits a form shared by the planner."""

    # Block form submission for archived weddings
    if couple.get("wedding_archived"):
        raise HTTPException(
            status_code=403, detail="Form submission is disabled for archived weddings"
        )

    form_object_id = _parse_couple_form_id(data.form_id)

    # Verify form exists and is shared with couple.
    form = await mongo.db["forms"].find_one(
        _build_couple_shared_form_query(form_object_id, couple)
    )

    if not form:
        raise HTTPException(
            status_code=404, detail="Form not found or not shared with you"
        )

    # Check for existing submission
    existing = await mongo.db["form_submissions"].find_one(
        {"form_id": data.form_id, "submitted_by": couple["email"]}
    )

    submission_doc = {
        "form_id": data.form_id,
        "wedding_id": couple["wedding_id"],
        "submitted_by": couple["email"],
        "submitted_by_name": f"{couple.get('partner1_name', '')} & {couple.get('partner2_name', '')}".strip(
            " &"
        ),
        "submitted_by_type": "couple",
        "responses": data.responses,
        "submitted_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    if existing:
        await mongo.db["form_submissions"].update_one(
            {"_id": existing["_id"]},
            {
                "$set": {
                    "responses": data.responses,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        submission_id = str(existing["_id"])
    else:
        result = await mongo.db["form_submissions"].insert_one(submission_doc)
        submission_id = str(result.inserted_id)

    # Notify planner via planner_notification_service (SSE + push included)
    try:
        planner_email = await _resolve_couple_planner_email(couple)
        if planner_email:
            from app.services.planner_notification_service import (
                planner_notification_service,
            )

            couple_name = f"{couple.get('partner1_name', '')} & {couple.get('partner2_name', '')}".strip(
                " &"
            )
            await planner_notification_service.create_notification(
                planner_id=planner_email,
                notification_type="form_submission",
                title=f'{couple_name} submitted "{form.get("title", "a form")}"',
                message=f'Your couple has {"updated" if existing else "submitted"} the form "{form.get("title")}". Review their responses in your dashboard.',
                wedding_id=couple["wedding_id"],
                action_url=f"/admin/forms?wedding_id={couple['wedding_id']}",
            )
    except Exception as e:
        logger.error(f"Failed to notify planner of form submission: {e}")

    return {"message": "Form submitted successfully", "submission_id": submission_id}


@router.get("/couple/portal/forms/{form_id}", tags=["Couple Portal"])
async def get_form_details(form_id: str, couple: dict = Depends(require_couple_auth)):
    """Get a specific form with its fields for the couple to fill out."""
    form_object_id = _parse_couple_form_id(form_id)

    form = await mongo.db["forms"].find_one(
        _build_couple_shared_form_query(form_object_id, couple)
    )

    if not form:
        raise HTTPException(
            status_code=404, detail="Form not found or not shared with you"
        )

    # Get existing submission if any
    submission = await mongo.db["form_submissions"].find_one(
        {"form_id": form_id, "submitted_by": couple["email"]}
    )

    return {
        "form": {
            "id": str(form["_id"]),
            "title": form.get("title"),
            "description": form.get("description"),
            "fields": form.get("fields", []),
            "created_at": (
                form.get("created_at").isoformat() if form.get("created_at") else None
            ),
        },
        "existing_responses": submission.get("responses") if submission else None,
        "submitted_at": (
            submission.get("submitted_at").isoformat()
            if submission and submission.get("submitted_at")
            else None
        ),
        "read_only": bool(couple.get("wedding_archived")),
        "archived": bool(couple.get("wedding_archived")),
        "read_only_reason": (
            "This wedding has been archived. Forms are view-only."
            if couple.get("wedding_archived")
            else None
        ),
    }


# ============================================================================
# PLANNER UPDATES (Planner-side: create updates for couple)
# ============================================================================


class CreateUpdateRequest(BaseModel):
    """Planner creates an update for the couple."""

    wedding_id: str = Field(...)
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1, max_length=5000)
    type: str = Field(default="update", pattern="^(update|milestone|announcement)$")
    category: Optional[str] = Field(
        None, max_length=50
    )  # venue, catering, decor, timeline, budget, etc.
    is_milestone: bool = Field(default=False)
    attachments: List[dict] = Field(default_factory=list)


@router.post("/couple-portal/updates", tags=["Couple Portal"])
async def create_update(
    data: CreateUpdateRequest,
    current_user: "ExtendedAuthUser" = Depends(require_team_or_planner),
):
    """
    Planner creates an update for the couple's portal.
    Requires planner authentication + wedding access.
    """
    _enforce_manage_couple_portal(current_user)

    # Verify planner has access to this wedding
    if not await check_wedding_access(current_user, data.wedding_id):
        raise HTTPException(
            status_code=403, detail="You don't have access to this wedding"
        )

    # Get planner name
    planner_name = f"{(current_user.user_data or {}).get('first_name', '')} {(current_user.user_data or {}).get('last_name', '')}".strip()
    if not planner_name:
        planner_name = (current_user.user_data or {}).get(
            "company_name", current_user.email
        )

    update_doc = {
        "wedding_id": data.wedding_id,
        "title": data.title,
        "content": data.content,
        "type": data.type,
        "category": data.category,
        "is_milestone": data.is_milestone,
        "attachments": data.attachments,
        "created_by": current_user.email,
        "created_by_name": planner_name,
        "created_at": datetime.now(timezone.utc),
    }

    result = await mongo.db["couple_updates"].insert_one(update_doc)

    async def _push_update_to_couple() -> None:
        couple_doc = await mongo.db["couple_users"].find_one(
            {"wedding_id": data.wedding_id},
            {"email": 1, "wedding_archived": 1, "is_active": 1, "setup_completed": 1},
        )
        await _send_couple_push_notification(
            couple_doc,
            title=data.title,
            body=_preview_push_body(data.content),
            url="/couple/dashboard?section=inbox",
            tag="couple_update",
        )

    await best_effort(
        max_retries=3,
        initial_delay=0.5,
        backoff=2.0,
        op_name="couple_push_update",
    ).run(_push_update_to_couple)

    logger.info(
        f"Couple update created for wedding {data.wedding_id} by {current_user.email}"
    )

    return {
        "message": "Update created successfully",
        "update_id": str(result.inserted_id),
    }


# ============================================================================
# SPRINT 2: ORDER OF EVENTS CRUD (Planner-side)
# ============================================================================
# These endpoints modify wedding.events[event_index].order_of_events[]
# Uses read-modify-write on the wedding document since events is a nested array.


class AddOrderItemRequest(BaseModel):
    """Add a new item to the order of events for a specific ceremony."""

    wedding_id: str = Field(...)
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    time: Optional[str] = Field(None, max_length=20, description="e.g. '6:30 PM'")
    duration_minutes: Optional[int] = Field(None, ge=1, le=1440)


class UpdateOrderItemRequest(BaseModel):
    """Update an existing order-of-events item."""

    wedding_id: str = Field(...)
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    time: Optional[str] = Field(None, max_length=20)
    duration_minutes: Optional[int] = Field(None, ge=1, le=1440)


class ReorderItemsRequest(BaseModel):
    """Reorder items in the order of events."""

    wedding_id: str = Field(...)
    item_ids: List[str] = Field(..., description="Item IDs in desired display order")


class DeleteOrderItemRequest(BaseModel):
    """Delete an order-of-events item."""

    wedding_id: str = Field(...)


async def _get_wedding_for_planner(wedding_id: str, current_user: ExtendedAuthUser):
    """Helper: verify planner access and return the wedding document."""
    _enforce_manage_couple_portal(current_user)
    if not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(
            status_code=403, detail="You don't have access to this wedding"
        )
    wedding = await mongo.get_weddings_collection().find_one({"_id": wedding_id})
    if not wedding:
        raise HTTPException(status_code=404, detail="Wedding not found")
    return wedding


async def _save_wedding_events(
    wedding: dict, field_path: str, value, current_user_email: str
):
    """
    Helper: write back an events sub-field with optimistic concurrency check.
    Uses updated_at to detect concurrent modifications. If another write happened
    between our read and write, we reject with 409 Conflict.
    """
    result = await mongo.get_weddings_collection().update_one(
        {
            "_id": wedding["_id"],
            "updated_at": wedding.get("updated_at"),  # optimistic lock
        },
        {
            "$set": {
                field_path: value,
                "updated_by": current_user_email,
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )
    if result.matched_count == 0:
        raise HTTPException(
            status_code=409,
            detail="Wedding was modified by another user. Please refresh and try again.",
        )


def _get_event_by_index(wedding: dict, event_index: int):
    """Helper: get an event from the wedding's events array by index."""
    events = wedding.get("events", [])
    if event_index < 0 or event_index >= len(events):
        raise HTTPException(
            status_code=404, detail=f"Event at index {event_index} not found"
        )
    return events[event_index]


@router.post(
    "/couple-portal/events/{event_index}/order-of-events", tags=["Couple Portal"]
)
async def add_order_item(
    data: AddOrderItemRequest,
    event_index: int = Path(..., ge=0),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """
    Add a new item to the order of events for a specific ceremony.
    The item is appended at the end of the list.
    """
    wedding = await _get_wedding_for_planner(data.wedding_id, current_user)
    event = _get_event_by_index(wedding, event_index)

    order_of_events = event.get("order_of_events", [])
    new_item: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "title": data.title,
        "description": data.description,
        "time": data.time,
        "duration_minutes": data.duration_minutes,
        "order": len(order_of_events),
        "notes": [],
    }
    order_of_events.append(new_item)

    await _save_wedding_events(
        wedding,
        f"events.{event_index}.order_of_events",
        order_of_events,
        current_user.email,
    )

    logger.info(f"Order item added to event {event_index} of wedding {data.wedding_id}")

    return {"message": "Item added", "item": new_item}


@router.put(
    "/couple-portal/events/{event_index}/order-of-events/{item_id}",
    tags=["Couple Portal"],
)
async def update_order_item(
    data: UpdateOrderItemRequest,
    event_index: int = Path(..., ge=0),
    item_id: str = Path(...),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """Update an existing order-of-events item (title, description, time, duration)."""
    wedding = await _get_wedding_for_planner(data.wedding_id, current_user)
    event = _get_event_by_index(wedding, event_index)

    order_of_events = event.get("order_of_events", [])
    item = next((i for i in order_of_events if i.get("id") == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail=f"Order item {item_id} not found")

    # Apply updates (only non-None fields)
    if data.title is not None:
        item["title"] = data.title
    if data.description is not None:
        item["description"] = data.description
    if data.time is not None:
        item["time"] = data.time
    if data.duration_minutes is not None:
        item["duration_minutes"] = data.duration_minutes

    await _save_wedding_events(
        wedding,
        f"events.{event_index}.order_of_events",
        order_of_events,
        current_user.email,
    )

    return {"message": "Item updated", "item": item}


@router.put(
    "/couple-portal/events/{event_index}/order-of-events/reorder",
    tags=["Couple Portal"],
)
async def reorder_items(
    data: ReorderItemsRequest,
    event_index: int = Path(..., ge=0),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """Reorder items in the order of events. Accepts item IDs in desired display order."""
    wedding = await _get_wedding_for_planner(data.wedding_id, current_user)
    event = _get_event_by_index(wedding, event_index)

    order_of_events = event.get("order_of_events", [])
    items_by_id = {i["id"]: i for i in order_of_events}

    # Validate all IDs exist
    for iid in data.item_ids:
        if iid not in items_by_id:
            raise HTTPException(
                status_code=400, detail=f"Item {iid} not found in order of events"
            )

    # Rebuild list in new order, updating the order field
    reordered = []
    for idx, iid in enumerate(data.item_ids):
        item = items_by_id[iid]
        item["order"] = idx
        reordered.append(item)

    # Append any items not in the request (safety: don't lose items)
    seen_ids = set(data.item_ids)
    for item in order_of_events:
        if item["id"] not in seen_ids:
            item["order"] = len(reordered)
            reordered.append(item)

    await _save_wedding_events(
        wedding, f"events.{event_index}.order_of_events", reordered, current_user.email
    )

    return {"message": "Items reordered", "count": len(reordered)}


@router.delete(
    "/couple-portal/events/{event_index}/order-of-events/{item_id}",
    tags=["Couple Portal"],
)
async def delete_order_item(
    event_index: int = Path(..., ge=0),
    item_id: str = Path(...),
    wedding_id: str = Query(...),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """Delete an order-of-events item."""
    wedding = await _get_wedding_for_planner(wedding_id, current_user)
    event = _get_event_by_index(wedding, event_index)

    order_of_events = event.get("order_of_events", [])
    original_count = len(order_of_events)
    order_of_events = [i for i in order_of_events if i.get("id") != item_id]

    if len(order_of_events) == original_count:
        raise HTTPException(status_code=404, detail=f"Order item {item_id} not found")

    # Re-index order fields
    for idx, item in enumerate(order_of_events):
        item["order"] = idx

    await _save_wedding_events(
        wedding,
        f"events.{event_index}.order_of_events",
        order_of_events,
        current_user.email,
    )

    return {"message": "Item deleted"}


# ============================================================================
# SPRINT 2: COLLABORATIVE NOTES — Couple-side (add notes)
# ============================================================================


class AddNoteRequest(BaseModel):
    """Couple adds a note to an event or order-of-events item."""

    text: str = Field(..., min_length=1, max_length=2000)


@router.post("/couple/portal/events/{event_index}/notes", tags=["Couple Portal"])
async def add_event_note(
    data: AddNoteRequest,
    event_index: int = Path(..., ge=0),
    couple: dict = Depends(require_couple_auth),
):
    """Couple adds a general note to an event (e.g. 'Keep reception under 3 hours')."""
    if couple.get("wedding_archived"):
        raise HTTPException(
            status_code=403, detail="Notes are disabled for archived weddings"
        )

    wedding = await mongo.get_weddings_collection().find_one(
        {"_id": couple["wedding_id"]}
    )
    if not wedding:
        raise HTTPException(status_code=404, detail="Wedding not found")

    event = _get_event_by_index(wedding, event_index)
    couple_name = (
        f"{couple.get('partner1_name', '')} & {couple.get('partner2_name', '')}".strip(
            " &"
        )
    )

    new_note = {
        "id": str(uuid.uuid4()),
        "author_role": "couple",
        "author_name": couple_name or couple["email"],
        "text": data.text,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    event_notes = event.get("event_notes", [])
    event_notes.append(new_note)

    await mongo.get_weddings_collection().update_one(
        {"_id": wedding["_id"]},
        {"$set": {f"events.{event_index}.event_notes": event_notes}},
    )

    # Notify planner
    await _notify_planner_of_note(
        couple, wedding, f"New note on {event.get('type', 'event')}", data.text
    )

    return {"message": "Note added", "note": new_note}


@router.post(
    "/couple/portal/events/{event_index}/order-of-events/{item_id}/notes",
    tags=["Couple Portal"],
)
async def add_item_note(
    data: AddNoteRequest,
    event_index: int = Path(..., ge=0),
    item_id: str = Path(...),
    couple: dict = Depends(require_couple_auth),
):
    """Couple adds a note to a specific order-of-events item (e.g. 'Use Ed Sheeran for first dance')."""
    if couple.get("wedding_archived"):
        raise HTTPException(
            status_code=403, detail="Notes are disabled for archived weddings"
        )

    wedding = await mongo.get_weddings_collection().find_one(
        {"_id": couple["wedding_id"]}
    )
    if not wedding:
        raise HTTPException(status_code=404, detail="Wedding not found")

    event = _get_event_by_index(wedding, event_index)
    order_of_events = event.get("order_of_events", [])
    item = next((i for i in order_of_events if i.get("id") == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail=f"Order item {item_id} not found")

    couple_name = (
        f"{couple.get('partner1_name', '')} & {couple.get('partner2_name', '')}".strip(
            " &"
        )
    )

    new_note = {
        "id": str(uuid.uuid4()),
        "author_role": "couple",
        "author_name": couple_name or couple["email"],
        "text": data.text,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    notes = item.get("notes", [])
    notes.append(new_note)
    item["notes"] = notes

    await mongo.get_weddings_collection().update_one(
        {"_id": wedding["_id"]},
        {"$set": {f"events.{event_index}.order_of_events": order_of_events}},
    )

    # Notify planner
    await _notify_planner_of_note(
        couple, wedding, f'Note on "{item.get("title", "item")}"', data.text
    )

    return {"message": "Note added", "note": new_note}


async def _notify_planner_of_note(couple: dict, wedding: dict, title: str, text: str):
    """Send a planner notification when the couple leaves a note. Uses planner_notification_service for SSE + push."""
    try:
        planner_email = await _resolve_couple_planner_email(couple, wedding)
        if not planner_email:
            return
        from app.services.planner_notification_service import (
            planner_notification_service,
        )

        couple_name = f"{couple.get('partner1_name', '')} & {couple.get('partner2_name', '')}".strip(
            " &"
        )
        preview = text[:100] + ("..." if len(text) > 100 else "")
        await planner_notification_service.create_notification(
            planner_id=planner_email,
            notification_type="couple_note",
            title=f"{couple_name}: {title}",
            message=preview,
            wedding_id=couple.get("wedding_id"),
            action_url=f"/admin/communications/inbox?wedding_id={couple.get('wedding_id')}&conversation=couple",
        )
    except Exception as e:
        logger.error(f"Failed to notify planner of couple note: {e}")


# ============================================================================
# SPRINT 2: NOTE STATUS MANAGEMENT (Planner-side)
# ============================================================================


class UpdateNoteStatusRequest(BaseModel):
    """Planner updates a note's status."""

    wedding_id: str = Field(...)
    status: str = Field(..., pattern="^(pending|seen|addressed)$")


@router.patch(
    "/couple-portal/events/{event_index}/notes/{note_id}", tags=["Couple Portal"]
)
async def update_event_note_status(
    data: UpdateNoteStatusRequest,
    event_index: int = Path(..., ge=0),
    note_id: str = Path(...),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """Planner marks an event-level note as seen or addressed."""
    wedding = await _get_wedding_for_planner(data.wedding_id, current_user)
    event = _get_event_by_index(wedding, event_index)

    event_notes = event.get("event_notes", [])
    note = next((n for n in event_notes if n.get("id") == note_id), None)
    if not note:
        raise HTTPException(status_code=404, detail=f"Note {note_id} not found")

    note["status"] = data.status

    await _save_wedding_events(
        wedding, f"events.{event_index}.event_notes", event_notes, current_user.email
    )

    return {"message": f"Note marked as {data.status}"}


@router.patch(
    "/couple-portal/events/{event_index}/order-of-events/{item_id}/notes/{note_id}",
    tags=["Couple Portal"],
)
async def update_item_note_status(
    data: UpdateNoteStatusRequest,
    event_index: int = Path(..., ge=0),
    item_id: str = Path(...),
    note_id: str = Path(...),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """Planner marks an order-of-events item note as seen or addressed."""
    wedding = await _get_wedding_for_planner(data.wedding_id, current_user)
    event = _get_event_by_index(wedding, event_index)

    order_of_events = event.get("order_of_events", [])
    item = next((i for i in order_of_events if i.get("id") == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail=f"Order item {item_id} not found")

    notes = item.get("notes", [])
    note = next((n for n in notes if n.get("id") == note_id), None)
    if not note:
        raise HTTPException(status_code=404, detail=f"Note {note_id} not found")

    note["status"] = data.status

    await _save_wedding_events(
        wedding,
        f"events.{event_index}.order_of_events",
        order_of_events,
        current_user.email,
    )

    return {"message": f"Note marked as {data.status}"}


# ============================================================================
# SPRINT 2: CONTRACT REVIEW (Couple-side)
# Reuses _get_contract_info from CouplePortalService — no duplication.
# ============================================================================


@router.get("/couple/portal/contracts", tags=["Couple Portal"])
async def get_contract_details(couple: dict = Depends(require_couple_auth)):
    """
    Get detailed contract information for the couple.
    Reuses couple_portal_service.get_contract_for_couple() — no direct DB access.
    """
    wedding_id = couple.get("wedding_id")
    if not wedding_id:
        raise HTTPException(status_code=404, detail="No wedding linked to this account")

    contract_detail = await couple_portal_service.get_contract_for_couple(
        wedding_id, couple["email"]
    )

    if not contract_detail:
        return {"contract": None, "message": "No contract found for this wedding"}

    return {"contract": contract_detail}


# ============================================================================
# SPRINT 2: COUPLE ACCESS MANAGEMENT (Planner-side)
# ============================================================================


@router.patch("/couple-portal/couples/{couple_id}/revoke", tags=["Couple Portal"])
async def revoke_couple_access(
    couple_id: str = Path(...),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """Revoke a couple's portal access."""
    _enforce_manage_couple_portal(current_user)

    couple = await mongo.db["couple_users"].find_one({"_id": ObjectId(couple_id)})
    if not couple:
        raise HTTPException(status_code=404, detail="Couple not found")

    if not await check_wedding_access(current_user, couple["wedding_id"]):
        raise HTTPException(
            status_code=403, detail="You don't have access to this wedding"
        )

    await mongo.db["couple_users"].update_one(
        {"_id": ObjectId(couple_id)},
        {"$set": couple_lifecycle_service.build_revoke_update(current_user.email)},
    )

    logger.info(f"Couple access revoked for {couple['email']} by {current_user.email}")

    return {"message": "Couple access revoked"}


@router.patch("/couple-portal/couples/{couple_id}/restore", tags=["Couple Portal"])
async def restore_couple_access(
    couple_id: str = Path(...),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """Restore a previously revoked couple's portal access."""
    _enforce_manage_couple_portal(current_user)

    couple = await mongo.db["couple_users"].find_one({"_id": ObjectId(couple_id)})
    if not couple:
        raise HTTPException(status_code=404, detail="Couple not found")

    if not await check_wedding_access(current_user, couple["wedding_id"]):
        raise HTTPException(
            status_code=403, detail="You don't have access to this wedding"
        )

    await mongo.db["couple_users"].update_one(
        {"_id": ObjectId(couple_id)},
        {"$set": couple_lifecycle_service.build_manual_restore_update(couple)},
    )

    return {"message": "Couple access restored"}


# ============================================================================
# SPRINT 3: COUPLE ↔ PLANNER MESSAGING
# ============================================================================
# Uses `couple_messages` collection. Messages are scoped to a wedding_id.
# Both couple and planner can send/receive. Read tracking per-participant.


class SendMessageRequest(BaseModel):
    """Send a message in the couple↔planner conversation."""

    content: str = Field(..., min_length=1, max_length=5000)


class PlannerSendMessageRequest(BaseModel):
    """Planner sends a message to a couple."""

    wedding_id: str = Field(...)
    content: str = Field(..., min_length=1, max_length=5000)


class PlannerMarkMessagesReadRequest(BaseModel):
    """Planner marks a wedding conversation as read."""

    wedding_id: str = Field(...)


def _normalize_query_id(value: str) -> str | ObjectId:
    """Normalize a wedding identifier for Mongo queries."""
    return normalize_wedding_query_id(value)


async def _get_message_broadcast_recipients(wedding_id: str) -> set[str]:
    """Collect planner/team recipients who should see couple-message updates."""
    recipients: set[str] = set()

    wedding = await mongo.get_weddings_collection().find_one(
        {"_id": _normalize_query_id(wedding_id)},
        {"assigned_planner_id": 1, "assigned_planner_email": 1},
    )
    owner_identity = await resolve_wedding_owner_identity(wedding)
    owner_email = owner_identity.get("planner_email")
    owner_id = owner_identity.get("planner_id")
    if owner_email:
        recipients.add(owner_email)

        team_query = build_team_owner_query(owner_id, owner_email)
        async for team_member in mongo.db["team_members"].find(
            {
                **team_query,
                "status": "active",
                "custom_permissions.message_couples": True,
            },
            {"email": 1, "wedding_access": 1, "assigned_wedding_ids": 1},
        ):
            access = team_member.get("wedding_access", "all")
            if access == "all" or wedding_id in (
                team_member.get("assigned_wedding_ids") or []
            ):
                email = team_member.get("email")
                if email:
                    recipients.add(email)

    return recipients


def _collect_email_targets(*values: object) -> list[str]:
    """Normalize optional email-like values into a concrete string list."""
    emails: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        email = value.strip()
        if email and email not in emails:
            emails.append(email)
    return emails


def _build_couple_push_principal(couple: Optional[dict]) -> Optional[str]:
    """Return the push principal for an active, setup-complete couple account."""
    if not couple:
        return None
    if couple.get("wedding_archived"):
        return None
    if couple.get("is_active") is not True or couple.get("setup_completed") is not True:
        return None

    try:
        return build_couple_principal_key(get_couple_record_id(couple))
    except ValueError:
        return None


async def _send_couple_push_notification(
    couple: Optional[dict],
    *,
    title: str,
    body: str,
    url: str,
    tag: str,
) -> None:
    """Send a Web Push notification to a couple subscription if configured."""
    principal = _build_couple_push_principal(couple)
    if not principal or not web_push_service.enabled:
        return

    await web_push_service.send_notification(
        user_id=principal,
        title=title,
        body=body,
        url=url,
        tag=tag,
    )


def _preview_push_body(content: str, max_length: int = 120) -> str:
    normalized = " ".join(content.split())
    if len(normalized) <= max_length:
        return normalized
    return f"{normalized[: max_length - 3]}..."


async def _broadcast_couple_message_change(
    wedding_id: str,
    action: str,
    record_id: Optional[str] = None,
    include_couple_id: Optional[str] = None,
    extra_planner_emails: Optional[List[str]] = None,
) -> None:
    """Broadcast couple-message updates to relevant planner/team/couple clients."""
    recipients = await _get_message_broadcast_recipients(wedding_id)
    if extra_planner_emails:
        recipients.update(email for email in extra_planner_emails if email)

    for email in recipients:
        await sse_manager.broadcast_data_change(
            email,
            resource="couple_message",
            action=action,
            wedding_id=wedding_id,
            record_id=record_id,
        )

    if include_couple_id:
        await sse_manager.broadcast_to_user(
            couple_sse_channel(include_couple_id),
            "data-change",
            {
                "resource": "couple_message",
                "action": action,
                "wedding_id": wedding_id,
                "record_id": record_id,
            },
        )


async def _get_accessible_couple_wedding_ids(
    current_user: ExtendedAuthUser,
    wedding_id: Optional[str] = None,
) -> list[str]:
    """Resolve wedding IDs the current user can access for couple conversations."""
    if wedding_id:
        if not await check_wedding_access(current_user, wedding_id):
            raise HTTPException(
                status_code=403, detail="You don't have access to this wedding"
            )
        return [wedding_id]

    if current_user.is_root_admin:
        weddings = (
            await mongo.get_weddings_collection()
            .find({}, {"_id": 1})
            .to_list(length=None)
        )
        return [str(wedding["_id"]) for wedding in weddings]

    if current_user.is_wedding_planner:
        return await list_wedding_ids_for_owner(
            planner_id=current_user.user_data.get("_id"),
            planner_email=current_user.email,
        )

    if current_user.is_team_member:
        return await list_wedding_ids_for_owner(
            planner_id=current_user.parent_planner_id,
            planner_email=current_user.team_owner_email,
            accessible_wedding_ids=get_accessible_wedding_ids(current_user),
        )

    return []


# --- Couple-side messaging ---


@router.post("/couple/portal/messages", tags=["Couple Portal - Messages"])
async def couple_send_message(
    data: SendMessageRequest, couple: dict = Depends(require_couple_auth)
):
    """Couple sends a message to their planner."""
    wedding_id = couple.get("wedding_id")
    if not wedding_id:
        raise HTTPException(status_code=404, detail="No wedding linked to this account")

    # Block messaging for archived weddings
    if couple.get("wedding_archived"):
        raise HTTPException(
            status_code=403, detail="Messaging is disabled for archived weddings"
        )

    # Verify wedding exists before inserting message
    wedding = await mongo.get_weddings_collection().find_one(
        {"_id": wedding_id}, {"_id": 1}
    )
    if not wedding:
        raise HTTPException(status_code=404, detail="Wedding not found")

    couple_display_name = get_couple_display_name(couple)

    message_doc = {
        "wedding_id": wedding_id,
        "sender_role": SENDER_ROLE_COUPLE,
        "sender_email": couple["email"],
        "sender_name": couple_display_name or couple["email"],
        "content": data.content,
        "read_by_couple": True,
        "read_by_planner": False,
        "created_at": datetime.now(timezone.utc),
    }

    result = await mongo.db["couple_messages"].insert_one(message_doc)

    # Notify planner via planner_notification_service (SSE + push included).
    # This is a best-effort side-effect: the message has already persisted, so
    # the entire block — including the planner-email lookup — runs under
    # best_effort. Any failure retries with backoff and is then swallowed so
    # the caller's send always returns 200 once the message is stored. See
    # app/utils/best_effort_task.py.
    async def _notify_planner_of_couple_message() -> None:
        planner_email = await _resolve_couple_planner_email(couple)
        if not planner_email:
            return
        from app.services.planner_notification_service import (
            planner_notification_service,
        )

        preview = data.content[:100] + ("..." if len(data.content) > 100 else "")
        await planner_notification_service.create_notification(
            planner_id=planner_email,
            notification_type="couple_message",
            title=f"New message from {couple_display_name or couple['email']}",
            message=preview,
            wedding_id=wedding_id,
            action_url=f"/admin/communications/inbox?wedding_id={wedding_id}&conversation=couple",
        )

    await best_effort(
        max_retries=3,
        initial_delay=0.5,
        backoff=2.0,
        op_name="planner_notification_couple_message",
    ).run(_notify_planner_of_couple_message)

    try:
        planner_targets = _collect_email_targets(
            await _resolve_couple_planner_email(couple)
        )
        await _broadcast_couple_message_change(
            wedding_id,
            action="created",
            record_id=str(result.inserted_id),
            include_couple_id=get_couple_record_id(couple),
            extra_planner_emails=planner_targets or None,
        )
    except Exception as exc:
        logger.warning(f"Failed to broadcast couple message change: {exc}")

    return {
        "message": "Message sent",
        "message_id": str(result.inserted_id),
    }


@router.get("/couple/portal/messages", tags=["Couple Portal - Messages"])
async def couple_get_messages(
    couple: dict = Depends(require_couple_auth),
    limit: int = Query(50, ge=1, le=200),
    before: Optional[str] = Query(
        None, description="Cursor: message ID to load older messages before"
    ),
):
    """Get message history for the couple's wedding conversation."""
    wedding_id = couple.get("wedding_id")
    if not wedding_id:
        raise HTTPException(status_code=404, detail="No wedding linked to this account")

    query: dict = {"wedding_id": wedding_id}
    if before:
        try:
            query["_id"] = {"$lt": ObjectId(before)}
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid cursor")

    messages = []
    async for msg in (
        mongo.db["couple_messages"].find(query).sort("_id", -1).limit(limit)
    ):
        messages.append(
            {
                "id": str(msg["_id"]),
                "sender_role": msg.get("sender_role"),
                # SECURITY: do NOT return sender_email on the couple-facing GET.
                # Planner/team login emails are internal contact info and the
                # couple dashboard does not need identity-first authorship —
                # `isSelfAuthored` in app/types/messaging.ts falls back to
                # sender_role comparison, which is a complete disambiguator
                # for the couple viewer (role is either 'couple' or 'planner').
                # The planner-facing GET at /couple-portal/messages still
                # projects sender_email — planners need it to distinguish
                # between multiple team members on a shared thread.
                "sender_name": msg.get("sender_name"),
                "content": msg.get("content"),
                "read_by_couple": msg.get("read_by_couple", False),
                "read_by_planner": msg.get("read_by_planner", False),
                "created_at": (
                    msg.get("created_at").isoformat() if msg.get("created_at") else None
                ),
            }
        )

    # `messages` is newest-first here, so the last element is the oldest one
    # in the page — that's the cursor clients should pass as `before` to load
    # the next (older) page. `null` signals no more history.
    next_cursor = messages[-1]["id"] if len(messages) == limit else None

    # Return in chronological order (oldest first)
    messages.reverse()

    return {
        "messages": messages,
        "count": len(messages),
        "next_cursor": next_cursor,
    }


@router.post("/couple/portal/messages/read", tags=["Couple Portal - Messages"])
async def couple_mark_messages_read(couple: dict = Depends(require_couple_auth)):
    """Mark planner messages as read for the authenticated couple."""
    wedding_id = couple.get("wedding_id")
    if not wedding_id:
        raise HTTPException(status_code=404, detail="No wedding linked to this account")

    result = await mongo.db["couple_messages"].update_many(
        {
            "wedding_id": wedding_id,
            "sender_role": SENDER_ROLE_PLANNER,
            "read_by_couple": False,
        },
        {"$set": {"read_by_couple": True}},
    )

    if result.modified_count > 0:
        try:
            await _broadcast_couple_message_change(
                wedding_id,
                action="updated",
                include_couple_id=get_couple_record_id(couple),
            )
        except Exception as exc:
            logger.warning(f"Failed to broadcast couple read-state change: {exc}")

    return {"marked_read": result.modified_count}


@router.get("/couple/portal/messages/unread-count", tags=["Couple Portal - Messages"])
async def couple_unread_count(couple: dict = Depends(require_couple_auth)):
    """Get count of unread messages for the couple."""
    wedding_id = couple.get("wedding_id")
    if not wedding_id:
        return {"unread_count": 0}

    count = await mongo.db["couple_messages"].count_documents(
        {
            "wedding_id": wedding_id,
            "sender_role": SENDER_ROLE_PLANNER,
            "read_by_couple": False,
        }
    )
    return {"unread_count": count}


# --- Planner-side messaging ---


@router.post("/couple-portal/messages", tags=["Couple Portal - Messages"])
async def planner_send_message(
    data: PlannerSendMessageRequest,
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """Planner sends a message to the couple for a specific wedding."""
    _enforce_message_couples(current_user)

    if not await check_wedding_access(current_user, data.wedding_id):
        raise HTTPException(
            status_code=403, detail="You don't have access to this wedding"
        )

    couple_doc = await mongo.db["couple_users"].find_one(
        {"wedding_id": data.wedding_id},
        {"email": 1, "wedding_archived": 1, "is_active": 1, "setup_completed": 1},
    )
    if couple_doc and couple_doc.get("wedding_archived"):
        raise HTTPException(
            status_code=403, detail="Messaging is disabled for archived weddings"
        )

    planner_name = f"{(current_user.user_data or {}).get('first_name', '')} {(current_user.user_data or {}).get('last_name', '')}".strip()
    if not planner_name:
        planner_name = (current_user.user_data or {}).get(
            "company_name", current_user.email
        )

    message_doc = {
        "wedding_id": data.wedding_id,
        "sender_role": SENDER_ROLE_PLANNER,
        "sender_email": current_user.email,
        "sender_name": planner_name,
        "content": data.content,
        "read_by_couple": False,
        "read_by_planner": True,
        "created_at": datetime.now(timezone.utc),
    }

    result = await mongo.db["couple_messages"].insert_one(message_doc)

    planner_targets = _collect_email_targets(
        current_user.email,
        current_user.team_owner_email if current_user.is_team_member else None,
    )

    await best_effort(
        max_retries=3,
        initial_delay=0.5,
        backoff=2.0,
        op_name="couple_push_planner_message",
    ).run(
        lambda: _send_couple_push_notification(
            couple_doc,
            title=f"New message from {planner_name}",
            body=_preview_push_body(data.content),
            url="/couple/dashboard?section=inbox",
            tag="couple_message",
        )
    )

    try:
        await _broadcast_couple_message_change(
            data.wedding_id,
            action="created",
            record_id=str(result.inserted_id),
            include_couple_id=(
                to_str_id(couple_doc)
                if couple_doc
                and couple_doc.get("is_active")
                and couple_doc.get("setup_completed")
                else None
            ),
            extra_planner_emails=planner_targets,
        )
    except Exception as exc:
        logger.warning(f"Failed to broadcast planner message change: {exc}")

    logger.info(
        f"Planner {current_user.email} sent message for wedding {data.wedding_id}"
    )

    return {
        "message": "Message sent",
        "message_id": str(result.inserted_id),
    }


@router.get("/couple-portal/messages", tags=["Couple Portal - Messages"])
async def planner_get_messages(
    wedding_id: str = Query(...),
    limit: int = Query(50, ge=1, le=200),
    before: Optional[str] = Query(
        None, description="Cursor: message ID to load older messages before"
    ),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """Planner gets message history for a specific wedding's couple conversation."""
    _enforce_message_couples(current_user)

    if not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(
            status_code=403, detail="You don't have access to this wedding"
        )

    query: dict = {"wedding_id": wedding_id}
    if before:
        try:
            query["_id"] = {"$lt": ObjectId(before)}
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid cursor")

    messages = []
    async for msg in (
        mongo.db["couple_messages"].find(query).sort("_id", -1).limit(limit)
    ):
        messages.append(
            {
                "id": str(msg["_id"]),
                "sender_role": msg.get("sender_role"),
                "sender_email": msg.get("sender_email"),
                "sender_name": msg.get("sender_name"),
                "content": msg.get("content"),
                "read_by_couple": msg.get("read_by_couple", False),
                "created_at": (
                    msg.get("created_at").isoformat() if msg.get("created_at") else None
                ),
            }
        )

    # `messages` is newest-first here; the last element is the oldest in the
    # page and becomes the cursor for the next (older) page. `null` means
    # no more history.
    next_cursor = messages[-1]["id"] if len(messages) == limit else None

    messages.reverse()

    return {
        "messages": messages,
        "count": len(messages),
        "next_cursor": next_cursor,
    }


@router.post("/couple-portal/messages/read", tags=["Couple Portal - Messages"])
async def planner_mark_messages_read(
    data: PlannerMarkMessagesReadRequest,
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """Mark couple messages as read for a planner-accessible wedding conversation."""
    _enforce_message_couples(current_user)

    if not await check_wedding_access(current_user, data.wedding_id):
        raise HTTPException(
            status_code=403, detail="You don't have access to this wedding"
        )

    result = await mongo.db["couple_messages"].update_many(
        {
            "wedding_id": data.wedding_id,
            "sender_role": SENDER_ROLE_COUPLE,
            "read_by_planner": False,
        },
        {"$set": {"read_by_planner": True}},
    )

    planner_targets = _collect_email_targets(
        current_user.email,
        current_user.team_owner_email if current_user.is_team_member else None,
    )

    if result.modified_count > 0:
        try:
            await _broadcast_couple_message_change(
                data.wedding_id,
                action="updated",
                extra_planner_emails=planner_targets,
            )
        except Exception as exc:
            logger.warning(f"Failed to broadcast planner read-state change: {exc}")

    return {"marked_read": result.modified_count}


@router.get("/couple-portal/messages/unread-count", tags=["Couple Portal - Messages"])
async def planner_unread_count(
    wedding_id: str = Query(...),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """Get count of unread messages from the couple for a specific wedding."""
    _enforce_message_couples(current_user)

    if not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(
            status_code=403, detail="You don't have access to this wedding"
        )

    count = await mongo.db["couple_messages"].count_documents(
        {
            "wedding_id": wedding_id,
            "sender_role": SENDER_ROLE_COUPLE,
            "read_by_planner": False,
        }
    )
    return {"unread_count": count}


@router.get("/couple-portal/conversations", tags=["Couple Portal - Messages"])
async def planner_list_conversations(
    wedding_id: Optional[str] = Query(None),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """List couple conversation summaries for weddings the current user can access."""
    _enforce_message_couples(current_user)

    accessible_wedding_ids = await _get_accessible_couple_wedding_ids(
        current_user, wedding_id=wedding_id
    )
    if not accessible_wedding_ids:
        return {"conversations": [], "count": 0}

    couples = (
        await mongo.db["couple_users"]
        .find(
            {
                "wedding_id": {"$in": accessible_wedding_ids},
                "is_active": True,
                "setup_completed": True,
                "wedding_archived": {"$ne": True},
            },
            {
                "email": 1,
                "partner1_name": 1,
                "partner2_name": 1,
                "wedding_id": 1,
                "last_login": 1,
                "created_at": 1,
            },
        )
        .to_list(length=None)
    )

    if not couples:
        return {"conversations": [], "count": 0}

    summaries = (
        await mongo.db["couple_messages"]
        .aggregate(
            [
                {"$match": {"wedding_id": {"$in": accessible_wedding_ids}}},
                {"$sort": {"created_at": -1, "_id": -1}},
                {
                    "$group": {
                        "_id": "$wedding_id",
                        "last_message_at": {"$first": "$created_at"},
                        "last_message_preview": {"$first": "$content"},
                        "last_sender_role": {"$first": "$sender_role"},
                        # `last_sender_email` is what makes the planner
                        # conversation-list "You:" preview identity-first —
                        # see `isSelfAuthored` in `app/types/messaging.ts`.
                        # Legacy rows written before identity stamping do not
                        # carry sender_email; the aggregation will surface
                        # null for those and the frontend falls back to role.
                        "last_sender_email": {"$first": "$sender_email"},
                        "unread_count": {
                            "$sum": {
                                "$cond": [
                                    {
                                        "$and": [
                                            {
                                                "$eq": [
                                                    "$sender_role",
                                                    SENDER_ROLE_COUPLE,
                                                ]
                                            },
                                            {"$eq": ["$read_by_planner", False]},
                                        ]
                                    },
                                    1,
                                    0,
                                ]
                            }
                        },
                    }
                },
            ]
        )
        .to_list(length=None)
    )

    summary_map = {summary["_id"]: summary for summary in summaries}
    conversations = []

    for couple in couples:
        summary = summary_map.get(couple["wedding_id"], {})
        conversations.append(
            {
                "id": (
                    str(couple["_id"])
                    if isinstance(couple["_id"], ObjectId)
                    else couple["_id"]
                ),
                "email": couple["email"],
                "partner1_name": couple.get("partner1_name"),
                "partner2_name": couple.get("partner2_name"),
                "wedding_id": couple.get("wedding_id"),
                "last_login": (
                    couple.get("last_login").isoformat()
                    if couple.get("last_login")
                    else None
                ),
                "created_at": (
                    couple.get("created_at").isoformat()
                    if couple.get("created_at")
                    else None
                ),
                "last_message_at": (
                    summary.get("last_message_at").isoformat()
                    if summary.get("last_message_at")
                    else None
                ),
                "last_message_preview": summary.get("last_message_preview"),
                "last_sender_role": summary.get("last_sender_role"),
                "last_sender_email": summary.get("last_sender_email"),
                "unread_count": summary.get("unread_count", 0),
            }
        )

    conversations.sort(
        key=lambda convo: (
            convo.get("last_message_at")
            or convo.get("last_login")
            or convo.get("created_at")
            or ""
        ),
        reverse=True,
    )

    return {"conversations": conversations, "count": len(conversations)}


# ============================================================================
# SPRINT 3: PLANNER NOTIFICATION CENTER
# ============================================================================
# NOTE: Couple-portal notifications (couple_message, couple_note, form_submission)
# are created via planner_notification_service and exposed through the EXISTING
# /planner/activity-notifications endpoints (see planner_notifications.py).
# The frontend filters by notification_type to show couple-related notifications.
# No duplicate notification endpoints needed here.


# ============================================================================
# SPRINT 3: EMAIL DIGEST (planner-triggered)
# ============================================================================


@router.post("/couple-portal/send-digest", tags=["Couple Portal - Digest"])
async def trigger_couple_digest(
    wedding_id: str = Query(...),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """
    Planner triggers a digest email to the couple summarizing unread messages,
    new updates, upcoming payments, and pending forms.
    Reuses couple_portal_service for data aggregation and email_service for sending.
    """
    _enforce_message_couples(current_user)

    if not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(
            status_code=403, detail="You don't have access to this wedding"
        )

    # Find the couple for this wedding
    couple_doc = await mongo.db["couple_users"].find_one(
        {
            "wedding_id": wedding_id,
            "is_active": True,
            "setup_completed": True,
        }
    )

    if not couple_doc:
        raise HTTPException(
            status_code=404, detail="No active couple account found for this wedding"
        )

    # Generate digest (look back 7 days by default)
    from datetime import timedelta

    since = datetime.now(timezone.utc) - timedelta(days=7)
    digest = await couple_portal_service.generate_couple_digest(
        couple_email=couple_doc["email"],
        wedding_id=wedding_id,
        since=since,
    )

    if not digest:
        return {
            "message": "No new activity to report — digest not sent.",
            "sent": False,
        }

    sent = await couple_portal_service.send_couple_digest_email(couple_doc, digest)

    return {
        "message": (
            "Digest email sent successfully" if sent else "Failed to send digest email"
        ),
        "sent": sent,
        "digest_summary": {
            "unread_messages": digest["unread_messages"],
            "new_updates": digest["new_updates_count"],
            "upcoming_payments": len(digest["upcoming_payments"]),
            "pending_forms": digest["pending_forms_count"],
        },
    }


# ============================================================================
# SPRINT 4: WEDDING ARCHIVAL
# ============================================================================
# Uses existing archive_wedding_data() from CouplePortalService.
# Planner triggers → service snapshots all data → couple sees archived view.


@router.post("/couple-portal/archive", tags=["Couple Portal - Archival"])
async def archive_wedding(
    wedding_id: str = Query(...),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """
    Planner triggers wedding archival. This snapshots all wedding data
    (guests, RSVPs, budget, contracts, forms, updates, messages) into
    the archived_weddings collection and marks couple accounts as archived.
    Archived couples can still log in but see a read-only archived view.
    """
    _enforce_manage_couple_portal(current_user)

    if not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(
            status_code=403, detail="You don't have access to this wedding"
        )

    # Check wedding exists
    wedding = await mongo.get_weddings_collection().find_one({"_id": wedding_id})
    if not wedding:
        raise HTTPException(status_code=404, detail="Wedding not found")

    # Check not already archived
    existing_archive = await mongo.db["archived_weddings"].find_one(
        {"original_wedding_id": wedding_id}
    )
    if existing_archive:
        raise HTTPException(
            status_code=409, detail="This wedding has already been archived"
        )

    try:
        result = await couple_portal_service.archive_wedding_data(wedding_id)
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        # Also archive couple messages into the snapshot
        messages = []
        async for msg in mongo.db["couple_messages"].find({"wedding_id": wedding_id}):
            msg["_id"] = str(msg["_id"])
            messages.append(msg)

        if messages:
            await mongo.db["archived_weddings"].update_one(
                {"original_wedding_id": wedding_id},
                {"$set": {"messages": messages, "messages_archived": len(messages)}},
            )

        logger.info(f"Wedding {wedding_id} archived by {current_user.email}")

        return {
            "message": "Wedding archived successfully",
            "archive_id": result["archive_id"],
            "summary": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to archive wedding {wedding_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to archive wedding")


@router.delete("/couple-portal/archive", tags=["Couple Portal - Archival"])
async def unarchive_wedding(
    wedding_id: str = Query(...),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """
    Planner reverses an archival — removes the archive snapshot and
    restores the archived wedding view for eligible couple accounts.
    """
    _enforce_manage_couple_portal(current_user)

    if not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(
            status_code=403, detail="You don't have access to this wedding"
        )

    # Remove archive
    result = await mongo.db["archived_weddings"].delete_one(
        {"original_wedding_id": wedding_id}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="No archive found for this wedding")

    # Restore couple accounts
    await mongo.db["couple_users"].update_many(
        {"wedding_id": wedding_id},
        {"$set": {"wedding_archived": False}, "$unset": {"archived_at": True}},
    )

    logger.info(f"Wedding {wedding_id} unarchived by {current_user.email}")

    return {
        "message": "Wedding unarchived — eligible couple portal access is restored based on the current account lifecycle state"
    }


# ============================================================================
# SPRINT 4: CUSTOM FORM TEMPLATES
# ============================================================================
# Planners can save any form as a reusable template and create forms from
# their saved templates. Built-in templates (forms.py) are separate.


class SaveAsTemplateRequest(BaseModel):
    """Save an existing form as a reusable template."""

    form_id: str = Field(...)
    template_name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    category: Optional[str] = Field(None, max_length=50)


class CreateFromTemplateRequest(BaseModel):
    """Create a new form from a saved custom template."""

    template_id: str = Field(...)
    form_name: str = Field(..., min_length=1, max_length=200)
    wedding_id: str = Field(...)


@router.post("/couple-portal/form-templates", tags=["Couple Portal - Form Templates"])
async def save_form_as_template(
    data: SaveAsTemplateRequest,
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """
    Save an existing form as a reusable custom template.
    Copies the form's fields and settings (not responses or wedding-specific data).
    """
    _enforce_manage_couple_portal(current_user)

    try:
        ObjectId(data.form_id)
    except (InvalidId, Exception):
        raise HTTPException(status_code=400, detail="Invalid form ID format")

    # Get source form
    source_form = await mongo.db["forms"].find_one({"_id": ObjectId(data.form_id)})
    if not source_form:
        raise HTTPException(status_code=404, detail="Source form not found")

    # Check planner owns this form
    if source_form.get("created_by") != current_user.email:
        if not await check_wedding_access(
            current_user, source_form.get("wedding_id", "")
        ):
            raise HTTPException(
                status_code=403, detail="You don't have access to this form"
            )

    template_scope = await _resolve_custom_template_owner_scope(current_user)
    template_doc = {
        "planner_email": template_scope["owner_email"],
        "created_by_email": current_user.email,
        "name": data.template_name,
        "description": data.description,
        "category": data.category,
        "source_form_id": data.form_id,
        "fields": source_form.get("fields", []),
        "settings": {
            k: v
            for k, v in source_form.get("settings", {}).items()
            if k not in ("title", "wedding_id")  # Strip wedding-specific settings
        },
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    result = await mongo.db["custom_form_templates"].insert_one(template_doc)

    logger.info(f"Form template '{data.template_name}' saved by {current_user.email}")

    return {
        "message": "Form saved as template",
        "template_id": str(result.inserted_id),
    }


@router.get("/couple-portal/form-templates", tags=["Couple Portal - Form Templates"])
async def list_custom_templates(
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """List all custom form templates saved by this planner."""
    _enforce_manage_couple_portal(current_user)
    template_scope = await _resolve_custom_template_owner_scope(current_user)
    templates = []
    async for tpl in (
        mongo.db["custom_form_templates"]
        .find({"planner_email": template_scope["owner_email"]})
        .sort("created_at", -1)
    ):
        templates.append(
            {
                "id": str(tpl["_id"]),
                "name": tpl.get("name"),
                "description": tpl.get("description"),
                "category": tpl.get("category"),
                "field_count": len(tpl.get("fields", [])),
                "created_at": (
                    tpl.get("created_at").isoformat() if tpl.get("created_at") else None
                ),
            }
        )

    return {"templates": templates}


@router.post(
    "/couple-portal/form-templates/create-form", tags=["Couple Portal - Form Templates"]
)
async def create_form_from_custom_template(
    data: CreateFromTemplateRequest,
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """Create a new form from a saved custom template and assign it to a wedding."""
    _enforce_manage_couple_portal(current_user)

    try:
        ObjectId(data.template_id)
        ObjectId(data.wedding_id)
    except (InvalidId, Exception):
        raise HTTPException(status_code=400, detail="Invalid ID format")

    if not await check_wedding_access(current_user, data.wedding_id):
        raise HTTPException(
            status_code=403, detail="You don't have access to this wedding"
        )

    template_scope = await _resolve_custom_template_owner_scope(current_user)
    # Get template
    template = await mongo.db["custom_form_templates"].find_one(
        {
            "_id": ObjectId(data.template_id),
            "planner_email": template_scope["owner_email"],
        }
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Build the form from template fields
    form_doc = {
        "name": data.form_name,
        "settings": {
            **template.get("settings", {}),
            "title": data.form_name,
        },
        "fields": copy.deepcopy(template.get("fields", [])),
        "created_by": current_user.email,
        "wedding_id": data.wedding_id,
        "template_type": str(template["_id"]),
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    result = await mongo.db["forms"].insert_one(form_doc)

    logger.info(
        f"Form '{data.form_name}' created from template by {current_user.email}"
    )

    return {
        "message": "Form created from template",
        "form_id": str(result.inserted_id),
    }


@router.delete(
    "/couple-portal/form-templates/{template_id}",
    tags=["Couple Portal - Form Templates"],
)
async def delete_custom_template(
    template_id: str = Path(...),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """Delete a saved custom form template."""
    _enforce_manage_couple_portal(current_user)
    try:
        ObjectId(template_id)
    except (InvalidId, Exception):
        raise HTTPException(status_code=400, detail="Invalid template ID format")

    template_scope = await _resolve_custom_template_owner_scope(current_user)
    result = await mongo.db["custom_form_templates"].delete_one(
        {
            "_id": ObjectId(template_id),
            "planner_email": template_scope["owner_email"],
        }
    )

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Template not found")

    return {"message": "Template deleted"}


# ============================================================================
# P1-6: PLANNER NOTE REPLIES (Threaded inline conversation)
# Planners can reply to couple notes, creating threaded conversations
# ============================================================================


class ReplyToNoteRequest(BaseModel):
    """Planner replies to a couple's note."""

    wedding_id: str = Field(...)
    text: str = Field(..., min_length=1, max_length=2000)


@router.post(
    "/couple-portal/events/{event_index}/notes/{note_id}/reply",
    tags=["Couple Portal - Note Replies"],
)
async def reply_to_event_note(
    data: ReplyToNoteRequest,
    event_index: int = Path(..., ge=0),
    note_id: str = Path(...),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """Planner replies to an event-level note from the couple. Creates a new note with reply_to set."""
    wedding = await _get_wedding_for_planner(data.wedding_id, current_user)

    # Block replies on archived weddings
    couple = await mongo.db["couple_users"].find_one(
        {"wedding_id": data.wedding_id, "wedding_archived": True}
    )
    if couple:
        raise HTTPException(
            status_code=403, detail="Notes are disabled for archived weddings"
        )

    event = _get_event_by_index(wedding, event_index)

    event_notes = event.get("event_notes", [])
    parent_note = next((n for n in event_notes if n.get("id") == note_id), None)
    if not parent_note:
        raise HTTPException(status_code=404, detail=f"Note {note_id} not found")

    reply_note = {
        "id": str(uuid.uuid4()),
        "author_role": "planner",
        "author_name": current_user.email,
        "text": data.text,
        "status": "addressed",
        "reply_to": note_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    event_notes.append(reply_note)

    # Also mark parent note as addressed if still pending/seen
    if parent_note.get("status") in ("pending", "seen"):
        parent_note["status"] = "addressed"

    await _save_wedding_events(
        wedding, f"events.{event_index}.event_notes", event_notes, current_user.email
    )

    logger.info(f"Planner {current_user.email} replied to event note {note_id}")
    return {"message": "Reply added", "note": reply_note}


@router.post(
    "/couple-portal/events/{event_index}/order-of-events/{item_id}/notes/{note_id}/reply",
    tags=["Couple Portal - Note Replies"],
)
async def reply_to_item_note(
    data: ReplyToNoteRequest,
    event_index: int = Path(..., ge=0),
    item_id: str = Path(...),
    note_id: str = Path(...),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """Planner replies to an order-of-events item note from the couple."""
    wedding = await _get_wedding_for_planner(data.wedding_id, current_user)

    # Block replies on archived weddings
    couple = await mongo.db["couple_users"].find_one(
        {"wedding_id": data.wedding_id, "wedding_archived": True}
    )
    if couple:
        raise HTTPException(
            status_code=403, detail="Notes are disabled for archived weddings"
        )

    event = _get_event_by_index(wedding, event_index)

    order_of_events = event.get("order_of_events", [])
    item = next((i for i in order_of_events if i.get("id") == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail=f"Order item {item_id} not found")

    notes = item.get("notes", [])
    parent_note = next((n for n in notes if n.get("id") == note_id), None)
    if not parent_note:
        raise HTTPException(status_code=404, detail=f"Note {note_id} not found")

    reply_note = {
        "id": str(uuid.uuid4()),
        "author_role": "planner",
        "author_name": current_user.email,
        "text": data.text,
        "status": "addressed",
        "reply_to": note_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    notes.append(reply_note)

    # Also mark parent note as addressed
    if parent_note.get("status") in ("pending", "seen"):
        parent_note["status"] = "addressed"

    await _save_wedding_events(
        wedding,
        f"events.{event_index}.order_of_events",
        order_of_events,
        current_user.email,
    )

    logger.info(
        f"Planner {current_user.email} replied to item note {note_id} on item {item_id}"
    )
    return {"message": "Reply added", "note": reply_note}


def _serialize_meeting(task: dict, include_planner_fields: bool = True) -> dict:
    """Consistent meeting response format. Set include_planner_fields=False for couple-facing responses."""
    result = {
        "id": str(task["_id"]),
        "title": task.get("title", ""),
        "description": task.get("description"),
        "start_date": (
            task["start_date"].isoformat() if task.get("start_date") else None
        ),
        "end_date": task["end_date"].isoformat() if task.get("end_date") else None,
        "conference_url": task.get("conference_url"),
        "is_recurring": task.get("is_recurring", False),
        "recurrence_rule": task.get("recurrence_rule"),
        "status": task.get("status", "pending"),
    }
    if include_planner_fields:
        result["reminder_minutes"] = task.get("reminder_minutes")
    return result


# --- Couple-side meeting endpoints ---


@router.get("/couple/portal/meetings", tags=["Couple Portal - Meetings"])
async def list_meetings_couple(couple: dict = Depends(require_couple_auth)):
    """Couple views their upcoming meetings with the planner."""
    if couple.get("wedding_archived"):
        return {"meetings": [], "count": 0, "archived": True, "read_only": True}

    wedding_id = couple.get("wedding_id")
    if not wedding_id:
        return {"meetings": [], "count": 0}

    tasks_collection = mongo.get_planner_tasks_collection()
    now = datetime.now(timezone.utc)
    cursor = (
        tasks_collection.find(
            {
                "wedding_id": wedding_id,
                "category": "meeting",
                "start_date": {"$gte": now},
            }
        )
        .sort("start_date", 1)
        .limit(20)
    )

    meetings = []
    async for task in cursor:
        meetings.append(_serialize_meeting(task, include_planner_fields=False))

    return {"meetings": meetings, "count": len(meetings)}


# ============================================================================
# Couple Self-Service Booking
# ============================================================================


class CoupleBookMeetingRequest(BaseModel):
    """Body for couple-initiated meeting bookings."""

    staff_id: str = Field(..., description="Planner staff member to book with")
    start: datetime = Field(..., description="Slot start, ISO datetime with tzinfo")
    end: datetime = Field(..., description="Slot end, ISO datetime with tzinfo")
    title: str = Field(..., min_length=1, max_length=200)
    notes: Optional[str] = Field(default=None, max_length=2000)
    timezone: str = Field(default="UTC", description="IANA timezone identifier")
    idempotency_key: str = Field(
        ..., min_length=8, max_length=128, description="Client-supplied idempotency key"
    )


@router.get(
    "/couple/portal/availability",
    tags=["Couple Portal - Booking"],
)
async def get_couple_availability(
    duration: int = Query(..., ge=15, le=240, description="Slot duration in minutes"),
    start: Optional[datetime] = Query(default=None),
    end: Optional[datetime] = Query(default=None),
    staff_id: Optional[str] = Query(default=None),
    couple: dict = Depends(require_couple_auth),
) -> dict:
    """Return bookable slots for the wedding's allowed planner team."""
    from app.services.availability_slot_service import availability_slot_service

    wedding_id = couple.get("wedding_id")
    if not wedding_id:
        raise HTTPException(status_code=404, detail="Wedding not found")
    if couple.get("wedding_archived"):
        raise HTTPException(status_code=403, detail="Wedding is archived")
    try:
        slots = await availability_slot_service.generate_slots(
            wedding_id=wedding_id,
            duration_minutes=duration,
            range_start=start,
            range_end=end,
            staff_id=staff_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Availability lookup failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Scheduling temporarily unavailable, please try again shortly",
        ) from exc
    return {"slots": [slot.to_dict() for slot in slots], "count": len(slots)}


@router.post(
    "/couple/portal/meetings/book",
    tags=["Couple Portal - Booking"],
)
async def book_couple_meeting(
    body: CoupleBookMeetingRequest,
    couple: dict = Depends(require_couple_auth),
) -> dict:
    """Book a meeting with the assigned planner team.

    Pipeline: lock the (staff, start, end) tuple, re-check availability inside
    the lock, persist the planner_task with all sync-required fields, project
    onto the staff's external calendar via calendar_sync_service, and enqueue
    an ICS invite. Idempotent on ``idempotency_key``.
    """
    from app.services.availability_slot_service import availability_slot_service
    from app.services.calendar_idempotency_service import calendar_idempotency_service
    from app.services.calendar_job_service import calendar_job_service
    from app.services.calendar_sync_service import calendar_sync_service
    from app.core.cache import cache
    from app.utils.planner_ownership import (
        extract_wedding_owner_identity,
        normalize_wedding_query_id,
    )
    from app.models.calendar import (
        CalendarSyncPolicy,
        InviteDeliveryMode,
        MeetingLifecycleStatus,
        ScheduleItemType,
    )

    wedding_id = couple.get("wedding_id")
    if not wedding_id:
        raise HTTPException(status_code=404, detail="Wedding not found")
    if couple.get("wedding_archived"):
        raise HTTPException(status_code=403, detail="Wedding is archived")

    if body.end <= body.start:
        raise HTTPException(status_code=400, detail="end must be after start")

    wedding = await mongo.get_weddings_collection().find_one(
        {"_id": normalize_wedding_query_id(wedding_id)}
    )
    if not wedding:
        raise HTTPException(status_code=404, detail="Wedding not found")
    owner_id, owner_email = extract_wedding_owner_identity(wedding)

    candidate_users, _ = await availability_slot_service._resolve_candidate_staff(
        wedding_id=wedding_id, staff_id=body.staff_id
    )
    if not candidate_users:
        raise HTTPException(status_code=403, detail="Staff not available for this wedding")
    staff = candidate_users[0]

    scope_key = f"couple_meeting_book:{wedding_id}:{couple.get('email')}"
    request_hash = calendar_idempotency_service.build_request_hash(
        action="couple_meeting_book",
        payload=body.model_dump(),
    )
    resolution = await calendar_idempotency_service.begin(
        scope_key=scope_key,
        idempotency_key=body.idempotency_key,
        request_hash=request_hash,
    )
    if resolution.state == "replay" and resolution.response_payload:
        return resolution.response_payload
    if resolution.state == "conflict":
        raise HTTPException(
            status_code=409, detail="Idempotency key reused with a different payload"
        )
    if resolution.state == "in_progress":
        raise HTTPException(status_code=409, detail="Booking already in progress; retry")

    lock_key = (
        f"couple_meeting_book:{staff.user_id}:{body.start.isoformat()}:{body.end.isoformat()}"
    )
    lock_value = uuid.uuid4().hex
    acquired = await cache.acquire_lock(lock_key, lock_value, expire=30)
    if acquired is False:
        raise HTTPException(
            status_code=409, detail="That slot is being booked by someone else; try again"
        )
    if acquired is None:
        # Redis unavailable — without the lock we cannot guarantee single-write
        # semantics on the slot. Fail closed rather than racing duplicates.
        raise HTTPException(
            status_code=503,
            detail="Booking lock service is unavailable; please try again shortly",
        )

    try:
        slots = await availability_slot_service.generate_slots(
            wedding_id=wedding_id,
            duration_minutes=int((body.end - body.start).total_seconds() // 60),
            range_start=body.start,
            range_end=body.end,
            staff_id=staff.user_id,
        )
        slot_match = next(
            (
                slot
                for slot in slots
                if slot.start == body.start and slot.end == body.end
            ),
            None,
        )
        if slot_match is None:
            raise HTTPException(status_code=409, detail="Slot is no longer available")

        # couple_users stores a single shared email per couple; ICS goes to it.
        couple_emails = [email for email in (couple.get("email"),) if email]
        now = datetime.now(timezone.utc)
        task_doc = {
            "owner_planner_id": owner_id,
            "owner_planner_email": owner_email,
            "planner_email": owner_email,
            "created_by_user_id": owner_id,
            "created_by_email": owner_email,
            "assigned_user_ids": [staff.user_id],
            "assigned_user_emails": [staff.user_email] if staff.user_email else [],
            "wedding_id": wedding_id,
            "title": body.title,
            "description": body.notes or "",
            "category": "meeting",
            "schedule_item_type": ScheduleItemType.MEETING.value,
            "calendar_sync_policy": CalendarSyncPolicy.ASSIGNED_ONLY.value,
            "couple_attendee_emails": couple_emails,
            "invite_delivery_mode": InviteDeliveryMode.EMAIL_ICS.value,
            "meeting_status": MeetingLifecycleStatus.SCHEDULED.value,
            "external_sync_requested": True,
            "start_date": body.start,
            "end_date": body.end,
            "timezone": body.timezone,
            "all_day": False,
            "status": "pending",
            "priority": "medium",
            "external_conflict_status": "none",
            "created_by_couple": True,
            "created_at": now,
            "updated_at": now,
            "version": 1,
        }
        result = await mongo.get_planner_tasks_collection().insert_one(task_doc)
        task_doc["_id"] = result.inserted_id
        sync_status = await calendar_sync_service.sync_schedule_item(
            task_doc,
            actor_user_id=staff.user_id,
            actor_is_owner=False,
            actor_role_scope=None,
        )
        invite_status = await calendar_job_service.enqueue_invite_job(
            task_doc,
            method="REQUEST",
            reason="couple_self_booking",
            source="couple",
        )
        response_payload = {
            "meeting_id": str(task_doc["_id"]),
            "sync_status": sync_status,
            "invite_status": invite_status,
            "start": body.start.isoformat(),
            "end": body.end.isoformat(),
            "staff_id": staff.user_id,
        }
        await calendar_idempotency_service.complete(
            scope_key=scope_key,
            idempotency_key=body.idempotency_key,
            response_payload=response_payload,
        )
        return response_payload
    except HTTPException as exc:
        await calendar_idempotency_service.fail(
            scope_key=scope_key,
            idempotency_key=body.idempotency_key,
            error_detail=str(exc.detail),
        )
        raise
    except Exception as exc:
        logger.exception("Couple booking failed: %s", exc)
        await calendar_idempotency_service.fail(
            scope_key=scope_key,
            idempotency_key=body.idempotency_key,
            error_detail=str(exc),
        )
        raise HTTPException(
            status_code=503,
            detail="Booking failed; please try again shortly",
        ) from exc
    finally:
        if acquired:
            await cache.release_lock(lock_key, lock_value)


# ============================================================================
# SPRINT 6: REGISTRY CRUD (Couple + Planner shared access)
# ============================================================================


class RegistryItemRequest(BaseModel):
    """Request model for adding/updating a registry item."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Registry name (e.g., 'Target', 'Amazon')",
    )
    url: str = Field(..., min_length=1, max_length=2000, description="Registry URL")
    color: Optional[str] = Field(
        default="bg-gray-600", description="Button color class"
    )


@router.get("/couple/portal/registries", tags=["Couple Portal - Registry"])
async def list_registries_couple(couple: dict = Depends(require_couple_auth)):
    """Couple views their wedding registries."""
    wedding_id = couple.get("wedding_id")
    if not isinstance(wedding_id, str) or not wedding_id:
        raise HTTPException(status_code=404, detail="Wedding not found")

    if couple.get("wedding_archived"):
        archive = await get_archived_wedding_record(wedding_id)
        return {
            "registries": get_archived_registries(archive),
            "archived": True,
            "read_only": True,
        }
    wedding = await mongo.get_weddings_collection().find_one(
        {"_id": wedding_id}, {"registries": 1}
    )
    if not wedding:
        raise HTTPException(status_code=404, detail="Wedding not found")

    return {"registries": wedding.get("registries", [])}


@router.post("/couple/portal/registries", tags=["Couple Portal - Registry"])
async def add_registry_couple(
    body: RegistryItemRequest, couple: dict = Depends(require_couple_auth)
):
    """Couple adds a registry item. Syncs to the wedding model (shared with planner)."""
    if couple.get("wedding_archived"):
        raise HTTPException(status_code=403, detail="Cannot modify archived wedding")

    wedding_id = couple.get("wedding_id")
    wedding_oid = wedding_id

    registry_item = {
        "name": body.name.strip(),
        "url": body.url.strip(),
        "color": body.color or "bg-gray-600",
    }

    result = await mongo.get_weddings_collection().update_one(
        {"_id": wedding_oid}, {"$push": {"registries": registry_item}}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Wedding not found")

    logger.info(
        f"Couple {couple['email']} added registry '{body.name}' to wedding {wedding_id}"
    )
    return {"message": "Registry added", "registry": registry_item}


@router.put("/couple/portal/registries/{index}", tags=["Couple Portal - Registry"])
async def update_registry_couple(
    index: int,
    body: RegistryItemRequest,
    couple: dict = Depends(require_couple_auth),
):
    """Couple updates a registry item by index. Syncs to the wedding model."""
    if couple.get("wedding_archived"):
        raise HTTPException(status_code=403, detail="Cannot modify archived wedding")

    wedding_id = couple.get("wedding_id")
    wedding_oid = wedding_id

    # Verify index is valid
    wedding = await mongo.get_weddings_collection().find_one(
        {"_id": wedding_oid}, {"registries": 1}
    )
    if not wedding:
        raise HTTPException(status_code=404, detail="Wedding not found")

    registries = wedding.get("registries", [])
    if index < 0 or index >= len(registries):
        raise HTTPException(status_code=404, detail="Registry item not found")

    updated_item = {
        "name": body.name.strip(),
        "url": body.url.strip(),
        "color": body.color or "bg-gray-600",
    }

    await mongo.get_weddings_collection().update_one(
        {"_id": wedding_oid}, {"$set": {f"registries.{index}": updated_item}}
    )

    logger.info(
        f"Couple {couple['email']} updated registry[{index}] in wedding {wedding_id}"
    )
    return {"message": "Registry updated", "registry": updated_item}


@router.delete("/couple/portal/registries/{index}", tags=["Couple Portal - Registry"])
async def delete_registry_couple(
    index: int,
    couple: dict = Depends(require_couple_auth),
):
    """Couple deletes a registry item by index."""
    if couple.get("wedding_archived"):
        raise HTTPException(status_code=403, detail="Cannot modify archived wedding")

    wedding_id = couple.get("wedding_id")
    wedding_oid = wedding_id

    wedding = await mongo.get_weddings_collection().find_one(
        {"_id": wedding_oid}, {"registries": 1}
    )
    if not wedding:
        raise HTTPException(status_code=404, detail="Wedding not found")

    registries = wedding.get("registries", [])
    if index < 0 or index >= len(registries):
        raise HTTPException(status_code=404, detail="Registry item not found")

    # Remove by setting to None then pulling
    removed_name = registries[index].get("name", "Unknown")
    registries.pop(index)

    await mongo.get_weddings_collection().update_one(
        {"_id": wedding_oid}, {"$set": {"registries": registries}}
    )

    logger.info(
        f"Couple {couple['email']} deleted registry '{removed_name}' from wedding {wedding_id}"
    )
    return {"message": "Registry deleted"}


# ============================================================================
# SPRINT 6: FAQ CRUD (Couple + Planner shared access)
# ============================================================================


class FAQItemRequest(BaseModel):
    """Request model for adding/updating an FAQ item."""

    question: str = Field(..., min_length=1, max_length=500, description="FAQ question")
    answer: str = Field(..., min_length=1, max_length=5000, description="FAQ answer")
    link_url: Optional[str] = Field(
        default=None, max_length=2000, description="Optional CTA link URL"
    )
    link_label: Optional[str] = Field(
        default=None, max_length=200, description="Optional CTA link label"
    )


@router.get("/couple/portal/faqs", tags=["Couple Portal - FAQ"])
async def list_faqs_couple(couple: dict = Depends(require_couple_auth)):
    """Couple views their wedding FAQs."""
    wedding_id = couple.get("wedding_id")
    if not isinstance(wedding_id, str) or not wedding_id:
        raise HTTPException(status_code=404, detail="Wedding not found")

    if couple.get("wedding_archived"):
        archive = await get_archived_wedding_record(wedding_id)
        return {
            "faqs": get_archived_faqs(archive),
            "archived": True,
            "read_only": True,
        }
    wedding = await mongo.get_weddings_collection().find_one(
        {"_id": wedding_id}, {"faqs": 1}
    )
    if not wedding:
        raise HTTPException(status_code=404, detail="Wedding not found")

    return {"faqs": wedding.get("faqs", [])}


@router.post("/couple/portal/faqs", tags=["Couple Portal - FAQ"])
async def add_faq_couple(
    body: FAQItemRequest, couple: dict = Depends(require_couple_auth)
):
    """Couple adds an FAQ item. Syncs to the wedding model (shared with planner)."""
    if couple.get("wedding_archived"):
        raise HTTPException(status_code=403, detail="Cannot modify archived wedding")

    wedding_id = couple.get("wedding_id")
    wedding_oid = wedding_id

    faq_item = {
        "question": body.question.strip(),
        "answer": body.answer.strip(),
        "link_url": body.link_url.strip() if body.link_url else None,
        "link_label": body.link_label.strip() if body.link_label else None,
    }

    result = await mongo.get_weddings_collection().update_one(
        {"_id": wedding_oid}, {"$push": {"faqs": faq_item}}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Wedding not found")

    logger.info(
        f"Couple {couple['email']} added FAQ '{body.question[:50]}' to wedding {wedding_id}"
    )
    return {"message": "FAQ added", "faq": faq_item}


@router.put("/couple/portal/faqs/{index}", tags=["Couple Portal - FAQ"])
async def update_faq_couple(
    index: int,
    body: FAQItemRequest,
    couple: dict = Depends(require_couple_auth),
):
    """Couple updates an FAQ item by index. Syncs to the wedding model."""
    if couple.get("wedding_archived"):
        raise HTTPException(status_code=403, detail="Cannot modify archived wedding")

    wedding_id = couple.get("wedding_id")
    wedding_oid = wedding_id

    wedding = await mongo.get_weddings_collection().find_one(
        {"_id": wedding_oid}, {"faqs": 1}
    )
    if not wedding:
        raise HTTPException(status_code=404, detail="Wedding not found")

    faqs = wedding.get("faqs", [])
    if index < 0 or index >= len(faqs):
        raise HTTPException(status_code=404, detail="FAQ item not found")

    updated_item = {
        "question": body.question.strip(),
        "answer": body.answer.strip(),
        "link_url": body.link_url.strip() if body.link_url else None,
        "link_label": body.link_label.strip() if body.link_label else None,
    }

    await mongo.get_weddings_collection().update_one(
        {"_id": wedding_oid}, {"$set": {f"faqs.{index}": updated_item}}
    )

    logger.info(
        f"Couple {couple['email']} updated FAQ[{index}] in wedding {wedding_id}"
    )
    return {"message": "FAQ updated", "faq": updated_item}


@router.delete("/couple/portal/faqs/{index}", tags=["Couple Portal - FAQ"])
async def delete_faq_couple(
    index: int,
    couple: dict = Depends(require_couple_auth),
):
    """Couple deletes an FAQ item by index."""
    if couple.get("wedding_archived"):
        raise HTTPException(status_code=403, detail="Cannot modify archived wedding")

    wedding_id = couple.get("wedding_id")
    wedding_oid = wedding_id

    wedding = await mongo.get_weddings_collection().find_one(
        {"_id": wedding_oid}, {"faqs": 1}
    )
    if not wedding:
        raise HTTPException(status_code=404, detail="Wedding not found")

    faqs = wedding.get("faqs", [])
    if index < 0 or index >= len(faqs):
        raise HTTPException(status_code=404, detail="FAQ item not found")

    removed_q = faqs[index].get("question", "Unknown")[:50]
    faqs.pop(index)

    await mongo.get_weddings_collection().update_one(
        {"_id": wedding_oid}, {"$set": {"faqs": faqs}}
    )

    logger.info(
        f"Couple {couple['email']} deleted FAQ '{removed_q}' from wedding {wedding_id}"
    )
    return {"message": "FAQ deleted"}


# ============================================================================
# SPRINT 6: QR CODE (Reuses guest_export_service.generate_qr_code)
# ============================================================================


@router.get("/couple/portal/qr-code", tags=["Couple Portal - QR Code"])
async def get_couple_qr_code(couple: dict = Depends(require_couple_auth)):
    """Generate a QR code PNG for the couple portal login URL."""
    frontend_url = os.getenv("FRONTEND_URL", "https://thespecialwedding.io")
    portal_url = f"{frontend_url}/couple/login"

    try:
        png_bytes = guest_export_service.generate_qr_code(portal_url)
        return Response(
            content=png_bytes,
            media_type="image/png",
            headers={"Content-Disposition": "inline; filename=portal-qr.png"},
        )
    except Exception as e:
        logger.error(f"QR code generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate QR code")


# ============================================================================
# SPRINT 6: PUSH NOTIFICATIONS (Couple-side subscribe/unsubscribe)
# ============================================================================


class CouplePushSubscriptionKeys(BaseModel):
    """VAPID keys from browser subscription."""

    p256dh: str
    auth: str


class CouplePushSubscription(BaseModel):
    """Push subscription from browser's PushManager."""

    endpoint: str
    keys: CouplePushSubscriptionKeys
    expirationTime: Optional[int] = None


class CoupleSubscribeRequest(BaseModel):
    """Wrapper for push subscription from couple frontend."""

    subscription: CouplePushSubscription


class CoupleUnsubscribeRequest(BaseModel):
    """Request to unsubscribe couple from push notifications."""

    endpoint: str


@router.post("/couple/portal/push/subscribe", tags=["Couple Portal - Push"])
async def subscribe_couple_push(
    body: CoupleSubscribeRequest,
    request: Request,
    couple: dict = Depends(require_couple_auth),
):
    """Couple subscribes to browser push notifications."""
    if not web_push_service.enabled:
        raise HTTPException(status_code=503, detail="Push notifications not configured")

    user_agent = request.headers.get("User-Agent")
    subscription_data = {
        "endpoint": body.subscription.endpoint,
        "keys": body.subscription.keys.model_dump(),
        "expirationTime": body.subscription.expirationTime,
    }

    success = await web_push_service.save_subscription(
        user_id=build_couple_principal_key(get_couple_record_id(couple)),
        subscription=subscription_data,
        user_agent=user_agent,
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to save subscription")

    logger.info(f"Couple {couple['email']} subscribed to push notifications")
    return {"success": True, "message": "Subscribed to push notifications"}


@router.delete("/couple/portal/push/unsubscribe", tags=["Couple Portal - Push"])
async def unsubscribe_couple_push(
    body: CoupleUnsubscribeRequest,
    couple: dict = Depends(require_couple_auth),
):
    """Couple unsubscribes from browser push notifications."""
    success = await web_push_service.remove_subscription(
        endpoint=body.endpoint,
        user_id=build_couple_principal_key(get_couple_record_id(couple)),
    )

    if not success:
        for legacy_user_id in list_couple_identity_keys(couple)[1:]:
            success = await web_push_service.remove_subscription(
                endpoint=body.endpoint,
                user_id=legacy_user_id,
            )
            if success:
                break

    if not success:
        raise HTTPException(status_code=500, detail="Failed to remove subscription")

    logger.info(f"Couple {couple['email']} unsubscribed from push notifications")
    return {"success": True, "message": "Unsubscribed from push notifications"}


@router.get("/couple/portal/push/status", tags=["Couple Portal - Push"])
async def get_couple_push_status(couple: dict = Depends(require_couple_auth)):
    """Check if couple has active push subscriptions."""
    if not web_push_service.enabled:
        return {"enabled": False, "subscribed": False, "reason": "Push not configured"}

    collection = mongo.db["push_subscriptions"]
    count = await collection.count_documents(
        {"user_id": {"$in": list_couple_identity_keys(couple)}}
    )

    return {
        "enabled": True,
        "subscribed": count > 0,
        "subscription_count": count,
        "vapid_public_key": web_push_service.get_public_key(),
    }
