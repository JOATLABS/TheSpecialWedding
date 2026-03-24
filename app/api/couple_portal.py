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
from fastapi import APIRouter, HTTPException, Request, Query, Depends, Path
from fastapi.responses import Response
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone
from app.core.database import mongo
from app.services.couple_portal_service import couple_portal_service
from app.services.guest_export_service import guest_export_service
from app.services.web_push_service import web_push_service
from app.dependencies.auth_extended import (
    ExtendedAuthUser, require_team_or_planner, enforce_team_permission, check_wedding_access
)
from app.dependencies.couple_auth import require_couple_auth
from bson import ObjectId
from bson.errors import InvalidId
import uuid
import copy
import logging
import os

logger = logging.getLogger(__name__)
router = APIRouter()


# Auth dependency: use require_couple_auth from app.dependencies.couple_auth


# ============================================================================
# DASHBOARD ENDPOINTS
# ============================================================================

@router.get("/couple/portal/dashboard", tags=["Couple Portal"])
async def get_dashboard(couple: dict = Depends(require_couple_auth)):
    """Get the couple's portal dashboard with all data."""

    wedding_id = couple.get("wedding_id")
    if not wedding_id:
        raise HTTPException(status_code=404, detail="No wedding linked to this account")

    # Check if archived
    if couple.get("wedding_archived"):
        # Return archived view
        archive = await mongo.db["archived_weddings"].find_one({"original_wedding_id": wedding_id})
        if archive:
            return {
                "archived": True,
                "wedding": archive.get("wedding"),
                "archived_at": archive.get("archived_at").isoformat() if archive.get("archived_at") else None,
                "message": "This wedding has been completed and archived. You can still view your wedding details."
            }

    dashboard = await couple_portal_service.get_portal_dashboard(wedding_id, couple["email"])
    if not dashboard:
        raise HTTPException(status_code=404, detail="Wedding data not found")

    return {"archived": False, **dashboard}


@router.get("/couple/portal/events", tags=["Couple Portal"])
async def get_events(couple: dict = Depends(require_couple_auth)):
    """Get wedding events/timeline."""
    wedding = await mongo.get_weddings_collection().find_one({"_id": couple["wedding_id"]})
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
        "timezone": wedding.get("timezone", "America/Chicago")
    }


@router.get("/couple/portal/updates", tags=["Couple Portal"])
async def get_updates(
    couple: dict = Depends(require_couple_auth),
    limit: int = Query(20, ge=1, le=100),
    skip: int = Query(0, ge=0)
):
    """Get planner updates for the couple."""

    updates = []
    async for update in mongo.db["couple_updates"].find(
        {"wedding_id": couple["wedding_id"]}
    ).sort("created_at", -1).skip(skip).limit(limit):
        updates.append({
            "id": str(update["_id"]),
            "type": update.get("type", "update"),
            "title": update.get("title"),
            "content": update.get("content"),
            "category": update.get("category"),
            "attachments": update.get("attachments", []),
            "is_milestone": update.get("is_milestone", False),
            "created_at": update.get("created_at").isoformat() if update.get("created_at") else None,
            "created_by": update.get("created_by_name"),
        })

    return {"updates": updates, "count": len(updates)}


# ============================================================================
# FORM SUBMISSION
# ============================================================================

class FormSubmissionRequest(BaseModel):
    """Couple submits a form response."""
    form_id: str = Field(...)
    responses: dict = Field(..., description="Form field responses keyed by field_id")


@router.post("/couple/portal/forms/submit", tags=["Couple Portal"])
async def submit_form(data: FormSubmissionRequest, couple: dict = Depends(require_couple_auth)):
    """Couple submits a form shared by the planner."""

    # Block form submission for archived weddings
    if couple.get("wedding_archived"):
        raise HTTPException(status_code=403, detail="Form submission is disabled for archived weddings")

    # Verify form exists and is shared with couple
    form = await mongo.db["forms"].find_one({
        "_id": ObjectId(data.form_id),
        "wedding_id": couple["wedding_id"],
        "$or": [
            {"shared_with_couple": True},
            {"target_audience": "couple"},
            {"couple_email": couple["email"]}
        ]
    })

    if not form:
        raise HTTPException(status_code=404, detail="Form not found or not shared with you")

    # Check for existing submission
    existing = await mongo.db["form_submissions"].find_one({
        "form_id": data.form_id,
        "submitted_by": couple["email"]
    })

    submission_doc = {
        "form_id": data.form_id,
        "wedding_id": couple["wedding_id"],
        "submitted_by": couple["email"],
        "submitted_by_name": f"{couple.get('partner1_name', '')} & {couple.get('partner2_name', '')}".strip(" &"),
        "submitted_by_type": "couple",
        "responses": data.responses,
        "submitted_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    if existing:
        await mongo.db["form_submissions"].update_one(
            {"_id": existing["_id"]},
            {"$set": {
                "responses": data.responses,
                "updated_at": datetime.now(timezone.utc)
            }}
        )
        submission_id = str(existing["_id"])
    else:
        result = await mongo.db["form_submissions"].insert_one(submission_doc)
        submission_id = str(result.inserted_id)

    # Notify planner via planner_notification_service (SSE + push included)
    try:
        planner_email = couple.get("planner_email")
        if planner_email:
            from app.services.planner_notification_service import planner_notification_service
            couple_name = f"{couple.get('partner1_name', '')} & {couple.get('partner2_name', '')}".strip(" &")
            await planner_notification_service.create_notification(
                planner_id=planner_email,
                notification_type="form_submission",
                title=f"{couple_name} submitted \"{form.get('title', 'a form')}\"",
                message=f"Your couple has {'updated' if existing else 'submitted'} the form \"{form.get('title')}\". Review their responses in your dashboard.",
                wedding_id=couple["wedding_id"],
                action_url=f"/admin/forms?wedding_id={couple['wedding_id']}",
            )
    except Exception as e:
        logger.error(f"Failed to notify planner of form submission: {e}")

    return {
        "message": "Form submitted successfully",
        "submission_id": submission_id
    }


@router.get("/couple/portal/forms/{form_id}", tags=["Couple Portal"])
async def get_form_details(form_id: str, couple: dict = Depends(require_couple_auth)):
    """Get a specific form with its fields for the couple to fill out."""

    form = await mongo.db["forms"].find_one({
        "_id": ObjectId(form_id),
        "wedding_id": couple["wedding_id"]
    })

    if not form:
        raise HTTPException(status_code=404, detail="Form not found")

    # Get existing submission if any
    submission = await mongo.db["form_submissions"].find_one({
        "form_id": form_id,
        "submitted_by": couple["email"]
    })

    return {
        "form": {
            "id": str(form["_id"]),
            "title": form.get("title"),
            "description": form.get("description"),
            "fields": form.get("fields", []),
            "created_at": form.get("created_at").isoformat() if form.get("created_at") else None,
        },
        "existing_responses": submission.get("responses") if submission else None,
        "submitted_at": submission.get("submitted_at").isoformat() if submission and submission.get("submitted_at") else None
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
    category: Optional[str] = Field(None, max_length=50)  # venue, catering, decor, timeline, budget, etc.
    is_milestone: bool = Field(default=False)
    attachments: List[dict] = Field(default_factory=list)


@router.post("/couple-portal/updates", tags=["Couple Portal"])
async def create_update(
    data: CreateUpdateRequest,
    current_user: "ExtendedAuthUser" = Depends(require_team_or_planner)
):
    """
    Planner creates an update for the couple's portal.
    Requires planner authentication + wedding access.
    """
    enforce_team_permission(current_user, "manage_contracts")

    # Verify planner has access to this wedding
    if not await check_wedding_access(current_user, data.wedding_id):
        raise HTTPException(status_code=403, detail="You don't have access to this wedding")

    # Get planner name
    planner_name = f"{(current_user.user_data or {}).get('first_name', '')} {(current_user.user_data or {}).get('last_name', '')}".strip()
    if not planner_name:
        planner_name = (current_user.user_data or {}).get("company_name", current_user.email)

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

    logger.info(f"Couple update created for wedding {data.wedding_id} by {current_user.email}")

    return {
        "message": "Update created successfully",
        "update_id": str(result.inserted_id)
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
    enforce_team_permission(current_user, "manage_contracts")
    if not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="You don't have access to this wedding")
    wedding = await mongo.get_weddings_collection().find_one({"_id": wedding_id})
    if not wedding:
        raise HTTPException(status_code=404, detail="Wedding not found")
    return wedding


async def _save_wedding_events(wedding: dict, field_path: str, value, current_user_email: str):
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
        {"$set": {
            field_path: value,
            "updated_by": current_user_email,
            "updated_at": datetime.now(timezone.utc),
        }}
    )
    if result.matched_count == 0:
        raise HTTPException(
            status_code=409,
            detail="Wedding was modified by another user. Please refresh and try again."
        )


def _get_event_by_index(wedding: dict, event_index: int):
    """Helper: get an event from the wedding's events array by index."""
    events = wedding.get("events", [])
    if event_index < 0 or event_index >= len(events):
        raise HTTPException(status_code=404, detail=f"Event at index {event_index} not found")
    return events[event_index]


@router.post("/couple-portal/events/{event_index}/order-of-events", tags=["Couple Portal"])
async def add_order_item(
    data: AddOrderItemRequest,
    event_index: int = Path(..., ge=0),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner)
):
    """
    Add a new item to the order of events for a specific ceremony.
    The item is appended at the end of the list.
    """
    wedding = await _get_wedding_for_planner(data.wedding_id, current_user)
    event = _get_event_by_index(wedding, event_index)

    order_of_events = event.get("order_of_events", [])
    new_item = {
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
        wedding, f"events.{event_index}.order_of_events", order_of_events, current_user.email
    )

    logger.info(f"Order item added to event {event_index} of wedding {data.wedding_id}")

    return {"message": "Item added", "item": new_item}


@router.put("/couple-portal/events/{event_index}/order-of-events/{item_id}", tags=["Couple Portal"])
async def update_order_item(
    data: UpdateOrderItemRequest,
    event_index: int = Path(..., ge=0),
    item_id: str = Path(...),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner)
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
        wedding, f"events.{event_index}.order_of_events", order_of_events, current_user.email
    )

    return {"message": "Item updated", "item": item}


@router.put("/couple-portal/events/{event_index}/order-of-events/reorder", tags=["Couple Portal"])
async def reorder_items(
    data: ReorderItemsRequest,
    event_index: int = Path(..., ge=0),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner)
):
    """Reorder items in the order of events. Accepts item IDs in desired display order."""
    wedding = await _get_wedding_for_planner(data.wedding_id, current_user)
    event = _get_event_by_index(wedding, event_index)

    order_of_events = event.get("order_of_events", [])
    items_by_id = {i["id"]: i for i in order_of_events}

    # Validate all IDs exist
    for iid in data.item_ids:
        if iid not in items_by_id:
            raise HTTPException(status_code=400, detail=f"Item {iid} not found in order of events")

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


@router.delete("/couple-portal/events/{event_index}/order-of-events/{item_id}", tags=["Couple Portal"])
async def delete_order_item(
    event_index: int = Path(..., ge=0),
    item_id: str = Path(...),
    wedding_id: str = Query(...),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner)
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
        wedding, f"events.{event_index}.order_of_events", order_of_events, current_user.email
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
    couple: dict = Depends(require_couple_auth)
):
    """Couple adds a general note to an event (e.g. 'Keep reception under 3 hours')."""
    if couple.get("wedding_archived"):
        raise HTTPException(status_code=403, detail="Notes are disabled for archived weddings")

    wedding = await mongo.get_weddings_collection().find_one({"_id": couple["wedding_id"]})
    if not wedding:
        raise HTTPException(status_code=404, detail="Wedding not found")

    event = _get_event_by_index(wedding, event_index)
    couple_name = f"{couple.get('partner1_name', '')} & {couple.get('partner2_name', '')}".strip(" &")

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
        {"$set": {f"events.{event_index}.event_notes": event_notes}}
    )

    # Notify planner
    await _notify_planner_of_note(couple, wedding, f"New note on {event.get('type', 'event')}", data.text)

    return {"message": "Note added", "note": new_note}


@router.post("/couple/portal/events/{event_index}/order-of-events/{item_id}/notes", tags=["Couple Portal"])
async def add_item_note(
    data: AddNoteRequest,
    event_index: int = Path(..., ge=0),
    item_id: str = Path(...),
    couple: dict = Depends(require_couple_auth)
):
    """Couple adds a note to a specific order-of-events item (e.g. 'Use Ed Sheeran for first dance')."""
    if couple.get("wedding_archived"):
        raise HTTPException(status_code=403, detail="Notes are disabled for archived weddings")

    wedding = await mongo.get_weddings_collection().find_one({"_id": couple["wedding_id"]})
    if not wedding:
        raise HTTPException(status_code=404, detail="Wedding not found")

    event = _get_event_by_index(wedding, event_index)
    order_of_events = event.get("order_of_events", [])
    item = next((i for i in order_of_events if i.get("id") == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail=f"Order item {item_id} not found")

    couple_name = f"{couple.get('partner1_name', '')} & {couple.get('partner2_name', '')}".strip(" &")

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
        {"$set": {f"events.{event_index}.order_of_events": order_of_events}}
    )

    # Notify planner
    await _notify_planner_of_note(couple, wedding, f"Note on \"{item.get('title', 'item')}\"", data.text)

    return {"message": "Note added", "note": new_note}


async def _notify_planner_of_note(couple: dict, wedding: dict, title: str, text: str):
    """Send a planner notification when the couple leaves a note. Uses planner_notification_service for SSE + push."""
    try:
        planner_email = couple.get("planner_email") or wedding.get("assigned_planner_email")
        if not planner_email:
            return
        from app.services.planner_notification_service import planner_notification_service
        couple_name = f"{couple.get('partner1_name', '')} & {couple.get('partner2_name', '')}".strip(" &")
        preview = text[:100] + ("..." if len(text) > 100 else "")
        await planner_notification_service.create_notification(
            planner_id=planner_email,
            notification_type="couple_note",
            title=f"{couple_name}: {title}",
            message=preview,
            wedding_id=couple.get("wedding_id"),
            action_url=f"/admin/couple-portal?wedding_id={couple.get('wedding_id')}",
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


@router.patch("/couple-portal/events/{event_index}/notes/{note_id}", tags=["Couple Portal"])
async def update_event_note_status(
    data: UpdateNoteStatusRequest,
    event_index: int = Path(..., ge=0),
    note_id: str = Path(...),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner)
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
    tags=["Couple Portal"]
)
async def update_item_note_status(
    data: UpdateNoteStatusRequest,
    event_index: int = Path(..., ge=0),
    item_id: str = Path(...),
    note_id: str = Path(...),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner)
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
        wedding, f"events.{event_index}.order_of_events", order_of_events, current_user.email
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

    contract_detail = await couple_portal_service.get_contract_for_couple(wedding_id, couple["email"])

    if not contract_detail:
        return {"contract": None, "message": "No contract found for this wedding"}

    return {"contract": contract_detail}


# ============================================================================
# SPRINT 2: COUPLE ACCESS MANAGEMENT (Planner-side)
# ============================================================================

@router.patch("/couple-portal/couples/{couple_id}/revoke", tags=["Couple Portal"])
async def revoke_couple_access(
    couple_id: str = Path(...),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner)
):
    """Revoke a couple's portal access. Sets is_active=False."""
    enforce_team_permission(current_user, "manage_contracts")

    couple = await mongo.db["couple_users"].find_one({"_id": ObjectId(couple_id)})
    if not couple:
        raise HTTPException(status_code=404, detail="Couple not found")

    if not await check_wedding_access(current_user, couple["wedding_id"]):
        raise HTTPException(status_code=403, detail="You don't have access to this wedding")

    await mongo.db["couple_users"].update_one(
        {"_id": ObjectId(couple_id)},
        {"$set": {
            "is_active": False,
            "revoked_at": datetime.now(timezone.utc),
            "revoked_by": current_user.email,
            "updated_at": datetime.now(timezone.utc),
        }}
    )

    logger.info(f"Couple access revoked for {couple['email']} by {current_user.email}")

    return {"message": "Couple access revoked"}


@router.patch("/couple-portal/couples/{couple_id}/restore", tags=["Couple Portal"])
async def restore_couple_access(
    couple_id: str = Path(...),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner)
):
    """Restore a previously revoked couple's portal access."""
    enforce_team_permission(current_user, "manage_contracts")

    couple = await mongo.db["couple_users"].find_one({"_id": ObjectId(couple_id)})
    if not couple:
        raise HTTPException(status_code=404, detail="Couple not found")

    if not await check_wedding_access(current_user, couple["wedding_id"]):
        raise HTTPException(status_code=403, detail="You don't have access to this wedding")

    await mongo.db["couple_users"].update_one(
        {"_id": ObjectId(couple_id)},
        {"$set": {
            "is_active": True,
            "revoked_at": None,
            "revoked_by": None,
            "updated_at": datetime.now(timezone.utc),
        }}
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


# --- Couple-side messaging ---

@router.post("/couple/portal/messages", tags=["Couple Portal - Messages"])
async def couple_send_message(
    data: SendMessageRequest,
    couple: dict = Depends(require_couple_auth)
):
    """Couple sends a message to their planner."""
    wedding_id = couple.get("wedding_id")
    if not wedding_id:
        raise HTTPException(status_code=404, detail="No wedding linked to this account")

    # Block messaging for archived weddings
    if couple.get("wedding_archived"):
        raise HTTPException(status_code=403, detail="Messaging is disabled for archived weddings")

    # Verify wedding exists before inserting message
    wedding = await mongo.get_weddings_collection().find_one({"_id": wedding_id}, {"_id": 1})
    if not wedding:
        raise HTTPException(status_code=404, detail="Wedding not found")

    couple_name = f"{couple.get('partner1_name', '')} & {couple.get('partner2_name', '')}".strip(" &")

    message_doc = {
        "wedding_id": wedding_id,
        "sender_role": "couple",
        "sender_email": couple["email"],
        "sender_name": couple_name or couple["email"],
        "content": data.content,
        "read_by_couple": True,
        "read_by_planner": False,
        "created_at": datetime.now(timezone.utc),
    }

    result = await mongo.db["couple_messages"].insert_one(message_doc)

    # Notify planner via planner_notification_service (SSE + push included)
    try:
        planner_email = couple.get("planner_email")
        if planner_email:
            from app.services.planner_notification_service import planner_notification_service
            preview = data.content[:100] + ("..." if len(data.content) > 100 else "")
            await planner_notification_service.create_notification(
                planner_id=planner_email,
                notification_type="couple_message",
                title=f"New message from {couple_name or couple['email']}",
                message=preview,
                wedding_id=wedding_id,
                action_url=f"/admin/couple-portal?wedding_id={wedding_id}&tab=messages",
            )
    except Exception as e:
        logger.error(f"Failed to notify planner of couple message: {e}")

    return {
        "message": "Message sent",
        "message_id": str(result.inserted_id),
    }


@router.get("/couple/portal/messages", tags=["Couple Portal - Messages"])
async def couple_get_messages(
    couple: dict = Depends(require_couple_auth),
    limit: int = Query(50, ge=1, le=200),
    before: Optional[str] = Query(None, description="Cursor: message ID to load older messages before")
):
    """Get message history for the couple's wedding conversation."""
    wedding_id = couple.get("wedding_id")
    if not wedding_id:
        raise HTTPException(status_code=404, detail="No wedding linked to this account")

    # Mark unread planner messages as read by couple (before fetching, to avoid race)
    await mongo.db["couple_messages"].update_many(
        {"wedding_id": wedding_id, "sender_role": "planner", "read_by_couple": False},
        {"$set": {"read_by_couple": True}}
    )

    query: dict = {"wedding_id": wedding_id}
    if before:
        try:
            query["_id"] = {"$lt": ObjectId(before)}
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid cursor")

    messages = []
    async for msg in mongo.db["couple_messages"].find(query).sort("_id", -1).limit(limit):
        messages.append({
            "id": str(msg["_id"]),
            "sender_role": msg.get("sender_role"),
            "sender_name": msg.get("sender_name"),
            "content": msg.get("content"),
            "read_by_planner": msg.get("read_by_planner", False),
            "created_at": msg.get("created_at").isoformat() if msg.get("created_at") else None,
        })

    # Return in chronological order (oldest first)
    messages.reverse()

    return {"messages": messages, "count": len(messages)}


@router.get("/couple/portal/messages/unread-count", tags=["Couple Portal - Messages"])
async def couple_unread_count(couple: dict = Depends(require_couple_auth)):
    """Get count of unread messages for the couple."""
    wedding_id = couple.get("wedding_id")
    if not wedding_id:
        return {"unread_count": 0}

    count = await mongo.db["couple_messages"].count_documents({
        "wedding_id": wedding_id,
        "sender_role": "planner",
        "read_by_couple": False,
    })
    return {"unread_count": count}


# --- Planner-side messaging ---

@router.post("/couple-portal/messages", tags=["Couple Portal - Messages"])
async def planner_send_message(
    data: PlannerSendMessageRequest,
    current_user: ExtendedAuthUser = Depends(require_team_or_planner)
):
    """Planner sends a message to the couple for a specific wedding."""
    enforce_team_permission(current_user, "manage_contracts")

    if not await check_wedding_access(current_user, data.wedding_id):
        raise HTTPException(status_code=403, detail="You don't have access to this wedding")

    planner_name = f"{(current_user.user_data or {}).get('first_name', '')} {(current_user.user_data or {}).get('last_name', '')}".strip()
    if not planner_name:
        planner_name = (current_user.user_data or {}).get("company_name", current_user.email)

    message_doc = {
        "wedding_id": data.wedding_id,
        "sender_role": "planner",
        "sender_email": current_user.email,
        "sender_name": planner_name,
        "content": data.content,
        "read_by_couple": False,
        "read_by_planner": True,
        "created_at": datetime.now(timezone.utc),
    }

    result = await mongo.db["couple_messages"].insert_one(message_doc)

    logger.info(f"Planner {current_user.email} sent message for wedding {data.wedding_id}")

    return {
        "message": "Message sent",
        "message_id": str(result.inserted_id),
    }


@router.get("/couple-portal/messages", tags=["Couple Portal - Messages"])
async def planner_get_messages(
    wedding_id: str = Query(...),
    limit: int = Query(50, ge=1, le=200),
    before: Optional[str] = Query(None, description="Cursor: message ID to load older messages before"),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner)
):
    """Planner gets message history for a specific wedding's couple conversation."""
    enforce_team_permission(current_user, "manage_contracts")

    if not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="You don't have access to this wedding")

    # Mark unread couple messages as read by planner (before fetching, to avoid race)
    await mongo.db["couple_messages"].update_many(
        {"wedding_id": wedding_id, "sender_role": "couple", "read_by_planner": False},
        {"$set": {"read_by_planner": True}}
    )

    query: dict = {"wedding_id": wedding_id}
    if before:
        try:
            query["_id"] = {"$lt": ObjectId(before)}
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid cursor")

    messages = []
    async for msg in mongo.db["couple_messages"].find(query).sort("_id", -1).limit(limit):
        messages.append({
            "id": str(msg["_id"]),
            "sender_role": msg.get("sender_role"),
            "sender_name": msg.get("sender_name"),
            "content": msg.get("content"),
            "read_by_couple": msg.get("read_by_couple", False),
            "created_at": msg.get("created_at").isoformat() if msg.get("created_at") else None,
        })

    messages.reverse()

    return {"messages": messages, "count": len(messages)}


@router.get("/couple-portal/messages/unread-count", tags=["Couple Portal - Messages"])
async def planner_unread_count(
    wedding_id: str = Query(...),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner)
):
    """Get count of unread messages from the couple for a specific wedding."""
    if not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="You don't have access to this wedding")

    count = await mongo.db["couple_messages"].count_documents({
        "wedding_id": wedding_id,
        "sender_role": "couple",
        "read_by_planner": False,
    })
    return {"unread_count": count}


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
    current_user: ExtendedAuthUser = Depends(require_team_or_planner)
):
    """
    Planner triggers a digest email to the couple summarizing unread messages,
    new updates, upcoming payments, and pending forms.
    Reuses couple_portal_service for data aggregation and email_service for sending.
    """
    enforce_team_permission(current_user, "manage_contracts")

    if not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="You don't have access to this wedding")

    # Find the couple for this wedding
    couple_doc = await mongo.db["couple_users"].find_one({
        "wedding_id": wedding_id,
        "is_active": True,
        "setup_completed": True,
    })

    if not couple_doc:
        raise HTTPException(status_code=404, detail="No active couple account found for this wedding")

    # Generate digest (look back 7 days by default)
    from datetime import timedelta
    since = datetime.now(timezone.utc) - timedelta(days=7)
    digest = await couple_portal_service.generate_couple_digest(
        couple_email=couple_doc["email"],
        wedding_id=wedding_id,
        since=since,
    )

    if not digest:
        return {"message": "No new activity to report — digest not sent.", "sent": False}

    sent = await couple_portal_service.send_couple_digest_email(couple_doc, digest)

    return {
        "message": "Digest email sent successfully" if sent else "Failed to send digest email",
        "sent": sent,
        "digest_summary": {
            "unread_messages": digest["unread_messages"],
            "new_updates": digest["new_updates_count"],
            "upcoming_payments": len(digest["upcoming_payments"]),
            "pending_forms": digest["pending_forms_count"],
        }
    }


# ============================================================================
# SPRINT 4: WEDDING ARCHIVAL
# ============================================================================
# Uses existing archive_wedding_data() from CouplePortalService.
# Planner triggers → service snapshots all data → couple sees archived view.

@router.post("/couple-portal/archive", tags=["Couple Portal - Archival"])
async def archive_wedding(
    wedding_id: str = Query(...),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner)
):
    """
    Planner triggers wedding archival. This snapshots all wedding data
    (guests, RSVPs, budget, contracts, forms, updates, messages) into
    the archived_weddings collection and marks couple accounts as archived.
    Archived couples can still log in but see a read-only archived view.
    """
    enforce_team_permission(current_user, "manage_contracts")

    try:
        wedding_id
    except (InvalidId, Exception):
        raise HTTPException(status_code=400, detail="Invalid wedding ID format")

    if not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="You don't have access to this wedding")

    # Check wedding exists
    wedding = await mongo.get_weddings_collection().find_one({"_id": wedding_id})
    if not wedding:
        raise HTTPException(status_code=404, detail="Wedding not found")

    # Check not already archived
    existing_archive = await mongo.db["archived_weddings"].find_one({"original_wedding_id": wedding_id})
    if existing_archive:
        raise HTTPException(status_code=409, detail="This wedding has already been archived")

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
                {"$set": {"messages": messages, "messages_archived": len(messages)}}
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
    current_user: ExtendedAuthUser = Depends(require_team_or_planner)
):
    """
    Planner reverses an archival — removes the archive snapshot and
    restores couple accounts to active state.
    """
    enforce_team_permission(current_user, "manage_contracts")

    if not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="You don't have access to this wedding")

    # Remove archive
    result = await mongo.db["archived_weddings"].delete_one({"original_wedding_id": wedding_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="No archive found for this wedding")

    # Restore couple accounts
    await mongo.db["couple_users"].update_many(
        {"wedding_id": wedding_id},
        {"$set": {"wedding_archived": False}, "$unset": {"archived_at": True}}
    )

    logger.info(f"Wedding {wedding_id} unarchived by {current_user.email}")

    return {"message": "Wedding unarchived — couple portal restored to active state"}


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
    current_user: ExtendedAuthUser = Depends(require_team_or_planner)
):
    """
    Save an existing form as a reusable custom template.
    Copies the form's fields and settings (not responses or wedding-specific data).
    """
    enforce_team_permission(current_user, "manage_contracts")

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
        if not await check_wedding_access(current_user, source_form.get("wedding_id", "")):
            raise HTTPException(status_code=403, detail="You don't have access to this form")

    template_doc = {
        "planner_email": current_user.email,
        "name": data.template_name,
        "description": data.description,
        "category": data.category,
        "source_form_id": data.form_id,
        "fields": source_form.get("fields", []),
        "settings": {
            k: v for k, v in source_form.get("settings", {}).items()
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
    current_user: ExtendedAuthUser = Depends(require_team_or_planner)
):
    """List all custom form templates saved by this planner."""
    templates = []
    async for tpl in mongo.db["custom_form_templates"].find(
        {"planner_email": current_user.email}
    ).sort("created_at", -1):
        templates.append({
            "id": str(tpl["_id"]),
            "name": tpl.get("name"),
            "description": tpl.get("description"),
            "category": tpl.get("category"),
            "field_count": len(tpl.get("fields", [])),
            "created_at": tpl.get("created_at").isoformat() if tpl.get("created_at") else None,
        })

    return {"templates": templates}


@router.post("/couple-portal/form-templates/create-form", tags=["Couple Portal - Form Templates"])
async def create_form_from_custom_template(
    data: CreateFromTemplateRequest,
    current_user: ExtendedAuthUser = Depends(require_team_or_planner)
):
    """Create a new form from a saved custom template and assign it to a wedding."""
    enforce_team_permission(current_user, "manage_contracts")

    try:
        ObjectId(data.template_id)
        ObjectId(data.wedding_id)
    except (InvalidId, Exception):
        raise HTTPException(status_code=400, detail="Invalid ID format")

    if not await check_wedding_access(current_user, data.wedding_id):
        raise HTTPException(status_code=403, detail="You don't have access to this wedding")

    # Get template
    template = await mongo.db["custom_form_templates"].find_one({
        "_id": ObjectId(data.template_id),
        "planner_email": current_user.email,
    })
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

    logger.info(f"Form '{data.form_name}' created from template by {current_user.email}")

    return {
        "message": "Form created from template",
        "form_id": str(result.inserted_id),
    }


@router.delete("/couple-portal/form-templates/{template_id}", tags=["Couple Portal - Form Templates"])
async def delete_custom_template(
    template_id: str = Path(...),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner)
):
    """Delete a saved custom form template."""
    try:
        ObjectId(template_id)
    except (InvalidId, Exception):
        raise HTTPException(status_code=400, detail="Invalid template ID format")

    result = await mongo.db["custom_form_templates"].delete_one({
        "_id": ObjectId(template_id),
        "planner_email": current_user.email,
    })

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
    tags=["Couple Portal - Note Replies"]
)
async def reply_to_event_note(
    data: ReplyToNoteRequest,
    event_index: int = Path(..., ge=0),
    note_id: str = Path(...),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner)
):
    """Planner replies to an event-level note from the couple. Creates a new note with reply_to set."""
    wedding = await _get_wedding_for_planner(data.wedding_id, current_user)

    # Block replies on archived weddings
    couple = await mongo.db["couple_users"].find_one({"wedding_id": data.wedding_id, "wedding_archived": True})
    if couple:
        raise HTTPException(status_code=403, detail="Notes are disabled for archived weddings")

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
    tags=["Couple Portal - Note Replies"]
)
async def reply_to_item_note(
    data: ReplyToNoteRequest,
    event_index: int = Path(..., ge=0),
    item_id: str = Path(...),
    note_id: str = Path(...),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner)
):
    """Planner replies to an order-of-events item note from the couple."""
    wedding = await _get_wedding_for_planner(data.wedding_id, current_user)

    # Block replies on archived weddings
    couple = await mongo.db["couple_users"].find_one({"wedding_id": data.wedding_id, "wedding_archived": True})
    if couple:
        raise HTTPException(status_code=403, detail="Notes are disabled for archived weddings")

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
        wedding, f"events.{event_index}.order_of_events", order_of_events, current_user.email
    )

    logger.info(f"Planner {current_user.email} replied to item note {note_id} on item {item_id}")
    return {"message": "Reply added", "note": reply_note}


# ============================================================================
# P1-2: RECURRING MEETING SCHEDULING
# Reuses planner_tasks collection + Google Calendar sync infrastructure.
# Meetings are planner tasks with category="meeting" and a wedding_id.
# ============================================================================

class ScheduleMeetingRequest(BaseModel):
    """Planner schedules a meeting with a couple."""
    wedding_id: str = Field(...)
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    start_date: datetime
    end_date: Optional[datetime] = None
    is_recurring: bool = False
    recurrence_rule: Optional[str] = Field(
        None, description="iCal RRULE string (e.g., 'FREQ=WEEKLY;BYDAY=MO;COUNT=10')"
    )
    reminder_minutes: Optional[int] = Field(None, ge=0, le=40320)
    sync_to_google: bool = True


@router.post("/couple-portal/meetings", tags=["Couple Portal - Meetings"])
async def schedule_meeting(
    data: ScheduleMeetingRequest,
    current_user: ExtendedAuthUser = Depends(require_team_or_planner)
):
    """
    Planner schedules a meeting with the couple.
    Creates a planner task with category='meeting' and syncs to Google Calendar.
    """
    if not await check_wedding_access(current_user, data.wedding_id):
        raise HTTPException(status_code=403, detail="You don't have access to this wedding")

    wedding_oid = data.wedding_id

    wedding = await mongo.get_weddings_collection().find_one(
        {"_id": wedding_oid}, {"couple_names": 1}
    )
    if not wedding:
        raise HTTPException(status_code=404, detail="Wedding not found")

    now = datetime.now(timezone.utc)

    task_doc = {
        "planner_email": current_user.email,
        "wedding_id": data.wedding_id,
        "title": data.title,
        "description": data.description,
        "category": "meeting",
        "priority": "medium",
        "status": "pending",
        "start_date": data.start_date,
        "end_date": data.end_date or data.start_date,
        "all_day": False,
        "due_date": None,
        "reminder_minutes": data.reminder_minutes,
        "is_recurring": data.is_recurring,
        "recurrence_rule": data.recurrence_rule if data.is_recurring else None,
        "color": "#1e3a5f",
        "notes": f"Meeting with {wedding.get('couple_names', 'couple')}",
        "synced_to_google": False,
        "google_event_id": None,
        "last_google_sync": None,
        "attachments": [],
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
    }

    tasks_collection = mongo.get_planner_tasks_collection()
    result = await tasks_collection.insert_one(task_doc)
    task_doc["_id"] = result.inserted_id

    # Sync to Google Calendar if requested
    if data.sync_to_google:
        try:
            from app.services.google_calendar_service import google_calendar_service
            status = await google_calendar_service.get_connection_status(current_user.email)
            if status.get("connected"):
                google_event_id = await google_calendar_service.create_google_event(
                    current_user.email, task_doc
                )
                if google_event_id:
                    await tasks_collection.update_one(
                        {"_id": result.inserted_id},
                        {"$set": {
                            "google_event_id": google_event_id,
                            "synced_to_google": True,
                            "last_google_sync": now,
                        }}
                    )
                    task_doc["synced_to_google"] = True
        except Exception as e:
            logger.error(f"Failed to sync meeting to Google Calendar: {e}")

    logger.info(f"Planner {current_user.email} scheduled meeting '{data.title}' for wedding {data.wedding_id}")

    return {
        "message": "Meeting scheduled",
        "meeting": _serialize_meeting(task_doc),
    }


def _serialize_meeting(task: dict, include_planner_fields: bool = True) -> dict:
    """Consistent meeting response format. Set include_planner_fields=False for couple-facing responses."""
    result = {
        "id": str(task["_id"]),
        "title": task.get("title", ""),
        "description": task.get("description"),
        "start_date": task["start_date"].isoformat() if task.get("start_date") else None,
        "end_date": task["end_date"].isoformat() if task.get("end_date") else None,
        "is_recurring": task.get("is_recurring", False),
        "recurrence_rule": task.get("recurrence_rule"),
        "status": task.get("status", "pending"),
    }
    if include_planner_fields:
        result["reminder_minutes"] = task.get("reminder_minutes")
        result["synced_to_google"] = task.get("synced_to_google", False)
    return result


@router.get("/couple-portal/meetings", tags=["Couple Portal - Meetings"])
async def list_meetings_planner(
    wedding_id: str = Query(...),
    limit: int = Query(default=50, ge=1, le=200),
    skip: int = Query(default=0, ge=0),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner)
):
    """Planner lists all meetings for a wedding. Supports pagination."""
    if not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="You don't have access to this wedding")

    tasks_collection = mongo.get_planner_tasks_collection()
    query = {
        "wedding_id": wedding_id,
        "category": "meeting",
        "planner_email": current_user.email,
    }
    total = await tasks_collection.count_documents(query)
    cursor = tasks_collection.find(query).sort("start_date", 1).skip(skip).limit(limit)

    meetings = []
    async for task in cursor:
        meetings.append(_serialize_meeting(task))

    return {"meetings": meetings, "count": len(meetings), "total": total}


@router.delete("/couple-portal/meetings/{meeting_id}", tags=["Couple Portal - Meetings"])
async def cancel_meeting(
    meeting_id: str = Path(...),
    wedding_id: str = Query(...),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner)
):
    """Planner cancels a scheduled meeting. Removes from Google Calendar if synced."""
    if not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="You don't have access to this wedding")

    try:
        ObjectId(meeting_id)
    except (InvalidId, Exception):
        raise HTTPException(status_code=400, detail="Invalid meeting ID format")

    tasks_collection = mongo.get_planner_tasks_collection()
    task = await tasks_collection.find_one({
        "_id": ObjectId(meeting_id),
        "planner_email": current_user.email,
        "wedding_id": wedding_id,
        "category": "meeting",
    })
    if not task:
        raise HTTPException(status_code=404, detail="Meeting not found")

    # Remove from Google Calendar if synced
    if task.get("synced_to_google") and task.get("google_event_id"):
        try:
            from app.services.google_calendar_service import google_calendar_service
            await google_calendar_service.delete_google_event(
                current_user.email, task["google_event_id"]
            )
        except Exception as e:
            logger.error(f"Failed to delete meeting from Google Calendar: {e}")

    await tasks_collection.delete_one({"_id": ObjectId(meeting_id)})

    logger.info(f"Planner {current_user.email} cancelled meeting {meeting_id}")
    return {"message": "Meeting cancelled"}


# --- Couple-side meeting endpoints ---

@router.get("/couple/portal/meetings", tags=["Couple Portal - Meetings"])
async def list_meetings_couple(couple: dict = Depends(require_couple_auth)):
    """Couple views their upcoming meetings with the planner."""
    if couple.get("wedding_archived"):
        return {"meetings": [], "count": 0}

    wedding_id = couple.get("wedding_id")
    planner_email = couple.get("planner_email")

    if not planner_email:
        # Fallback: look up from wedding
        wedding = await mongo.get_weddings_collection().find_one(
            {"_id": wedding_id}, {"assigned_planner_email": 1}
        )
        planner_email = wedding.get("assigned_planner_email") if wedding else None

    if not planner_email:
        return {"meetings": [], "count": 0}

    tasks_collection = mongo.get_planner_tasks_collection()
    now = datetime.now(timezone.utc)
    cursor = tasks_collection.find({
        "wedding_id": wedding_id,
        "category": "meeting",
        "planner_email": planner_email,
        "start_date": {"$gte": now},
    }).sort("start_date", 1).limit(20)

    meetings = []
    async for task in cursor:
        meetings.append(_serialize_meeting(task, include_planner_fields=False))

    return {"meetings": meetings, "count": len(meetings)}


# ============================================================================
# SPRINT 6: REGISTRY CRUD (Couple + Planner shared access)
# ============================================================================

class RegistryItemRequest(BaseModel):
    """Request model for adding/updating a registry item."""
    name: str = Field(..., min_length=1, max_length=200, description="Registry name (e.g., 'Target', 'Amazon')")
    url: str = Field(..., min_length=1, max_length=2000, description="Registry URL")
    color: Optional[str] = Field(default="bg-gray-600", description="Button color class")


@router.get("/couple/portal/registries", tags=["Couple Portal - Registry"])
async def list_registries_couple(couple: dict = Depends(require_couple_auth)):
    """Couple views their wedding registries."""
    if couple.get("wedding_archived"):
        return {"registries": []}

    wedding_id = couple.get("wedding_id")
    wedding = await mongo.get_weddings_collection().find_one(
        {"_id": wedding_id}, {"registries": 1}
    )
    if not wedding:
        raise HTTPException(status_code=404, detail="Wedding not found")

    return {"registries": wedding.get("registries", [])}


@router.post("/couple/portal/registries", tags=["Couple Portal - Registry"])
async def add_registry_couple(body: RegistryItemRequest, couple: dict = Depends(require_couple_auth)):
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
        {"_id": wedding_oid},
        {"$push": {"registries": registry_item}}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Wedding not found")

    logger.info(f"Couple {couple['email']} added registry '{body.name}' to wedding {wedding_id}")
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

    result = await mongo.get_weddings_collection().update_one(
        {"_id": wedding_oid},
        {"$set": {f"registries.{index}": updated_item}}
    )

    logger.info(f"Couple {couple['email']} updated registry[{index}] in wedding {wedding_id}")
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
        {"_id": wedding_oid},
        {"$set": {"registries": registries}}
    )

    logger.info(f"Couple {couple['email']} deleted registry '{removed_name}' from wedding {wedding_id}")
    return {"message": "Registry deleted"}


# ============================================================================
# SPRINT 6: FAQ CRUD (Couple + Planner shared access)
# ============================================================================

class FAQItemRequest(BaseModel):
    """Request model for adding/updating an FAQ item."""
    question: str = Field(..., min_length=1, max_length=500, description="FAQ question")
    answer: str = Field(..., min_length=1, max_length=5000, description="FAQ answer")
    link_url: Optional[str] = Field(default=None, max_length=2000, description="Optional CTA link URL")
    link_label: Optional[str] = Field(default=None, max_length=200, description="Optional CTA link label")


@router.get("/couple/portal/faqs", tags=["Couple Portal - FAQ"])
async def list_faqs_couple(couple: dict = Depends(require_couple_auth)):
    """Couple views their wedding FAQs."""
    if couple.get("wedding_archived"):
        return {"faqs": []}

    wedding_id = couple.get("wedding_id")
    wedding = await mongo.get_weddings_collection().find_one(
        {"_id": wedding_id}, {"faqs": 1}
    )
    if not wedding:
        raise HTTPException(status_code=404, detail="Wedding not found")

    return {"faqs": wedding.get("faqs", [])}


@router.post("/couple/portal/faqs", tags=["Couple Portal - FAQ"])
async def add_faq_couple(body: FAQItemRequest, couple: dict = Depends(require_couple_auth)):
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
        {"_id": wedding_oid},
        {"$push": {"faqs": faq_item}}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Wedding not found")

    logger.info(f"Couple {couple['email']} added FAQ '{body.question[:50]}' to wedding {wedding_id}")
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
        {"_id": wedding_oid},
        {"$set": {f"faqs.{index}": updated_item}}
    )

    logger.info(f"Couple {couple['email']} updated FAQ[{index}] in wedding {wedding_id}")
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
        {"_id": wedding_oid},
        {"$set": {"faqs": faqs}}
    )

    logger.info(f"Couple {couple['email']} deleted FAQ '{removed_q}' from wedding {wedding_id}")
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
            headers={"Content-Disposition": "inline; filename=portal-qr.png"}
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
        user_id=couple["email"],
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
        user_id=couple["email"],
        endpoint=body.endpoint,
    )

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
    count = await collection.count_documents({"user_id": couple["email"]})

    return {
        "enabled": True,
        "subscribed": count > 0,
        "subscription_count": count,
        "vapid_public_key": web_push_service.get_public_key(),
    }
