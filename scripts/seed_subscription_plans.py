"""
Seed Subscription Plans Script
Creates default subscription plans in MongoDB and corresponding products/prices in Stripe.
Runs on container startup via Dockerfile.coolify.
"""
import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from pymongo import MongoClient

# Load environment variables
load_dotenv()

# Check for Stripe
try:
    import stripe
    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False
    print("⚠️  Stripe not installed, skipping Stripe product creation")

# Connect to MongoDB
mongo_uri = (
    os.getenv("MONGO_URI") or os.getenv("MONGODB_URI") or os.getenv("MONGO_URL") or "mongodb://localhost:27017"
)
db_name = os.getenv("MONGO_DB", "wedding")

client: MongoClient = MongoClient(mongo_uri)
db = client[db_name]
collection = db["subscription_plans"]

# Configure Stripe if available
stripe_secret = os.getenv("STRIPE_SECRET_KEY")
stripe_enabled = os.getenv("STRIPE_ENABLED", "false").lower() == "true"

if STRIPE_AVAILABLE and stripe_secret and stripe_enabled:
    stripe.api_key = stripe_secret
    STRIPE_CONFIGURED = True
    print(f"✅ Stripe configured (mode: {'live' if stripe_secret.startswith('sk_live') else 'test'})")
else:
    STRIPE_CONFIGURED = False
    if not stripe_enabled:
        print("ℹ️  Stripe disabled via STRIPE_ENABLED=false")
    elif not stripe_secret:
        print("⚠️  STRIPE_SECRET_KEY not set, skipping Stripe integration")


def create_stripe_product_and_prices(plan: dict) -> dict:
    """Create Stripe product and prices, return IDs."""
    if not STRIPE_CONFIGURED:
        return {}

    plan_id = plan["_id"]
    plan_name = plan["name"]

    # Check if product already exists by metadata
    try:
        existing_products = stripe.Product.search(
            query=f"metadata['plan_id']:'{plan_id}'"
        )
        if existing_products.data:
            product = existing_products.data[0]
            print(f"  ↪ Stripe product exists: {product.id}")

            # Get existing prices
            prices = stripe.Price.list(product=product.id, active=True)
            monthly_price = None
            yearly_price = None

            for price in prices.data:
                if price.recurring and price.recurring.interval == "month":
                    monthly_price = price.id
                elif price.recurring and price.recurring.interval == "year":
                    yearly_price = price.id

            return {
                "stripe_product_id": product.id,
                "stripe_monthly_price_id": monthly_price,
                "stripe_yearly_price_id": yearly_price
            }
    except stripe.error.StripeError as e:
        print(f"  ⚠️  Error searching Stripe products: {e}")

    # Create new product
    try:
        product = stripe.Product.create(
            name=f"The Special Wedding - {plan_name}",
            description=plan.get("description", f"{plan_name} subscription plan"),
            metadata={
                "plan_id": plan_id,
                "source": "seed_script"
            }
        )
        print(f"  ✅ Created Stripe product: {product.id}")

        # Create monthly price
        monthly_price = stripe.Price.create(
            product=product.id,
            unit_amount=int(plan["price_monthly"] * 100),  # Convert to cents
            currency="usd",
            recurring={"interval": "month"},
            metadata={"plan_id": plan_id, "interval": "monthly"}
        )
        print(f"  ✅ Created monthly price: {monthly_price.id} (${plan['price_monthly']}/mo)")

        # Create yearly price
        yearly_price = stripe.Price.create(
            product=product.id,
            unit_amount=int(plan["price_yearly"] * 100),  # Convert to cents
            currency="usd",
            recurring={"interval": "year"},
            metadata={"plan_id": plan_id, "interval": "yearly"}
        )
        print(f"  ✅ Created yearly price: {yearly_price.id} (${plan['price_yearly']}/yr)")

        return {
            "stripe_product_id": product.id,
            "stripe_monthly_price_id": monthly_price.id,
            "stripe_yearly_price_id": yearly_price.id
        }

    except stripe.error.StripeError as e:
        print(f"  ❌ Stripe error creating product: {e}")
        return {}


# Define plans
plans = [
    {
        "_id": "plan_boutique",
        "name": "Boutique",
        "description": "For new planners onboarding their first weddings",
        "price_monthly": 29,
        "price_yearly": 290,  # ~2 months free
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
            "ai_features": True
        },
        "features_list": [
            "Up to 3 weddings",
            "150 guests per wedding",
            "Guest & RSVP manager",
            "Email invitations",
            "Wedding website",
            "Timeline builder",
            "100 AI credits/month"
        ],
        "is_active": True,
        "is_featured": False,
        "sort_order": 1,
        "created_by": "system",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    },
    {
        "_id": "plan_signature",
        "name": "Signature",
        "description": "Most popular plan with full automation features",
        "price_monthly": 59,
        "price_yearly": 590,  # ~2 months free
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
            "priority_support": True
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
            "Priority support"
        ],
        "is_active": True,
        "is_featured": True,
        "sort_order": 2,
        "created_by": "system",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    },
    {
        "_id": "plan_enterprise",
        "name": "Enterprise",
        "description": "For agencies and high-volume wedding planners",
        "price_monthly": 149,
        "price_yearly": 1490,  # ~2 months free
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
            "dedicated_support": True
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
            "Custom integrations"
        ],
        "is_active": True,
        "is_featured": False,
        "sort_order": 3,
        "created_by": "system",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
]

print("\n🌱 Seeding Subscription Plans...")
print("=" * 50)

created = 0
updated = 0
skipped = 0

for plan in plans:
    plan_id = plan["_id"]
    print(f"\n📦 Processing: {plan['name']} - ${plan['price_monthly']}/month")

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
                "created_at": plan_with_stripe.get("created_at", datetime.now(timezone.utc)),
                "created_by": plan_with_stripe.get("created_by", "system"),
            },
            "$set": {
                "name": plan_with_stripe["name"],
                "description": plan_with_stripe.get("description"),
                "price_monthly": plan_with_stripe["price_monthly"],
                "price_yearly": plan_with_stripe.get("price_yearly"),
                "is_metered": plan_with_stripe.get("is_metered", False),
                "max_weddings": plan_with_stripe.get("max_weddings"),
                "max_guests_per_wedding": plan_with_stripe.get("max_guests_per_wedding"),
                "ai_credits_monthly": plan_with_stripe.get("ai_credits_monthly"),
                "storage_gb": plan_with_stripe.get("storage_gb"),
                "staff_seats": plan_with_stripe.get("staff_seats"),
                "features": plan_with_stripe.get("features", {}),
                "features_list": plan_with_stripe.get("features_list", []),
                "is_active": plan_with_stripe.get("is_active", True),
                "is_featured": plan_with_stripe.get("is_featured", False),
                "sort_order": plan_with_stripe.get("sort_order", 0),
                "updated_at": datetime.now(timezone.utc),
                # Only update Stripe IDs if we have them
                **({"stripe_product_id": stripe_ids["stripe_product_id"]} if stripe_ids.get("stripe_product_id") else {}),
                **({"stripe_monthly_price_id": stripe_ids["stripe_monthly_price_id"]} if stripe_ids.get("stripe_monthly_price_id") else {}),
                **({"stripe_yearly_price_id": stripe_ids["stripe_yearly_price_id"]} if stripe_ids.get("stripe_yearly_price_id") else {}),
            }
        },
        upsert=True  # Atomic: creates if not exists, updates if exists
    )

    if result.upserted_id:
        print(f"  ✅ Created in database")
        created += 1
    elif result.modified_count > 0:
        print(f"  ✅ Updated in database")
        updated += 1
    else:
        print(f"  ⏭  No changes needed")
        skipped += 1

print("\n" + "=" * 50)
print(f"📊 Summary: Created {created}, Updated {updated}, Skipped {skipped}")

# Verify final state
all_plans = list(collection.find({"is_active": True}).sort("sort_order", 1))
print(f"\n📋 Active plans in database: {len(all_plans)}")
for p in all_plans:
    stripe_status = "✅ Stripe" if p.get("stripe_product_id") else "❌ No Stripe"
    print(f"  • {p['name']}: ${p['price_monthly']}/mo ({stripe_status})")

client.close()
print("\n✅ Subscription plans seeding complete!")
