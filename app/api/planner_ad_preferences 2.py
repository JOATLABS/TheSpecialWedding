"""
Planner Ad Preferences API Router

REST API for planners to manage their ad preferences:
- Hide specific vendors
- Suppress vendor categories
- Toggle reduced frequency mode ("Show fewer sponsored vendors")

These preferences are respected by the sponsored cards serving logic.

Routes: /planner/ads/preferences/*

Auth model:
- GET ``/preferences`` is open to any authenticated planner, root admin,
  or team member so the rail can render the current hide/suppress state
  regardless of whether the team member can mutate it.
- All mutation endpoints require ``manage_vendors`` — planners and root
  admins always pass; team members need the permission granted on their
  team_permissions record.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends

from app.core.database import mongo
from app.dependencies.auth_extended import (
    ExtendedAuthUser,
    get_current_user_extended,
    require_team_permission,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/planner/ads/preferences", tags=["Planner Ad Preferences"])


def _get_planner_id(user: ExtendedAuthUser) -> str:
    """Extract a stable planner identifier for ad preference records."""
    if user.parent_planner_id:
        return str(user.parent_planner_id)

    data = user.user_data or {}
    uid = data.get("_id")
    return str(uid) if uid else user.email


# =============================================================================
# GET PREFERENCES
# =============================================================================


@router.get(
    "",
    summary="Get ad preferences",
    description="Returns the planner's current ad preferences (hidden vendors, suppressed categories, frequency).",
)
async def get_preferences(
    user: ExtendedAuthUser = Depends(get_current_user_extended),
):
    planner_id = _get_planner_id(user)
    doc = await mongo.db["planner_ad_preferences"].find_one({"planner_id": planner_id})
    if not doc:
        return {
            "planner_id": planner_id,
            "hidden_vendor_ids": [],
            "suppressed_categories": [],
            "reduced_frequency": False,
        }
    doc.pop("_id", None)
    return doc


# =============================================================================
# HIDE VENDOR
# =============================================================================


@router.post(
    "/hide-vendor",
    summary="Hide a vendor",
    description="Hide a specific vendor from this planner's sponsored rail. Vendor will never be shown again.",
)
async def hide_vendor(
    vendor_id: str = Body(..., embed=True),
    user: ExtendedAuthUser = Depends(require_team_permission("manage_vendors")),
):
    planner_id = _get_planner_id(user)
    now = datetime.now(timezone.utc)

    await mongo.db["planner_ad_preferences"].update_one(
        {"planner_id": planner_id},
        {
            "$addToSet": {"hidden_vendor_ids": vendor_id},
            "$set": {"updated_at": now},
            "$setOnInsert": {
                "planner_id": planner_id,
                "suppressed_categories": [],
                "reduced_frequency": False,
            },
        },
        upsert=True,
    )

    # Record the dismiss event
    await mongo.db["ad_events"].insert_one(
        {
            "event_type": "dismiss",
            "planner_id": planner_id,
            "vendor_id": vendor_id,
            "created_at": now,
        }
    )

    logger.info(f"Planner {planner_id} hid vendor {vendor_id}")
    return {"status": "hidden", "vendor_id": vendor_id}


# =============================================================================
# UNHIDE VENDOR (undo)
# =============================================================================


@router.post(
    "/unhide-vendor",
    summary="Unhide a vendor",
    description="Remove a vendor from the hidden list.",
)
async def unhide_vendor(
    vendor_id: str = Body(..., embed=True),
    user: ExtendedAuthUser = Depends(require_team_permission("manage_vendors")),
):
    planner_id = _get_planner_id(user)

    await mongo.db["planner_ad_preferences"].update_one(
        {"planner_id": planner_id},
        {
            "$pull": {"hidden_vendor_ids": vendor_id},
            "$set": {"updated_at": datetime.now(timezone.utc)},
        },
    )
    return {"status": "unhidden", "vendor_id": vendor_id}


# =============================================================================
# SUPPRESS CATEGORY
# =============================================================================


@router.post(
    "/suppress-category",
    summary="Suppress a vendor category",
    description="Stop showing sponsored vendors from a specific category (e.g., photographer already booked).",
)
async def suppress_category(
    category: str = Body(..., embed=True),
    user: ExtendedAuthUser = Depends(require_team_permission("manage_vendors")),
):
    planner_id = _get_planner_id(user)
    now = datetime.now(timezone.utc)

    await mongo.db["planner_ad_preferences"].update_one(
        {"planner_id": planner_id},
        {
            "$addToSet": {"suppressed_categories": category},
            "$set": {"updated_at": now},
            "$setOnInsert": {
                "planner_id": planner_id,
                "hidden_vendor_ids": [],
                "reduced_frequency": False,
            },
        },
        upsert=True,
    )

    # Record the category suppression event
    await mongo.db["ad_events"].insert_one(
        {
            "event_type": "category_suppressed",
            "planner_id": planner_id,
            "category": category,
            "created_at": now,
        }
    )

    return {"status": "suppressed", "category": category}


# =============================================================================
# UNSUPPRESS CATEGORY
# =============================================================================


@router.post(
    "/unsuppress-category",
    summary="Unsuppress a vendor category",
    description="Resume showing sponsored vendors from a category.",
)
async def unsuppress_category(
    category: str = Body(..., embed=True),
    user: ExtendedAuthUser = Depends(require_team_permission("manage_vendors")),
):
    planner_id = _get_planner_id(user)

    await mongo.db["planner_ad_preferences"].update_one(
        {"planner_id": planner_id},
        {
            "$pull": {"suppressed_categories": category},
            "$set": {"updated_at": datetime.now(timezone.utc)},
        },
    )
    return {"status": "unsuppressed", "category": category}


# =============================================================================
# TOGGLE REDUCED FREQUENCY
# =============================================================================


@router.put(
    "/frequency",
    summary="Toggle reduced ad frequency",
    description="Toggle 'Show fewer sponsored vendors' — when on, max 1 card shown instead of 3.",
)
async def toggle_frequency(
    reduced_frequency: bool = Body(..., embed=True),
    user: ExtendedAuthUser = Depends(require_team_permission("manage_vendors")),
):
    planner_id = _get_planner_id(user)
    now = datetime.now(timezone.utc)

    await mongo.db["planner_ad_preferences"].update_one(
        {"planner_id": planner_id},
        {
            "$set": {"reduced_frequency": reduced_frequency, "updated_at": now},
            "$setOnInsert": {
                "planner_id": planner_id,
                "hidden_vendor_ids": [],
                "suppressed_categories": [],
            },
        },
        upsert=True,
    )

    logger.info(f"Planner {planner_id} set reduced_frequency={reduced_frequency}")
    return {"status": "updated", "reduced_frequency": reduced_frequency}
