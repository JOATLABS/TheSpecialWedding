from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime
from app.core.database import mongo
from app.dependencies.auth_extended import require_root_admin, ExtendedAuthUser
from app.services.stripe_service import stripe_service
from app.models.subscription import SubscriptionStatus
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/metering", tags=["ROOT_ADMIN", "Metering"])


@router.post("/retry-pending")
async def retry_pending_meter_events(current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """
    Retry Stripe meter events for weddings marked as meter_pending.
    ROOT_ADMIN only.
    """
    try:
        pending_weddings = await mongo.db["weddings"].find({"meter_pending": True}).to_list(length=None)
        retried = 0
        succeeded = 0
        failed = []

        for wedding in pending_weddings:
            planner_email = wedding.get("assigned_planner_email")
            if not planner_email:
                failed.append({"wedding_id": wedding.get("_id"), "reason": "no_planner_email"})
                continue

            planner = await mongo.get_users_collection().find_one({"email": planner_email})
            if not planner:
                failed.append({"wedding_id": wedding.get("_id"), "reason": "planner_not_found"})
                continue

            user_id = str(planner.get("_id"))
            sub = await mongo.db["user_subscriptions"].find_one({
                "user_id": user_id,
                "status": SubscriptionStatus.ACTIVE.value
            })
            if not sub or not sub.get("stripe_customer_id") or not sub.get("plan_id"):
                failed.append({"wedding_id": wedding.get("_id"), "reason": "no_active_subscription"})
                continue

            plan = await mongo.db["subscription_plans"].find_one({"_id": sub["plan_id"]})
            if not plan or not plan.get("is_metered") or not plan.get("meter_event_name"):
                failed.append({"wedding_id": wedding.get("_id"), "reason": "plan_not_metered"})
                continue

            retried += 1
            # Idempotency key for retry: ALWAYS use current period since we're billing for NOW
            # Note: billed_period stores the LAST successful billing, not the target period
            # Using current period ensures:
            # 1. Retries for THIS month are idempotent (won't double-bill this month)
            # 2. If last month failed and we're now in a new month, we bill for new month
            current_billing_period = datetime.utcnow().strftime("%Y-%m")
            idempotency_key = f"meter_retry_{wedding.get('_id')}_{sub['stripe_customer_id']}_{current_billing_period}"

            meter_result = stripe_service.report_meter_event(
                event_name=plan["meter_event_name"],
                payload={
                    "stripe_customer_id": sub["stripe_customer_id"],
                    "value": "1"
                },
                identifier=idempotency_key
            )
            if meter_result.get("status") == "success":
                succeeded += 1
                await mongo.db["weddings"].update_one(
                    {"_id": wedding.get("_id")},
                    {"$set": {
                        "last_billed_at": datetime.utcnow(),
                        "billed_period": datetime.utcnow().strftime("%Y-%m"),
                        "meter_pending": False,
                        "meter_pending_reason": None
                    }}
                )
            else:
                failed.append({"wedding_id": wedding.get("_id"), "reason": meter_result.get("message") or "retry_failed"})

        return {
            "retried": retried,
            "succeeded": succeeded,
            "failed": failed
        }

    except Exception as e:
        logger.error(f"Meter retry failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Meter retry failed")
