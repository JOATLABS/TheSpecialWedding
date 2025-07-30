#!/usr/bin/env python3
"""
Migration script to add default configuration values to existing weddings.
This ensures backward compatibility with the new wedding configuration features.
"""

import os
import sys
from pymongo import MongoClient
from datetime import datetime

# Add the app directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def migrate_weddings():
    """Add default configuration values to existing weddings"""
    
    # Connect to MongoDB
    mongo_uri = os.getenv("MONGO_URI", "mongodb://mongo:27017/wedding_db")
    client = MongoClient(mongo_uri)
    db = client.get_database()
    collection = db["weddings"]
    
    # Default values for new fields
    default_rsvp_config = {
        "greeting": "Join us in celebrating our special day! Please let us know if you'll be attending.",
        "help_text": "Check your phone for your personal invitation link, or contact us directly.",
        "phone_numbers": ["(319) 529-6088", "(405) 708-1076"]
    }
    
    default_registries = []  # Empty by default, will use fallback in frontend
    default_faqs = []  # Empty by default, will use fallback in frontend
    
    default_theme_config = {
        "primary_color": "#1e3a5f",
        "secondary_color": "#d4af37", 
        "accent_color": "#c8847e",
        "background_style": "gradient",
        "font_style": "elegant"
    }
    
    # Find weddings without the new fields
    weddings_to_update = collection.find({
        "$or": [
            {"rsvp_config": {"$exists": False}},
            {"registries": {"$exists": False}},
            {"faqs": {"$exists": False}},
            {"theme_config": {"$exists": False}}
        ]
    })
    
    update_count = 0
    
    for wedding in weddings_to_update:
        update_fields = {}
        
        # Add missing fields
        if "rsvp_config" not in wedding:
            update_fields["rsvp_config"] = default_rsvp_config
        
        if "registries" not in wedding:
            update_fields["registries"] = default_registries
        
        if "faqs" not in wedding:
            update_fields["faqs"] = default_faqs
            
        if "theme_config" not in wedding:
            update_fields["theme_config"] = default_theme_config
        
        # Update wedding events to include details field if not present
        if "events" in wedding:
            updated_events = []
            for event in wedding["events"]:
                if "details" not in event:
                    event["details"] = None
                updated_events.append(event)
            update_fields["events"] = updated_events
        
        # Perform update
        if update_fields:
            collection.update_one(
                {"_id": wedding["_id"]},
                {"$set": update_fields}
            )
            update_count += 1
            print(f"Updated wedding: {wedding.get('couple_names', wedding['_id'])}")
    
    print(f"\nMigration complete. Updated {update_count} weddings.")
    
    # Show sample of updated wedding structure
    if update_count > 0:
        sample = collection.find_one()
        print("\nSample wedding structure:")
        print(f"- ID: {sample['_id']}")
        print(f"- Couple Names: {sample['couple_names']}")
        print(f"- Has RSVP Config: {'rsvp_config' in sample}")
        print(f"- Has Registries: {'registries' in sample}")
        print(f"- Has FAQs: {'faqs' in sample}")
        print(f"- Has Theme Config: {'theme_config' in sample}")
        if 'events' in sample and len(sample['events']) > 0:
            print(f"- First Event Has Details: {'details' in sample['events'][0]}")

if __name__ == "__main__":
    print("Starting wedding configuration migration...")
    migrate_weddings()