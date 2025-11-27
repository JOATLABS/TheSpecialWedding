from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app.models.wedding import WeddingModel
from app.services.wedding_service import WeddingService
from app.dependencies.auth_extended import (
    require_root_admin,
    require_wedding_planner,
    require_admin_or_planner,
    ExtendedAuthUser,
    check_wedding_access
)
from app.services.subscription_service import SubscriptionService

router = APIRouter()
wedding_service = WeddingService()
subscription_service = SubscriptionService()

@router.post("/weddings", tags=["Admin"])
def create_wedding(wedding: WeddingModel, current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    """Create a new wedding - ROOT_ADMIN or wedding planners with subscription limits"""
    # Check subscription limits for non-ROOT_ADMIN users
    if not current_user.is_root_admin:
        user_id = current_user.user_data.get("_id")
        if user_id:
            # Check wedding creation limits
            limits_check = subscription_service.check_usage_limits(user_id, "weddings", 1)
            if not limits_check.get("allowed", False):
                raise HTTPException(
                    status_code=402,  # Payment Required
                    detail=limits_check.get("message", "Wedding creation limit exceeded")
                )

    # Add created_by and assigned_planner fields
    wedding_data = wedding.dict(by_alias=True)
    wedding_data["created_by"] = current_user.email

    # If created by wedding planner, assign them as the planner
    if current_user.is_wedding_planner:
        wedding_data["assigned_planner_email"] = current_user.email

    result = wedding_service.create_wedding(wedding_data)

    # Increment usage for non-ROOT_ADMIN users
    if not current_user.is_root_admin and current_user.user_data.get("_id"):
        subscription_service.increment_usage(current_user.user_data["_id"], "weddings", 1)

    return result

@router.get("/weddings", tags=["Wedding"])
def list_weddings_public(current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    """List weddings - PROTECTED endpoint requiring authentication"""
    # This endpoint now requires authentication for security
    # Use the admin endpoint for authenticated access
    if current_user.is_root_admin or current_user.is_legacy_admin:
        return wedding_service.list_weddings_with_planner_info()
    else:
        # Wedding planners see only their assigned weddings
        return wedding_service.list_weddings_for_planner(current_user.email)

@router.get("/weddings", tags=["Admin"])
def list_weddings_admin(current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    """List weddings - ROOT_ADMIN sees all, planners see only assigned"""
    if current_user.is_root_admin or current_user.is_legacy_admin:
        # ROOT_ADMIN and legacy admin see all weddings
        return wedding_service.list_weddings_with_planner_info()
    else:
        # Wedding planners see only their assigned weddings
        return wedding_service.list_weddings_for_planner(current_user.email)

@router.post("/weddings", tags=["Admin"])
def create_wedding_admin(wedding: dict, current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    """Create a new wedding via admin interface - ROOT_ADMIN or wedding planners with subscription limits"""
    # Check subscription limits for non-ROOT_ADMIN users
    if not current_user.is_root_admin:
        user_id = current_user.user_data.get("_id")
        if user_id:
            # Check wedding creation limits
            limits_check = subscription_service.check_usage_limits(user_id, "weddings", 1)
            if not limits_check.get("allowed", False):
                raise HTTPException(
                    status_code=402,  # Payment Required
                    detail=limits_check.get("message", "Wedding creation limit exceeded")
                )

    # Add metadata
    wedding["created_by"] = current_user.email

    # If created by wedding planner and no planner assigned, assign them
    if current_user.is_wedding_planner and not wedding.get("assigned_planner_email"):
        wedding["assigned_planner_email"] = current_user.email
        wedding["assigned_planner_id"] = current_user.user_data.get("_id", "")

    result = wedding_service.create_wedding(wedding)

    # Increment usage for non-ROOT_ADMIN users
    if not current_user.is_root_admin and current_user.user_data.get("_id"):
        subscription_service.increment_usage(current_user.user_data["_id"], "weddings", 1)

    return result

@router.put("/weddings/{wedding_id}", tags=["Admin"])
def update_wedding_admin(wedding_id: str, wedding: dict, current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    """Update a wedding via admin interface - with access control"""
    # Check if user has access to this wedding
    if not check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")

    # Add update metadata
    wedding["updated_by"] = current_user.email

    return wedding_service.update_wedding(wedding_id, wedding)

@router.delete("/weddings/{wedding_id}", tags=["Admin"])
def delete_wedding_admin(wedding_id: str, current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """Delete a wedding via admin interface - Only ROOT_ADMIN can delete weddings"""
    return wedding_service.delete_wedding(wedding_id)

@router.get("/weddings/{wedding_id}", tags=["Wedding"])
def get_wedding(wedding_id: str, current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    """Get a wedding by ID - with access control"""
    # Check if user has access to this wedding
    if not check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")
    return wedding_service.get_wedding(wedding_id)

@router.get("/weddings/slug/{slug}", tags=["Wedding"])
def get_wedding_by_slug(slug: str):
    """
    Get a wedding by slug - DEPRECATED for security reasons.
    This endpoint now returns minimal public information only.
    Use guest verification endpoints for full wedding details.
    """
    from app.services.guest_verification_service import GuestVerificationService

    verification_service = GuestVerificationService()
    privacy_info = verification_service.get_wedding_privacy_info(slug)

    # Only return basic info to show what authentication is required
    return {
        "couple_names": privacy_info.get("couple_names"),
        "slug": slug,
        "privacy_mode": privacy_info.get("privacy_mode"),
        "requires_authentication": privacy_info.get("privacy_mode") != "public",
        "message": "Use /weddings/verify-guest-access/{slug} with proper authentication to access full wedding details"
    }

@router.put("/weddings/{wedding_id}", tags=["Admin"])
def update_wedding(wedding_id: str, wedding: dict, current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    """Update a wedding - with access control"""
    # Check if user has access to this wedding
    if not check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")
    return wedding_service.update_wedding(wedding_id, wedding)

@router.delete("/weddings/{wedding_id}", tags=["Admin"])
def delete_wedding(wedding_id: str, current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """Delete a wedding - Only ROOT_ADMIN can delete weddings"""
    return wedding_service.delete_wedding(wedding_id)