"""
Seed Subscription Plans Script
Creates default subscription plans in MongoDB and corresponding products/prices in Stripe.
Runs on container startup via the runtime bootstrap script.
"""

from pathlib import Path
import os
import sys
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parents[1]
repo_root_str = str(REPO_ROOT)
if repo_root_str not in sys.path:
    sys.path.insert(0, repo_root_str)

from dotenv import load_dotenv  # noqa: E402

from app.constants.billing import (  # noqa: E402
    BILLING_MODEL_FLAT_RATE,
    BILLING_MODEL_METERED,
    CANONICAL_PUBLIC_PLAN_BILLING_MODEL,
    PLAN_BILLING_MODEL_MIGRATION_FLAG,
    RETIRED_PUBLIC_PLAN_IDS,
    plan_billing_model_migration_enabled,
)
from app.utils.subscription_plan_seed_policy import (  # noqa: E402
    build_effective_seed_plan,
    legacy_canonical_plan_aliases,
)

# ---------------------------------------------------------------------------
# PLAN_SEED_VERSION is the baseline strategy revision. Copy-only releases use
# PLAN_FIELD_SEED_VERSIONS so they cannot invalidate newer operator pricing,
# limits, entitlements, or display decisions.
#
# When to bump:
#   - You're changing canonical seed values (price, name, features, caps, etc.)
#     and want the change to land EVEN IF an admin previously tweaked that
#     field via /admin/saas.
#
# When NOT to bump:
#   - Plumbing / refactor changes that don't alter the strategy values.
#   - Stripe-side-only changes (those go through stripe_service helpers).
#
# Companion: app/services/subscription_service.update_plan writes per-field
# timestamps to plan["admin_overrides"][<field>] every time an admin edits.
# The pure merge policy lives in app/utils/subscription_plan_seed_policy.py.

if os.getenv("SEED_SUBSCRIPTION_PLANS_IMPORT_CHECK_ONLY") == "1":
    print("[OK] seed subscription import contract satisfied")
    sys.exit(0)

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

# Configure Stripe if available
stripe_secret = os.getenv("STRIPE_SECRET_KEY")
stripe_enabled = os.getenv("STRIPE_ENABLED", "false").lower() == "true"

if STRIPE_AVAILABLE and stripe and stripe_secret and stripe_enabled:
    stripe.api_key = stripe_secret
    # Mirror app/services/stripe_service.py — keep both in sync.
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

# Import meter helpers — zero mongo deps so safe at container startup.
try:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app.services.stripe_meter_helpers import (  # noqa: E402
        assert_meter_config,
        ensure_stripe_meter,
    )

    METER_HELPERS_AVAILABLE = True
except ImportError as e:

    def assert_meter_config(*args, **kwargs) -> None:
        pass  # type: ignore

    def ensure_stripe_meter(*args, **kwargs) -> str:
        return ""  # type: ignore

    METER_HELPERS_AVAILABLE = False
    print(
        f"[WARN] Could not import meter helpers ({e}); metered plans cannot be provisioned"
    )


def _provision_meter_if_needed(plan: dict) -> str | None:
    """Idempotently provision a Stripe Meter for a metered plan.

    Returns the meter_id if the plan is metered (and Stripe configured),
    otherwise None.
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
        # Existing meter found but misconfigured — manual intervention.
        print(f"  [ERROR] Existing meter for {event_name!r} is misconfigured: {e}")
        print(
            "  [ACTION] Operator must fix or deactivate the meter in the "
            "Stripe Dashboard before re-running the seed."
        )
        return None


def _build_recurring(interval: str, plan: dict, meter_id: str | None) -> dict:
    """Build the ``recurring`` config for a Stripe Price."""
    if plan.get("is_metered") and not meter_id:
        raise RuntimeError(
            f"Metered plan {plan.get('_id')} requires a Stripe meter before "
            "Stripe Price creation."
        )
    config: dict = {"interval": interval}
    if plan.get("is_metered") and meter_id:
        config["usage_type"] = "metered"
        config["meter"] = meter_id
    return config


def _stripe_price_matches(
    price, expected_cents: int, interval: str, is_metered: bool, meter_id: str | None
) -> bool:
    """Return True iff ``price`` matches the seed's expected configuration.

    Mirrors the comparison in ``app/services/stripe_service.py::ensure_price``
    — keep them aligned. If either side drifts, ``testbed/verify_seed_price_
    refresh_e2e.py`` will catch it.
    """
    if not price.recurring or price.recurring.interval != interval:
        return False
    if price.unit_amount != expected_cents:
        return False
    if price.currency != "usd":
        return False
    price_is_metered = price.recurring.usage_type == "metered"
    if price_is_metered != is_metered:
        return False
    if is_metered and meter_id:
        if getattr(price.recurring, "meter", None) != meter_id:
            return False
    return True


def _ensure_seed_price(
    product_id: str,
    plan: dict,
    interval: str,
    amount: float,
    existing_price_id: str | None,
    meter_id: str | None,
) -> str | None:
    """Create-or-reuse a Stripe Price honoring immutability.

    Stripe Prices are immutable on ``unit_amount`` / ``currency`` / ``product``.
    Per Stripe's "Change the price of existing subscriptions" guide, the only
    valid update is: create a new Price, then deactivate the old one (existing
    subscriptions keep working — they're grandfathered until explicitly moved).

    Without this check, a pricing-strategy refresh that flips ``price_monthly``
    from 29 → 49 would leave Mongo carrying $49 but ``stripe_price_id_monthly``
    pointing at the OLD $29 Stripe Price. New Checkout sessions would be
    charged the wrong amount.
    """
    if amount is None:
        # The catalog no longer sells this interval for this plan. Supersede
        # any previously recorded Stripe Price so it stops surfacing for new
        # Checkout sessions — existing subscriptions on it are grandfathered
        # by Stripe. (Both live plans currently sell monthly AND yearly; this
        # path is the generic guard for any future interval retirement.)
        if existing_price_id:
            try:
                stripe.Price.modify(existing_price_id, active=False)
                print(
                    f"  [ARCHIVED] {interval.title()} price {existing_price_id} "
                    "retired from sale (interval no longer offered)"
                )
            except StripeError as exc:
                print(
                    f"  [WARN] Could not deactivate removed {interval} price "
                    f"{existing_price_id}: {exc}"
                )
        return None

    expected_cents = int(amount * 100)
    is_metered = bool(plan.get("is_metered"))
    plan_id = plan["_id"]

    # Try to reuse the recorded price first — fastest path, avoids the
    # Price.list round trip when nothing has drifted.
    if existing_price_id:
        try:
            existing = stripe.Price.retrieve(existing_price_id)
            if _stripe_price_matches(
                existing, expected_cents, interval, is_metered, meter_id
            ):
                return existing_price_id
        except StripeError as exc:
            print(
                f"  [WARN] Could not retrieve recorded price {existing_price_id}: {exc}"
            )
            existing_price_id = None

    # Fallback discovery: scan active prices on this product for a match (handles
    # the case where Mongo doesn't have a price id yet but Stripe does — e.g.
    # the plan was previously seeded via a different code path).
    if not existing_price_id:
        try:
            for price in stripe.Price.list(
                product=product_id, active=True
            ).auto_paging_iter():
                if _stripe_price_matches(
                    price, expected_cents, interval, is_metered, meter_id
                ):
                    return price.id
        except StripeError as exc:
            print(f"  [WARN] Could not list prices on product {product_id}: {exc}")

    # No match — create a new Price.
    new_price = stripe.Price.create(
        product=product_id,
        unit_amount=expected_cents,
        currency="usd",
        recurring=_build_recurring(interval, plan, meter_id),  # type: ignore
        metadata={"plan_id": plan_id, "interval": f"{interval}ly"},
    )
    metered_tag = " [METERED]" if is_metered else ""
    print(
        f"  [CREATED] {interval.title()} price: {new_price.id} "
        f"(${amount}/{interval[:2]}){metered_tag}"
    )

    # Deactivate the old Price so it stops surfacing as the active default
    # for new Checkout sessions. Existing subscriptions on it are unaffected
    # (Stripe keeps charging archived prices for grandfathered subs).
    if existing_price_id:
        try:
            stripe.Price.modify(existing_price_id, active=False)
            print(
                f"  [ARCHIVED] Old {interval} price {existing_price_id} marked inactive"
            )
        except StripeError as exc:
            print(f"  [WARN] Could not deactivate old price {existing_price_id}: {exc}")

    return new_price.id


def create_stripe_product_and_prices(
    plan: dict, existing_mongo: dict | None = None
) -> dict:
    """Create Stripe product, meter (if metered), and prices. Return IDs.

    When ``existing_mongo`` is provided, the helper honors the recorded
    ``stripe_price_id_*`` fields and creates new Prices on mismatch (per the
    Stripe immutability contract — see ``_ensure_seed_price``). Without that
    argument the helper still works for first-time creation, but it can't
    detect a price refresh against an already-deployed product.
    """
    if not STRIPE_CONFIGURED or not stripe:
        return {}

    plan_id = plan["_id"]
    plan_name = plan["name"]
    existing_mongo = existing_mongo or {}

    meter_id = _provision_meter_if_needed(plan)
    if plan.get("is_metered") and not meter_id:
        raise RuntimeError(
            f"Metered plan {plan_id} requires a valid Stripe Meter for "
            f"{plan.get('meter_event_name')!r}; aborting seed before creating "
            "a flat Stripe Price by accident."
        )

    # 1. Resolve the Stripe Product — reuse if Mongo has a recorded id and
    # it's retrievable, otherwise fall back to metadata search, otherwise
    # create.
    # Track the live product (for the modify step below) plus its id.
    existing_product = None
    product_id = existing_mongo.get("stripe_product_id")
    if product_id:
        try:
            existing_product = stripe.Product.retrieve(product_id)
        except StripeError:
            product_id = None

    if not product_id:
        try:
            search = stripe.Product.search(query=f"metadata['plan_id']:'{plan_id}'")
            if search.data:
                existing_product = search.data[0]
                product_id = existing_product.id
                print(f"  [EXISTS] Stripe product: {product_id}")
        except StripeError as exc:
            print(f"  [WARN] Error searching Stripe products: {exc}")

    expected_name = f"The Special Wedding - {plan_name}"
    expected_description = plan.get("description", f"{plan_name} subscription plan")

    if not product_id:
        try:
            product = stripe.Product.create(
                name=expected_name,
                description=expected_description,
                metadata={"plan_id": plan_id, "source": "seed_script"},
            )
            product_id = product.id
            print(f"  [CREATED] Stripe product: {product_id}")
        except StripeError as exc:
            print(f"  [ERROR] Stripe error creating product: {exc}")
            return {"meter_id": meter_id} if meter_id else {}
    elif existing_product is not None:
        # Refresh the Stripe Product's name/description if the seed dict has
        # changed since the product was first created. Customer-visible on
        # hosted Checkout summaries and on the Stripe Dashboard. Skipping
        # this is what kept "Plan for new planners onboarding their first
        # weddings" on prod products long after the seed copy was rewritten.
        updates: dict = {}
        if getattr(existing_product, "name", None) != expected_name:
            updates["name"] = expected_name
        if getattr(existing_product, "description", None) != expected_description:
            updates["description"] = expected_description
        if updates:
            try:
                stripe.Product.modify(product_id, **updates)
                print(
                    f"  [REFRESHED] Stripe product {product_id} updated: "
                    f"{', '.join(updates.keys())}"
                )
            except StripeError as exc:
                # Non-fatal — product is still usable, name/description
                # just stays stale. Log and continue.
                print(f"  [WARN] Could not modify Stripe product {product_id}: {exc}")

    # 2. Ensure monthly + yearly Prices honoring immutability.
    try:
        monthly_price_id = _ensure_seed_price(
            product_id,
            plan,
            "month",
            plan["price_monthly"],
            existing_mongo.get("stripe_price_id_monthly"),
            meter_id,
        )
        yearly_price_id = _ensure_seed_price(
            product_id,
            plan,
            "year",
            plan.get("price_yearly"),
            existing_mongo.get("stripe_price_id_yearly"),
            meter_id,
        )
    except StripeError as exc:
        print(f"  [ERROR] Stripe error ensuring prices: {exc}")
        return {
            "stripe_product_id": product_id,
            **({"meter_id": meter_id} if meter_id else {}),
        }

    result = {
        "stripe_product_id": product_id,
        "stripe_price_id_monthly": monthly_price_id,
        "stripe_price_id_yearly": yearly_price_id,
    }
    if meter_id:
        result["meter_id"] = meter_id
    return result


def _seed_billing_model(plan: dict | None) -> str:
    if plan and plan.get("is_metered"):
        return BILLING_MODEL_METERED
    return BILLING_MODEL_FLAT_RATE


def _build_effective_seed_plan(seed_plan: dict, existing_plan: dict | None) -> dict:
    """Compute the values to write to Mongo for this plan.

    Field-scoped revision cutoffs let the current copy refresh repair retired
    public text without resetting newer operator-owned commercial settings.
    Existing activation, featured, and order values always survive so a hidden
    plan can never become sellable during Stripe synchronization.
    """
    effective = build_effective_seed_plan(seed_plan, existing_plan, log=print)

    if existing_plan and existing_plan.get("meter_id"):
        effective["meter_id"] = existing_plan["meter_id"]

    # 2026-05-09: seed owns the billing-model shape — use whatever the seed
    # plan declares. Previously this forced is_metered=True; now plans ship
    # flat by default and a per-plan override can flip a specific plan to
    # metered. See METERING_IMPLEMENTATION_2026-05-04.md.
    effective["billing_model"] = seed_plan.get(
        "billing_model", CANONICAL_PUBLIC_PLAN_BILLING_MODEL
    )
    effective["is_metered"] = bool(seed_plan.get("is_metered", False))
    # meter_event_name is optional — only required when is_metered=True.
    effective["meter_event_name"] = seed_plan.get("meter_event_name")
    return effective


def _guard_seed_billing_model_transition(
    plan_id: str, existing_plan: dict | None, next_plan: dict
) -> None:
    if not existing_plan:
        return

    previous_model = _seed_billing_model(existing_plan)
    next_model = _seed_billing_model(next_plan)
    if previous_model == next_model:
        return

    active_subscriptions = db["user_subscriptions"].count_documents(
        {"plan_id": plan_id, "status": {"$in": ["active", "trial", "trial_expiring"]}}
    )
    if active_subscriptions and not plan_billing_model_migration_enabled():
        print(
            f"  [ERROR] Refusing to change {plan_id} from {previous_model} to "
            f"{next_model} while {active_subscriptions} active subscriptions "
            "exist."
        )
        print(
            "  [ACTION] Existing Stripe subscriptions remain on old Stripe "
            "prices. Run an explicit subscription-item migration, then set "
            f"{PLAN_BILLING_MODEL_MIGRATION_FLAG}=true for that operator run."
        )
        sys.exit(1)


# Define plans
#
# 2026-07-28 pricing strategy (FINAL operator ruling, 2026-07-28 07:59 CDT):
#   - THE FREE TIER IS RETIRED. Every free account carries real Twilio/cloud/AI
#     cost; plan_solo is forced inactive below (see RETIRED_PUBLIC_PLAN_IDS).
#   - Solo Founding ($49/mo, id plan_boutique): founding-member rate, 1 seat.
#   - Solo Standard ($99/mo, id plan_solo_standard): standard solo rate, 1 seat.
#   - Yearly = monthly x 10 exactly ($490 / $990) — two months free.
#   - Signature ($149/mo, id plan_signature) is RETIRED, not renamed. The
#     in-flight Signature trial converts onto Solo Founding at $49/mo (launch
#     cohort — see the ops runbook in the pricing research doc).
#   - "White-Glove Setup" is a one-time $149 add-on (guided activation), NOT
#     a subscription tier — app/constants/billing.py::WHITE_GLOVE_SETUP_ADDON.
#   - Couple one-time $199 (one wedding; workspace closes 90 days post-wedding) lives in
#     app/constants/billing.py::COUPLE_LIFETIME_OFFER — no recurring plan doc.
#
# Mongo _ids deliberately stay stable; plan_boutique keeps its Stripe product
# AND its existing $49/$490 prices (the seed's price matcher reuses them), so
# no Stripe churn happens for the renamed Boutique -> Solo Founding plan.
#
# Differentiation is by implemented limits and support paths (team seats, AI credits,
# guest memories storage, planner storefronts, optional custom domains, and
# support-assisted onboarding). Do not advertise capabilities whose
# production contracts are not implemented.
# Trial = uniform 30 days across all paid plans.
# All plans are FLAT (is_metered=False). The metering hardening shipped 2026-05-04
# is available infrastructure — flip is_metered=True + add meter_event_name on any
# plan to switch to per-wedding billing.
#
# See docs/analysis/METERING_IMPLEMENTATION_2026-05-04.md for the metering option.
plans = [
    # ============================================================
    # SOLO FOUNDING — $49/mo, founding-member rate for solo planners
    # (formerly "Boutique"; same _id, same Stripe product and prices)
    # ============================================================
    {
        "_id": "plan_boutique",
        "name": "Solo Founding",
        "description": "Founding-member rate for independent planners running their solo practice.",
        "price_monthly": 49,
        "price_yearly": 490,  # 10x monthly — two months free
        "trial_days": 30,
        "billing_model": CANONICAL_PUBLIC_PLAN_BILLING_MODEL,
        "is_metered": False,
        "max_weddings": -1,  # Unlimited (cap removed 2026-05-12)
        "max_weddings_lifetime": False,
        "max_guests_per_wedding": -1,  # Unlimited (cap removed 2026-05-12)
        "ai_credits_monthly": 300,
        "storage_gb": 25,
        "staff_seats": 1,
        "features": {
            "guest_management": True,
            "email_invitations": True,
            "rsvp_system": True,
            "wedding_website": True,
            "timeline_builder": True,
            "basic_analytics": True,
            "vendor_management": True,
            "seating_orchestration": True,
            "ai_features": True,
            "qr_checkin": True,
            "automated_reminders": True,
            "calendar_sync": True,
            "payment_processing": True,
            "vendor_collaboration": False,
            "advanced_analytics": False,
            "planner_storefront": False,
            "custom_domain": False,
            "priority_support": False,
            "white_label": False,
            "api_access": False,
            "dedicated_support": False,
        },
        "features_list": [
            "Unlimited weddings",
            "Unlimited guests",
            "Vendor management",
            "Seating orchestration",
            "Automated reminders",
            "Calendar sync (Google, Outlook)",
            "300 AI credits/month",
            "25GB guest memories storage",
            "Email support",
        ],
        "is_active": True,
        "is_featured": True,
        "sort_order": 1,
        "display_order": 1,
        "created_by": "system",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    },
    # ============================================================
    # SOLO STANDARD — $99/mo, standard rate for solo planners (new)
    # ============================================================
    {
        "_id": "plan_solo_standard",
        "name": "Solo Standard",
        "description": "The standard rate for independent planners — everything a solo practice needs to run client weddings end to end.",
        "price_monthly": 99,
        "price_yearly": 990,  # 10x monthly — two months free
        "trial_days": 30,
        "billing_model": CANONICAL_PUBLIC_PLAN_BILLING_MODEL,
        "is_metered": False,
        "max_weddings": -1,  # Unlimited
        "max_weddings_lifetime": False,
        "max_guests_per_wedding": -1,  # Unlimited
        "ai_credits_monthly": 750,
        "storage_gb": 50,
        "staff_seats": 1,
        "features": {
            "guest_management": True,
            "email_invitations": True,
            "rsvp_system": True,
            "wedding_website": True,
            "timeline_builder": True,
            "basic_analytics": True,
            "vendor_management": True,
            "seating_orchestration": True,
            "ai_features": True,
            "qr_checkin": True,
            "automated_reminders": True,
            "calendar_sync": True,
            "payment_processing": True,
            "vendor_collaboration": False,
            "advanced_analytics": False,
            "planner_storefront": False,
            "custom_domain": False,
            "priority_support": False,
            "white_label": False,
            "api_access": False,
            "dedicated_support": False,
        },
        "features_list": [
            "Unlimited weddings",
            "Unlimited guests",
            "Everything in Solo Founding",
            "750 AI credits/month",
            "50GB guest memories storage",
            "Email support",
        ],
        "is_active": True,
        "is_featured": False,
        "sort_order": 2,
        "display_order": 2,
        "created_by": "system",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    },
]

print("\n[SEED] Seeding Subscription Plans...")
print("=" * 50)

# ---- 2026-07 one-time display/featured migration ----
# display_order / sort_order / is_featured are operator-preserved fields, so
# the new defaults (Solo Founding first + featured) cannot land via the
# normal upsert on databases seeded before this release. Detect the
# pre-migration document by its OLD name ("Boutique") so this can never fight
# a future operator edit — once renamed, this block is a no-op forever.
if collection.find_one({"_id": "plan_boutique", "name": "Boutique"}):
    collection.update_one(
        {"_id": "plan_boutique"},
        {
            "$set": {
                "sort_order": 1,
                "display_order": 1,
                "is_featured": True,
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )
    print(
        "[MIGRATE] plan_boutique display order -> 1, featured (Boutique -> Solo Founding)"
    )

created = 0
updated = 0
skipped = 0

for plan in plans:
    plan_id = plan["_id"]
    print(f"\n[PLAN] Processing: {plan['name']} - ${plan['price_monthly']}/month")
    existing_plan = collection.find_one({"_id": plan_id})
    plan_for_sync = _build_effective_seed_plan(plan, existing_plan)
    _guard_seed_billing_model_transition(plan_id, existing_plan, plan_for_sync)

    # Create Stripe products if configured (idempotent - checks existing first).
    # Inactive plans are intentionally hidden by root admin and should not
    # create fresh sellable Stripe Prices during a rolling deploy.
    # Pass existing_plan so the helper can honor recorded Stripe IDs and
    # detect unit_amount drift (see _ensure_seed_price for the immutability
    # contract this enforces).
    stripe_ids = (
        create_stripe_product_and_prices(plan_for_sync, existing_plan)
        if STRIPE_CONFIGURED and plan_for_sync.get("is_active", True)
        else {}
    )

    # Merge Stripe IDs into plan
    plan_with_stripe = {**plan_for_sync, **stripe_ids}

    # ATOMIC upsert: prevents race conditions when multiple containers start simultaneously
    #
    # Field placement rules (2026-05-10 strategy refresh):
    #
    # $set — strategy-controlled fields. Every redeploy carries the current
    # seed values into Mongo. This is what fixes the "Mongo holds $29 but the
    # seed declares $49" drift problem. Trade-off: ad-hoc admin price edits
    # via the saas admin UI get reverted on the next deploy. If a one-off
    # price experiment is needed, do it under a NEW plan id, not by editing
    # an existing canonical plan.
    #
    # $setOnInsert — admin display toggles. The admin saas page allows
    # hiding a plan or rearranging order; those choices must survive deploys
    # because they're operator decisions, not strategy.
    #
    # Why max_weddings_lifetime sits in $set: without it, the Solo lifetime
    # cap silently doesn't write to Mongo, and `_live_wedding_count_lifetime`
    # is never invoked (the branch in subscription_service reads the flag
    # from plan_snapshot). Free Solo planners would be able to create →
    # delete → create indefinitely, bypassing the "1 wedding lifetime" cap.
    result = collection.update_one(
        {"_id": plan_id},
        {
            "$setOnInsert": {
                "created_at": plan_with_stripe.get(
                    "created_at", datetime.now(timezone.utc)
                ),
                "created_by": plan_with_stripe.get("created_by", "system"),
                # Admin display toggles — survive deploys.
                "is_active": plan_with_stripe.get("is_active", True),
                "is_featured": plan_with_stripe.get("is_featured", False),
                "sort_order": plan_with_stripe.get("sort_order", 0),
                "display_order": plan_with_stripe.get(
                    "display_order", plan_with_stripe.get("sort_order", 0)
                ),
            },
            "$set": {
                # Strategy fields — refreshed on every deploy.
                "name": plan_with_stripe["name"],
                "description": plan_with_stripe.get("description"),
                "price_monthly": plan_with_stripe["price_monthly"],
                "price_yearly": plan_with_stripe.get("price_yearly"),
                "trial_days": plan_with_stripe.get("trial_days", 0),
                "max_weddings": plan_with_stripe.get("max_weddings"),
                "max_weddings_lifetime": plan_with_stripe.get(
                    "max_weddings_lifetime", False
                ),
                "max_guests_per_wedding": plan_with_stripe.get(
                    "max_guests_per_wedding"
                ),
                "ai_credits_monthly": plan_with_stripe.get("ai_credits_monthly"),
                "storage_gb": plan_with_stripe.get("storage_gb"),
                "staff_seats": plan_with_stripe.get("staff_seats"),
                "features": plan_with_stripe.get("features", {}),
                "features_list": plan_with_stripe.get("features_list", []),
                # Billing model — defaults track the 2026-05-09 strategy
                # (flat unless a plan deliberately opts in to metered).
                "billing_model": plan_with_stripe.get(
                    "billing_model", BILLING_MODEL_FLAT_RATE
                ),
                "is_metered": plan_with_stripe.get("is_metered", False),
                # Metered config — these MUST be in $set or the seed will
                # silently drop them on update, leaving plans in a half-
                # configured state. See METERING_GAP_SCENARIOS_2026-05-04.md
                # §CC3 (the structural bug that made setup feel manual).
                "meter_event_name": plan_with_stripe.get("meter_event_name"),
                "meter_id": plan_with_stripe.get("meter_id"),
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
                # Yearly is written whenever the Stripe sync ran (even as
                # None) so a removed yearly interval clears the stale price
                # pointer instead of leaving Mongo pointing at an archived
                # Stripe Price. Error paths omit the key and leave Mongo
                # untouched.
                **(
                    {"stripe_price_id_yearly": stripe_ids["stripe_price_id_yearly"]}
                    if "stripe_price_id_yearly" in stripe_ids
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

# ---- 2026-07 retired plans ----
# plan_solo (the free tier), plan_signature (Signature — never renamed; the
# in-flight trial converts onto Solo Founding per the ops runbook), and
# plan_enterprise are permanently off sale.
# Force them inactive with an operator-grade override (admin_overrides.is_active)
# so the ADMIN_PRESERVED merge policy and the Stripe product.updated webhook can
# never resurrect them, and archive their Stripe products/prices so no new
# checkout can be created. Documents are deliberately retained: existing
# subscriptions (e.g. legacy free accounts pending convert-or-close) must keep
# resolving their plan snapshot.
retired_count = 0
for retired_plan_id in sorted(RETIRED_PUBLIC_PLAN_IDS):
    retired_plan = collection.find_one({"_id": retired_plan_id})
    if not retired_plan:
        continue
    already_retired = (
        retired_plan.get("is_active") is False
        and (retired_plan.get("admin_overrides") or {}).get("is_active") is not None
    )
    if not already_retired:
        retired_at = datetime.now(timezone.utc)
        collection.update_one(
            {"_id": retired_plan_id},
            {
                "$set": {
                    "is_active": False,
                    "retired_at": retired_at,
                    "admin_overrides.is_active": retired_at,
                    "updated_at": retired_at,
                }
            },
        )
        retired_count += 1
        print(f"  [RETIRED] Plan '{retired_plan_id}' removed from sale")
    retired_product_id = retired_plan.get("stripe_product_id")
    if STRIPE_CONFIGURED and retired_product_id:
        try:
            retired_product = stripe.Product.retrieve(retired_product_id)
            if getattr(retired_product, "active", False):
                for retired_price in stripe.Price.list(
                    product=retired_product_id, active=True
                ).auto_paging_iter():
                    stripe.Price.modify(retired_price.id, active=False)
                stripe.Product.modify(retired_product_id, active=False)
                print(f"  [STRIPE] Archived retired product '{retired_product_id}'")
        except StripeError as exc:
            print(
                f"  [WARN] Could not archive retired Stripe product "
                f"'{retired_product_id}': {exc}"
            )

if retired_count:
    print(f"[RETIRED] {retired_count} plans removed from sale this run")

# ---- Canonical identity cleanup ----
# Only archive same-name aliases after every canonical upsert succeeded. If
# Stripe provisioning, billing guards, or Mongo writes fail above, the only
# existing legacy plan remains selectable. Alias documents are never deleted:
# historical users/subscriptions may still reference the old _id directly.
duplicates_archived = 0
all_seeded_plans = list(collection.find({}))
for pid, canonical_id in legacy_canonical_plan_aliases(all_seeded_plans):
    archived_at = datetime.now(timezone.utc)
    legacy_plan = collection.find_one({"_id": pid}) or {}
    collection.update_one(
        {"_id": pid},
        {
            "$set": {
                "is_active": False,
                "canonical_plan_id": canonical_id,
                "archived_as_duplicate_at": archived_at,
                "admin_overrides.is_active": archived_at,
                "updated_at": archived_at,
            }
        },
    )
    legacy_product_id = legacy_plan.get("stripe_product_id")
    if STRIPE_CONFIGURED and legacy_product_id:
        try:
            for legacy_price in stripe.Price.list(
                product=legacy_product_id, active=True
            ).auto_paging_iter():
                stripe.Price.modify(legacy_price.id, active=False)
            stripe.Product.modify(legacy_product_id, active=False)
            print(f"  [STRIPE] Archived legacy product '{legacy_product_id}'")
        except StripeError as exc:
            # The Mongo override remains authoritative and prevents a later
            # product.updated webhook from reactivating this alias.
            print(
                f"  [WARN] Could not archive legacy Stripe product "
                f"'{legacy_product_id}': {exc}"
            )
    duplicates_archived += 1
    print(f"  [DEDUP] Archived legacy plan '{pid}' as an alias of '{canonical_id}'")

if duplicates_archived > 0:
    print(f"[DEDUP] Archived {duplicates_archived} legacy plan aliases")
else:
    print("[OK] No active legacy plan aliases found")

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
