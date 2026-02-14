from fastapi import APIRouter, Depends, BackgroundTasks, Query
from datetime import datetime, timedelta, timezone
from app.dependencies.auth_extended import require_root_admin, ExtendedAuthUser
from app.services.stripe_service import stripe_service
from app.core.database import mongo
from app.models.subscription import SubscriptionStatus
import stripe as stripe_lib
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


@router.post("/billing/cleanup-orphaned-customers")
async def cleanup_orphaned_stripe_customers(
    background_tasks: BackgroundTasks,
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """
    Clean up orphaned Stripe customers from abandoned signups.
    Finds Stripe customer records where the user never completed checkout
    (no active subscription) and deletes them from Stripe.
    Should be called periodically (e.g., weekly) via cron or manually.
    """
    background_tasks.add_task(process_orphaned_customer_cleanup)
    return {"status": "accepted", "message": "Orphaned customer cleanup started in background"}


async def process_orphaned_customer_cleanup():
    """Find and clean up Stripe customers who never completed a subscription."""
    logger.info("Starting orphaned Stripe customer cleanup...")

    # Cutoff: only clean up customers older than 48 hours to avoid
    # removing customers who are still in the middle of checkout
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)

    stripe_customers = mongo.db["stripe_customers"]
    user_subscriptions = mongo.db["user_subscriptions"]
    users_collection = mongo.get_users_collection()

    # Find all local Stripe customer mappings created before cutoff
    cursor = stripe_customers.find({"created_at": {"$lt": cutoff}})
    orphaned_count = 0
    checked_count = 0
    errors = 0

    async for record in cursor:
        checked_count += 1
        user_id = record.get("user_id")
        customer_id = record.get("stripe_customer_id")

        if not customer_id:
            continue

        # Skip invitation-sourced records - they're handled by Part 2.
        # These have user_id like "invitation_{token}" which isn't a valid
        # ObjectId and would fail the user lookup silently.
        if record.get("source") == "invitation":
            continue

        try:
            # Check if user has ANY subscription record (any status means they
            # completed signup at some point - keep their Stripe customer for
            # billing history, reactivation, and portal access)
            has_subscription = await user_subscriptions.find_one({
                "user_id": user_id,
            })

            if has_subscription:
                continue  # User has a valid subscription, skip

            # Check if user exists and is still pending
            from bson import ObjectId
            try:
                user = await users_collection.find_one({"_id": ObjectId(user_id)})
            except Exception:
                user = None

            if user and user.get("subscription_status") not in ("pending_payment", "pending", None):
                continue  # User has progressed beyond pending, skip

            # Verify in Stripe that customer has no subscriptions
            try:
                stripe_subs = stripe_lib.Subscription.list(customer=customer_id, limit=1)
                if stripe_subs.data:
                    continue  # Has Stripe subscriptions, skip
            except stripe_lib.error.InvalidRequestError:
                # Customer doesn't exist in Stripe anymore - just clean local record
                await stripe_customers.delete_one({"_id": record["_id"]})
                orphaned_count += 1
                logger.info(f"Removed stale local customer record for {customer_id}")
                continue

            # Safe to delete - no subscriptions anywhere
            stripe_lib.Customer.delete(customer_id)
            await stripe_customers.delete_one({"_id": record["_id"]})
            orphaned_count += 1
            logger.info(f"Cleaned up orphaned Stripe customer {customer_id} (user: {user_id})")

        except Exception as e:
            errors += 1
            logger.error(f"Error cleaning up customer {customer_id}: {e}")

    # Part 2: Clean up Stripe customers from expired invitations
    # These are pre-created during admin invitation (user_management_service.invite_user)
    # and stored ONLY on the invitation document. If the invitation expires, the
    # Stripe customer would be orphaned forever without this cleanup.
    user_invitations = mongo.db["user_invitations"]
    invitation_cursor = user_invitations.find({
        "expires_at": {"$lt": cutoff},
        "stripe_customer_id": {"$exists": True, "$ne": None}
    })

    invitation_cleanup_count = 0
    async for invitation in invitation_cursor:
        try:
            customer_id = invitation.get("stripe_customer_id")
            if not customer_id:
                continue

            # Check if customer was adopted during signup (stored in stripe_customers)
            existing_mapping = await stripe_customers.find_one(
                {"stripe_customer_id": customer_id}
            )
            if existing_mapping:
                continue  # Customer is tracked and in use - skip

            # Verify in Stripe that customer has no subscriptions
            try:
                stripe_subs = stripe_lib.Subscription.list(customer=customer_id, limit=1)
                if stripe_subs.data:
                    continue  # Has active Stripe subscriptions - skip
            except stripe_lib.error.InvalidRequestError:
                # Customer already deleted from Stripe - just clear the reference
                pass
            else:
                # No subscriptions - safe to delete from Stripe
                try:
                    stripe_lib.Customer.delete(customer_id)
                except stripe_lib.error.InvalidRequestError:
                    pass  # Already deleted

            # Clear reference from invitation (before TTL deletes the document)
            await user_invitations.update_one(
                {"_id": invitation["_id"]},
                {"$unset": {"stripe_customer_id": ""}}
            )
            invitation_cleanup_count += 1
            logger.info(f"Cleaned up Stripe customer {customer_id} from expired invitation")

        except Exception as e:
            errors += 1
            logger.error(f"Error cleaning up invitation customer {invitation.get('stripe_customer_id')}: {e}")

    logger.info(
        f"Orphaned customer cleanup complete. "
        f"Checked {checked_count}, cleaned {orphaned_count} from stripe_customers, "
        f"{invitation_cleanup_count} from expired invitations, {errors} errors"
    )


@router.post("/billing/archive-inactive-subscriptions")
async def archive_inactive_subscriptions(
    background_tasks: BackgroundTasks,
    retention_days: int = Query(default=90, ge=30, description="Days since cancellation/expiration before archival"),
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """
    Archive old cancelled/expired subscriptions and clean up associated data.

    Archived subscriptions:
    - Get an `archived_at` timestamp (soft delete, still queryable)
    - Have their usage_tracking records deleted (no longer needed)
    - Are permanently deleted by TTL index 180 days after archival

    Should be called periodically (e.g., monthly) via cron or manually.
    """
    background_tasks.add_task(process_subscription_archival, retention_days)
    return {
        "status": "accepted",
        "message": f"Subscription archival started (retention: {retention_days} days)"
    }


async def process_subscription_archival(retention_days: int = 90):
    """Archive inactive subscriptions and clean up associated usage data."""
    logger.info(f"Starting subscription archival (retention: {retention_days} days)...")

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=retention_days)

    subscriptions = mongo.db["user_subscriptions"]
    usage_tracking = mongo.db["usage_tracking"]

    # Find cancelled/expired subscriptions older than cutoff that aren't already archived.
    # Uses $or to catch both paths:
    # - Cancelled subs (including Stripe-cancelled trials where trial_expired_at is never set)
    # - Expired subs (from trial_expiration_service)
    query = {
        "archived_at": {"$exists": False},
        "$or": [
            {"status": "cancelled", "cancelled_at": {"$lt": cutoff}},
            {"status": "expired", "trial_expired_at": {"$lt": cutoff}},
        ]
    }

    cursor = subscriptions.find(query)
    archived_count = 0
    usage_deleted = 0
    errors = 0

    async for sub in cursor:
        try:
            sub_id = sub["_id"]

            # Soft-archive the subscription
            result = await subscriptions.update_one(
                {"_id": sub_id},
                {"$set": {
                    "archived_at": now,
                    "updated_at": now
                }}
            )

            if result.modified_count > 0:
                archived_count += 1

                # Clean up usage_tracking records for this subscription
                # usage_tracking documents have subscription_id field (set in
                # subscription_service.initialize_usage_tracking)
                usage_result = await usage_tracking.delete_many(
                    {"subscription_id": str(sub_id)}
                )
                if usage_result.deleted_count > 0:
                    usage_deleted += usage_result.deleted_count
                    logger.info(
                        f"Archived subscription {sub_id}, "
                        f"deleted {usage_result.deleted_count} usage records"
                    )

        except Exception as e:
            errors += 1
            logger.error(f"Error archiving subscription {sub.get('_id')}: {e}")

    logger.info(
        f"Subscription archival complete. "
        f"Archived {archived_count} subscriptions, "
        f"deleted {usage_deleted} usage records, {errors} errors"
    )
