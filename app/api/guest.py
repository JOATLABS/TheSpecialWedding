from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Any
import inspect
from app.services.guest_service import GuestService
from app.services.activity_log_service import activity_log_service
from app.models.guest import UpdateGuestRequest, GuestModel, CreateGuestRequest
from app.dependencies.auth_extended import require_wedding_planner_only, ExtendedAuthUser, check_wedding_access, enforce_team_permission
from app.utils.token_generator import generate_token
from app.core.database import mongo
from bson import ObjectId
from bson.errors import InvalidId
import logging

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
    action: Literal["add", "remove"] = Field(..., description="Add or remove the constraint")


class BulkSeatingConstraintRequest(BaseModel):
    """Bulk update seating constraints"""
    constraints: List[SeatingConstraintRequest] = Field(..., description="List of constraints to apply")


@router.get("/invite/{token}", tags=["Guest"])
async def get_guest(token: str, wedding_id: str = Query(...)):
    try:
        return await guest_service.get_guest_by_token(token, wedding_id)
    except HTTPException as e:
        raise e
    except Exception:
        raise HTTPException(status_code=500, detail="Unexpected error occurred")


@router.get("/invite/search", tags=["Guest"])
async def search_guest(
    wedding_id: str = Query(..., description="Wedding ID to search within"),
    phone: str = Query(None, description="Guest phone number"),
    name: str = Query(None, description="Guest name"),
    current_user: ExtendedAuthUser = Depends(require_wedding_planner_only)
):
    """
    Search for a guest by phone or name within a specific wedding.
    Requires authentication and wedding access.
    """
    # Verify user has access to this wedding
    if not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")

    try:
        return await guest_service.get_guest_by_phone_or_name(
            phone=phone,
            name=name,
            wedding_id=wedding_id
        )
    except HTTPException as e:
        raise e
    except Exception:
        raise HTTPException(status_code=500, detail="Unexpected error occurred")


@router.get("/guests", tags=["Admin"])
async def list_guests(wedding_id: str = Query(...), current_user: ExtendedAuthUser = Depends(require_wedding_planner_only)):
    # Check if user has access to this wedding
    if not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")
    try:
        return await guest_service.list_guests_by_wedding(wedding_id)
    except HTTPException as e:
        raise e
    except Exception:
        raise HTTPException(status_code=500, detail="Unexpected error occurred")


@router.put("/guests/{guest_id}", tags=["Admin"])
async def update_guest(
    guest_id: str,
    update_data: UpdateGuestRequest,
    current_user: ExtendedAuthUser = Depends(require_wedding_planner_only)
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
                changes=update_dict,
                updated_by=current_user.email
            )
        except Exception as log_err:
            logger.warning(f"Failed to log guest update activity: {log_err}")

        return result
    except HTTPException as e:
        raise e
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Failed to update guest: {str(err)}")


@router.delete("/guests/{guest_id}", tags=["Admin"])
async def delete_guest(guest_id: str, current_user: ExtendedAuthUser = Depends(require_wedding_planner_only)):
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
                deleted_by=current_user.email
            )
        except Exception as log_err:
            logger.warning(f"Failed to log guest delete activity: {log_err}")

        return result
    except HTTPException as e:
        raise e
    except Exception:
        raise HTTPException(status_code=500, detail="Unexpected error occurred")


@router.post("/guests", tags=["Admin"])
async def create_guest(
    guest_data: CreateGuestRequest,
    wedding_id: str = Query(...),
    current_user: ExtendedAuthUser = Depends(require_wedding_planner_only)
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
                guest_email=result.get("email"),
                added_by=current_user.email
            )
        except Exception as log_err:
            logger.warning(f"Failed to log guest create activity: {log_err}")

        return result
    except HTTPException as e:
        raise e
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Failed to create guest: {str(err)}")


# =========================================================================
# SEATING CONSTRAINTS MANAGEMENT
# =========================================================================

@router.post("/guests/seating-constraints", tags=["Admin"])
async def update_seating_constraints(
    request: BulkSeatingConstraintRequest,
    wedding_id: str = Query(...),
    current_user: ExtendedAuthUser = Depends(require_wedding_planner_only)
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
        results: dict[str, list[dict[str, Any]]] = {
            "updated": [],
            "errors": []
        }

        guests_collection = mongo.db["guests"]

        for constraint in request.constraints:
            try:
                # Convert string IDs to ObjectId for MongoDB _id queries
                try:
                    oid_1 = ObjectId(constraint.guest_id_1)
                    oid_2 = ObjectId(constraint.guest_id_2)
                except InvalidId:
                    results["errors"].append({
                        "guest_ids": [constraint.guest_id_1, constraint.guest_id_2],
                        "error": "Invalid guest ID format"
                    })
                    continue

                # Verify both guests exist and belong to this wedding
                guest1 = await guests_collection.find_one({
                    "_id": oid_1,
                    "wedding_id": wedding_id
                })
                guest2 = await guests_collection.find_one({
                    "_id": oid_2,
                    "wedding_id": wedding_id
                })

                if not guest1:
                    results["errors"].append({
                        "guest_id": constraint.guest_id_1,
                        "error": "Guest not found in this wedding"
                    })
                    continue
                if not guest2:
                    results["errors"].append({
                        "guest_id": constraint.guest_id_2,
                        "error": "Guest not found in this wedding"
                    })
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
                        {"_id": oid_1},
                        {"$addToSet": {field: id_str_2}}
                    )
                    await guests_collection.update_one(
                        {"_id": oid_2},
                        {"$addToSet": {field: id_str_1}}
                    )
                else:  # remove
                    # Remove from both guests' lists
                    await guests_collection.update_one(
                        {"_id": oid_1},
                        {"$pull": {field: id_str_2}}
                    )
                    await guests_collection.update_one(
                        {"_id": oid_2},
                        {"$pull": {field: id_str_1}}
                    )

                results["updated"].append({
                    "guest_id_1": constraint.guest_id_1,
                    "guest_id_2": constraint.guest_id_2,
                    "constraint_type": constraint.constraint_type,
                    "action": constraint.action
                })

            except Exception as e:
                results["errors"].append({
                    "guest_ids": [constraint.guest_id_1, constraint.guest_id_2],
                    "error": str(e)
                })

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
                    "updated_by": current_user.email
                }
            )
        except Exception as log_err:
            logger.warning(f"Failed to log seating constraints activity: {log_err}")

        return {
            "success": True,
            "updated_count": len(results["updated"]),
            "error_count": len(results["errors"]),
            "details": results
        }

    except Exception as err:
        logger.error(f"Failed to update seating constraints: {str(err)}")
        raise HTTPException(status_code=500, detail=f"Failed to update seating constraints: {str(err)}")


@router.get("/guests/seating-constraints", tags=["Admin"])
async def get_seating_constraints(
    wedding_id: str = Query(...),
    current_user: ExtendedAuthUser = Depends(require_wedding_planner_only)
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
        cursor = guests_collection.find({
            "wedding_id": wedding_id,
            "$or": [
                {"must_sit_with": {"$exists": True, "$ne": []}},
                {"must_sit_apart": {"$exists": True, "$ne": []}}
            ]
        })

        guests = await cursor.to_list(length=None)

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
            missing_cursor = guests_collection.find({
                "_id": {"$in": missing_oids},
                "wedding_id": wedding_id
            })
            missing_guests = await missing_cursor.to_list(length=None)
            for g in missing_guests:
                guest_names[str(g.get("_id"))] = g.get("name", "Unknown")

        # Format response with names
        def format_pairs(pairs):
            return [
                {
                    "guest_1": {"id": p[0], "name": guest_names.get(p[0], "Unknown")},
                    "guest_2": {"id": p[1], "name": guest_names.get(p[1], "Unknown")}
                }
                for p in pairs
            ]

        return {
            "wedding_id": wedding_id,
            "must_sit_together": format_pairs(must_sit_together),
            "must_sit_apart": format_pairs(must_sit_apart),
            "summary": {
                "total_must_sit_together": len(must_sit_together),
                "total_must_sit_apart": len(must_sit_apart),
                "guests_with_constraints": len(guests)
            }
        }

    except Exception as err:
        logger.error(f"Failed to get seating constraints: {str(err)}")
        raise HTTPException(status_code=500, detail=f"Failed to get seating constraints: {str(err)}")
