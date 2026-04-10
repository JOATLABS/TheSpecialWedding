"""
Testimonials / Customer Reviews CRUD API

Provides dedicated endpoints for managing customer testimonials displayed
on the SaaS landing page.  ROOT_ADMIN endpoints require authentication;
the public listing endpoint is unauthenticated so the landing page can
fetch reviews at runtime.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.database import mongo
from app.dependencies.auth_extended import ExtendedAuthUser, require_root_admin

router = APIRouter()

COLLECTION = "testimonials"

# ── Default seed data (matches the hardcoded values in app/page.tsx) ──────────

DEFAULT_TESTIMONIALS: List[Dict[str, Any]] = [
    {
        "name": "Maya Glenn",
        "company": "Aurora Collective",
        "role": "Director of Events",
        "quote": (
            "I used to juggle Google Sheets for guests, QuickBooks for budgets, and "
            "DocuSign for contracts \u2014 all disconnected. Now my 240-person guest list, "
            "seating chart, and budget tracker live in one place. Last Saturday I "
            "reassigned three tables in the seating orchestrator ten minutes before "
            "doors opened and guest memories were already flowing into the couple "
            "portal before dinner."
        ),
        "is_active": True,
        "display_order": 1,
        "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
    },
    {
        "name": "Elias Romero",
        "company": "Harbor & Bloom",
        "role": "Lead Coordinator",
        "quote": (
            "Building a service package with AI-suggested pricing took me ten minutes "
            "instead of a full afternoon of market research. I sent the quote through "
            "the contract canvas with e-sign the same day, and the client\u2019s milestone "
            "payment hit my dashboard before dinner. The entire book-to-pay cycle that "
            "used to take me a week now happens in a single session."
        ),
        "is_active": True,
        "display_order": 2,
        "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
    },
    {
        "name": "Priya Chandran",
        "company": "Verdant Celebrations",
        "role": "Senior Planner",
        "quote": (
            "Coordinating twelve vendors across two venues was a nightmare of group "
            "texts and missed emails. Now every florist, caterer, and photographer has "
            "role-based access to the timeline, uploads deliverables to the gallery, "
            "and signs off on contracts inside the platform. The automated reminders "
            "alone saved me from three near-disasters last season."
        ),
        "is_active": True,
        "display_order": 3,
        "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
    },
    {
        "name": "Tom\u00e1s Vega",
        "company": "D\u00eda Perfecto Weddings",
        "role": "Founder",
        "quote": (
            "We run fifteen weddings a month and the planning calendar synced with "
            "Google Calendar keeps my team sane. I set up intake forms for new couples "
            "in the forms canvas, the RSVP reminders go out automatically by SMS and "
            "email, and every wedding has its own branded configuration so clients feel "
            "like they have a dedicated app. The knowledge base even onboards our "
            "junior planners faster than I can."
        ),
        "is_active": True,
        "display_order": 4,
        "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
    },
]


# ── Pydantic schemas ─────────────────────────────────────────────────────────


class TestimonialCreate(BaseModel):
    name: str = Field(
        ..., min_length=1, max_length=200, description="Reviewer full name"
    )
    company: str = Field("", max_length=200, description="Company / organisation name")
    role: str = Field("", max_length=200, description="Job title or role")
    quote: str = Field(
        ..., min_length=1, max_length=2000, description="Testimonial text"
    )
    avatar_url: Optional[str] = Field(
        None, max_length=500, description="Optional avatar image URL"
    )
    is_active: bool = Field(True, description="Show on landing page")
    display_order: int = Field(0, description="Sort priority (lower = first)")


class TestimonialUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    company: Optional[str] = Field(None, max_length=200)
    role: Optional[str] = Field(None, max_length=200)
    quote: Optional[str] = Field(None, min_length=1, max_length=2000)
    avatar_url: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None
    display_order: Optional[int] = None


# ── Helpers ───────────────────────────────────────────────────────────────────


def _serialize(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a MongoDB document to a JSON-safe dict."""
    doc["_id"] = str(doc["_id"])
    for key in ("created_at", "updated_at"):
        if isinstance(doc.get(key), datetime):
            doc[key] = doc[key].isoformat()
    return doc


async def _ensure_seeded() -> None:
    """Insert default testimonials if the collection is empty.

    Uses per-document upserts keyed on ``name + company`` to avoid
    duplicating seed data when concurrent requests both see an empty
    collection (classic check-then-act race condition).
    """
    count = await mongo.db[COLLECTION].count_documents({})
    if count == 0:
        for t in DEFAULT_TESTIMONIALS:
            await mongo.db[COLLECTION].update_one(
                {"name": t["name"], "company": t["company"]},
                {"$setOnInsert": dict(t)},
                upsert=True,
            )


# ── Public endpoint (no auth — consumed by landing page) ─────────────────────


@router.get("/public/testimonials", tags=["Public"])
async def list_public_testimonials():
    """Return active testimonials for the public landing page."""
    try:
        await _ensure_seeded()
        cursor = mongo.db[COLLECTION].find({"is_active": True}).sort("display_order", 1)
        docs = await cursor.to_list(length=50)
        return [_serialize(d) for d in docs]
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Error fetching testimonials: {exc}"
        )


# ── Admin CRUD (ROOT_ADMIN only) ─────────────────────────────────────────────


@router.get("/testimonials", tags=["ROOT_ADMIN"])
async def list_testimonials(
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """List all testimonials (active + inactive) for admin management."""
    try:
        await _ensure_seeded()
        cursor = mongo.db[COLLECTION].find({}).sort("display_order", 1)
        docs = await cursor.to_list(length=200)
        return [_serialize(d) for d in docs]
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Error fetching testimonials: {exc}"
        )


@router.post("/testimonials", tags=["ROOT_ADMIN"])
async def create_testimonial(
    body: TestimonialCreate,
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Create a new customer testimonial."""
    try:
        now = datetime.now(timezone.utc)
        doc = body.model_dump()
        doc.update(
            created_by=current_user.email,
            created_at=now,
            updated_at=now,
        )
        result = await mongo.db[COLLECTION].insert_one(doc)
        return {"message": "Testimonial created", "_id": str(result.inserted_id)}
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Error creating testimonial: {exc}"
        )


@router.put("/testimonials/{testimonial_id}", tags=["ROOT_ADMIN"])
async def update_testimonial(
    testimonial_id: str,
    body: TestimonialUpdate,
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Update an existing testimonial."""
    try:
        if not ObjectId.is_valid(testimonial_id):
            raise HTTPException(status_code=400, detail="Invalid testimonial ID")

        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        updates["updated_by"] = current_user.email
        updates["updated_at"] = datetime.now(timezone.utc)

        result = await mongo.db[COLLECTION].update_one(
            {"_id": ObjectId(testimonial_id)},
            {"$set": updates},
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Testimonial not found")

        return {"message": "Testimonial updated"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Error updating testimonial: {exc}"
        )


@router.delete("/testimonials/{testimonial_id}", tags=["ROOT_ADMIN"])
async def delete_testimonial(
    testimonial_id: str,
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Permanently delete a testimonial."""
    try:
        if not ObjectId.is_valid(testimonial_id):
            raise HTTPException(status_code=400, detail="Invalid testimonial ID")

        result = await mongo.db[COLLECTION].delete_one(
            {"_id": ObjectId(testimonial_id)}
        )
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Testimonial not found")

        return {"message": "Testimonial deleted"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Error deleting testimonial: {exc}"
        )


@router.put("/testimonials/{testimonial_id}/toggle", tags=["ROOT_ADMIN"])
async def toggle_testimonial(
    testimonial_id: str,
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Toggle a testimonial's active/inactive status."""
    try:
        if not ObjectId.is_valid(testimonial_id):
            raise HTTPException(status_code=400, detail="Invalid testimonial ID")

        doc = await mongo.db[COLLECTION].find_one({"_id": ObjectId(testimonial_id)})
        if not doc:
            raise HTTPException(status_code=404, detail="Testimonial not found")

        new_status = not doc.get("is_active", True)
        await mongo.db[COLLECTION].update_one(
            {"_id": ObjectId(testimonial_id)},
            {
                "$set": {
                    "is_active": new_status,
                    "updated_by": current_user.email,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        return {
            "message": f"Testimonial {'activated' if new_status else 'deactivated'}",
            "is_active": new_status,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Error toggling testimonial: {exc}"
        )
