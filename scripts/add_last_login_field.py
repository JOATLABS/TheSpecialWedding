#!/usr/bin/env python3
"""
Migration script to add last_login field to existing user collections
"""
import sys
sys.path.append('.')

try:
    from app.core.database import mongo
    from datetime import datetime
    print("✅ Successfully imported database connection")

    # Add last_login field to admin_users collection (for legacy admin/ROOT_ADMIN)
    print("\n=== Updating admin_users collection ===")
    admin_result = mongo.db["admin_users"].update_many(
        {"last_login": {"$exists": False}},  # Only update documents without last_login
        {"$set": {"last_login": None}}
    )
    print(f"Updated {admin_result.modified_count} admin users with last_login field")

    # Add last_login field to users collection (for wedding planners, vendors)
    print("\n=== Updating users collection ===")
    users_result = mongo.db["users"].update_many(
        {"last_login": {"$exists": False}},  # Only update documents without last_login
        {"$set": {"last_login": None}}
    )
    print(f"Updated {users_result.modified_count} users with last_login field")

    # Show current state
    print("\n=== Current Users ===")
    print("Admin Users:")
    admin_users = list(mongo.db["admin_users"].find({}, {"email": 1, "last_login": 1}))
    for user in admin_users:
        print(f"  - {user.get('email')}: last_login = {user.get('last_login', 'None')}")

    print("\nRegular Users:")
    users = list(mongo.db["users"].find({}, {"email": 1, "role": 1, "last_login": 1}))
    for user in users:
        print(f"  - {user.get('email')} ({user.get('role', 'unknown')}): last_login = {user.get('last_login', 'None')}")

    print("\n✅ Migration completed successfully")

except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running this from the project root directory")
except Exception as e:
    print(f"❌ Error: {e}")