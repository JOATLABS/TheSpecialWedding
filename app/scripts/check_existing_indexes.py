#!/usr/bin/env python3
"""
Check Existing Database Indexes
Lists all current indexes in MongoDB collections
"""

import os
import sys
from pathlib import Path
from pymongo import MongoClient
from bson import json_util
import json

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.core.database import mongo


def check_existing_indexes():
    """Check and display all existing indexes in the database"""

    print("🔍 Checking existing database indexes...")
    print("=" * 60)

    db = mongo.db

    # Collections to check
    collections = [
        "guests",
        "rsvps",
        "plus_ones",
        "form_responses",
        "weddings",
        "checkins",
        "otp_codes",
        "reminders_sent",
        "security_audit_logs",
        "forms",
        "users"
    ]

    all_indexes = {}
    total_indexes = 0

    for collection_name in collections:
        try:
            collection = db[collection_name]
            indexes = list(collection.list_indexes())

            if indexes:
                print(f"\n📦 Collection: {collection_name}")
                print("-" * 40)

                collection_indexes = []
                for index in indexes:
                    index_name = index.get("name", "unnamed")
                    index_keys = index.get("key", {})

                    # Format index keys for display
                    key_list = [f"{field}: {direction}" for field, direction in index_keys.items()]

                    print(f"  • {index_name}")
                    print(f"    Keys: {', '.join(key_list)}")

                    # Check for special properties
                    if index.get("unique"):
                        print(f"    ⚠️  UNIQUE constraint")
                    if index.get("sparse"):
                        print(f"    💨 SPARSE index")
                    if index.get("expireAfterSeconds"):
                        print(f"    ⏰ TTL: {index['expireAfterSeconds']} seconds")
                    if index.get("background"):
                        print(f"    🔄 Background index")

                    collection_indexes.append({
                        "name": index_name,
                        "keys": index_keys,
                        "properties": {
                            "unique": index.get("unique", False),
                            "sparse": index.get("sparse", False),
                            "ttl": index.get("expireAfterSeconds"),
                            "background": index.get("background", False)
                        }
                    })

                all_indexes[collection_name] = collection_indexes
                total_indexes += len(indexes)
            else:
                print(f"\n📦 Collection: {collection_name}")
                print("  ❌ No indexes found (only default _id index)")

        except Exception as e:
            print(f"\n⚠️  Collection '{collection_name}' not found or error: {str(e)}")

    # Summary
    print("\n" + "=" * 60)
    print("📊 INDEX SUMMARY")
    print("=" * 60)
    print(f"Total indexes found: {total_indexes}")

    # Check for critical missing indexes
    print("\n🚨 CRITICAL INDEX CHECK:")

    critical_indexes = [
        ("guests", [("wedding_id", 1), ("email", 1)]),
        ("guests", [("wedding_id", 1), ("phone", 1)]),
        ("rsvps", [("wedding_id", 1), ("guest_id", 1)]),
        ("rsvps", [("guest_id", 1)]),
        ("plus_ones", [("guest_id", 1)]),
        ("forms", [("wedding_id", 1)]),
    ]

    missing_critical = []

    for collection_name, expected_keys in critical_indexes:
        if collection_name in all_indexes:
            # Check if index exists with these keys
            has_index = False
            for idx in all_indexes[collection_name]:
                idx_keys = list(idx["keys"].items())
                if idx_keys == expected_keys:
                    has_index = True
                    break

            if not has_index:
                missing_critical.append((collection_name, expected_keys))

    if missing_critical:
        print("\n❌ Missing critical indexes for performance:")
        for coll, keys in missing_critical:
            key_str = ", ".join([f"{k[0]}:{k[1]}" for k in keys])
            print(f"  • {coll}: [{key_str}]")
    else:
        print("  ✅ All critical indexes appear to be present")

    # Save report
    report_path = Path(__file__).parent / "index_report.json"
    with open(report_path, "w") as f:
        json.dump(all_indexes, f, indent=2, default=json_util.default)

    print(f"\n💾 Full report saved to: {report_path}")

    return all_indexes


if __name__ == "__main__":
    check_existing_indexes()