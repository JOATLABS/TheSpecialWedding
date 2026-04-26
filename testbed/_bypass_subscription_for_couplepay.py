#!/usr/bin/env python3
"""ONE-OFF test bypass: flip the couplepay test planner to subscription_status=active.

Used when running verify_couple_payments_gate.py — the driver registers and
activates the planner but does NOT subscribe them, so the planner billing
page kicks them to 'Choose Your Plan' before they can see the Couple
Payments tab. Since this verification is about Connect gating (not the
subscription flow), we flip subscription_status directly in Mongo to
unblock the UI checkpoint.

Safe to re-run. Only touches the test_planner+couplepay user.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

EMAIL = "test_planner+couplepay@thespecialwedding.io"

MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")
MONGO_DB = os.getenv("MONGO_DB") or os.getenv("MONGO_NAME", "wedding")

mongo = MongoClient(MONGO_URI)[MONGO_DB]
user = mongo["users"].find_one({"email": EMAIL})
if not user:
    raise SystemExit(
        f"no Mongo user for {EMAIL} — run verify_couple_payments_gate first"
    )

now = datetime.now(timezone.utc)

mongo["users"].update_one(
    {"_id": user["_id"]},
    {
        "$set": {
            "subscription_status": "active",
            "is_active": True,
            "user_data.plan_id": "plan_signature",
        }
    },
)

mongo["user_subscriptions"].update_one(
    {"user_id": str(user["_id"])},
    {
        "$set": {
            "user_id": str(user["_id"]),
            "plan_id": "plan_signature",
            "status": "active",
            "billing_interval": "monthly",
            "current_period_start": now.isoformat(),
            "current_period_end": (now + timedelta(days=30)).isoformat(),
            "payment_status": "paid",
            "created_at": now.isoformat(),
            "source": "verify_couple_payments_gate test bypass",
        }
    },
    upsert=True,
)

after = mongo["users"].find_one({"_id": user["_id"]})
print(f"✅ flipped subscription_status=active for {EMAIL}")
print(f"   user_id: {user['_id']}")
print(f"   subscription_status now: {after.get('subscription_status')}")
print()
print("Reload the planner billing page in Chrome — you should now see the")
print("My Subscription / Couple Payments tabs instead of the plan picker.")
