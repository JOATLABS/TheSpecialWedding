import logging
from fastapi import APIRouter, Depends, HTTPException
from app.models.wedding import WeddingModel
from app.services.wedding_service import WeddingService
from app.services.cascade_delete_service import cascade_delete_service
from app.dependencies.auth_extended import (
    require_root_admin,
    require_admin_or_planner,
    ExtendedAuthUser,
    check_wedding_access
)
from app.services.subscription_service import SubscriptionService
from app.services.stripe_service import stripe_service
from app.models.subscription import SubscriptionStatus
from app.utils.response import dict_response
from app.core.database import mongo
from datetime import datetime, timezone
from bson import ObjectId

logger = logging.getLogger(__name__)

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
                        except Exception as e:
                            logger.warning(f"Failed to parse current_period_start: {current_period_start}, error: {e}")
                            current_period_start = None
                    if isinstance(current_period_start, datetime) and current_period_start.tzinfo is None:
                        current_period_start = current_period_start.replace(tzinfo=datetime.now(timezone.utc).astimezone().tzinfo)

                    # Check if this wedding was already billed this period
                    wedding_record = await mongo.db["weddings"].find_one({"_id": wedding_data["_id"]})
                    if wedding_record:
                        last_billed_at = wedding_record.get("last_billed_at")
                        if isinstance(last_billed_at, str):
                            try:
                                last_billed_at = datetime.fromisoformat(last_billed_at.replace("Z", "+00:00"))
                            except Exception as e:
                                logger.warning(f"Failed to parse last_billed_at: {last_billed_at}, error: {e}")
                                last_billed_at = None

                    already_billed_this_period = (
                        last_billed_at and current_period_start and last_billed_at >= current_period_start
                    )

                    if not already_billed_this_period:
                        # Idempotency key: prevents double-billing on retries
                        billing_period = datetime.now(timezone.utc).strftime("%Y-%m")
                        idempotency_key = f"wedding_create_{wedding_data['_id']}_{sub['stripe_customer_id']}_{billing_period}"

                        meter_result = stripe_service.report_meter_event(
                            event_name=plan["meter_event_name"],
                            payload={
                                "stripe_customer_id": sub["stripe_customer_id"],
                                "value": "1"
                            },
                            identifier=idempotency_key
                        )
                        if meter_result.get("status") == "success":
                            await mongo.db["weddings"].update_one(
                                {"_id": wedding_data["_id"]},
                                {"$set": {
                                    "last_billed_at": datetime.now(timezone.utc),
                                    "billed_period": datetime.now(timezone.utc).strftime("%Y-%m"),
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
                                    "billed_period": datetime.now(timezone.utc).strftime("%Y-%m")
                                }}
                            )
        except Exception as e:
            logger.error(f"Error reporting meter event on creation: {e}")

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
async def delete_wedding_admin(
    wedding_id: str,
    current_user: ExtendedAuthUser = Depends(require_root_admin),
    hard_delete: bool = False
):
    """
    Delete a wedding and all dependent data.

    By default, performs a soft delete (archives records with deleted_at/deleted_by fields).
    If hard_delete=true, permanently removes all data (irreversible).

    For soft delete with billing:
    - Marks wedding status as 'cancelled'
    - Archives all dependent records (guests, forms, budget, etc.)
    - Handles meter reversal if on metered subscription
    - Preserves data for audit and recovery

    For hard delete:
    - Permanently removes all records from database
    - Should only be used for compliance, testing, or data cleanup
    - WARNING: This is IRREVERSIBLE
    """
    wedding = await mongo.db["weddings"].find_one({"_id": wedding_id})
    if not wedding:
        raise HTTPException(status_code=404, detail="Wedding not found")

    if hard_delete:
        # Perform hard delete via cascade service
        try:
            result = await cascade_delete_service.hard_delete_wedding(wedding_id, current_user.email)
            logger.info(f"Hard deleted wedding {wedding_id}: {result}")
            return result
        except Exception as e:
            logger.error(f"Hard delete failed for wedding {wedding_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Hard delete failed: {str(e)}")

    # Perform soft delete with meter handling
    try:
        # Attempt meter reversal only once per period to keep billing accurate without enabling avoidance
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
                    current_period = datetime.now(timezone.utc).strftime("%Y-%m")
                    already_reversed = wedding.get("meter_reversed_period") == current_period

                    if not already_reversed:
                        # Idempotency key for reversal: prevents double-crediting on retries
                        idempotency_key = f"wedding_delete_{wedding_id}_{sub['stripe_customer_id']}_{current_period}"

                        reverse_result = stripe_service.report_meter_event(
                            event_name=plan["meter_event_name"],
                            payload={
                                "stripe_customer_id": sub["stripe_customer_id"],
                                "value": "-1"
                            },
                            identifier=idempotency_key
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

        # Perform soft delete cascade
        result = await cascade_delete_service.soft_delete_wedding(wedding_id, current_user.email)

        # Also mark wedding status as cancelled for backward compatibility
        await mongo.db["weddings"].update_one(
            {"_id": wedding_id},
            {"$set": {
                "status": "cancelled",
                "cancelled_at": datetime.now(timezone.utc)
            }}
        )

        logger.info(f"Soft deleted wedding {wedding_id}: {result}")
        result["message"] = "Wedding cancelled (soft delete); all dependent records archived; billing usage preserved"
        return result

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Delete operation failed for wedding {wedding_id}: {exc}")
        raise HTTPException(status_code=500, detail=f"Delete operation failed: {str(exc)}")


@router.get("/weddings/{wedding_id}", tags=["Wedding"])
async def get_wedding(wedding_id: str, current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    """Get a wedding by ID - with access control"""
    # Check if user has access to this wedding
    if not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")
    return await wedding_service.get_wedding(wedding_id)


@router.get("/weddings/slug/{slug}", tags=["Wedding"])
async def get_wedding_by_slug(slug: str):
    """
    Get a wedding by slug - DEPRECATED for security reasons.
    This endpoint now returns minimal public information only.
    Use guest verification endpoints for full wedding details.
    """
    from app.services.guest_verification_service import GuestVerificationService

    verification_service = GuestVerificationService()
    privacy_info = await verification_service.get_wedding_privacy_info(slug)

    return privacy_info
