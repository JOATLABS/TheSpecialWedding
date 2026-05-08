"""
Seed Subscription Plans Script
Creates default subscription plans in MongoDB and corresponding products/prices in Stripe.
Runs on container startup via Dockerfile.coolify.

Metered-plan provisioning lives here too: when a plan dict has
``is_metered=True`` and ``meter_event_name`` set, the script calls
``ensure_stripe_meter`` to idempotently provision the Stripe Billing Meter
before creating the Product/Price pair. The Price is then created with
``recurring.usage_type=metered`` and ``recurring.meter=<meter_id>`` so
``stripe.billing.MeterEvent.create`` calls actually drive billing.

The shared helpers in ``app/services/stripe_meter_helpers`` are a tiny
mongo-independent module so this script can import them without dragging
in the full async service layer. See METERING_REVIEW_2026-05-04_PART2.md
§5 for the rationale.
"""

import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("\n[SEED] Starting subscription plans seeding...")
print("=" * 50)

# Check for Stripe (v13+ uses direct imports)
try:
    import stripe
    from stripe import StripeError  # v13+ exception class

    STRIPE_AVAILABLE = True
except ImportError:
    stripe = None  # type: ignore
    STRIPE_AVAILABLE = False
    StripeError = Exception  # type: ignore # Fallback for type hints
    print("[WARN] Stripe not installed, skipping Stripe product creation")

# Connect to MongoDB with error handling
try:
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
except ImportError:
    print("[ERROR] pymongo not installed!")
    sys.exit(1)

mongo_uri = (
    os.getenv("MONGO_URI")
    or os.getenv("MONGODB_URI")
    or os.getenv("MONGO_URL")
    or "mongodb://localhost:27017"
)
db_name = os.getenv("MONGO_DB", "wedding")

print(f"[INFO] Connecting to MongoDB database: {db_name}")

try:
    client: MongoClient = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    # Force connection test
    client.admin.command("ping")
    print("[OK] MongoDB connected successfully")
except (ConnectionFailure, ServerSelectionTimeoutError) as e:
    print(f"[ERROR] MongoDB connection failed: {e}")
    print(f"[DEBUG] URI prefix: {mongo_uri[:30]}...")
    sys.exit(1)

db = client[db_name]
collection = db["subscription_plans"]

# ---- Deduplication cleanup ----
# Remove duplicate plans (same name, different IDs) keeping the canonical _id.
# This handles cases where plans were created through both seed script and API endpoints.
canonical_ids = {"plan_boutique", "plan_signature", "plan_enterprise"}
all_existing = list(collection.find({}))
seen_names = {}
duplicates_removed = 0

for plan in all_existing:
    name = plan.get("name", "").lower().strip()
    pid = plan["_id"]
    if name in seen_names:
        # Keep the canonical ID, remove the other
        existing_pid = seen_names[name]
        if pid in canonical_ids and existing_pid not in canonical_ids:
            # Current plan has canonical ID - remove the previous one
            collection.delete_one({"_id": existing_pid})
            seen_names[name] = pid
            duplicates_removed += 1
            print(
                f"  [DEDUP] Removed duplicate plan '{existing_pid}' (keeping '{pid}')"
            )
        elif pid not in canonical_ids:
            # Current plan doesn't have canonical ID - remove it
            collection.delete_one({"_id": pid})
            duplicates_removed += 1
            print(
                f"  [DEDUP] Removed duplicate plan '{pid}' (keeping '{existing_pid}')"
            )
    else:
        seen_names[name] = pid

# Also fix any legacy wrong field names from previous seed runs
legacy_fix = collection.update_many(
    {"stripe_monthly_price_id": {"$exists": True}},
    [
        {
            "$set": {
                "stripe_price_id_monthly": "$stripe_monthly_price_id",
                "stripe_price_id_yearly": "$stripe_yearly_price_id",
            }
        },
        {"$unset": ["stripe_monthly_price_id", "stripe_yearly_price_id"]},
    ],
)
if legacy_fix.modified_count > 0:
    print(f"[FIX] Migrated {legacy_fix.modified_count} plans from legacy field names")

if duplicates_removed > 0:
    print(f"[DEDUP] Removed {duplicates_removed} duplicate plans")
else:
    print("[OK] No duplicate plans found")

# Configure Stripe if available
stripe_secret = os.getenv("STRIPE_SECRET_KEY")
stripe_enabled = os.getenv("STRIPE_ENABLED", "false").lower() == "true"

if STRIPE_AVAILABLE and stripe and stripe_secret and stripe_enabled:
    stripe.api_key = stripe_secret
    # Pin the Stripe API version. Mirrored in
    # app/services/stripe_service.py — keep both in sync. The seed and the
    # runtime must use the same version so MeterEvent / Meter behavior is
    # identical between container-startup provisioning and request-time
    # meter event reporting.
    stripe.api_version = "2026-04-22.dahlia"
    STRIPE_CONFIGURED = True
    print(
        f"[OK] Stripe configured (mode: {'live' if stripe_secret.startswith('sk_live') else 'test'}, api_version: {stripe.api_version})"
    )
else:
    STRIPE_CONFIGURED = False
    if not stripe_enabled:
        print("[INFO] Stripe disabled via STRIPE_ENABLED=false")
    elif not stripe_secret:
        print("[WARN] STRIPE_SECRET_KEY not set, skipping Stripe integration")

# Import meter helpers. These have ZERO mongo dependencies, so importing
# them at container-startup time (before the FastAPI app boots) is safe —
# see app/services/stripe_meter_helpers.py module docstring.
try:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app.services.stripe_meter_helpers import (  # noqa: E402
        assert_meter_config,
        ensure_stripe_meter,
    )

    METER_HELPERS_AVAILABLE = True
except ImportError as e:
    METER_HELPERS_AVAILABLE = False
    print(
        f"[WARN] Could not import meter helpers ({e}); metered plans cannot be provisioned"
    )


def _provision_meter_if_needed(plan: dict) -> str | None:
    """Idempotently provision a Stripe Meter for a metered plan.

    Returns the meter_id if the plan is metered (and Stripe is configured),
    otherwise None. If the plan already has ``meter_id`` set, the existing
    value is validated via ``assert_meter_config`` and returned.
    """
    if not plan.get("is_metered") or not plan.get("meter_event_name"):
        return None
    if not METER_HELPERS_AVAILABLE:
        print(
            "  [WARN] Plan is metered but meter helpers unavailable — skipping meter provisioning"
        )
        return None

    event_name = plan["meter_event_name"]
    existing_meter_id = plan.get("meter_id")

    if existing_meter_id:
        try:
            assert_meter_config(existing_meter_id)
            print(
                f"  [OK] Existing Stripe meter {existing_meter_id} matches required config"
            )
            return existing_meter_id
        except ValueError as e:
            print(f"  [ERROR] Configured meter_id {existing_meter_id} is invalid: {e}")
            print(f"  [INFO] Falling back to ensure_stripe_meter for {event_name!r}")

    try:
        meter_id = ensure_stripe_meter(
            event_name=event_name,
            display_name=f"{plan['name']} ({event_name})",
        )
        print(f"  [METER] Provisioned Stripe meter for {event_name!r}: {meter_id}")
        return meter_id
    except StripeError as e:
        print(f"  [ERROR] Could not provision meter for {event_name!r}: {e}")
        return None
    except ValueError as e:
        # ensure_stripe_meter raises ValueError when an existing meter is
        # found but misconfigured. We intentionally do NOT auto-fix this —
        # silently replacing the meter would orphan prior events. The
        # operator must intervene in the Stripe Dashboard. See
        # METERING_GAP_SCENARIOS_2026-05-04.md §C2.
        print(f"  [ERROR] Existing meter for {event_name!r} is misconfigured: {e}")
        print(
            "  [ACTION] Operator must fix or deactivate the meter in the "
            "Stripe Dashboard before re-running the seed."
        )
        return None


def _build_recurring(interval: str, plan: dict, meter_id: str | None) -> dict:
    """Build the ``recurring`` config for a Stripe Price.

    Flat plans → ``{interval: ...}``. Metered plans get
    ``usage_type=metered`` and ``meter=<id>`` so meter events drive billing.
    See https://docs.stripe.com/billing/subscriptions/usage-based/recording-usage.
    """
    config: dict = {"interval": interval}
    if plan.get("is_metered") and meter_id:
        config["usage_type"] = "metered"
        config["meter"] = meter_id
    return config


def create_stripe_product_and_prices(plan: dict) -> dict:
    """Create Stripe product, meter (if metered), and prices. Return IDs.

    Metered plans get a properly configured ``recurring.usage_type=metered``
    price linked to the Stripe Meter. This is the single seed-time path that
    matches what ``app/services/stripe_service.sync_plan_to_stripe`` does at
    runtime — keep them aligned.
    """
    if not STRIPE_CONFIGURED or not stripe:
        return {}

    plan_id = plan["_id"]
    plan_name = plan["name"]

    # 1. Provision the meter first (no-op for flat plans). This must happen
    #    BEFORE price creation because metered prices reference the meter ID.
    meter_id = _provision_meter_if_needed(plan)
    is_metered = plan.get("is_metered") and meter_id is not None

    # 2. Check if product already exists by metadata
    try:
        existing_products = stripe.Product.search(
            query=f"metadata['plan_id']:'{plan_id}'"
        )
        if existing_products.data:
            product = existing_products.data[0]
            print(f"  [EXISTS] Stripe product: {product.id}")

            # Get existing prices and verify metering shape matches plan
            prices = stripe.Price.list(product=product.id, active=True)
            monthly_price = None
            yearly_price = None

            for price in prices.data:
                if not price.recurring:
                    continue
                # Reject prices whose metered-ness no longer matches the
                # plan's intent — caller will create a fresh price below.
                price_is_metered = price.recurring.usage_type == "metered"
                if price_is_metered != bool(is_metered):
                    continue
                if price.recurring.interval == "month":
                    monthly_price = price.id
                elif price.recurring.interval == "year":
                    yearly_price = price.id

            result = {
                "stripe_product_id": product.id,
                "stripe_price_id_monthly": monthly_price,
                "stripe_price_id_yearly": yearly_price,
            }
            if meter_id:
                result["meter_id"] = meter_id
            # If a price was missing or stale-shape, fall through to create
            # the missing one(s) using the same product.
            if monthly_price and yearly_price:
                return result
            print(
                "  [INFO] Some prices missing or shape changed — creating to backfill"
            )
            # Use the existing product going forward.
            product_id = product.id
        else:
            product_id = None
    except StripeError as e:
        print(f"[WARN] Error searching Stripe products: {e}")
        product_id = None

    # 3. Create product if not found
    try:
        if not product_id:
            product = stripe.Product.create(
                name=f"The Special Wedding - {plan_name}",
                description=plan.get("description", f"{plan_name} subscription plan"),
                metadata={"plan_id": plan_id, "source": "seed_script"},
            )
            product_id = product.id
            print(f"  [CREATED] Stripe product: {product_id}")

        # 4. Create monthly price (metered-aware)
        new_monthly_price = stripe.Price.create(
            product=product_id,
            unit_amount=int(plan["price_monthly"] * 100),  # Convert to cents
            currency="usd",
            recurring=_build_recurring("month", plan, meter_id),
            metadata={"plan_id": plan_id, "interval": "monthly"},
        )
        metered_tag = " [METERED]" if is_metered else ""
        print(
            f"  [CREATED] Monthly price: {new_monthly_price.id} "
            f"(${plan['price_monthly']}/mo){metered_tag}"
        )

        # 5. Create yearly price (metered-aware)
        new_yearly_price = stripe.Price.create(
            product=product_id,
            unit_amount=int(plan["price_yearly"] * 100),  # Convert to cents
            currency="usd",
            recurring=_build_recurring("year", plan, meter_id),
            metadata={"plan_id": plan_id, "interval": "yearly"},
        )
        print(
            f"  [CREATED] Yearly price: {new_yearly_price.id} "
            f"(${plan['price_yearly']}/yr){metered_tag}"
        )

        result = {
            "stripe_product_id": product_id,
            "stripe_price_id_monthly": new_monthly_price.id,
            "stripe_price_id_yearly": new_yearly_price.id,
        }
        if meter_id:
            result["meter_id"] = meter_id
        return result

    except StripeError as e:
        print(f"  [ERROR] Stripe error creating product/prices: {e}")
        # Even on failure, return any meter_id we provisioned so it gets
        # persisted to Mongo and the next run can reuse it.
        return {"meter_id": meter_id} if meter_id else {}


# Define plans
plans = [
    {
        "_id": "plan_boutique",
        "name": "Boutique",
        "description": "For new planners onboarding their first weddings",
        "price_monthly": 29,
        "price_yearly": 290,  # ~2 months free
        "trial_days": 30,
        "is_metered": False,
        "max_weddings": 3,
        "max_guests_per_wedding": 150,
        "ai_credits_monthly": 100,
        "storage_gb": 10,
        "staff_seats": 1,
        "features": {
            "guest_management": True,
            "email_invitations": True,
            "wedding_website": True,
            "timeline_builder": True,
            "basic_analytics": True,
            "vendor_management": False,
            "seating_orchestration": False,
            "ai_features": True,
        },
        "features_list": [
            "Up to 3 weddings",
            "150 guests per wedding",
            "Guest & RSVP manager",
            "Email invitations",
            "Wedding website",
            "Timeline builder",
            "100 AI credits/month",
        ],
        "is_active": True,
        "is_featured": False,
        "sort_order": 1,
        "display_order": 1,
        "created_by": "system",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    },
    {
        "_id": "plan_signature",
        "name": "Signature",
        "description": "Most popular plan with full automation features",
        "price_monthly": 59,
        "price_yearly": 590,  # ~2 months free
        "trial_days": 30,
        "is_metered": False,
        "max_weddings": 10,
        "max_guests_per_wedding": 350,
        "ai_credits_monthly": 300,
        "storage_gb": 50,
        "staff_seats": 3,
        "features": {
            "guest_management": True,
            "email_invitations": True,
            "wedding_website": True,
            "timeline_builder": True,
            "basic_analytics": True,
            "vendor_management": True,
            "seating_orchestration": True,
            "ai_features": True,
            "qr_checkin": True,
            "automated_reminders": True,
            "vendor_collaboration": True,
            "priority_support": True,
        },
        "features_list": [
            "Up to 10 weddings",
            "350 guests per wedding",
            "Everything in Boutique",
            "Seating orchestration",
            "QR check-in & live counts",
            "Automated reminders",
            "Vendor collaboration",
            "300 AI credits/month",
            "Priority support",
        ],
        "is_active": True,
        "is_featured": True,
        "sort_order": 2,
        "display_order": 2,
        "created_by": "system",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    },
    {
        "_id": "plan_enterprise",
        "name": "Enterprise",
        "description": "For agencies and high-volume wedding planners",
        "price_monthly": 149,
        "price_yearly": 1490,  # ~2 months free
        "trial_days": 30,
        "is_metered": False,
        "max_weddings": -1,  # Unlimited
        "max_guests_per_wedding": -1,  # Unlimited
        "ai_credits_monthly": 1000,
        "storage_gb": 200,
        "staff_seats": 10,
        "features": {
            "guest_management": True,
            "email_invitations": True,
            "wedding_website": True,
            "timeline_builder": True,
            "basic_analytics": True,
            "advanced_analytics": True,
            "vendor_management": True,
            "seating_orchestration": True,
            "ai_features": True,
            "qr_checkin": True,
            "automated_reminders": True,
            "vendor_collaboration": True,
            "priority_support": True,
            "white_label": True,
            "api_access": True,
            "dedicated_support": True,
        },
        "features_list": [
            "Unlimited weddings",
            "Unlimited guests",
            "Everything in Signature",
            "White-label branding",
            "API access",
            "1000 AI credits/month",
            "10 staff seats",
            "Dedicated support",
            "Custom integrations",
        ],
        "is_active": True,
        "is_featured": False,
        "sort_order": 3,
        "display_order": 3,
        "created_by": "system",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    },
]

print("\n[SEED] Seeding Subscription Plans...")
print("=" * 50)

created = 0
updated = 0
skipped = 0

for plan in plans:
    plan_id = plan["_id"]
    print(f"\n[PLAN] Processing: {plan['name']} - ${plan['price_monthly']}/month")

    # Create Stripe products if configured (idempotent - checks existing first)
    stripe_ids = create_stripe_product_and_prices(plan) if STRIPE_CONFIGURED else {}

    # Merge Stripe IDs into plan
    plan_with_stripe = {**plan, **stripe_ids}

    # ATOMIC upsert: prevents race conditions when multiple containers start simultaneously
    # $setOnInsert: only set these fields if document is newly created
    # $set: always update these fields
    result = collection.update_one(
        {"_id": plan_id},
        {
            "$setOnInsert": {
                "created_at": plan_with_stripe.get(
                    "created_at", datetime.now(timezone.utc)
                ),
                "created_by": plan_with_stripe.get("created_by", "system"),
            },
            "$set": {
                "name": plan_with_stripe["name"],
                "description": plan_with_stripe.get("description"),
                "price_monthly": plan_with_stripe["price_monthly"],
                "price_yearly": plan_with_stripe.get("price_yearly"),
                "is_metered": plan_with_stripe.get("is_metered", False),
                # Metered config — these MUST be in $set or the seed will
                # silently drop them on update, leaving plans in a half-
                # configured state (is_metered=True with no event_name).
                # See METERING_REVIEW_2026-05-04_PART2.md §1 (CC3).
                "meter_event_name": plan_with_stripe.get("meter_event_name"),
                "meter_id": plan_with_stripe.get("meter_id"),
                "max_weddings": plan_with_stripe.get("max_weddings"),
                "max_guests_per_wedding": plan_with_stripe.get(
                    "max_guests_per_wedding"
                ),
                "ai_credits_monthly": plan_with_stripe.get("ai_credits_monthly"),
                "storage_gb": plan_with_stripe.get("storage_gb"),
                "staff_seats": plan_with_stripe.get("staff_seats"),
                "features": plan_with_stripe.get("features", {}),
                "features_list": plan_with_stripe.get("features_list", []),
                "is_active": plan_with_stripe.get("is_active", True),
                "is_featured": plan_with_stripe.get("is_featured", False),
                "sort_order": plan_with_stripe.get("sort_order", 0),
                "display_order": plan_with_stripe.get(
                    "display_order", plan_with_stripe.get("sort_order", 0)
                ),
                "updated_at": datetime.now(timezone.utc),
                # Only update Stripe IDs if we have them (field names must match codebase convention)
                **(
                    {"stripe_product_id": stripe_ids["stripe_product_id"]}
                    if stripe_ids.get("stripe_product_id")
                    else {}
                ),
                **(
                    {"stripe_price_id_monthly": stripe_ids["stripe_price_id_monthly"]}
                    if stripe_ids.get("stripe_price_id_monthly")
                    else {}
                ),
                **(
                    {"stripe_price_id_yearly": stripe_ids["stripe_price_id_yearly"]}
                    if stripe_ids.get("stripe_price_id_yearly")
                    else {}
                ),
            },
        },
        upsert=True,  # Atomic: creates if not exists, updates if exists
    )

    if result.upserted_id:
        print("  [CREATED] Added to database")
        created += 1
    elif result.modified_count > 0:
        print("  [UPDATED] Updated in database")
        updated += 1
    else:
        print("  [SKIP] No changes needed")
        skipped += 1

print("\n" + "=" * 50)
print(f"[SUMMARY] Created {created}, Updated {updated}, Skipped {skipped}")

# Verify final state
all_plans = list(collection.find({"is_active": True}).sort("sort_order", 1))
print(f"\n[VERIFY] Active plans in database: {len(all_plans)}")
for p in all_plans:
    stripe_status = "[STRIPE]" if p.get("stripe_product_id") else "[NO STRIPE]"
    print(f"  - {p['name']}: ${p['price_monthly']}/mo {stripe_status}")

client.close()
print("\n[DONE] Subscription plans seeding complete!")
