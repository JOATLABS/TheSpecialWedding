#!/usr/bin/env python3
"""
Synchronous migration script to create Emmanuel as wedding planner.
Simpler version that works with current database setup.
"""

import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# Add the app directory to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set environment variables before importing
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("MONGO_DB", "wedding")

from app.core.database import mongo
from app.utils.auth_utils import get_password_hash
import bcrypt

def migrate_emmanuel_to_planner():
    """Main migration function"""
    print("Starting Emmanuel Wedding Planner Migration (Sync Version)")
    print("=" * 70)
    
    email = "emmanuel.t.akinwale@gmail.com"
    password = "j89x8G&8SM8^m"
    
    try:
        # Initialize database collections
        users_collection = mongo.get_users_collection()
        weddings_collection = mongo.get_weddings_collection()
        plans_collection = mongo.db["subscription_plans"]
        subscriptions_collection = mongo.db["user_subscriptions"]
        
        # Step 1: Check existing user
        print(f"Checking for existing user: {email}")
        existing_user = users_collection.find_one({"email": email})
        
        if existing_user:
            user_id = str(existing_user["_id"])
            print(f"Found existing user")
            print(f"   Current role: {existing_user.get('role', 'N/A')}")
            
            # Update to wedding planner role
            update_data = {
                "role": "wedding_planner",
                "is_active": True,
                "email_verified": True,
                "subscription_status": "active",
                "updated_at": datetime.utcnow()
            }
            
            # Update password if needed
            current_hash = existing_user.get("password_hash") or existing_user.get("password")
            if not current_hash or not bcrypt.checkpw(password.encode('utf-8'), current_hash.encode('utf-8')):
                update_data["password_hash"] = get_password_hash(password)
                print("   Password updated to match ROOT_ADMIN")
            
            users_collection.update_one({"_id": existing_user["_id"]}, {"$set": update_data})
            print("Updated user to wedding planner role")
            
        else:
            # Create new user
            print("Creating new wedding planner account")
            user_data = {
                "email": email,
                "password_hash": get_password_hash(password),
                "role": "wedding_planner",
                "first_name": "Emmanuel",
                "last_name": "Akinwale",
                "company_name": "The Special Wedding",
                "is_active": True,
                "email_verified": True,
                "subscription_status": "active",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "created_by": "migration_script"
            }
            
            result = users_collection.insert_one(user_data)
            user_id = str(result.inserted_id)
            print(f"Created new user with ID: {user_id}")
        
        # Step 2: Create Enterprise Plan
        print("\nSetting up Enterprise subscription plan")
        plan_id = "plan_enterprise"
        
        existing_plan = plans_collection.find_one({"_id": plan_id})
        if not existing_plan:
            enterprise_plan = {
                "_id": plan_id,
                "name": "Enterprise",
                "description": "Full-featured plan for professional wedding planners",
                "price_monthly": 99.00,
                "price_yearly": 990.00,
                "features": [
                    "Unlimited weddings",
                    "Unlimited AI credits", 
                    "Unlimited storage",
                    "Unlimited vendor seats",
                    "Unlimited staff seats",
                    "Priority support",
                    "Custom branding",
                    "Advanced analytics"
                ],
                "limits": {
                    "max_weddings": -1,
                    "ai_credits_monthly": -1,
                    "storage_gb": -1,
                    "vendor_seats": -1,
                    "staff_seats": -1
                },
                "is_active": True,
                "sort_order": 3,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "created_by": "migration_script"
            }
            
            plans_collection.insert_one(enterprise_plan)
            print("Created Enterprise plan")
        else:
            print("Enterprise plan already exists")
        
        # Step 3: Assign Enterprise Subscription
        print("\nAssigning Enterprise subscription")
        
        # Check existing subscription
        existing_sub = subscriptions_collection.find_one({
            "user_id": user_id,
            "status": {"$in": ["active", "trial"]}
        })
        
        if existing_sub and existing_sub.get("plan_id") == plan_id:
            print("User already has Enterprise subscription")
        else:
            # Cancel existing subscription if any
            if existing_sub:
                subscriptions_collection.update_one(
                    {"_id": existing_sub["_id"]},
                    {"$set": {"status": "cancelled", "cancelled_at": datetime.utcnow()}}
                )
                print("Cancelled existing subscription")
            
            # Create new enterprise subscription
            now = datetime.utcnow()
            subscription_data = {
                "_id": f"sub_{user_id}_{plan_id}_{int(now.timestamp())}",
                "user_id": user_id,
                "user_email": email,
                "plan_id": plan_id,
                "status": "active",
                "billing_interval": "yearly",
                "start_date": now,
                "current_period_start": now,
                "current_period_end": now + timedelta(days=365),
                "usage": {
                    "weddings_created": 0,
                    "ai_credits_used": 0,
                    "storage_used_gb": 0,
                    "vendor_seats_used": 0,
                    "staff_seats_used": 0
                },
                "created_at": now,
                "updated_at": now,
                "created_by": "migration_script"
            }
            
            subscriptions_collection.insert_one(subscription_data)
            print("Created Enterprise subscription")
        
        # Update user
        users_collection.update_one(
            {"email": email},
            {"$set": {
                "subscription_plan_id": plan_id,
                "subscription_status": "active",
                "updated_at": datetime.utcnow()
            }}
        )
        
        # Step 4: Find and migrate Emmanuel's wedding
        print("\nLooking for Emmanuel's wedding...")
        
        # Search for wedding by ID first
        wedding = weddings_collection.find_one({"_id": "wedding_1749945524609"})
        
        if wedding:
            print(f"Found wedding: {wedding.get('couple_names', 'Unknown')}")
            
            # Migrate existing wedding
            result = weddings_collection.update_one(
                {"_id": wedding["_id"]},
                {"$set": {
                    "assigned_planner_email": email,
                    "assigned_planner_id": user_id,
                    "updated_at": datetime.utcnow(),
                    "migration_notes": "Migrated by script - Emmanuel as wedding planner"
                }}
            )
            
            if result.modified_count > 0:
                print(f"Migrated wedding: {wedding.get('couple_names', 'Unknown')}")
                print(f"   Wedding ID: {wedding['_id']}")
                print(f"   Slug: {wedding.get('slug', 'N/A')}")
            else:
                print("Wedding already assigned or update failed")
        else:
            print("Wedding not found - may need to create a sample")
        
        # Step 5: Verification
        print("\nVerification Summary:")
        print("=" * 50)
        
        # Check final user state
        final_user = users_collection.find_one({"email": email})
        if final_user:
            print(f"User Account:")
            print(f"   Email: {final_user['email']}")
            print(f"   Role: {final_user['role']}")
            print(f"   Status: {final_user.get('subscription_status', 'N/A')}")
            print(f"   Plan: {final_user.get('subscription_plan_id', 'N/A')}")
        
        # Check weddings
        user_weddings = list(weddings_collection.find({"assigned_planner_email": email}))
        print(f"\nAssigned Weddings: {len(user_weddings)}")
        for w in user_weddings:
            print(f"   - {w.get('couple_names', 'Unnamed')} (ID: {w['_id']})")
        
        print("\nMigration completed successfully!")
        print(f"\nAccess URLs:")
        print(f"   ROOT_ADMIN: http://localhost:3000/admin")
        print(f"   PLANNER: http://localhost:3000/admin/planner") 
        print(f"   Login: {email}")
        print(f"   Password: [Same as ROOT_ADMIN password]")
        
        print(f"\nEmmanuel now has dual access:")
        print(f"   - ROOT_ADMIN capabilities (thedeveloper@thespecialwedding.com)")
        print(f"   - Wedding Planner for own wedding(s) (emmanuel.t.akinwale@gmail.com)")
        
    except Exception as e:
        print(f"\nMigration failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = migrate_emmanuel_to_planner()
    sys.exit(0 if success else 1)