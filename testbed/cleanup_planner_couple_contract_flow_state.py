#!/usr/bin/env python3
"""Clean up state from verify_planner_couple_contract_flow.py.

Removes the test planner's contract row, scheduled_payments rows,
test wedding, the planner user itself, and the Stripe Express test
account that the verifier created. Safe to re-run.

Usage:
    python testbed/cleanup_planner_couple_contract_flow_state.py
"""

from __future__ import annotations

import logging
import os
import sys

import stripe
from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("cleanup_contract_flow")

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY") or os.getenv("STRIPE_API_KEY")
MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")
MONGO_DB = os.getenv("MONGO_DB") or os.getenv("MONGO_NAME", "wedding")

PLANNER_EMAIL = "test_planner+contractflow@thespecialwedding.io"
COUPLE_EMAIL = "test_couple+contractflow@thespecialwedding.io"

if not STRIPE_SECRET_KEY:
    logger.error("STRIPE_SECRET_KEY is not set in .env")
    sys.exit(1)
if not MONGO_URI:
    logger.error("MONGO_URI / MONGODB_URI is not set in .env")
    sys.exit(1)

stripe.api_key = STRIPE_SECRET_KEY
mongo = MongoClient(MONGO_URI)[MONGO_DB]


def delete_stripe_account(account_id: str) -> None:
    try:
        stripe.Account.delete(account_id)
        logger.info("  ✅ Deleted Stripe Express account %s", account_id)
    except stripe.error.StripeError as exc:
        logger.warning("  ⚠️ Could not delete Stripe account %s: %s", account_id, exc)


def cleanup() -> None:
    user = mongo["users"].find_one({"email": PLANNER_EMAIL})
    if not user:
        logger.info("  (no planner user — nothing to clean)")
        return

    user_id = str(user["_id"])
    logger.info("Cleaning state for planner %s (user_id=%s)…", PLANNER_EMAIL, user_id)

    # Stripe Connect account
    if user.get("stripe_connect_id"):
        delete_stripe_account(user["stripe_connect_id"])

    # Find contracts owned by this planner with the test couple
    contracts = list(
        mongo["contracts"].find({"planner_id": user_id, "couple.email": COUPLE_EMAIL})
    )
    for contract in contracts:
        contract_id_str = str(contract["_id"])
        # scheduled_payments rows
        sp_result = mongo["scheduled_payments"].delete_many(
            {"contract_id": contract_id_str}
        )
        if sp_result.deleted_count:
            logger.info(
                "  ✅ scheduled_payments: removed %d for contract %s",
                sp_result.deleted_count,
                contract_id_str,
            )
        # Stripe customer cleanup (couple's Customer object)
        customer_id = contract.get("stripe_customer_id")
        if customer_id:
            try:
                stripe.Customer.delete(customer_id)
                logger.info("  ✅ Deleted Stripe customer %s", customer_id)
            except stripe.error.StripeError as exc:
                logger.warning(
                    "  ⚠️ Could not delete Stripe customer %s: %s", customer_id, exc
                )

    if contracts:
        result = mongo["contracts"].delete_many(
            {"planner_id": user_id, "couple.email": COUPLE_EMAIL}
        )
        if result.deleted_count:
            logger.info("  ✅ contracts: removed %d", result.deleted_count)

    # Test wedding
    w_result = mongo["weddings"].delete_many(
        {"planner_id": user_id, "couple.email": COUPLE_EMAIL}
    )
    if w_result.deleted_count:
        logger.info("  ✅ weddings: removed %d", w_result.deleted_count)

    # Subscriptions / customer-link rows for the planner
    for coll_name in ("user_subscriptions", "stripe_customers", "team_members"):
        result = mongo[coll_name].delete_many({"user_id": user_id})
        if result.deleted_count:
            logger.info("  ✅ %s: removed %d", coll_name, result.deleted_count)

    # The planner user itself
    result = mongo["users"].delete_one({"_id": ObjectId(user_id)})
    if result.deleted_count:
        logger.info("  ✅ users: removed %s", PLANNER_EMAIL)


def main() -> int:
    logger.info("Starting cleanup of planner-couple contract flow verification state…")
    logger.info("  Mongo DB: %s", MONGO_DB)
    logger.info("  Planner:  %s", PLANNER_EMAIL)
    logger.info("  Couple:   %s", COUPLE_EMAIL)
    logger.info("")
    cleanup()
    logger.info("")
    logger.info("Cleanup complete. SEED phase can run from a blank slate.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        logger.error("Cleanup aborted: %s", exc, exc_info=True)
        raise SystemExit(1)
