#!/usr/bin/env python3
"""Read-only diagnostic for the "admin plan edit doesn't persist" bug.

Dumps the current Mongo state of every canonical subscription plan so we
can see exactly what's persisted vs what the admin UI claims. Focus areas:

  * ``is_active`` and ``is_featured`` — fields the user reports as not
    persisting after admin edits.
  * ``deleted_at`` — soft-delete marker. If set, the plan is archived
    and admin edits to ``is_active`` may visually flip back to Inactive
    even though the field itself is True, depending on frontend logic.
  * ``admin_overrides`` — per-field timestamps that record admin edits.
    If admin_overrides.<field> exists with a recent timestamp, the edit
    DID write to Mongo; the symptom is then elsewhere (frontend cache,
    list filter, or a downstream sync).
  * ``updated_at`` — proves whether the last write succeeded.
  * Field shape — full doc so we can spot drift like is_active=null.

Usage::

    python scripts/inspect_plan_state.py

Output is grep-friendly. Doesn't modify anything.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from pprint import pformat

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


MONGO_URI = (
    os.getenv("MONGO_URI")
    or os.getenv("MONGODB_URI")
    or os.getenv("MONGO_URL")
    or "mongodb://localhost:27017"
)
DB_NAME = os.getenv("MONGO_DB", "wedding")

# Live 2026-07 catalog first, then the retired plans (kept for historical
# subscription lookups; they should report is_active=False).
CANONICAL_IDS = (
    "plan_boutique",
    "plan_solo_standard",
    "plan_solo",
    "plan_signature",
    "plan_enterprise",
)


def main() -> int:
    print("=" * 70)
    print("SUBSCRIPTION PLAN STATE DUMP")
    print(f"  Mongo: {MONGO_URI[:40]}...")
    print(f"  DB   : {DB_NAME}")
    print("=" * 70)

    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command("ping")
    except Exception as exc:
        print(f"[ERROR] Mongo connection failed: {exc}", file=sys.stderr)
        return 1

    coll = client[DB_NAME]["subscription_plans"]

    for plan_id in CANONICAL_IDS:
        plan = coll.find_one({"_id": plan_id})
        print(f"\n--- {plan_id} ---")
        if not plan:
            print("  (not in Mongo)")
            continue

        # Headline status fields
        print(f"  is_active           : {plan.get('is_active')!r}")
        print(f"  is_featured         : {plan.get('is_featured')!r}")
        print(f"  deleted_at          : {plan.get('deleted_at')!r}")
        print(f"  updated_at          : {plan.get('updated_at')!r}")
        print(f"  display_order       : {plan.get('display_order')!r}")
        print(f"  sort_order          : {plan.get('sort_order')!r}")

        # Strategy fields
        print(f"  price_monthly       : {plan.get('price_monthly')!r}")
        print(f"  price_yearly        : {plan.get('price_yearly')!r}")
        print(f"  trial_days          : {plan.get('trial_days')!r}")
        print(f"  max_weddings        : {plan.get('max_weddings')!r}")
        print(f"  max_weddings_lifetime: {plan.get('max_weddings_lifetime')!r}")
        print(f"  max_guests_per_wedding: {plan.get('max_guests_per_wedding')!r}")
        print(f"  ai_credits_monthly  : {plan.get('ai_credits_monthly')!r}")
        print(f"  storage_gb          : {plan.get('storage_gb')!r}")
        print(f"  staff_seats         : {plan.get('staff_seats')!r}")
        print(f"  billing_model       : {plan.get('billing_model')!r}")
        print(f"  is_metered          : {plan.get('is_metered')!r}")

        # Admin-override tracking — proves whether admin edits hit Mongo
        admin_overrides = plan.get("admin_overrides") or {}
        if admin_overrides:
            print("  admin_overrides     :")
            for field, ts in sorted(admin_overrides.items()):
                print(f"    {field:25s} = {ts!r}")
        else:
            print("  admin_overrides     : (empty)")

        # Stripe linkage
        print(f"  stripe_product_id   : {plan.get('stripe_product_id')!r}")
        print(f"  stripe_price_id_monthly: {plan.get('stripe_price_id_monthly')!r}")
        print(f"  stripe_price_id_yearly : {plan.get('stripe_price_id_yearly')!r}")

        # Any other unexpected fields?
        known = {
            "_id",
            "name",
            "description",
            "is_active",
            "is_featured",
            "deleted_at",
            "updated_at",
            "created_at",
            "created_by",
            "updated_by",
            "display_order",
            "sort_order",
            "price_monthly",
            "price_yearly",
            "trial_days",
            "max_weddings",
            "max_weddings_lifetime",
            "max_guests_per_wedding",
            "ai_credits_monthly",
            "storage_gb",
            "staff_seats",
            "billing_model",
            "is_metered",
            "meter_event_name",
            "meter_id",
            "admin_overrides",
            "stripe_product_id",
            "stripe_price_id_monthly",
            "stripe_price_id_yearly",
            "features",
            "features_list",
        }
        extras = {k: v for k, v in plan.items() if k not in known}
        if extras:
            print("  EXTRA FIELDS        :")
            for k, v in extras.items():
                print(f"    {k:25s} = {pformat(v, width=60)[:80]}")

    print("\n" + "=" * 70)
    print("LEGEND")
    print("=" * 70)
    print("If is_active=False on a plan you just saved as Active:")
    print("  • Check admin_overrides.is_active — if its timestamp is RECENT")
    print("    (within last few minutes), the admin write reached Mongo but")
    print("    something post-write reverted it. Most likely culprit was the")
    print("    product.updated webhook handler; the 2026-05-13 fix in")
    print("    app/services/stripe_service.py::_handle_product_updated now")
    print("    respects admin_overrides.is_active.")
    print("  • If admin_overrides.is_active is empty/missing, the admin write")
    print("    never reached the new code path. Either the backend hasn't been")
    print("    restarted after the fix, or the route is calling an older")
    print("    update_plan binding. Check service restart and inspect")
    print("    app/services/subscription_service.py::update_plan logs.")
    print("If deleted_at is set, the plan is in a half-state.")
    print("  • update_plan now $unsets deleted_at when is_active is flipped")
    print("    back to True. If you still see deleted_at set after an admin")
    print("    save, the new update_plan code isn't running on this backend.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
