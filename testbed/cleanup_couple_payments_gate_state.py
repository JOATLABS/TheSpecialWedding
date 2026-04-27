#!/usr/bin/env python3
"""Clean up partial/leaked state from verify_couple_payments_gate.py.

Removes the planner's Mongo records, payment_requests rows, and the
Stripe Express test account that the verification driver created. Safe
to re-run; only touches records matching the plus-variant email used by
the verification script.

Usage:
    python testbed/cleanup_couple_payments_gate_state.py
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
logger = logging.getLogger("cleanup_couple_payments_gate")

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY") or os.getenv("STRIPE_API_KEY")
MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")
MONGO_DB = os.getenv("MONGO_DB") or os.getenv("MONGO_NAME", "wedding")

PLANNER_EMAIL = "test_planner+couplepay@thespecialwedding.io"

if not STRIPE_SECRET_KEY:
    logger.error("STRIPE_SECRET_KEY is not set in .env")
    sys.exit(1)

if not MONGO_URI:
    logger.error("MONGO_URI / MONGODB_URI is not set in .env")
    sys.exit(1)

stripe.api_key = STRIPE_SECRET_KEY
mongo = MongoClient(MONGO_URI)[MONGO_DB]


def delete_stripe_connect_account(account_id: str) -> None:
    """Delete the Express test account from Stripe."""
    try:
        stripe.Account.delete(account_id)
        logger.info("  ✅ Deleted Stripe Express account %s", account_id)
    except stripe.error.StripeError as exc:
        # Already-deleted or API rejected — log and move on.
        logger.warning("  ⚠️ Could not delete Stripe account %s: %s", account_id, exc)


def delete_mongo_user_chain(email: str) -> None:
    """Drop the planner user, their payment_requests, and any subscription rows."""
    user = mongo["users"].find_one({"email": email})
    if not user:
        logger.info("  (no Mongo user for %s)", email)
        return

    user_id = str(user["_id"])
    logger.info("Cleaning Mongo chain for %s (user_id=%s)…", email, user_id)

    # Delete the Stripe Connect account FIRST while we still have the id.
    connect_id = user.get("stripe_connect_id")
    if connect_id:
        delete_stripe_connect_account(connect_id)

    for coll_name in (
        "payment_requests",
        "user_subscriptions",
        "stripe_customers",
        "team_members",
    ):
        result = mongo[coll_name].delete_many({"user_id": user_id})
        if result.deleted_count:
            logger.info("  ✅ %s: removed %d doc(s)", coll_name, result.deleted_count)

    result = mongo["users"].delete_one({"_id": user["_id"]})
    if result.deleted_count:
        logger.info("  ✅ users: removed %s", email)


def main() -> int:
    logger.info("Starting cleanup of couple-payments-gate verification state…")
    logger.info("  Mongo DB: %s", MONGO_DB)
    logger.info("  Planner:  %s", PLANNER_EMAIL)
    logger.info("")

    delete_mongo_user_chain(PLANNER_EMAIL)
    logger.info("")
    logger.info("Cleanup complete. The SEED phase can now run from a blank slate.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        logger.error("Cleanup aborted: %s", exc, exc_info=True)
        raise SystemExit(1)
