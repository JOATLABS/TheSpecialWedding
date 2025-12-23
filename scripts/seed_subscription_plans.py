import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from pymongo import MongoClient

# Load environment variables
load_dotenv()

# Connect to MongoDB using env vars with sensible fallbacks
mongo_uri = (
    os.getenv("MONGO_URI")
    or os.getenv("MONGODB_URI")
    or os.getenv("MONGO_URL")
    or "mongodb://localhost:27017"
)
db_name = os.getenv("MONGO_DB", "wedding")

client: MongoClient = MongoClient(mongo_uri)
db = client[db_name]
collection = db["subscription_plans"]

plans = [
    {
        "_id": "plan_boutique",
        "name": "Boutique",
        "description": "For new planners onboarding their first weddings",
        "price_monthly": 29,
        "price_yearly": 348,
        "is_metered": True,
        "meter_event_name": "wedding_active",
        "max_weddings": 3,
        "max_guests_per_wedding": 150,
        "ai_credits_monthly": 100,
        "storage_gb": 10,
        "staff_seats": 1,
        "features": {
            "guest_management": True,
            "email_invitations": True,
            "wedding_website": True,
            "timeline_builder": True
        },
        "features_list": [
            "Guest & RSVP manager",
            "Email invitations",
            "Wedding website",
            "Timeline builder"
        ],
        "is_active": True,
        "is_featured": False,
        "sort_order": 1,
        "created_by": "thedeveloper@thespecialwedding.com",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    },
    {
        "_id": "plan_signature",
        "name": "Signature",
        "description": "Most popular plan with automation features",
        "price_monthly": 59,
        "price_yearly": 708,
        "is_metered": True,
        "meter_event_name": "wedding_active",
        "max_weddings": 10,
        "max_guests_per_wedding": 350,
        "ai_credits_monthly": 300,
        "storage_gb": 50,
        "staff_seats": 3,
        "features": {
            "seating_orchestration": True,
            "qr_checkin": True,
            "automated_reminders": True,
            "vendor_collaboration": True
        },
        "features_list": [
            "Seating orchestration",
            "QR check-in & live counts",
            "Automated reminders",
            "Vendor collaboration"
        ],
        "is_active": True,
        "is_featured": True,
        "sort_order": 2,
        "created_by": "thedeveloper@thespecialwedding.com",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
]

created = 0
skipped = 0

for plan in plans:
    existing = collection.find_one({"_id": plan["_id"]})
    if existing:
        print(f"⏭️  Plan '{plan['name']}' already exists")
        skipped += 1
    else:
        collection.insert_one(plan)
        print(f"✅ Created: {plan['name']} - ${plan['price_monthly']}/month")
        created += 1

print(f"\n📊 Summary: Created {created}, Skipped {skipped}")

# Verify
all_plans = list(collection.find({"is_active": True}).sort("sort_order", 1))
print(f"\n📋 Total active plans in database: {len(all_plans)}")
for p in all_plans:
    print(f"  • {p['name']}: ${p['price_monthly']}/mo")

client.close()
