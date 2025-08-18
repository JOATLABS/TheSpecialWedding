#!/usr/bin/env python3
"""
Local test migration script for SAAS functionality.
This script tests the migration logic without actually modifying the database.
"""

import os
import sys
from datetime import datetime, timedelta

# For testing purposes, let's create mock collections
class MockCollection:
    def __init__(self, name):
        self.name = name
        self.data = []
    
    def find(self, query=None):
        return iter(self.data)
    
    def find_one(self, query=None):
        if not self.data:
            return None
        return self.data[0] if query is None else None
    
    def insert_many(self, documents):
        self.data.extend(documents)
        return f"Inserted {len(documents)} documents into {self.name}"
    
    def insert_one(self, document):
        self.data.append(document)
        return f"Inserted 1 document into {self.name}"
    
    def update_many(self, filter_query, update_query):
        # Mock update operation
        return type('UpdateResult', (), {'modified_count': 2})()
    
    def count_documents(self, query):
        return len(self.data)
    
    def create_index(self, keys, **kwargs):
        print(f"Created index on {self.name}: {keys}")

class MockMongo:
    def __init__(self):
        self.collections = {
            'subscription_plans': MockCollection('subscription_plans'),
            'saas_content': MockCollection('saas_content'),
            'users': MockCollection('users'),
            'admin_users': MockCollection('admin_users'),
            'weddings': MockCollection('weddings'),
        }
        
        # Add mock admin user
        self.collections['admin_users'].data = [{
            '_id': 'mock_admin_id',
            'email': 'thedeveloper@thespecialwedding.com',
            'hashed_password': '$2b$12$mock_hash',
            'role': 'admin',
            'created_at': datetime.utcnow()
        }]
        
        # Add mock weddings
        self.collections['weddings'].data = [
            {
                '_id': 'wedding_001',
                'couple_names': 'Test Couple 1',
                'date': '2024-12-01',
                'slug': 'test-couple-1'
            },
            {
                '_id': 'wedding_002', 
                'couple_names': 'Test Couple 2',
                'date': '2024-12-15',
                'slug': 'test-couple-2'
            }
        ]
    
    def get_subscription_plans_collection(self):
        return self.collections['subscription_plans']
    
    def get_saas_content_collection(self):
        return self.collections['saas_content']
    
    def get_users_collection(self):
        return self.collections['users']
    
    def get_admin_users_collection(self):
        return self.collections['admin_users']
    
    def get_weddings_collection(self):
        return self.collections['weddings']

def create_default_subscription_plans(mongo):
    """Create default subscription plans"""
    plans_collection = mongo.get_subscription_plans_collection()
    
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
            "max_weddings": -1,
            "ai_credits_monthly": 500,
            "storage_gb": 100,
            "vendor_seats": 50,
            "is_active": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
    ]
    
    result = plans_collection.insert_many(default_plans)
    print(f"Created {len(default_plans)} default subscription plans")

def create_default_saas_content(mongo):
    """Create default SAAS landing page content"""
    content_collection = mongo.get_saas_content_collection()
    
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
                "description": "The ultimate wedding planning platform for professional wedding planners.",
                "cta_text": "Start Free Trial"
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
                "features": []
            },
            "is_active": True,
            "display_order": 2,
            "updated_by": "thedeveloper@thespecialwedding.com",
            "updated_at": datetime.utcnow()
        }
    ]
    
    result = content_collection.insert_many(default_content)
    print(f"Created {len(default_content)} default SAAS content sections")

def migrate_existing_admin_to_root_admin(mongo):
    """Migrate the existing admin user to ROOT_ADMIN in the new users collection"""
    users_collection = mongo.get_users_collection()
    admin_users_collection = mongo.get_admin_users_collection()
    
    root_admin = users_collection.find_one({"email": "thedeveloper@thespecialwedding.com"})
    if root_admin:
        print("ROOT_ADMIN already exists in users collection, skipping...")
        return
    
    existing_admin = admin_users_collection.find_one({"email": "thedeveloper@thespecialwedding.com"})
    if not existing_admin:
        print("No existing admin user found to migrate")
        return
    
    password_field = existing_admin.get("password_hash") or existing_admin.get("hashed_password")
    
    root_admin_user = {
        "_id": "root_admin_001",
        "email": "thedeveloper@thespecialwedding.com",
        "password_hash": password_field,
        "role": "ROOT_ADMIN",
        "company_name": "Special Wedding Development",
        "subscription_plan_id": None,
        "subscription_status": "unlimited",
        "max_weddings": -1,
        "ai_credits_remaining": 99999,
        "is_active": True,
        "email_verified": True,
        "created_at": existing_admin.get("created_at", datetime.utcnow()),
        "updated_at": datetime.utcnow(),
        "last_login": None
    }
    
    users_collection.insert_one(root_admin_user)
    print("Migrated existing admin to ROOT_ADMIN in users collection")

def update_existing_weddings(mongo):
    """Update existing weddings to include SAAS fields"""
    weddings_collection = mongo.get_weddings_collection()
    
    result = weddings_collection.update_many(
        {"created_by": {"$exists": False}},
        {
            "$set": {
                "assigned_planner_email": None,
                "created_by": "thedeveloper@thespecialwedding.com",
                "status": "active"
            }
        }
    )
    
    print(f"Updated {result.modified_count} existing weddings with SAAS fields")

def create_indexes(mongo):
    """Create database indexes for better performance"""
    print("Creating database indexes...")
    
    # Users collection indexes
    users_collection = mongo.get_users_collection()
    users_collection.create_index("email", unique=True)
    users_collection.create_index("role")
    users_collection.create_index("subscription_plan_id")
    
    print("Created database indexes for SAAS collections")

def main():
    """Run the local migration test"""
    print("Starting LOCAL SAAS migration test...")
    print("=" * 50)
    print("This is a TEST run - no real database changes will be made")
    print("=" * 50)
    
    # Create mock database
    mongo = MockMongo()
    
    try:
        # Step 1: Create default subscription plans
        create_default_subscription_plans(mongo)
        
        # Step 2: Create default SAAS content
        create_default_saas_content(mongo)
        
        # Step 3: Migrate existing admin to ROOT_ADMIN
        migrate_existing_admin_to_root_admin(mongo)
        
        # Step 4: Update existing weddings
        update_existing_weddings(mongo)
        
        # Step 5: Create database indexes
        create_indexes(mongo)
        
        print("=" * 50)
        print("LOCAL SAAS migration test completed successfully!")
        print("\nTest Results:")
        print(f"- Subscription plans: {len(mongo.collections['subscription_plans'].data)}")
        print(f"- SAAS content sections: {len(mongo.collections['saas_content'].data)}")
        print(f"- Users: {len(mongo.collections['users'].data)}")
        print(f"- Weddings: {len(mongo.collections['weddings'].data)}")
        
        print("\nTo run on actual database:")
        print("1. Update connection string in migrate_to_saas.py")
        print("2. Run: python scripts/migrate_to_saas.py")
        
    except Exception as e:
        print(f"Migration test failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()