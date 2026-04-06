"""
Sync a user's subscription state from Stripe to the platform DB.

Use when the local DB is out of sync with Stripe (e.g., plan changed
via Stripe Customer Portal but webhook didn't update the platform).

Usage:
  python -m app.scripts.sync_stripe_subscription test_planner2@thespecialwedding.io
"""

import asyncio
import sys
import os
import stripe
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.core.database import mongo, init_database  # noqa: E402
from app.models.subscription import normalize_subscription_status  # noqa: E402
from app.core.settings import settings  # noqa: E402


async def sync(email: str):
    await init_database()
    db = mongo.db

    stripe.api_key = settings.stripe_secret_key
    if not stripe.api_key:
        print("[ERROR] STRIPE_SECRET_KEY not set")
        mongo.close()
        return

    users_col = db["users"]
    subs_col = db["user_subscriptions"]
    plans_col = db["subscription_plans"]

    # Find the user
    user = await users_col.find_one({"email": email})
    if not user:
        print(f"[ERROR] User not found: {email}")
        mongo.close()
        return

    user_id = str(user["_id"])
    stripe_sub_id = user.get("stripe_subscription_id")
    stripe_cust_id = user.get("stripe_customer_id")

    print(f"[INFO] User: {email}")
    print(f"[INFO] Local plan_id: {user.get('plan_id')}")
    print(f"[INFO] Local subscription_status: {user.get('subscription_status')}")
    print(f"[INFO] Stripe subscription ID: {stripe_sub_id}")
    print(f"[INFO] Stripe customer ID: {stripe_cust_id}")

    if not stripe_sub_id:
        print("[ERROR] No stripe_subscription_id on user record")
        mongo.close()
        return

    # Fetch subscription from Stripe
    try:
        stripe_sub = stripe.Subscription.retrieve(stripe_sub_id)
    except Exception as e:
        print(f"[ERROR] Failed to retrieve Stripe subscription: {e}")
        mongo.close()
        return

    # Convert Stripe object to dict for safe access
    sub_dict = stripe_sub.to_dict() if hasattr(stripe_sub, 'to_dict') else dict(stripe_sub)

    print(f"\n[STRIPE] Subscription status: {sub_dict.get('status')}")

    # Get the current price from subscription items
    items_data = sub_dict.get("items", {})
    items_list = items_data.get("data", []) if isinstance(items_data, dict) else []
    if not items_list:
        print("[ERROR] No items on Stripe subscription")
        mongo.close()
        return

    first_item = items_list[0] if isinstance(items_list[0], dict) else (items_list[0].to_dict() if hasattr(items_list[0], 'to_dict') else {})

    # Period dates live on items in newer Stripe API
    raw_period_start = first_item.get("current_period_start") or sub_dict.get("current_period_start")
    raw_period_end = first_item.get("current_period_end") or sub_dict.get("current_period_end")
    print(f"[STRIPE] Current period: {raw_period_start} → {raw_period_end}")

    price_obj = first_item.get("price", {})
    if not isinstance(price_obj, dict) and hasattr(price_obj, 'to_dict'):
        price_obj = price_obj.to_dict()
    elif not isinstance(price_obj, dict):
        price_obj = {}

    current_price_id = price_obj.get("id")
    price_amount = (price_obj.get("unit_amount") or 0) / 100
    recurring = price_obj.get("recurring", {}) or {}
    price_interval = recurring.get("interval", "month") if isinstance(recurring, dict) else "month"

    print(f"[STRIPE] Current price ID: {current_price_id}")
    print(f"[STRIPE] Price: ${price_amount}/{price_interval}")

    # Resolve platform plan from Stripe price
    matched_plan = await plans_col.find_one({
        "$or": [
            {"stripe_price_id_monthly": current_price_id},
            {"stripe_price_id_yearly": current_price_id},
        ]
    })

    if not matched_plan:
        print(f"[ERROR] No platform plan found matching Stripe price: {current_price_id}")
        # List all plans for debugging
        all_plans = await plans_col.find({}).to_list(length=None)
        print("\n[DEBUG] Available plans:")
        for p in all_plans:
            print(f"  {p['_id']}: monthly={p.get('stripe_price_id_monthly')}, yearly={p.get('stripe_price_id_yearly')}")
        mongo.close()
        return

    resolved_plan_id = matched_plan["_id"]
    print(f"[RESOLVED] Platform plan: {resolved_plan_id} ({matched_plan.get('name')})")

    # Map Stripe status to internal status
    internal_status = normalize_subscription_status(stripe_sub.status) or "active"

    now = datetime.now(timezone.utc)

    # Determine billing interval
    billing_interval = "yearly" if price_interval == "year" else "monthly"

    # Build plan snapshot
    plan_snapshot = {
        "plan_name": matched_plan.get("name"),
        "max_weddings": matched_plan.get("max_weddings", 1),
        "max_guests_per_wedding": matched_plan.get("max_guests_per_wedding", 100),
        "ai_credits_monthly": matched_plan.get("ai_credits_monthly", 10),
        "storage_gb": matched_plan.get("storage_gb", 1),
        "staff_seats": matched_plan.get("staff_seats", 0),
        "features": matched_plan.get("features", {}),
        "price_monthly": matched_plan.get("price_monthly", 0),
        "price_yearly": matched_plan.get("price_yearly"),
        "snapshot_date": now,
    }

    # Parse period dates (from items or top-level)
    period_start = datetime.fromtimestamp(raw_period_start, tz=timezone.utc) if raw_period_start else now
    period_end = datetime.fromtimestamp(raw_period_end, tz=timezone.utc) if raw_period_end else now

    print(f"\n[SYNC] Updating platform:")
    print(f"  plan_id: {user.get('plan_id')} → {resolved_plan_id}")
    print(f"  subscription_status: {user.get('subscription_status')} → {internal_status}")
    print(f"  billing_interval: {billing_interval}")
    print(f"  period: {period_start.isoformat()} → {period_end.isoformat()}")

    # Update users collection
    await users_col.update_one(
        {"_id": user["_id"]},
        {"$set": {
            "plan_id": resolved_plan_id,
            "subscription_status": internal_status,
            "stripe_subscription_id": stripe_sub_id,
            "updated_at": now,
        }}
    )
    print("[OK] Users collection updated")

    # Update user_subscriptions collection
    result = await subs_col.update_one(
        {"user_id": user_id},
        {"$set": {
            "plan_id": resolved_plan_id,
            "status": internal_status,
            "stripe_status": stripe_sub.status,
            "billing_interval": billing_interval,
            "current_period_start": period_start,
            "current_period_end": period_end,
            "plan_snapshot": plan_snapshot,
            "updated_at": now,
        }}
    )
    print(f"[OK] Subscriptions updated: {result.modified_count}")

    print(f"\n[DONE] {email} synced to {matched_plan.get('name')} ({resolved_plan_id}) — status: {internal_status}")

    mongo.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m app.scripts.sync_stripe_subscription <email>")
        sys.exit(1)
    asyncio.run(sync(sys.argv[1]))
