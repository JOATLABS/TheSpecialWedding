"""
Manually trigger checkout completion sync for a user whose Stripe webhook was missed.

Usage:
    python scripts/resend_checkout_webhook.py webhook.test@example.com

This script:
1. Looks up the user by email
2. Finds their Stripe checkout session
3. Retrieves subscription from Stripe API
4. Updates MongoDB with the subscription data (same logic as webhook handler)
"""

import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

import stripe
from bson import ObjectId
from pymongo import MongoClient

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.models.subscription import normalize_subscription_status

# Connect to MongoDB (same pattern as seed_subscription_plans.py)
mongo_uri = (
    os.getenv("MONGO_URI")
    or os.getenv("MONGODB_URI")
    or os.getenv("MONGO_URL")
    or "mongodb://localhost:27017"
)
db_name = os.getenv("MONGO_DB", "wedding")

print(f"Connecting to MongoDB: {db_name}")
client = MongoClient(mongo_uri)
db = client[db_name]

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/resend_checkout_webhook.py <email>")
        sys.exit(1)

    email = sys.argv[1]

    # Find the user
    user = db["users"].find_one({"email": email})
    if not user:
        print(f"User not found: {email}")
        sys.exit(1)

    user_id = str(user["_id"])
    print(f"Found user: {email} (ID: {user_id})")
    print(f"  is_active: {user.get('is_active')}")
    print(f"  email_verified: {user.get('email_verified')}")
    print(f"  subscription_status: {user.get('subscription_status')}")
    print(f"  plan_id: {user.get('plan_id')}")

    # Find their subscription record
    sub_record = db["user_subscriptions"].find_one({"user_id": user_id})
    if not sub_record:
        print(f"\nNo subscription record found for user {user_id}")
        sys.exit(1)

    print(f"\nSubscription record:")
    print(f"  plan_id: {sub_record.get('plan_id')}")
    print(f"  status: {sub_record.get('status')}")
    print(f"  stripe_customer_id: {sub_record.get('stripe_customer_id')}")
    print(
        f"  stripe_checkout_session_id: {sub_record.get('stripe_checkout_session_id')}"
    )

    # Get the checkout session from Stripe
    checkout_session_id = sub_record.get("stripe_checkout_session_id")
    if not checkout_session_id:
        print("No checkout session ID found")
        sys.exit(1)

    print(f"\nRetrieving checkout session from Stripe: {checkout_session_id}")
    session = stripe.checkout.Session.retrieve(checkout_session_id)

    print(f"  status: {session.status}")
    print(f"  payment_status: {session.payment_status}")
    print(f"  subscription: {session.subscription}")
    print(f"  customer: {session.customer}")
    print(f"  metadata: {dict(session.metadata)}")

    if session.status != "complete":
        print(f"\nCheckout session is not complete (status: {session.status})")
        sys.exit(1)

    subscription_id = session.subscription
    if not subscription_id:
        print("\nNo subscription ID in checkout session")
        sys.exit(1)

    # Retrieve the full subscription from Stripe
    print(f"\nRetrieving subscription from Stripe: {subscription_id}")
    subscription = stripe.Subscription.retrieve(subscription_id, expand=["items.data"])

    print(f"  status: {subscription.status}")
    print(f"  metadata: {dict(subscription.metadata)}")

    # Stripe API v13+: current_period_start/end are on subscription items, not top-level
    sub_item = (
        subscription["items"]["data"][0] if subscription["items"]["data"] else None
    )
    raw_period_start = None
    raw_period_end = None
    if sub_item:
        raw_period_start = sub_item.get("current_period_start") or subscription.get(
            "start_date"
        )
        raw_period_end = sub_item.get("current_period_end")
        print(f"  current_period_start: {raw_period_start}")
        print(f"  current_period_end: {raw_period_end}")
    else:
        # Fallback to subscription-level fields
        raw_period_start = subscription.get("start_date")
        print(f"  start_date: {raw_period_start}")

    # Get plan_id from subscription metadata (checkout session metadata may be empty)
    plan_id = (
        subscription.metadata.get("plan_id")
        or session.metadata.get("plan_id")
        or sub_record.get("plan_id")
    )
    customer_id = session.customer
    print(f"  resolved plan_id: {plan_id}")

    # Map Stripe status to internal status
    internal_status = (
        normalize_subscription_status(subscription.status) or subscription.status
    )

    now = datetime.now(timezone.utc)
    period_start = (
        datetime.fromtimestamp(raw_period_start, tz=timezone.utc)
        if raw_period_start
        else now
    )
    period_end = (
        datetime.fromtimestamp(raw_period_end, tz=timezone.utc)
        if raw_period_end
        else now
    )

    # Build plan snapshot
    plan = db["subscription_plans"].find_one({"_id": plan_id})
    plan_snapshot = None
    if plan:
        plan_snapshot = {
            "plan_name": plan.get("name"),
            "max_weddings": plan.get("max_weddings", 1),
            "max_guests_per_wedding": plan.get("max_guests_per_wedding", 100),
            "ai_credits_monthly": plan.get("ai_credits_monthly", 10),
            "storage_gb": plan.get("storage_gb", 1),
            "staff_seats": plan.get("staff_seats", 0),
            "features": plan.get("features", {}),
            "price_monthly": plan.get("price_monthly", 0),
            "price_yearly": plan.get("price_yearly"),
            "snapshot_date": now,
        }

    # Update user_subscriptions collection
    print(f"\n--- Updating subscription record ---")
    sub_update = {
        "stripe_subscription_id": subscription_id,
        "stripe_customer_id": customer_id,
        "status": internal_status,
        "stripe_status": subscription.status,
        "current_period_start": period_start,
        "current_period_end": period_end,
        "payment_status": session.payment_status,
        "stripe_checkout_completed_at": now,
        "updated_at": now,
    }
    if plan_id:
        sub_update["plan_id"] = plan_id
    if plan_snapshot:
        sub_update["plan_snapshot"] = plan_snapshot

    result = db["user_subscriptions"].update_one(
        {"user_id": user_id}, {"$set": sub_update}
    )
    print(f"  matched: {result.matched_count}, modified: {result.modified_count}")

    # Update users collection
    print(f"\n--- Updating user record ---")
    user_update = {
        "subscription_status": internal_status,
        "plan_id": plan_id,
        "stripe_customer_id": customer_id,
        "stripe_subscription_id": subscription_id,
        "updated_at": now,
    }

    if internal_status in ("active", "trial"):
        user_update["is_active"] = True
        user_update["email_verified"] = True

    user_unset = {}
    if internal_status in ("active", "trial"):
        user_unset["email_verification_token"] = ""
        user_unset["verification_token_expires"] = ""
        user_unset["pending_expires_at"] = ""

    update_doc = {"$set": user_update}
    if user_unset:
        update_doc["$unset"] = user_unset

    result = db["users"].update_one({"_id": user["_id"]}, update_doc)
    print(f"  matched: {result.matched_count}, modified: {result.modified_count}")

    # Initialize usage tracking
    print(f"\n--- Initializing usage tracking ---")
    sub_id = str(sub_record["_id"])
    existing_usage = db["usage_tracking"].find_one({"user_id": user_id})
    if existing_usage:
        print(f"  Usage tracking already exists for user {user_id}")
    else:
        # Get plan limits
        max_weddings = plan.get("max_weddings", 1) if plan else 1
        max_guests = plan.get("max_guests_per_wedding", 100) if plan else 100
        ai_credits = plan.get("ai_credits_monthly", 10) if plan else 10
        storage_gb = plan.get("storage_gb", 1) if plan else 1

        usage_doc = {
            "user_id": user_id,
            "subscription_id": sub_id,
            "plan_id": plan_id,
            "weddings_used": 0,
            "weddings_limit": max_weddings,
            "guests_used": 0,
            "guests_limit": max_guests,
            "ai_credits_used": 0,
            "ai_credits_limit": ai_credits,
            "storage_used_gb": 0.0,
            "storage_limit_gb": storage_gb,
            "billing_period_start": period_start,
            "billing_period_end": period_end,
            "created_at": now,
            "updated_at": now,
        }
        db["usage_tracking"].insert_one(usage_doc)
        print(f"  Created usage tracking record")

    # Verify final state
    updated_sub = db["user_subscriptions"].find_one({"user_id": user_id})
    updated_user = db["users"].find_one({"_id": user["_id"]})
    usage = db["usage_tracking"].find_one({"user_id": user_id})

    print(f"\n{'=' * 50}")
    print(f"FINAL STATE")
    print(f"{'=' * 50}")

    print(f"\nSubscription:")
    print(f"  status: {updated_sub.get('status')}")
    print(f"  stripe_status: {updated_sub.get('stripe_status')}")
    print(f"  stripe_subscription_id: {updated_sub.get('stripe_subscription_id')}")
    print(f"  current_period_start: {updated_sub.get('current_period_start')}")
    print(f"  current_period_end: {updated_sub.get('current_period_end')}")
    print(f"  plan_id: {updated_sub.get('plan_id')}")
    print(f"  plan_snapshot: {'YES' if updated_sub.get('plan_snapshot') else 'NO'}")

    print(f"\nUser:")
    print(f"  is_active: {updated_user.get('is_active')}")
    print(f"  email_verified: {updated_user.get('email_verified')}")
    print(f"  subscription_status: {updated_user.get('subscription_status')}")
    print(f"  plan_id: {updated_user.get('plan_id')}")
    print(f"  stripe_customer_id: {updated_user.get('stripe_customer_id')}")

    if usage:
        print(f"\nUsage Tracking:")
        print(f"  weddings: {usage.get('weddings_used')}/{usage.get('weddings_limit')}")
        print(f"  guests: {usage.get('guests_used')}/{usage.get('guests_limit')}")
        print(
            f"  ai_credits: {usage.get('ai_credits_used')}/{usage.get('ai_credits_limit')}"
        )
        print(
            f"  storage_gb: {usage.get('storage_used_gb')}/{usage.get('storage_limit_gb')}"
        )
    else:
        print(f"\nUsage Tracking: NOT FOUND")

    print(f"\nDone!")
    client.close()


if __name__ == "__main__":
    main()
