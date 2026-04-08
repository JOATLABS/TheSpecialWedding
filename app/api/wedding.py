import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from app.models.wedding import WeddingModel
from app.services.wedding_service import WeddingService
from app.services.cascade_delete_service import cascade_delete_service
from app.dependencies.auth_extended import (
    require_root_admin,
    require_team_or_planner,
    ExtendedAuthUser,
    check_wedding_access,
    enforce_team_permission,
    get_accessible_wedding_ids,
)
from app.services.subscription_service import SubscriptionService
from app.services.stripe_service import stripe_service
from app.models.subscription import SubscriptionStatus
from app.services.sse_manager import sse_manager
from app.core.database import mongo
from app.utils.planner_ownership import (
    extract_wedding_owner_identity,
    normalize_query_id,
)
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

router = APIRouter()
wedding_service = WeddingService()
subscription_service = SubscriptionService()


def _get_planner_scope(
    current_user: ExtendedAuthUser,
) -> tuple[Optional[str], Optional[str]]:
    if current_user.is_team_member:
        return current_user.parent_planner_id, current_user.team_owner_email
    return current_user.user_data.get("_id"), current_user.email


async def _sync_couple_owner_mirrors(wedding_id: str) -> None:
    """Keep couple ownership mirrors aligned after wedding ownership writes."""
    wedding = await mongo.db["weddings"].find_one(
        {"_id": normalize_query_id(wedding_id)},
        {"assigned_planner_id": 1, "assigned_planner_email": 1},
    )
    owner_id, owner_email = extract_wedding_owner_identity(wedding)
    set_fields = {"updated_at": datetime.now(timezone.utc)}
    if owner_id:
        set_fields["planner_id"] = owner_id
    if owner_email:
        set_fields["planner_email"] = owner_email

    if len(set_fields) == 1:
        return

    await mongo.db["couple_users"].update_many(
        {"wedding_id": wedding_id},
        {"$set": set_fields},
    )


@router.get("/weddings", tags=["Admin"])
async def list_weddings(
    page: int = Query(1, ge=1, le=10000),
    limit: int = Query(50, ge=1, le=100),
    search: Optional[str] = Query(None),
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """
    List weddings with pagination - ROOT_ADMIN sees all, planners see only assigned.
    Team members with "assigned" access see only their assigned weddings.
    """
    if current_user.is_root_admin:
        return await wedding_service.list_weddings_with_planner_info(
            page=page, limit=limit, search=search
        )

    # Get accessible wedding IDs for team members
    accessible_ids = get_accessible_wedding_ids(current_user)
    planner_id, planner_email = _get_planner_scope(current_user)
    if accessible_ids is not None:
        # Team member with "assigned" access - filter by their assigned weddings
        return await wedding_service.list_weddings_for_planner(
            planner_id=planner_id,
            planner_email=planner_email,
            accessible_ids=accessible_ids,
            page=page,
            limit=limit,
            search=search,
        )

    # Planner owner or team member with "all" access
    return await wedding_service.list_weddings_for_planner(
        planner_id=planner_id,
        planner_email=planner_email,
        page=page,
        limit=limit,
        search=search,
    )


@router.post("/weddings", tags=["Admin"])
async def create_wedding(
    wedding: WeddingModel,
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """Create a new wedding with subscription metering"""
    enforce_team_permission(current_user, "manage_wedding_settings")
    owner_id, owner_email = _get_planner_scope(current_user)
    # Enforce limits for planners
    if not current_user.is_root_admin:
        user_id = owner_id
        if user_id:
            limits_check = await subscription_service.check_usage_limits(
                user_id, "weddings", 1
            )
            if not limits_check.get("allowed", False):
                raise HTTPException(
                    status_code=402,
                    detail=limits_check.get(
                        "message", "Wedding creation limit exceeded"
                    ),
                )

    wedding_data = wedding.dict(by_alias=True)
    wedding_data["created_by"] = current_user.email
    if not current_user.is_root_admin:
        if owner_email and not wedding_data.get("assigned_planner_email"):
            wedding_data["assigned_planner_email"] = owner_email
        if owner_id and not wedding_data.get("assigned_planner_id"):
            wedding_data["assigned_planner_id"] = owner_id

    result = await wedding_service.create_wedding(wedding_data)

    # Increment usage and meter (idempotent per period)
    if not current_user.is_root_admin and owner_id:
        user_id = owner_id
        await subscription_service.increment_usage(user_id, "weddings", 1)

        try:
            sub = await mongo.db["user_subscriptions"].find_one(
                {"user_id": user_id, "status": SubscriptionStatus.ACTIVE.value}
            )

            if sub and sub.get("stripe_customer_id") and sub.get("plan_id"):
                plan = await mongo.db["subscription_plans"].find_one(
                    {"_id": sub["plan_id"]}
                )

                if plan and plan.get("is_metered") and plan.get("meter_event_name"):
                    current_period_start = sub.get("current_period_start")
                    last_billed_at = None

                    if isinstance(current_period_start, str):
                        try:
                            current_period_start = datetime.fromisoformat(
                                current_period_start.replace("Z", "+00:00")
                            )
                        except Exception as e:
                            logger.warning(
                                f"Failed to parse current_period_start: {current_period_start}, error: {e}"
                            )
                            current_period_start = None
                    if (
                        isinstance(current_period_start, datetime)
                        and current_period_start.tzinfo is None
                    ):
                        current_period_start = current_period_start.replace(
                            tzinfo=datetime.now(timezone.utc).astimezone().tzinfo
                        )

                    # Check if this wedding was already billed this period
                    wedding_record = await mongo.db["weddings"].find_one(
                        {"_id": wedding_data["_id"]}
                    )
                    if wedding_record:
                        last_billed_at = wedding_record.get("last_billed_at")
                        if isinstance(last_billed_at, str):
                            try:
                                last_billed_at = datetime.fromisoformat(
                                    last_billed_at.replace("Z", "+00:00")
                                )
                            except Exception as e:
                                logger.warning(
                                    f"Failed to parse last_billed_at: {last_billed_at}, error: {e}"
                                )
                                last_billed_at = None

                    already_billed_this_period = (
                        last_billed_at
                        and current_period_start
                        and last_billed_at >= current_period_start
                    )

                    if not already_billed_this_period:
                        # Idempotency key: prevents double-billing on retries
                        billing_period = datetime.now(timezone.utc).strftime("%Y-%m")
                        idempotency_key = f"wedding_create_{wedding_data['_id']}_{sub['stripe_customer_id']}_{billing_period}"

                        meter_result = stripe_service.report_meter_event(
                            event_name=plan["meter_event_name"],
                            payload={
                                "stripe_customer_id": sub["stripe_customer_id"],
                                "value": "1",
                            },
                            identifier=idempotency_key,
                        )
                        if meter_result.get("status") == "success":
                            await mongo.db["weddings"].update_one(
                                {"_id": wedding_data["_id"]},
                                {
                                    "$set": {
                                        "last_billed_at": datetime.now(timezone.utc),
                                        "billed_period": datetime.now(
                                            timezone.utc
                                        ).strftime("%Y-%m"),
                                        "meter_pending": False,
                                        "meter_pending_reason": None,
                                    }
                                },
                            )
                        else:
                            await mongo.db["weddings"].update_one(
                                {"_id": wedding_data["_id"]},
                                {
                                    "$set": {
                                        "meter_pending": True,
                                        "meter_pending_reason": meter_result.get(
                                            "message"
                                        )
                                        or "metering_failed",
                                        "billed_period": datetime.now(
                                            timezone.utc
                                        ).strftime("%Y-%m"),
                                    }
                                },
                            )
        except Exception as e:
            logger.error(f"Error reporting meter event on creation: {e}")

    # Broadcast SSE data-change so planner UI updates
    await sse_manager.broadcast_data_change(
        current_user.email,
        "wedding",
        "created",
        wedding_id=str(wedding_data.get("_id", "")),
    )

    return result


@router.put("/weddings/{wedding_id}", tags=["Admin"])
async def update_wedding_admin(
    wedding_id: str,
    wedding: dict,
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """Update a wedding via admin interface - with access control"""
    enforce_team_permission(current_user, "manage_wedding_settings")
    # Check if user has access to this wedding
    if not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")

    # Add update metadata
    wedding["updated_by"] = current_user.email
    if not current_user.is_root_admin:
        owner_id, owner_email = _get_planner_scope(current_user)
        if owner_email:
            wedding["assigned_planner_email"] = owner_email
        if owner_id:
            wedding["assigned_planner_id"] = owner_id

    result = await wedding_service.update_wedding(wedding_id, wedding)
    await _sync_couple_owner_mirrors(wedding_id)

    # Broadcast SSE data-change so planner UI updates
    await sse_manager.broadcast_data_change(
        current_user.email,
        "wedding",
        "updated",
        wedding_id=wedding_id,
    )

    return result


@router.delete("/weddings/{wedding_id}", tags=["Admin"])
async def delete_wedding_admin(
    wedding_id: str,
    current_user: ExtendedAuthUser = Depends(require_root_admin),
    hard_delete: bool = False,
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
    wedding = await mongo.db["weddings"].find_one(
        {"_id": normalize_query_id(wedding_id)}
    )
    if not wedding:
        raise HTTPException(status_code=404, detail="Wedding not found")

    if hard_delete:
        # Perform hard delete via cascade service
        try:
            result = await cascade_delete_service.hard_delete_wedding(
                wedding_id, current_user.email
            )
            logger.info(f"Hard deleted wedding {wedding_id}: {result}")
            await sse_manager.broadcast_data_change(
                current_user.email,
                "wedding",
                "deleted",
                wedding_id=wedding_id,
            )
            return result
        except Exception as e:
            logger.error(f"Hard delete failed for wedding {wedding_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Hard delete failed: {str(e)}")

    # Perform soft delete with meter handling
    try:
        # Attempt meter reversal only once per period to keep billing accurate without enabling avoidance
        planner_id, planner_email = extract_wedding_owner_identity(wedding)
        planner = None
        if planner_id:
            planner = await mongo.get_users_collection().find_one(
                {"_id": normalize_query_id(planner_id)}
            )
        if not planner and planner_email:
            planner = await mongo.get_users_collection().find_one(
                {"email": planner_email}
            )

        if planner:
            user_id = str(planner.get("_id"))
            sub = await mongo.db["user_subscriptions"].find_one(
                {"user_id": user_id, "status": SubscriptionStatus.ACTIVE.value}
            )
            if sub and sub.get("stripe_customer_id") and sub.get("plan_id"):
                plan = await mongo.db["subscription_plans"].find_one(
                    {"_id": sub["plan_id"]}
                )
                if plan and plan.get("is_metered") and plan.get("meter_event_name"):
                    current_period = datetime.now(timezone.utc).strftime("%Y-%m")
                    already_reversed = (
                        wedding.get("meter_reversed_period") == current_period
                    )

                    if not already_reversed:
                        # Idempotency key for reversal: prevents double-crediting on retries
                        idempotency_key = f"wedding_delete_{wedding_id}_{sub['stripe_customer_id']}_{current_period}"

                        reverse_result = stripe_service.report_meter_event(
                            event_name=plan["meter_event_name"],
                            payload={
                                "stripe_customer_id": sub["stripe_customer_id"],
                                "value": "-1",
                            },
                            identifier=idempotency_key,
                        )
                        reversal_success = reverse_result.get("status") == "success"
                        await mongo.db["weddings"].update_one(
                            {"_id": normalize_query_id(wedding_id)},
                            {
                                "$set": {
                                    "meter_reversed_period": current_period
                                    if reversal_success
                                    else wedding.get("meter_reversed_period"),
                                    "meter_pending": not reversal_success,
                                    "meter_pending_reason": None
                                    if reversal_success
                                    else reverse_result.get("message")
                                    or "meter_reversal_failed",
                                }
                            },
                        )

        # Perform soft delete cascade
        result = await cascade_delete_service.soft_delete_wedding(
            wedding_id, current_user.email
        )

        # Also mark wedding status as cancelled for backward compatibility
        await mongo.db["weddings"].update_one(
            {"_id": normalize_query_id(wedding_id)},
            {
                "$set": {
                    "status": "cancelled",
                    "cancelled_at": datetime.now(timezone.utc),
                }
            },
        )

        logger.info(f"Soft deleted wedding {wedding_id}: {result}")
        result["message"] = (
            "Wedding cancelled (soft delete); all dependent records archived; billing usage preserved"
        )

        await sse_manager.broadcast_data_change(
            current_user.email,
            "wedding",
            "deleted",
            wedding_id=wedding_id,
        )

        return result

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Delete operation failed for wedding {wedding_id}: {exc}")
        raise HTTPException(
            status_code=500, detail=f"Delete operation failed: {str(exc)}"
        )


@router.get("/weddings/{wedding_id}", tags=["Wedding"])
async def get_wedding(
    wedding_id: str, current_user: ExtendedAuthUser = Depends(require_team_or_planner)
):
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
