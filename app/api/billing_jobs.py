from fastapi import APIRouter, Depends, BackgroundTasks
from datetime import datetime, timezone
from app.dependencies.auth_extended import require_root_admin, ExtendedAuthUser
from app.services.stripe_service import stripe_service
from app.core.database import mongo
from app.models.subscription import SubscriptionStatus
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/billing/sync-usage")
async def sync_usage_to_stripe(
    background_tasks: BackgroundTasks,
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """
    Manually trigger synchronization of active wedding usage to Stripe Meters.
    This should be called periodically (e.g., daily) via cron or scheduler.
    """

    # Run in background to avoid timeout
    background_tasks.add_task(process_daily_usage_check)

    return {"status": "accepted", "message": "Usage sync started in background"}


async def process_daily_usage_check():
    """
    Iterate over active subscriptions and report active weddings usage.
    """
    logger.info("Starting daily usage sync...")

    # 1. Get all active subscriptions
    subscriptions = mongo.db["user_subscriptions"].find({
        "status": SubscriptionStatus.ACTIVE.value,
        "stripe_subscription_id": {"$exists": True}
    })

    count_processed = 0
    count_reported = 0

    async for sub in subscriptions:
        try:
            user_id = sub["user_id"]
            plan_id = sub["plan_id"]
            stripe_customer_id = sub.get("stripe_customer_id")

            if not stripe_customer_id:
                continue

            # Get Plan to check if metered
            plan = await mongo.db["subscription_plans"].find_one({"_id": plan_id})
            if not plan or not plan.get("is_metered"):
                continue

            meter_event_name = plan.get("meter_event_name")
            if not meter_event_name:
                continue

            # 2. Get active weddings for this user
            weddings = mongo.db["weddings"].find({
                "created_by": user_id,  # Assuming created_by or owner field
                "status": "active"  # Only active weddings
            })

            # 3. Check if billing is needed
            # We need to know the current billing period start/end for the subscription
            current_period_start = sub.get("current_period_start")
            if not current_period_start:
                # If missing (legacy?), fetch from Stripe? Or skip?
                continue

            if isinstance(current_period_start, str):
                try:
                    current_period_start = datetime.fromisoformat(current_period_start.replace('Z', '+00:00'))
                except ValueError:
                    continue

            # If current_period_start is naive, make it aware (assume UTC)
            # If current_period_start is naive, make it aware (assume UTC)
            if current_period_start.tzinfo is None:
                current_period_start = current_period_start.replace(tzinfo=timezone.utc)

            async for wedding in weddings:
                last_billed = wedding.get("last_billed_at")

                # If never billed, or billed before current period start -> Bill it!
                needs_billing = False
                if not last_billed:
                    needs_billing = True
                else:
                    # Ensure last_billed is timezone aware for comparison
                    if last_billed.tzinfo is None:
                        # Assume UTC if naive, as database typically stores UTC
                        last_billed = last_billed.replace(tzinfo=timezone.utc)

                    if last_billed < current_period_start:
                        needs_billing = True

                if needs_billing:
                    # Report usage
                    payload = {
                        "stripe_customer_id": stripe_customer_id,
                        "value": "1"
                    }

                    # Idempotency key: prevents double-billing on job retries
                    billing_period = current_period_start.strftime("%Y-%m")
                    idempotency_key = f"billing_job_{wedding['_id']}_{stripe_customer_id}_{billing_period}"

                    result = stripe_service.report_meter_event(
                        event_name=meter_event_name,
                        payload=payload,
                        identifier=idempotency_key
                    )

                    if result.get("status") == "success":
                        # Update last_billed_at
                        await mongo.db["weddings"].update_one(
                            {"_id": wedding["_id"]},
                            {"$set": {"last_billed_at": datetime.now(timezone.utc)}}
                        )
                        count_reported += 1

            count_processed += 1

        except Exception as e:
            logger.error(f"Error processing subscription {sub.get('_id')}: {e}")

    logger.info(f"Daily usage sync complete. Processed {count_processed} subs, reported {count_reported} events.")
