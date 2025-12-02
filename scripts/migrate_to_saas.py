#!/usr/bin/env python3
"""
Database migration script for SAAS functionality.
This script safely adds new collections and migrates existing data without breaking anything.
"""

import os
import sys
from datetime import datetime, timedelta
from bson import ObjectId

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.core.database import mongo
from app.models.saas import SubscriptionPlanModel, SaasContentModel
from app.models.user_extended import UserModel

def create_default_subscription_plans():
    """Create default subscription plans"""
    plans_collection = mongo.get_subscription_plans_collection()
    # Check if plans already exist
    if plans_collection.count_documents({}) > 0:
        print("Subscription plans already exist, skipping...")
        return
    default_plans = [
        {
            "_id": "plan_starter",
            "name": "Starter",
            "price": 0.0,
            "features": [
                "1 Wedding",
                "Basic RSVP Management",
                "Simple Wedding Website",
                "Guest List Management",
                "Email Notifications"
            ],
            "max_weddings": 1,
            "ai_credits_monthly": 10,
            "storage_gb": 1,
            "vendor_seats": 0,
            "is_active": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        },
        {
            "_id": "plan_professional",
            "name": "Professional",
            "price": 49.0,
            "features": [
                "Up to 5 Weddings",
                "Advanced RSVP Management",
                "Custom Wedding Websites",
                "Vendor Management",
                "AI-Powered Tools",
                "Advanced Reporting",
                "SMS Notifications",
                "Priority Support"
            ],
            "max_weddings": 5,
            "ai_credits_monthly": 100,
            "storage_gb": 10,
            "vendor_seats": 10,
            "is_active": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        },
        {
            "_id": "plan_enterprise",
            "name": "Enterprise",
            "price": 149.0,
            "features": [
                "Unlimited Weddings",
                "White-label Solution",
                "Advanced AI Features",
                "Custom Integrations",
                "Dedicated Support",
                "Advanced Analytics",
                "Multi-user Collaboration",
                "API Access"
            ],
            "max_weddings": -1,  # -1 means unlimited
            "ai_credits_monthly": 500,
            "storage_gb": 100,
            "vendor_seats": 50,
            "is_active": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
    ]
    plans_collection.insert_many(default_plans)
    print(f"Created {len(default_plans)} default subscription plans")

def create_default_saas_content():
    """Create default SAAS landing page content"""
    content_collection = mongo.get_saas_content_collection()
    # Check if content already exists
    if content_collection.count_documents({}) > 0:
        print("SAAS content already exists, skipping...")
        return
    default_content = [
        {
            "_id": "hero_section",
            "section": "hero",
            "content": {
                "title": "Welcome to Special Wedding",
                "subtitle": "Wedding Planning Made Simple",
                "description": "The ultimate wedding planning platform for professional wedding planners. Manage multiple weddings, coordinate with vendors, and create beautiful wedding websites with AI-powered tools.",
                "cta_text": "Start Free Trial",
                "background_image": "/images/hero-bg.jpg"
            },
            "is_active": True,
            "display_order": 1,
            "updated_by": "thedeveloper@thespecialwedding.com",
            "updated_at": datetime.utcnow()
        },
        {
            "_id": "features_section",
            "section": "features",
            "content": {
                "title": "Powerful Features for Wedding Professionals",
                "features": [
                    {
                        "id": "wedding_management",
                        "title": "Complete Wedding Management",
                        "description": "Manage multiple weddings with ease. Track guests, RSVPs, vendors, and timelines all in one place.",
                        "icon": "calendar"
                    },
                    {
                        "id": "ai_presentation",
                        "title": "AI Presentation Generator",
                        "description": "Create stunning wedding presentations in minutes with our AI-powered tools.",
                        "icon": "presentation"
                    },
                    {
                        "id": "smart_email",
                        "title": "Smart Email Assistant",
                        "description": "Send professional emails with embedded reports and updates using AI.",
                        "icon": "email"
                    },
                    {
                        "id": "budget_optimization",
                        "title": "Budget Optimization Engine",
                        "description": "Calculate optimal spending for maximum impact on your client's special day.",
                        "icon": "calculator"
                    },
                    {
                        "id": "design_research",
                        "title": "Design Research AI",
                        "description": "Get color palettes, themes, and design inspiration tailored to your clients.",
                        "icon": "palette"
                    },
                    {
                        "id": "vendor_management",
                        "title": "Vendor Collaboration",
                        "description": "Give vendors access to update their portions of the wedding checklist.",
                        "icon": "network"
                    }
                ]
            },
            "is_active": True,
            "display_order": 2,
            "updated_by": "thedeveloper@thespecialwedding.com",
            "updated_at": datetime.utcnow()
        },
        {
            "_id": "testimonials_section",
            "section": "testimonials",
            "content": {
                "title": "What Wedding Planners Are Saying",
                "testimonials": [
                    {
                        "id": "testimonial_1",
                        "name": "Sarah Johnson",
                        "company": "Elegant Events Planning",
                        "role": "Senior Wedding Planner",
                        "text": "Special Wedding has revolutionized how I manage my clients' weddings. The AI tools save me hours every week!",
                        "avatar": "/images/testimonial-1.jpg"
                    },
                    {
                        "id": "testimonial_2",
                        "name": "Michael Chen",
                        "company": "Dream Day Weddings",
                        "role": "Wedding Coordinator",
                        "text": "The vendor collaboration features are game-changing. Everyone stays on the same page effortlessly.",
                        "avatar": "/images/testimonial-2.jpg"
                    },
                    {
                        "id": "testimonial_3",
                        "name": "Emily Rodriguez",
                        "company": "Perfect Moments",
                        "role": "Lead Planner",
                        "text": "My clients love their custom wedding websites, and I love how easy they are to create and manage.",
                        "avatar": "/images/testimonial-3.jpg"
                    }
                ]
            },
            "is_active": True,
            "display_order": 4,
            "updated_by": "thedeveloper@thespecialwedding.com",
            "updated_at": datetime.utcnow()
        }
    ]
    content_collection.insert_many(default_content)
    print(f"Created {len(default_content)} default SAAS content sections")

def migrate_existing_admin_to_root_admin():
    """Migrate the existing admin user to ROOT_ADMIN in the new users collection"""
    users_collection = mongo.get_users_collection()
    admin_users_collection = mongo.get_admin_users_collection()
    # Check if ROOT_ADMIN already exists in users collection
    root_admin = users_collection.find_one({"email": "thedeveloper@thespecialwedding.com"})
    if root_admin:
        print("ROOT_ADMIN already exists in users collection, skipping...")
        return
    # Find the existing admin user
    existing_admin = admin_users_collection.find_one({"email": "thedeveloper@thespecialwedding.com"})
    if not existing_admin:
        print("No existing admin user found to migrate")
        return

    # Create ROOT_ADMIN user in the new users collection
    # Handle both 'password_hash' and 'hashed_password' field names
    password_field = existing_admin.get("password_hash") or existing_admin.get("hashed_password")

    root_admin_user = {
        "_id": str(ObjectId()),
        "email": "thedeveloper@thespecialwedding.com",
        "password_hash": password_field,
        "role": "ROOT_ADMIN",
        "company_name": "Special Wedding Development",
        "subscription_plan_id": None,  # ROOT_ADMIN doesn't need a subscription
        "subscription_status": "unlimited",
        "max_weddings": -1,  # Unlimited
        "ai_credits_remaining": 99999,  # Unlimited
        "is_active": True,
        "email_verified": True,
        "created_at": existing_admin.get("created_at", datetime.utcnow()),
        "updated_at": datetime.utcnow(),
        "last_login": None
    }
    users_collection.insert_one(root_admin_user)
    print("Migrated existing admin to ROOT_ADMIN in users collection")

def update_existing_weddings():
    """Update existing weddings to include SAAS fields"""
    weddings_collection = mongo.get_weddings_collection()
    # Update all existing weddings to include SAAS fields
    result = weddings_collection.update_many(
        {"created_by": {"$exists": False}},  # Only update weddings that don't have SAAS fields
        {
            "$set": {
                "assigned_planner_email": None,  # Will be assigned later by ROOT_ADMIN
                "created_by": "thedeveloper@thespecialwedding.com",  # ROOT_ADMIN created existing weddings
                "status": "active"
            }
        }
    )
    print(f"Updated {result.modified_count} existing weddings with SAAS fields")

def create_indexes():
    """Create database indexes for better performance"""
    # Users collection indexes
    users_collection = mongo.get_users_collection()
    users_collection.create_index("email", unique=True)
    users_collection.create_index("role")
    users_collection.create_index("subscription_plan_id")
    users_collection.create_index("created_by")
    # Vendors collection indexes
    vendors_collection = mongo.get_vendors_collection()
    vendors_collection.create_index("email", unique=True)
    vendors_collection.create_index("wedding_id")
    vendors_collection.create_index("created_by")
    # Wedding checklist indexes
    checklist_collection = mongo.get_wedding_checklist_collection()
    checklist_collection.create_index("wedding_id")
    checklist_collection.create_index("assigned_vendor_id")
    checklist_collection.create_index("status")
    # AI usage indexes
    ai_usage_collection = mongo.get_ai_usage_collection()
    ai_usage_collection.create_index("user_email")
    ai_usage_collection.create_index("created_at")
    ai_usage_collection.create_index("wedding_id")
    # SAAS content indexes
    content_collection = mongo.get_saas_content_collection()
    content_collection.create_index("section", unique=True)
    content_collection.create_index("display_order")
    # Weddings collection indexes (add to existing)
    weddings_collection = mongo.get_weddings_collection()
    weddings_collection.create_index("assigned_planner_email")
    weddings_collection.create_index("created_by")
    weddings_collection.create_index("status")
    print("Created database indexes for SAAS collections")

def main():
    """Run the migration"""
    print("Starting SAAS migration...")
    print("=" * 50)

    try:
        # Step 1: Create default subscription plans
        create_default_subscription_plans()

        # Step 2: Create default SAAS content
        create_default_saas_content()

        # Step 3: Migrate existing admin to ROOT_ADMIN
        migrate_existing_admin_to_root_admin()

        # Step 4: Update existing weddings
        update_existing_weddings()

        # Step 5: Create database indexes
        create_indexes()

        print("=" * 50)
        print("SAAS migration completed successfully!")
        print("\nNext steps:")
        print("1. The ROOT_ADMIN (thedeveloper@thespecialwedding.com) can now access the SAAS admin panel")
        print("2. Create wedding planners and assign existing weddings to them")
        print("3. Configure the SAAS landing page content as needed")
    except Exception as e:
        print(f"Migration failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()