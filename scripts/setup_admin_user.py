#!/usr/bin/env python3
"""
Setup Root Admin User Script

Creates the root admin user on application startup if it doesn't exist.
Uses environment variables ROOT_ADMIN_EMAIL and ROOT_ADMIN_PASSWORD.
This script only manages the root admin account. It does not create any
TEST_* planner, vendor, couple, or team-member accounts from `.env`.

Usage:
    python scripts/setup_admin_user.py --auto-create

Flags:
    --auto-create: Skip confirmation prompts (for Docker/CI environments)
"""

import os
import sys
import argparse
import asyncio
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def setup_admin_user(auto_create: bool = False):
    """Create the root admin user if it doesn't exist."""

    # Import after path setup
    from app.core.database import mongo
    from app.utils.auth_utils import get_password_hash

    # Get credentials from environment
    admin_email = os.environ.get("ROOT_ADMIN_EMAIL")
    admin_password = os.environ.get("ROOT_ADMIN_PASSWORD")

    if not admin_email or not admin_password:
        print("[SKIP] ROOT_ADMIN_EMAIL or ROOT_ADMIN_PASSWORD not set. Skipping admin setup.")
        return True

    print(f"[INFO] Checking for root admin user: {admin_email}")
    print("[INFO] TEST_* accounts are manual-flow fixtures and are not created by this script.")

    try:
        # Get collection (Motor connects lazily on first query)
        users_collection = mongo.get_users_collection()

        # Check if admin already exists by email
        existing_user = await users_collection.find_one({"email": admin_email})

        if existing_user:
            print(f"[OK] Root admin user already exists: {admin_email}")
            # Always sync password hash and ensure role is ROOT_ADMIN
            password_hash = get_password_hash(admin_password)
            update_fields = {
                "password_hash": password_hash,
                "is_active": True,
                "email_verified": True,
                "updated_at": datetime.now(timezone.utc),
            }
            if existing_user.get("role") != "ROOT_ADMIN":
                update_fields["role"] = "ROOT_ADMIN"
                print("[UPDATED] Upgraded user role to ROOT_ADMIN")
            await users_collection.update_one(
                {"email": admin_email},
                {"$set": update_fields}
            )
            print("[SYNCED] Password hash and active status synced from environment")
            return True

        # Check if a ROOT_ADMIN exists with a different email (email migration)
        existing_root = await users_collection.find_one({"role": "ROOT_ADMIN"})
        if existing_root and existing_root["email"] != admin_email:
            old_email = existing_root["email"]
            password_hash = get_password_hash(admin_password)
            await users_collection.update_one(
                {"_id": existing_root["_id"]},
                {"$set": {
                    "email": admin_email,
                    "password_hash": password_hash,
                    "updated_at": datetime.now(timezone.utc),
                }}
            )
            print(f"[MIGRATED] Root admin email updated: {old_email} → {admin_email}")
            return True

        # Confirm creation in interactive mode
        if not auto_create:
            confirm = input(f"Create root admin user '{admin_email}'? [y/N]: ")
            if confirm.lower() != 'y':
                print("[SKIP] Admin creation cancelled by user.")
                return True

        # Create the root admin user
        password_hash = get_password_hash(admin_password)

        admin_doc = {
            "_id": f"user_{int(datetime.now(timezone.utc).timestamp() * 1000)}",
            "email": admin_email,
            "password_hash": password_hash,
            "role": "ROOT_ADMIN",
            "is_active": True,
            "email_verified": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "registration_source": "system_init",
            # Root admin has unlimited access
            "max_weddings": 999,
            "ai_credits_remaining": 9999,
        }

        await users_collection.insert_one(admin_doc)
        print(f"[CREATED] Root admin user created successfully: {admin_email}")
        return True

    except Exception as e:
        print(f"[ERROR] Failed to setup admin user: {str(e)}")
        # Don't fail the entire startup - log and continue
        return True
    finally:
        # Close connection (sync method)
        try:
            mongo.close()
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description="Setup root admin user")
    parser.add_argument(
        "--auto-create",
        action="store_true",
        help="Automatically create admin without confirmation (for Docker/CI)"
    )
    args = parser.parse_args()

    # Run async function
    result = asyncio.run(setup_admin_user(auto_create=args.auto_create))

    # Exit with appropriate code
    sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()
