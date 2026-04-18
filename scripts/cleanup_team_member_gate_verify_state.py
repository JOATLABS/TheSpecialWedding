#!/usr/bin/env python3
"""Clean up partial/leaked state from verify_team_member_gate_via_test_clock.py.

Removes the planner + team-member Mongo records and any Stripe customer
attached to the verification test clock so the SEED phase can run cleanly
from scratch. Does NOT delete the test clock itself.

Usage:
    python scripts/cleanup_team_member_gate_verify_state.py

Safe to re-run. Only touches records matching the plus-variant emails used
by the verification script.
"""

from __future__ import annotations

import logging
import os
import sys

import stripe
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("cleanup_verify_state")

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY") or os.getenv("STRIPE_API_KEY")
MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")
MONGO_DB = os.getenv("MONGO_DB") or os.getenv("MONGO_NAME", "wedding")

PLANNER_EMAIL = "test_planner2+teamgate@thespecialwedding.io"
TEAM_MEMBER_EMAIL = "test_team_member+teamgate@thespecialwedding.io"
TEST_CLOCK_ID = "clock_1TNGs4JbfaNLE8qUOMEjk2ZU"

if not STRIPE_SECRET_KEY:
    logger.error("STRIPE_SECRET_KEY is not set in .env")
    sys.exit(1)

if not MONGO_URI:
    logger.error("MONGO_URI / MONGODB_URI is not set in .env")
    sys.exit(1)

stripe.api_key = STRIPE_SECRET_KEY
mongo = MongoClient(MONGO_URI)[MONGO_DB]


def delete_stripe_customers_on_clock() -> None:
    """Delete every Stripe customer pinned to the verification test clock.

    We use Stripe's native ``test_clock`` list filter rather than iterating
    every customer and checking client-side, because the ``test_clock``
    field is not always populated on Customer objects returned by the list
    endpoint — only the filtered list guarantees correct membership.
    """
    logger.info(f"Listing Stripe customers on clock {TEST_CLOCK_ID}…")
    deleted = 0
    for customer in stripe.Customer.list(
        test_clock=TEST_CLOCK_ID, limit=100
    ).auto_paging_iter():
        try:
            stripe.Customer.delete(customer.id)
            logger.info(
                f"  ✅ Deleted Stripe customer {customer.id} ({customer.email or '—'})"
            )
            deleted += 1
        except stripe.error.StripeError as exc:
            logger.warning(f"  ⚠️ Could not delete {customer.id}: {exc}")
    if deleted == 0:
        logger.info("  (no customers on that clock — nothing to delete)")


def delete_mongo_user_chain(email: str) -> None:
    """Delete a user and every document that references them by user_id."""
    user = mongo["users"].find_one({"email": email})
    if not user:
        logger.info(f"  (no Mongo user for {email})")
        return

    user_id = str(user["_id"])
    logger.info(f"Cleaning Mongo chain for {email} (user_id={user_id})…")

    # Records keyed by user_id
    for coll_name in ("user_subscriptions", "stripe_customers", "team_members"):
        result = mongo[coll_name].delete_many({"user_id": user_id})
        if result.deleted_count:
            logger.info(f"  ✅ {coll_name}: removed {result.deleted_count} doc(s)")

    # Records keyed by invitee email (for incoming invites to this user)
    result = mongo["team_members"].delete_many({"email": email})
    if result.deleted_count:
        logger.info(
            f"  ✅ team_members (by invitee email): removed {result.deleted_count} doc(s)"
        )

    # Finally the user itself
    result = mongo["users"].delete_one({"_id": user["_id"]})
    if result.deleted_count:
        logger.info(f"  ✅ users: removed {email}")


def main() -> int:
    logger.info("Starting cleanup of verification state…")
    logger.info(f"  Mongo DB:    {MONGO_DB}")
    logger.info(f"  Planner:     {PLANNER_EMAIL}")
    logger.info(f"  Team member: {TEAM_MEMBER_EMAIL}")
    logger.info(f"  Test clock:  {TEST_CLOCK_ID} (will NOT be deleted)")
    logger.info("")

    delete_stripe_customers_on_clock()
    logger.info("")
    delete_mongo_user_chain(PLANNER_EMAIL)
    delete_mongo_user_chain(TEAM_MEMBER_EMAIL)
    logger.info("")
    logger.info("Cleanup complete. The SEED phase can now run from a blank slate.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        logger.error(f"Cleanup aborted: {exc}", exc_info=True)
        raise SystemExit(1)
