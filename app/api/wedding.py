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
from app.services.stripe_service import stripe_service
from app.models.subscription import SubscriptionStatus
from app.core.database import mongo
from datetime import datetime
from bson import ObjectId

router = APIRouter()
wedding_service = WeddingService()
subscription_service = SubscriptionService()

@router.get("/weddings", tags=["Admin"])
async def list_weddings(current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    """List weddings - ROOT_ADMIN sees all, planners see only assigned"""
    if current_user.is_root_admin:
        return await wedding_service.list_weddings_with_planner_info()
    return await wedding_service.list_weddings_for_planner(current_user.email)

@router.post("/weddings", tags=["Admin"])
async def create_wedding(wedding: WeddingModel, current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    """Create a new wedding with subscription metering"""
    # Enforce limits for planners
    if not current_user.is_root_admin:
        user_id = current_user.user_data.get("_id")
        if user_id:
            limits_check = await subscription_service.check_usage_limits(user_id, "weddings", 1)
            if not limits_check.get("allowed", False):
                raise HTTPException(
                    status_code=402,
                    detail=limits_check.get("message", "Wedding creation limit exceeded")
                )

    wedding_data = wedding.dict(by_alias=True)
    wedding_data["created_by"] = current_user.email
    if current_user.is_wedding_planner:
        # Use direct assignment if None, since setdefault won't override existing None values
        if not wedding_data.get("assigned_planner_email"):
            wedding_data["assigned_planner_email"] = current_user.email
        if not wedding_data.get("assigned_planner_id"):
            wedding_data["assigned_planner_id"] = current_user.user_data.get("_id", "")

    result = await wedding_service.create_wedding(wedding_data)

    # Increment usage and meter (idempotent per period)
    if not current_user.is_root_admin and current_user.user_data.get("_id"):
        user_id = current_user.user_data["_id"]
        await subscription_service.increment_usage(user_id, "weddings", 1)

        try:
            sub = await mongo.db["user_subscriptions"].find_one({
                "user_id": user_id,
                "status": SubscriptionStatus.ACTIVE.value
            })

            if sub and sub.get("stripe_customer_id") and sub.get("plan_id"):
                plan = await mongo.db["subscription_plans"].find_one({"_id": sub["plan_id"]})

                if plan and plan.get("is_metered") and plan.get("meter_event_name"):
                    current_period_start = sub.get("current_period_start")
                    last_billed_at = None

                    if isinstance(current_period_start, str):
                        try:
                            current_period_start = datetime.fromisoformat(current_period_start.replace("Z", "+00:00"))
                        except Exception:
                            current_period_start = None
                    if isinstance(current_period_start, datetime) and current_period_start.tzinfo is None:
                        current_period_start = current_period_start.replace(tzinfo=datetime.utcnow().astimezone().tzinfo)

                    # Check if this wedding was already billed this period
                    wedding_record = await mongo.db["weddings"].find_one({"_id": wedding_data["_id"]})
                    if wedding_record:
                        last_billed_at = wedding_record.get("last_billed_at")
                        if isinstance(last_billed_at, str):
                            try:
                                last_billed_at = datetime.fromisoformat(last_billed_at.replace("Z", "+00:00"))
                            except Exception:
                                last_billed_at = None

                    already_billed_this_period = (
                        last_billed_at
                        and current_period_start
                        and last_billed_at >= current_period_start
                    )

                    if not already_billed_this_period:
                        meter_result = stripe_service.report_meter_event(
                            event_name=plan["meter_event_name"],
                            payload={
                                "stripe_customer_id": sub["stripe_customer_id"],
                                "value": "1"
                            }
                        )
                        if meter_result.get("status") == "success":
                            await mongo.db["weddings"].update_one(
                                {"_id": wedding_data["_id"]},
                                {"$set": {
                                    "last_billed_at": datetime.utcnow(),
                                    "billed_period": datetime.utcnow().strftime("%Y-%m"),
                                    "meter_pending": False,
                                    "meter_pending_reason": None
                                }}
                            )
                        else:
                            await mongo.db["weddings"].update_one(
                                {"_id": wedding_data["_id"]},
                                {"$set": {
                                    "meter_pending": True,
                                    "meter_pending_reason": meter_result.get("message") or "metering_failed",
                                    "billed_period": datetime.utcnow().strftime("%Y-%m")
                                }}
                            )
        except Exception as e:
            print(f"Error reporting meter event on creation: {e}")

    return result

@router.put("/weddings/{wedding_id}", tags=["Admin"])
async def update_wedding_admin(wedding_id: str, wedding: dict, current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    """Update a wedding via admin interface - with access control"""
    # Check if user has access to this wedding
    if not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")

    # Add update metadata
    wedding["updated_by"] = current_user.email

    return await wedding_service.update_wedding(wedding_id, wedding)

@router.delete("/weddings/{wedding_id}", tags=["Admin"])
async def delete_wedding_admin(wedding_id: str, current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """Soft-delete a wedding (mark cancelled) to prevent billing avoidance."""
    wedding = await mongo.db["weddings"].find_one({"_id": wedding_id})
    if not wedding:
        raise HTTPException(status_code=404, detail="Wedding not found")

    # Attempt meter reversal only once per period to keep billing accurate without enabling avoidance
    try:
        planner_email = wedding.get("assigned_planner_email")
        if planner_email:
            planner = await mongo.get_users_collection().find_one({"email": planner_email})
        else:
            planner = None

        if planner:
            user_id = str(planner.get("_id"))
            sub = await mongo.db["user_subscriptions"].find_one({
                "user_id": user_id,
                "status": SubscriptionStatus.ACTIVE.value
            })
            if sub and sub.get("stripe_customer_id") and sub.get("plan_id"):
                plan = await mongo.db["subscription_plans"].find_one({"_id": sub["plan_id"]})
                if plan and plan.get("is_metered") and plan.get("meter_event_name"):
                    current_period = datetime.utcnow().strftime("%Y-%m")
                    already_reversed = wedding.get("meter_reversed_period") == current_period

                    if not already_reversed:
                        reverse_result = stripe_service.report_meter_event(
                            event_name=plan["meter_event_name"],
                            payload={
                                "stripe_customer_id": sub["stripe_customer_id"],
                                "value": "-1"
                            }
                        )
                        reversal_success = reverse_result.get("status") == "success"
                        await mongo.db["weddings"].update_one(
                            {"_id": wedding_id},
                            {"$set": {
                                "meter_reversed_period": current_period if reversal_success else wedding.get("meter_reversed_period"),
                                "meter_pending": not reversal_success,
                                "meter_pending_reason": None if reversal_success else reverse_result.get("message") or "meter_reversal_failed"
                            }}
                        )
    except Exception as exc:
        print(f"Meter reversal on cancellation failed: {exc}")

    # Preserve billing marker; do not decrement usage to avoid gaming billing
    await mongo.db["weddings"].update_one(
        {"_id": wedding_id},
        {"$set": {
            "status": "cancelled",
            "cancelled_at": datetime.utcnow()
        }}
    )
    return {"message": "Wedding cancelled (soft delete); billing usage preserved"}

@router.get("/weddings/{wedding_id}", tags=["Wedding"])
async def get_wedding(wedding_id: str, current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    """Get a wedding by ID - with access control"""
    # Check if user has access to this wedding
    if not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")
    return await wedding_service.get_wedding(wedding_id)

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

@router.delete("/weddings/{wedding_id}", tags=["Admin"])
async def delete_wedding(wedding_id: str, current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """Alias soft-delete: mark cancelled; do not remove from billing usage."""
    return await delete_wedding_admin(wedding_id, current_user)
