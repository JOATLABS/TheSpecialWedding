#!/usr/bin/env python3
"""One-shot recovery for plans clobbered by the product.updated webhook bug.

Background (2026-05-13):
Before the bug-fix at ``stripe_service._handle_stripe_product_updated``,
every admin save would fire a Stripe ``product.updated`` webhook that
re-asserted ``is_active = Stripe.product.active`` to Mongo. If the
Stripe Product was archived for any reason (prior delete_plan, manual
Dashboard archive), the webhook reverted the admin's re-activation
edit immediately.

This script repairs the damage by:

  1. Reading every canonical plan from Mongo
  2. For each one whose ``is_active`` is False AND whose Stripe Product
     is archived, OFFERING to:
       a. Un-archive the Stripe Product (Product.modify active=True)
       b. Set Mongo ``is_active=True`` AND clear ``deleted_at`` if set
       c. Record ``admin_overrides.is_active = <now>`` so the fix's
          webhook handler will never clobber this again

Run mode flags:
  DRY_RUN=1  (default) — print what WOULD happen, write nothing
  DRY_RUN=0  — actually apply the repair

Usage::

    # First pass: see what's broken
    python scripts/reactivate_clobbered_plans.py

    # Apply the repair
    DRY_RUN=0 python scripts/reactivate_clobbered_plans.py

The fix at app/services/stripe_service.py (both the
``stripe.Product.modify(active=...)`` in ``sync_plan_to_stripe`` and the
``admin_overrides`` check in ``_handle_stripe_product_updated``) ensures
this won't happen again after the next deploy.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / ".env")

try:
    from pymongo import MongoClient
except ImportError:
    print("[ERROR] pymongo not installed", file=sys.stderr)
    sys.exit(1)

try:
    import stripe
    from stripe import StripeError
except ImportError:
    print("[ERROR] stripe SDK not installed", file=sys.stderr)
    sys.exit(1)


MONGO_URI = (
    os.getenv("MONGO_URI")
    or os.getenv("MONGODB_URI")
    or os.getenv("MONGO_URL")
    or "mongodb://localhost:27017"
)
DB_NAME = os.getenv("MONGO_DB", "wedding")
STRIPE_KEY = os.getenv("STRIPE_SECRET_KEY")
DRY_RUN = os.getenv("DRY_RUN", "1") != "0"

# 2026-07 pricing strategy: plan_solo and plan_enterprise are RETIRED and
# must never be reactivated by this recovery script. Only the live catalog
# (Solo Founding / Solo Standard / White Glove) is eligible for repair.
CANONICAL_IDS = ("plan_boutique", "plan_solo_standard", "plan_signature")


def main() -> int:
    if not STRIPE_KEY:
        print("[ERROR] STRIPE_SECRET_KEY not set", file=sys.stderr)
        return 1
    stripe.api_key = STRIPE_KEY

    print("=" * 70)
    print("PLAN RE-ACTIVATION RECOVERY")
    print(
        f"  Mode: {'DRY RUN — no writes' if DRY_RUN else 'APPLY — will write to Mongo + Stripe'}"
    )
    print(f"  Mongo: {MONGO_URI[:40]}...")
    print(f"  DB   : {DB_NAME}")
    print("=" * 70)

    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    coll = client[DB_NAME]["subscription_plans"]
    now = datetime.now(timezone.utc)

    affected = 0
    repaired = 0
    skipped = 0

    for plan_id in CANONICAL_IDS:
        plan = coll.find_one({"_id": plan_id})
        print(f"\n--- {plan_id} ---")

        if not plan:
            print("  (not in Mongo — skip)")
            continue

        is_active = plan.get("is_active")
        deleted_at = plan.get("deleted_at")
        stripe_product_id = plan.get("stripe_product_id")
        admin_overrides = plan.get("admin_overrides") or {}

        print(f"  Mongo.is_active        : {is_active!r}")
        print(f"  Mongo.deleted_at       : {deleted_at!r}")
        print(f"  Mongo.stripe_product_id: {stripe_product_id!r}")
        print(
            f"  Mongo.admin_overrides.is_active: {admin_overrides.get('is_active')!r}"
        )

        if is_active is True and deleted_at is None:
            print("  ✅ Plan already active and not soft-deleted; nothing to fix.")
            skipped += 1
            continue

        if not stripe_product_id:
            print("  ⚠️  No stripe_product_id; can only fix Mongo side.")
            stripe_active = None
        else:
            try:
                product = stripe.Product.retrieve(stripe_product_id)
                stripe_active = product.active
                print(f"  Stripe.product.active   : {stripe_active!r}")
            except StripeError as exc:
                print(f"  ⚠️  Could not retrieve Stripe Product: {exc}")
                stripe_active = None

        affected += 1

        if DRY_RUN:
            print("  [DRY RUN] Would apply:")
            if stripe_active is False:
                print(f"    - stripe.Product.modify({stripe_product_id}, active=True)")
            print(
                f"    - Mongo $set is_active=True, admin_overrides.is_active={now.isoformat()}"
            )
            if deleted_at is not None:
                print("    - Mongo $unset deleted_at")
            continue

        # APPLY
        if stripe_active is False and stripe_product_id:
            try:
                stripe.Product.modify(stripe_product_id, active=True)
                print(f"  [APPLIED] Un-archived Stripe Product {stripe_product_id}")
            except StripeError as exc:
                print(f"  ⚠️  Could not un-archive Stripe Product: {exc}")

        set_doc = {
            "is_active": True,
            "admin_overrides.is_active": now,
            "updated_at": now,
        }
        update_args: dict = {"$set": set_doc}
        if deleted_at is not None:
            update_args["$unset"] = {"deleted_at": ""}

        result = coll.update_one({"_id": plan_id}, update_args)
        if result.modified_count > 0:
            repaired += 1
            print(f"  [APPLIED] Mongo updated (modified_count={result.modified_count})")
        else:
            print("  [WARN] Mongo update_one didn't modify anything")

    print()
    print("=" * 70)
    print("SUMMARY")
    print(f"  Plans inspected: {len(CANONICAL_IDS)}")
    print(f"  Affected (would-repair / repaired): {affected}")
    print(f"  Already healthy: {skipped}")
    if not DRY_RUN:
        print(f"  Mongo writes: {repaired}")
    print("=" * 70)

    if DRY_RUN and affected > 0:
        print()
        print(f"To actually repair: DRY_RUN=0 python {Path(__file__).name}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
