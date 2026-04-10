"""
Force-expire a user's trial for testing.

Usage:
  python -m app.scripts.force_expire_trial test_planner2@thespecialwedding.io
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.core.database import init_database, mongo  # noqa: E402


async def force_expire(email: str):
    await init_database()
    db = mongo.db

    users_col = db["users"]
    subs_col = db["user_subscriptions"]

    # Set trial_end_date to 1 hour ago
    past_date = datetime.now(timezone.utc) - timedelta(hours=1)

    user = await users_col.find_one({"email": email})
    if not user:
        print(f"[ERROR] User not found: {email}")
        mongo.close()
        return

    user_id = str(user["_id"])
    print(f"[INFO] Found user: {email} (id: {user_id})")
    print(f"[INFO] Current subscription_status: {user.get('subscription_status')}")
    print(f"[INFO] Current trial_end_date: {user.get('trial_end_date')}")
    print(f"[INFO] Setting trial_end_date to: {past_date.isoformat()}")

    # Update users collection — keep is_active=True so planner can
    # still log in and reach the billing page to upgrade
    await users_col.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "trial_end_date": past_date,
                "is_active": True,
                "subscription_status": "trial",
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )

    # Update user_subscriptions collection
    result = await subs_col.update_one(
        {"user_id": user_id, "status": "trial"},
        {
            "$set": {
                "trial_end_date": past_date,
                "current_period_end": past_date,
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )

    print("[OK] Users collection updated")
    print(f"[OK] Subscriptions updated: {result.modified_count}")
    print("\nNext login attempt will trigger trial expiration (402).")

    mongo.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m app.scripts.force_expire_trial <email>")
        sys.exit(1)
    asyncio.run(force_expire(sys.argv[1]))
