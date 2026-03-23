"""
Couple Portal API Routes

Endpoints for the couple's dashboard portal.
Includes couple-facing endpoints (require couple auth) and planner-facing
management endpoints (require planner auth).

Sprint 1: Dashboard, events, forms, updates
Sprint 2: Order-of-events CRUD, collaborative notes, contract review
"""
from fastapi import APIRouter, HTTPException, Request, Query, Depends, Path
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone
from app.core.database import mongo
from app.services.couple_portal_service import couple_portal_service
from app.dependencies.auth_extended import (
    ExtendedAuthUser, require_team_or_planner, enforce_team_permission, check_wedding_access
)
from app.dependencies.couple_auth import require_couple_auth
from bson import ObjectId
import uuid
import logging

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
    wedding = await mongo.get_weddings_collection().find_one({"_id": ObjectId(couple["wedding_id"])})
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

    # Notify planner
    try:
        planner_email = couple.get("planner_email")
        if planner_email:
            couple_name = f"{couple.get('partner1_name', '')} & {couple.get('partner2_name', '')}".strip(" &")
            await mongo.db["planner_notifications"].insert_one({
                "planner_email": planner_email,
                "type": "form_submission",
                "title": f"{couple_name} submitted \"{form.get('title', 'a form')}\"",
                "message": f"Your couple has {'updated' if existing else 'submitted'} the form \"{form.get('title')}\". Review their responses in your dashboard.",
                "link": f"/admin/forms?wedding_id={couple['wedding_id']}",
                "read": False,
                "created_at": datetime.now(timezone.utc)
            })
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
    wedding = await mongo.get_weddings_collection().find_one({"_id": ObjectId(wedding_id)})
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
    wedding = await mongo.get_weddings_collection().find_one({"_id": ObjectId(couple["wedding_id"])})
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
    wedding = await mongo.get_weddings_collection().find_one({"_id": ObjectId(couple["wedding_id"])})
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
    """Send a planner notification when the couple leaves a note. Reuses planner_notifications collection."""
    try:
        planner_email = couple.get("planner_email") or wedding.get("assigned_planner_email")
        if not planner_email:
            return
        couple_name = f"{couple.get('partner1_name', '')} & {couple.get('partner2_name', '')}".strip(" &")
        preview = text[:100] + ("..." if len(text) > 100 else "")
        await mongo.db["planner_notifications"].insert_one({
            "planner_email": planner_email,
            "type": "couple_note",
            "title": f"{couple_name}: {title}",
            "message": preview,
            "link": f"/admin/couple-portal?wedding_id={couple.get('wedding_id')}",
            "read": False,
            "created_at": datetime.now(timezone.utc),
        })
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
