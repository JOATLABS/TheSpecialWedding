#!/usr/bin/env python3
"""
Migration script to ensure all weddings have proper privacy settings.

This script will:
1. Find weddings without privacy_settings
2. Add default privacy_settings with privacy_mode='private'
3. Report on the changes made

Usage:
    python scripts/migrate_wedding_privacy.py
"""

import sys
import os
from datetime import datetime

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import mongo

def migrate_wedding_privacy():
    """Migrate all weddings to have proper privacy settings"""
    
    print("🔒 Wedding Privacy Migration Script")
    print("-" * 50)
    
    try:
        weddings_collection = mongo.db["weddings"]
        
        # Find all weddings
        all_weddings = list(weddings_collection.find({}))
        total_weddings = len(all_weddings)
        
        print(f"📊 Found {total_weddings} weddings in database")
        
        if total_weddings == 0:
            print("✅ No weddings found - migration not needed")
            return
        
        # Analyze current privacy settings
        weddings_without_privacy = []
        weddings_with_privacy = []
        weddings_public = []
        
        for wedding in all_weddings:
            wedding_id = wedding.get("_id", "unknown")
            couple_names = wedding.get("couple_names", "Unknown Couple")
            privacy_settings = wedding.get("privacy_settings")
            
            if not privacy_settings:
                # No privacy settings at all
                weddings_without_privacy.append({
                    "id": wedding_id,
                    "couple_names": couple_names,
                    "wedding": wedding
                })
            else:
                privacy_mode = privacy_settings.get("privacy_mode", "not_set")
                if privacy_mode == "public":
                    weddings_public.append({
                        "id": wedding_id,
                        "couple_names": couple_names,
                        "privacy_mode": privacy_mode
                    })
                else:
                    weddings_with_privacy.append({
                        "id": wedding_id,
                        "couple_names": couple_names,
                        "privacy_mode": privacy_mode
                    })
        
        print(f"\n📈 Current Privacy Status:")
        print(f"  • Weddings without privacy settings: {len(weddings_without_privacy)}")
        print(f"  • Weddings with private/password settings: {len(weddings_with_privacy)}")
        print(f"  • Weddings explicitly set to public: {len(weddings_public)}")
        
        # Show weddings that will be affected
        if weddings_without_privacy:
            print(f"\n🔧 Weddings that will be updated to PRIVATE:")
            for wedding in weddings_without_privacy:
                print(f"  • {wedding['couple_names']} (ID: {wedding['id']})")
        
        if weddings_public:
            print(f"\n⚠️  Weddings currently set to PUBLIC (will remain public):")
            for wedding in weddings_public:
                print(f"  • {wedding['couple_names']} (ID: {wedding['id']})")
        
        # Confirm migration
        if weddings_without_privacy:
            print(f"\n❓ This will make {len(weddings_without_privacy)} weddings PRIVATE by default.")
            print("   Visitors will need to verify as guests to access these weddings.")
            response = input("\n   Proceed with migration? (y/N): ").lower().strip()
            
            if response != 'y':
                print("❌ Migration cancelled by user")
                return
        else:
            print("\n✅ All weddings already have privacy settings - no migration needed")
            return
        
        # Perform migration
        print(f"\n🔄 Migrating {len(weddings_without_privacy)} weddings...")
        
        # Default privacy settings for private weddings
        default_privacy_settings = {
            "privacy_mode": "private",
            "guest_auth_required": True,
            "password_protection": None,
            "allow_guest_sharing": False,
            "require_phone_verification": True,
            "require_name_verification": True
        }
        
        updated_count = 0
        for wedding_info in weddings_without_privacy:
            wedding_id = wedding_info["id"]
            couple_names = wedding_info["couple_names"]
            
            try:
                result = weddings_collection.update_one(
                    {"_id": wedding_id},
                    {"$set": {
                        "privacy_settings": default_privacy_settings,
                        "updated_at": datetime.utcnow(),
                        "privacy_migrated_at": datetime.utcnow()
                    }}
                )
                
                if result.modified_count > 0:
                    updated_count += 1
                    print(f"  ✅ Updated: {couple_names}")
                else:
                    print(f"  ⚠️  Warning: {couple_names} - no changes made")
                    
            except Exception as e:
                print(f"  ❌ Error updating {couple_names}: {str(e)}")
        
        print(f"\n🎉 Migration Complete!")
        print(f"  • Successfully updated: {updated_count} weddings")
        print(f"  • All updated weddings are now PRIVATE by default")
        print(f"  • Guests will need to verify their identity to access wedding pages")
        
        # Summary
        print(f"\n📋 Final Privacy Status:")
        print(f"  • Total weddings: {total_weddings}")
        print(f"  • Private weddings: {len(weddings_with_privacy) + updated_count}")
        print(f"  • Public weddings: {len(weddings_public)}")
        print(f"  • Migration timestamp: {datetime.utcnow().isoformat()}")
        
        print(f"\n💡 Next Steps:")
        print(f"  • Test a wedding URL to ensure guest verification is working")
        print(f"  • If you want specific weddings to be public, update their privacy_mode to 'public'")
        print(f"  • The privacy system is now fully enforced!")
        
    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")
        sys.exit(1)

def show_privacy_status():
    """Show current privacy status without making changes"""
    try:
        weddings_collection = mongo.db["weddings"]
        all_weddings = list(weddings_collection.find({}, {"couple_names": 1, "privacy_settings": 1}))
        
        print("🔒 Current Wedding Privacy Status")
        print("-" * 40)
        
        for wedding in all_weddings:
            couple_names = wedding.get("couple_names", "Unknown")
            privacy_settings = wedding.get("privacy_settings", {})
            privacy_mode = privacy_settings.get("privacy_mode", "NOT SET")
            
            status_icon = {
                "private": "🔒",
                "public": "🌍", 
                "password": "🔑",
                "NOT SET": "❓"
            }.get(privacy_mode, "❓")
            
            print(f"  {status_icon} {couple_names}: {privacy_mode}")
            
    except Exception as e:
        print(f"❌ Error checking status: {str(e)}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--status":
        show_privacy_status()
    else:
        migrate_wedding_privacy()