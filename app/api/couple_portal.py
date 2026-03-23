"""
Couple Portal API Routes

Endpoints for the couple's dashboard portal.
All endpoints require couple authentication.
"""
from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone
from app.core.database import mongo
from app.services.couple_portal_service import couple_portal_service
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================================
# AUTH HELPER
# ============================================================================

async def get_authenticated_couple(request: Request) -> dict:
    """Extract and validate couple from JWT token."""
    from app.utils.auth_utils import verify_token

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = auth_header.split(" ")[1]
    try:
        payload = verify_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    email = payload.get("sub")
    role = payload.get("role")

    if role != "couple":
        raise HTTPException(status_code=403, detail="Couple access required")

    couple = await mongo.db["couple_users"].find_one({"email": email, "is_active": True})
    if not couple:
        raise HTTPException(status_code=404, detail="Couple account not found")

    return couple


# ============================================================================
# DASHBOARD ENDPOINTS
# ============================================================================

@router.get("/couple/portal/dashboard", tags=["Couple Portal"])
async def get_dashboard(request: Request):
    """Get the couple's portal dashboard with all data."""
    couple = await get_authenticated_couple(request)

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
async def get_events(request: Request):
    """Get wedding events/timeline."""
    couple = await get_authenticated_couple(request)
    wedding = await mongo.get_weddings_collection().find_one({"_id": ObjectId(couple["wedding_id"])})
    if not wedding:
        raise HTTPException(status_code=404, detail="Wedding not found")

    return {
        "events": [
            {
                "type": e.get("type"),
                "date": e.get("date"),
                "details": e.get("details")
            }
            for e in wedding.get("events", [])
        ],
        "wedding_date": wedding.get("date"),
        "timezone": wedding.get("timezone", "America/Chicago")
    }


@router.get("/couple/portal/updates", tags=["Couple Portal"])
async def get_updates(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    skip: int = Query(0, ge=0)
):
    """Get planner updates for the couple."""
    couple = await get_authenticated_couple(request)

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
async def submit_form(data: FormSubmissionRequest, request: Request):
    """Couple submits a form shared by the planner."""
    couple = await get_authenticated_couple(request)

    # Verify form exists and is shared with couple
    form = await mongo.db["forms"].find_one({
        "_id": ObjectId(data.form_id),
        "wedding_id": couple["wedding_id"]
    })

    if not form:
        raise HTTPException(status_code=404, detail="Form not found")

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
async def get_form_details(form_id: str, request: Request):
    """Get a specific form with its fields for the couple to fill out."""
    couple = await get_authenticated_couple(request)

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
    request: Request
):
    """
    Planner creates an update for the couple's portal.
    Requires planner authentication.
    """
    from app.dependencies.auth_extended import get_current_user_extended, check_wedding_access
    from fastapi.security import HTTPBearer

    # Auth check for planner
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    from app.utils.auth_utils import verify_token
    token = auth_header.split(" ")[1]
    try:
        payload = verify_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    email = payload.get("sub")
    role = payload.get("role")

    if role not in ("wedding_planner", "ROOT_ADMIN", "team_member"):
        raise HTTPException(status_code=403, detail="Planner access required")

    # Get planner name
    planner = await mongo.get_users_collection().find_one({"email": email})
    planner_name = "Your Planner"
    if planner:
        planner_name = f"{planner.get('first_name', '')} {planner.get('last_name', '')}".strip()
        if not planner_name:
            planner_name = planner.get("company_name", email)

    update_doc = {
        "wedding_id": data.wedding_id,
        "title": data.title,
        "content": data.content,
        "type": data.type,
        "category": data.category,
        "is_milestone": data.is_milestone,
        "attachments": data.attachments,
        "created_by": email,
        "created_by_name": planner_name,
        "created_at": datetime.now(timezone.utc),
    }

    result = await mongo.db["couple_updates"].insert_one(update_doc)

    logger.info(f"Couple update created for wedding {data.wedding_id} by {email}")

    return {
        "message": "Update created successfully",
        "update_id": str(result.inserted_id)
    }
