import inspect
import logging
from typing import Any, Literal

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.database import mongo
from app.dependencies.auth_extended import (
    ExtendedAuthUser,
    check_wedding_access,
    enforce_team_permission,
    require_wedding_planner_only,
)
from app.models.guest import CreateGuestRequest, UpdateGuestRequest
from app.services.activity_log_service import activity_log_service
from app.services.guest_service import GuestService
from app.services.sse_manager import sse_manager
from app.utils.query_validation import validated_string_filter
from app.utils.response import dict_response
from app.utils.rsvp_status import GUEST_RSVP_STATUS_FILTERS, RSVP_FILTER_ALL

logger = logging.getLogger(__name__)

router = APIRouter()

guest_service = GuestService()


# =========================================================================
# SEATING CONSTRAINT MODELS
# =========================================================================


class SeatingConstraintRequest(BaseModel):
    """Request to add or remove a seating constraint between two guests"""

    guest_id_1: str = Field(..., description="First guest ID")
    guest_id_2: str = Field(..., description="Second guest ID")
    constraint_type: Literal["must_sit_together", "must_sit_apart"] = Field(
        ..., description="Type of constraint"
    )
    action: Literal["add", "remove"] = Field(
        ..., description="Add or remove the constraint"
    )


class BulkSeatingConstraintRequest(BaseModel):
    """Bulk update seating constraints"""

    constraints: list[SeatingConstraintRequest] = Field(
        ..., description="List of constraints to apply"
    )


@router.get("/invite/{token}", tags=["Guest"])
async def get_guest(token: str, wedding_id: str = Query(...)):
    try:
        return await guest_service.get_guest_by_token(token, wedding_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error getting guest by token: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unexpected error occurred")


@router.get("/invite/search", tags=["Guest"])
async def search_guest(
    wedding_id: str = Query(..., description="Wedding ID to search within"),
    phone: str | None = Query(None, description="Guest phone number"),
    name: str | None = Query(None, description="Guest name"),
    current_user: ExtendedAuthUser = Depends(require_wedding_planner_only),
):
    """
    Search for a guest by phone or name within a specific wedding.
    Requires authentication and wedding access.
    """
    # Verify user has access to this wedding
    if not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")

    try:
        # Validate search parameters
        phone = validated_string_filter(phone, max_length=20)
        name = validated_string_filter(name, max_length=100)

        return await guest_service.get_guest_by_phone_or_name(
            phone=phone, name=name, wedding_id=wedding_id
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error searching guests: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unexpected error occurred")


@router.get("/guests", tags=["Admin"])
async def list_guests(
    wedding_id: str = Query(...),
    page: int = Query(1, ge=1, le=10000, description="Page number (1-indexed)"),
    limit: int = Query(50, ge=1, le=100, description="Number of guests per page"),
    fetch_all: bool = Query(
        False, description="Return all matching guests without pagination"
    ),
    name: str | None = Query(None, description="Filter by guest name"),
    email: str | None = Query(None, description="Filter by guest email"),
    phone: str | None = Query(None, description="Filter by guest phone"),
    group_id: str | None = Query(None, description="Filter by guest group"),
    role: str | None = Query(None, description="Filter by guest role"),
    rsvp_status: str | None = Query(None, description="Filter by RSVP status"),
    plus_one_status: str | None = Query(None, description="Filter by plus-one status"),
    phone_issue: str | None = Query(None, description="Filter by phone/contact issue"),
    sms_status: str | None = Query(None, description="Filter by SMS opt-in status"),
    sort_field: str | None = Query("name", description="Sort field"),
    sort_direction: str | None = Query("asc", description="Sort direction"),
    current_user: ExtendedAuthUser = Depends(require_wedding_planner_only),
):
    # Check if user has access to this wedding
    if not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")
    try:
        validated_name = validated_string_filter(name, max_length=100)
        validated_email = validated_string_filter(email, max_length=100)
        validated_phone = validated_string_filter(phone, max_length=30)
        validated_group_id = validated_string_filter(group_id, max_length=100)
        validated_role = validated_string_filter(role, max_length=50)
        validated_rsvp_status = (
            rsvp_status if rsvp_status in GUEST_RSVP_STATUS_FILTERS else RSVP_FILTER_ALL
        )
        validated_plus_one_status = (
            plus_one_status
            if plus_one_status in {"all", "allowed", "submitted", "none"}
            else "all"
        )
        validated_phone_issue = (
            phone_issue
            if phone_issue in {"all", "invalid_or_unreachable", "no_contact"}
            else "all"
        )
        validated_sms_status = (
            sms_status if sms_status in {"all", "opted_in", "opted_out"} else "all"
        )
        validated_sort_field = (
            sort_field
            if sort_field
            in {
                "name",
                "email",
                "phone",
                "role",
                "group_id",
                "rsvp_status",
                "plus_ones",
            }
            else "name"
        )
        validated_sort_direction = "desc" if sort_direction == "desc" else "asc"

        return await guest_service.list_guests_by_wedding(
            wedding_id,
            page=page,
            limit=limit,
            fetch_all=fetch_all,
            name=validated_name,
            email=validated_email,
            phone=validated_phone,
            group_id=validated_group_id,
            role=validated_role,
            rsvp_status=validated_rsvp_status,
            plus_one_status=validated_plus_one_status,
            phone_issue=validated_phone_issue,
            sms_status=validated_sms_status,
            sort_field=validated_sort_field,
            sort_direction=validated_sort_direction,
        )
    except HTTPException as e:
        raise e
    except Exception:
        raise HTTPException(status_code=500, detail="Unexpected error occurred")


@router.put("/guests/{guest_id}", tags=["Admin"])
async def update_guest(
    guest_id: str,
    update_data: UpdateGuestRequest,
    current_user: ExtendedAuthUser = Depends(require_wedding_planner_only),
):
    """Update guest information. Only updateable fields: name, phone, email, group_id, role, plus_one settings."""
    enforce_team_permission(current_user, "manage_guests")
    # Get guest to check wedding access
    guest = await guest_service.get_guest(guest_id)
    if inspect.isawaitable(guest):
        guest = await guest
    if not await check_wedding_access(current_user, guest.get("wedding_id")):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")
    try:
        # Convert Pydantic model to dict, excluding unset fields
        update_dict = update_data.model_dump(exclude_unset=True)
        result = await guest_service.update_guest(guest_id, update_dict)

        # Log activity for planner dashboard
        try:
            await activity_log_service.log_guest_updated(
                wedding_id=guest.get("wedding_id"),
                guest_name=(result or {}).get("name", guest.get("name", "Unknown")),
                planner_email=current_user.email,
                guest_id=guest_id,
                changes=update_dict,
                updated_by=current_user.email,
            )
        except Exception as log_err:
            logger.warning(f"Failed to log guest update activity: {log_err}")

        # Notify connected clients so they see the change instantly
        await sse_manager.broadcast_data_change(
            current_user.email,
            "guest",
            "updated",
            wedding_id=str(guest.get("wedding_id", "")),
            record_id=guest_id,
        )

        return result
    except HTTPException as e:
        raise e
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Failed to update guest: {err!s}")


@router.delete("/guests/{guest_id}", tags=["Admin"])
async def delete_guest(
    guest_id: str,
    current_user: ExtendedAuthUser = Depends(require_wedding_planner_only),
):
    enforce_team_permission(current_user, "manage_guests")
    # Get guest to check wedding access
    guest = await guest_service.get_guest(guest_id)
    if inspect.isawaitable(guest):
        guest = await guest
    if not await check_wedding_access(current_user, guest.get("wedding_id")):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")
    try:
        result = await guest_service.delete_guest(guest_id)

        # Log activity for planner dashboard
        try:
            await activity_log_service.log_guest_deleted(
                wedding_id=guest.get("wedding_id"),
                guest_name=guest.get("name", "Unknown"),
                planner_email=current_user.email,
                guest_id=guest_id,
                deleted_by=current_user.email,
            )
        except Exception as log_err:
            logger.warning(f"Failed to log guest delete activity: {log_err}")

        await sse_manager.broadcast_data_change(
            current_user.email,
            "guest",
            "deleted",
            wedding_id=str(guest.get("wedding_id", "")),
            record_id=guest_id,
        )

        return result
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error deleting guest: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unexpected error occurred")


@router.post("/guests", tags=["Admin"])
async def create_guest(
    guest_data: CreateGuestRequest,
    wedding_id: str = Query(...),
    current_user: ExtendedAuthUser = Depends(require_wedding_planner_only),
):
    """Create a single guest for a wedding."""
    enforce_team_permission(current_user, "manage_guests")
    # Check if user has access to this wedding
    if not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")
    try:
        result = await guest_service.create_guest(guest_data, wedding_id)

        # Log activity for planner dashboard
        try:
            await activity_log_service.log_guest_added(
                wedding_id=wedding_id,
                guest_name=result.get("name", guest_data.name),
                planner_email=current_user.email,
                guest_id=result.get("id"),
                guest_email=result.get("email"),
                added_by=current_user.email,
            )
        except Exception as log_err:
            logger.warning(f"Failed to log guest create activity: {log_err}")

        await sse_manager.broadcast_data_change(
            current_user.email,
            "guest",
            "created",
            wedding_id=wedding_id,
            record_id=result.get("id"),
        )

        return result
    except HTTPException as e:
        raise e
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Failed to create guest: {err!s}")


# =========================================================================
# GUEST ACTIVITY LOG
# =========================================================================


@router.get("/guests/{guest_id}/activity", tags=["Admin"])
async def get_guest_activity(
    guest_id: str,
    limit: int = Query(
        default=30, ge=1, le=100, description="Max number of activity entries"
    ),
    current_user: ExtendedAuthUser = Depends(require_wedding_planner_only),
):
    """
    Get activity log for a specific guest.

    Searches activity_logs by:
    - metadata.guest_id matching the guest_id
    - metadata.guest_name matching the guest's name
    - Message text containing the guest's name

    Returns activities sorted by most recent first.
    """
    # Get guest to check wedding access and get guest name
    guest = await guest_service.get_guest(guest_id)
    if inspect.isawaitable(guest):
        guest = await guest
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")
    if not await check_wedding_access(current_user, guest.get("wedding_id")):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")

    try:
        activity_collection = mongo.get_collection("activity_logs")
        guest_name = guest.get("name", "")
        wedding_id = guest.get("wedding_id", "")

        # Build query: match by guest_id in metadata OR guest_name in metadata/message
        # Scoped to the same wedding.
        #
        # IMPORTANT: only add `metadata.guest_email` to the OR if we actually
        # have a non-empty email. Adding `{"metadata.guest_email": None}`
        # would match every activity_log row that lacks that field — which is
        # almost all of them — and bleed the entire wedding's activity into
        # this guest's view.
        or_conditions: list[dict[str, Any]] = [
            {"metadata.guest_id": guest_id},
        ]
        if guest_name:
            or_conditions.append({"metadata.guest_name": guest_name})
        guest_email = guest.get("email")
        if guest_email:
            or_conditions.append({"metadata.guest_email": guest_email})

        query = {
            "$and": [
                {
                    "$or": [
                        {"wedding_id": wedding_id},
                        {
                            "wedding_id": (
                                ObjectId(wedding_id)
                                if ObjectId.is_valid(wedding_id)
                                else wedding_id
                            )
                        },
                    ]
                },
                {"$or": or_conditions},
            ]
        }

        cursor = (
            activity_collection.find(
                query,
                {
                    "_id": 1,
                    "type": 1,
                    "message": 1,
                    "timestamp": 1,
                    "created_at": 1,
                    "metadata": 1,
                },
            )
            .sort([("timestamp", -1), ("created_at", -1)])
            .limit(limit)
        )

        # Bounded by the limit parameter already set by caller (max 100)
        activities_raw = await cursor.to_list(length=limit)

        activities = []
        for activity in activities_raw:
            timestamp = activity.get("timestamp") or activity.get("created_at")
            if hasattr(timestamp, "isoformat"):
                timestamp = timestamp.isoformat()

            activities.append(
                {
                    "id": str(activity.get("_id")),
                    "type": activity.get("type", "info"),
                    "message": activity.get("message", ""),
                    "timestamp": timestamp or "",
                    "metadata": {
                        k: v
                        for k, v in (activity.get("metadata") or {}).items()
                        if k not in ("guest_email",)  # Don't expose emails in response
                    },
                }
            )

        return dict_response(data={"activities": activities, "total": len(activities)})

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching guest activity: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch guest activity")


# =========================================================================
# SEATING CONSTRAINTS MANAGEMENT
# =========================================================================


@router.post("/guests/seating-constraints", tags=["Admin"])
async def update_seating_constraints(
    request: BulkSeatingConstraintRequest,
    wedding_id: str = Query(...),
    current_user: ExtendedAuthUser = Depends(require_wedding_planner_only),
):
    """
    Add or remove seating constraints between guests.

    Constraint types:
    - must_sit_together: Guests must be at the same table (e.g., couples, close family)
    - must_sit_apart: Guests must NOT be at the same table (e.g., ex-partners, conflicts)

    This endpoint updates the guest records directly, which are then used
    by the AI seating optimization to create better arrangements.
    """
    enforce_team_permission(current_user, "manage_seating")
    # Check wedding access
    if not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")

    try:
        results: dict[str, list[dict[str, Any]]] = {"updated": [], "errors": []}

        guests_collection = mongo.db["guests"]

        for constraint in request.constraints:
            try:
                # Convert string IDs to ObjectId for MongoDB _id queries
                try:
                    oid_1 = ObjectId(constraint.guest_id_1)
                    oid_2 = ObjectId(constraint.guest_id_2)
                except InvalidId:
                    results["errors"].append(
                        {
                            "guest_ids": [constraint.guest_id_1, constraint.guest_id_2],
                            "error": "Invalid guest ID format",
                        }
                    )
                    continue

                # Verify both guests exist and belong to this wedding
                guest1 = await guests_collection.find_one(
                    {"_id": oid_1, "wedding_id": wedding_id}
                )
                guest2 = await guests_collection.find_one(
                    {"_id": oid_2, "wedding_id": wedding_id}
                )

                if not guest1:
                    results["errors"].append(
                        {
                            "guest_id": constraint.guest_id_1,
                            "error": "Guest not found in this wedding",
                        }
                    )
                    continue
                if not guest2:
                    results["errors"].append(
                        {
                            "guest_id": constraint.guest_id_2,
                            "error": "Guest not found in this wedding",
                        }
                    )
                    continue

                # Determine which field to update
                if constraint.constraint_type == "must_sit_together":
                    field = "must_sit_with"
                else:
                    field = "must_sit_apart"

                # Store constraint references as strings for consistent ID handling
                id_str_1 = str(oid_1)
                id_str_2 = str(oid_2)

                if constraint.action == "add":
                    # Add guest2 to guest1's constraint list and vice versa
                    await guests_collection.update_one(
                        {"_id": oid_1}, {"$addToSet": {field: id_str_2}}
                    )
                    await guests_collection.update_one(
                        {"_id": oid_2}, {"$addToSet": {field: id_str_1}}
                    )
                else:  # remove
                    # Remove from both guests' lists
                    await guests_collection.update_one(
                        {"_id": oid_1}, {"$pull": {field: id_str_2}}
                    )
                    await guests_collection.update_one(
                        {"_id": oid_2}, {"$pull": {field: id_str_1}}
                    )

                results["updated"].append(
                    {
                        "guest_id_1": constraint.guest_id_1,
                        "guest_id_2": constraint.guest_id_2,
                        "constraint_type": constraint.constraint_type,
                        "action": constraint.action,
                    }
                )

            except Exception as e:
                results["errors"].append(
                    {
                        "guest_ids": [constraint.guest_id_1, constraint.guest_id_2],
                        "error": str(e),
                    }
                )

        # Log activity
        try:
            await activity_log_service.log_activity(
                activity_type="seating_constraints_updated",
                message=f"Updated {len(results['updated'])} seating constraints",
                wedding_id=wedding_id,
                planner_email=current_user.email,
                metadata={
                    "updated_count": len(results["updated"]),
                    "error_count": len(results["errors"]),
                    "updated_by": current_user.email,
                },
            )
        except Exception as log_err:
            logger.warning(f"Failed to log seating constraints activity: {log_err}")

        return dict_response(
            data={
                "updated_count": len(results["updated"]),
                "error_count": len(results["errors"]),
                "details": results,
            },
            message="Seating constraints updated",
        )

    except Exception as err:
        logger.error(f"Failed to update seating constraints: {err!s}")
        raise HTTPException(
            status_code=500, detail=f"Failed to update seating constraints: {err!s}"
        )


@router.get("/guests/seating-constraints", tags=["Admin"])
async def get_seating_constraints(
    wedding_id: str = Query(...),
    current_user: ExtendedAuthUser = Depends(require_wedding_planner_only),
):
    """
    Get all seating constraints for a wedding.

    Returns a summary of all must_sit_together and must_sit_apart relationships.
    """
    if not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")

    try:
        guests_collection = mongo.db["guests"]

        # Find all guests with any seating constraints
        cursor = guests_collection.find(
            {
                "wedding_id": wedding_id,
                "$or": [
                    {"must_sit_with": {"$exists": True, "$ne": []}},
                    {"must_sit_apart": {"$exists": True, "$ne": []}},
                ],
            }
        )

        # Safety cap: most weddings have far fewer guests with constraints
        MAX_CONSTRAINED_GUESTS = 5000
        guests = await cursor.to_list(length=MAX_CONSTRAINED_GUESTS)

        # Build unique constraint pairs
        must_sit_together = set()
        must_sit_apart = set()

        guest_names = {}  # Cache for guest names

        for guest in guests:
            guest_id = str(guest.get("_id"))
            guest_names[guest_id] = guest.get("name", "Unknown")

            for partner_id in guest.get("must_sit_with", []):
                pair = tuple(sorted([guest_id, partner_id]))
                must_sit_together.add(pair)

            for conflict_id in guest.get("must_sit_apart", []):
                pair = tuple(sorted([guest_id, conflict_id]))
                must_sit_apart.add(pair)

        # Fetch names for any guests we don't have yet
        all_related_ids: set[str] = set()
        for pair in must_sit_together:
            all_related_ids.update(pair)
        for pair in must_sit_apart:
            all_related_ids.update(pair)

        missing_ids = all_related_ids - set(guest_names.keys())
        if missing_ids:
            # Convert string IDs to ObjectId for _id queries
            missing_oids = []
            for mid in missing_ids:
                try:
                    missing_oids.append(ObjectId(mid))
                except InvalidId:
                    pass
            missing_cursor = guests_collection.find(
                {"_id": {"$in": missing_oids}, "wedding_id": wedding_id}
            )
            # Already limited by size of missing_ids (max 5000 from above fetch)
            missing_guests = await missing_cursor.to_list(length=5000)
            for g in missing_guests:
                guest_names[str(g.get("_id"))] = g.get("name", "Unknown")

        # Format response with names
        def format_pairs(pairs):
            return [
                {
                    "guest_1": {"id": p[0], "name": guest_names.get(p[0], "Unknown")},
                    "guest_2": {"id": p[1], "name": guest_names.get(p[1], "Unknown")},
                }
                for p in pairs
            ]

        return dict_response(
            data={
                "must_sit_together": format_pairs(must_sit_together),
                "must_sit_apart": format_pairs(must_sit_apart),
            },
            message="Seating constraints retrieved",
        )

    except Exception as err:
        logger.error(f"Failed to get seating constraints: {err!s}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get seating constraints: {err!s}"
        )
