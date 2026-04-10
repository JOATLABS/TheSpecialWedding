#!/usr/bin/env python3
"""
Reset seeded user data for local development.

This script removes account records and user-generated operational data so the
database can be reseeded from the identities stored in `.env`.
The `.env` identities are treated as manual-flow fixtures, not auto-seeded
accounts. After reset, recreate planner/vendor/couple/team-member records
through the frontend flows you want to test.

It intentionally preserves static platform configuration such as subscription
plans, SaaS config, KB/blog content, and templates.

Usage:
    python scripts/reset_test_user_data.py
    python scripts/reset_test_user_data.py --execute
    python scripts/reset_test_user_data.py --execute --yes
    python scripts/reset_test_user_data.py --verify
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Dict, Iterable, List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import mongo  # noqa: E402

ENV_IDENTITY_KEYS = [
    "ROOT_ADMIN_EMAIL",
    "TEST_COUPLE_EMAIL",
    "TEST_PLANNER_WITH_PACKAGE_EMAIL",
    "TEST_VENDOR_EMAIL",
    "TEST_PLANNER_EMAIL",
    "TEST_TEAM_MEMBER_EMAIL",
]

COLLECTION_GROUPS: "OrderedDict[str, List[str]]" = OrderedDict(
    [
        (
            "identity_and_auth",
            [
                "users",
                "deleted_users",
                "couple_users",
                "team_members",
                "user_invitations",
                "user_subscriptions",
                "usage_tracking",
                "stripe_customers",
                "push_subscriptions",
                "otps",
            ],
        ),
        (
            "planner_and_couple_data",
            [
                "weddings",
                "archived_weddings",
                "guests",
                "rsvps",
                "plus_ones",
                "tables",
                "gallery",
                "forms",
                "form_submissions",
                "form_responses",
                "form_distributions",
                "budgets",
                "budget_categories",
                "budget_alerts",
                "packages",
                "tasks",
                "planner_tasks",
                "contracts",
                "contract_followup_drafts",
                "couple_messages",
                "couple_updates",
                "reminders_sent",
                "sent_task_reminders",
                "checkins",
            ],
        ),
        (
            "vendor_and_ads",
            [
                "vendor_profiles",
                "vendor_directory",
                "vendor_forms",
                "vendor_form_submissions",
                "vendor_quotes",
                "vendor_contracts",
                "vendor_communications",
                "vendor_assignments",
                "vendor_payment_milestones",
                "vendor_submissions",
                "planner_ad_preferences",
                "ad_campaigns",
                "ad_creatives",
                "ad_events",
                "ad_leads",
                "ad_lead_charges",
                "ad_fraud_signals",
                "campaign_day_stats",
                "placement_day_stats",
                "vendor_ad_billing",
                "sponsored_vendors",
            ],
        ),
        (
            "payments_and_messaging",
            [
                "payment_requests",
                "scheduled_payments",
                "payment_records",
                "payment_links",
                "autopilot_payment_logs",
                "stripe_webhook_events",
                "email_logs",
                "email_events",
                "inbound_emails",
                "notifications",
                "planner_notifications",
                "support_tickets",
                "sms_retry_queue",
            ],
        ),
        (
            "operational_logs",
            [
                "admin_activity_log",
                "activity_logs",
                "audit_logs",
                "security_audit_logs",
                "access_logs",
                "errors",
                "platform_metrics",
                "backup_history",
                "ai_usage_log",
                "ai_low_credit_alerts",
                "ai_cache",
            ],
        ),
    ]
)

RESET_COLLECTIONS: List[str] = [
    collection
    for collections in COLLECTION_GROUPS.values()
    for collection in collections
]

PRESERVED_COLLECTIONS = [
    "subscription_plans",
    "saas_config",
    "kb_articles",
    "blog_articles",
    "contract_templates",
    "custom_form_templates",
    "budget_templates",
    "notification_templates",
]


def _load_repo_env(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def _load_identity_emails() -> Dict[str, str]:
    env_values = _load_repo_env(Path(__file__).resolve().parent.parent / ".env")
    identities: Dict[str, str] = {}
    for key in ENV_IDENTITY_KEYS:
        value = os.environ.get(key) or env_values.get(key)
        if value:
            identities[key] = value.strip().lower()
    return identities


async def _list_existing_collections() -> set[str]:
    return set(await mongo.db.list_collection_names())


async def _count_documents(collection_name: str) -> int:
    return await mongo.db[collection_name].count_documents({})


async def _collection_counts(collection_names: Iterable[str]) -> Dict[str, int]:
    existing = await _list_existing_collections()
    counts: Dict[str, int] = {}
    for name in collection_names:
        counts[name] = await _count_documents(name) if name in existing else 0
    return counts


async def _identity_presence(
    identity_emails: Dict[str, str],
) -> Dict[str, Dict[str, int]]:
    presence: Dict[str, Dict[str, int]] = {}
    collections = ["users", "couple_users", "team_members", "user_invitations"]
    existing = await _list_existing_collections()

    for label, email in identity_emails.items():
        email_presence: Dict[str, int] = {}
        for collection in collections:
            if collection not in existing:
                email_presence[collection] = 0
                continue

            query = {"email": email}
            if collection == "team_members":
                count = await mongo.db[collection].count_documents(
                    {"$or": [{"email": email}, {"owner_email": email}]}
                )
            else:
                count = await mongo.db[collection].count_documents(query)

            email_presence[collection] = count
        presence[label] = email_presence

    return presence


def _print_counts(title: str, counts: Dict[str, int]) -> None:
    print(f"\n=== {title} ===")
    for group_name, collections in COLLECTION_GROUPS.items():
        print(f"\n[{group_name}]")
        for collection in collections:
            print(f"  - {collection}: {counts.get(collection, 0)}")


def _print_identity_presence(
    presence: Dict[str, Dict[str, int]], identities: Dict[str, str]
) -> None:
    print("\n=== .env Identity Presence ===")
    for key, email in identities.items():
        counts = presence.get(key, {})
        total = sum(counts.values())
        print(f"\n{key} = {email}")
        print(f"  total_matches: {total}")
        for collection, count in counts.items():
            print(f"  - {collection}: {count}")


async def dry_run() -> None:
    identities = _load_identity_emails()
    counts = await _collection_counts(RESET_COLLECTIONS)
    presence = await _identity_presence(identities)

    print("Dry run only. No data has been deleted.")
    print(
        "The TEST_* identities in .env are manual-flow fixtures and are not recreated by this script."
    )
    print("\nThis reset WILL preserve these collections:")
    for collection in PRESERVED_COLLECTIONS:
        print(f"  - {collection}")

    _print_counts("Reset Collection Counts", counts)
    _print_identity_presence(presence, identities)


async def execute_reset(assume_yes: bool) -> int:
    counts_before = await _collection_counts(RESET_COLLECTIONS)
    total_docs = sum(counts_before.values())

    print("About to delete account and user-generated data from these collections:")
    for group_name, collections in COLLECTION_GROUPS.items():
        print(f"  [{group_name}]")
        for collection in collections:
            print(f"    - {collection}: {counts_before.get(collection, 0)}")

    print(f"\nTotal documents queued for deletion: {total_docs}")
    print("\nPreserved collections:")
    for collection in PRESERVED_COLLECTIONS:
        print(f"  - {collection}")

    if not assume_yes:
        confirmation = input("\nType DELETE ALL USER DATA to continue: ").strip()
        if confirmation != "DELETE ALL USER DATA":
            print("Reset cancelled.")
            return 1

    existing = await _list_existing_collections()
    deleted_total = 0
    for collection in RESET_COLLECTIONS:
        if collection not in existing:
            print(f"[SKIP] {collection}: collection does not exist")
            continue

        result = await mongo.db[collection].delete_many({})
        deleted_total += result.deleted_count
        print(f"[DELETED] {collection}: {result.deleted_count}")

    print(f"\nDeleted {deleted_total} total documents.")
    print("Run this script again with --verify to confirm the reset is clean.")
    print(
        "Note: only the root admin may be recreated on the next application startup by scripts/setup_admin_user.py."
    )
    print(
        "All TEST_* accounts must be recreated manually through the frontend flows you want to validate."
    )
    return 0


async def verify_reset() -> int:
    identities = _load_identity_emails()
    counts = await _collection_counts(RESET_COLLECTIONS)
    presence = await _identity_presence(identities)

    _print_counts("Verification Counts", counts)
    _print_identity_presence(presence, identities)

    residual_docs = {name: count for name, count in counts.items() if count > 0}
    residual_identities = {
        key: collection_counts
        for key, collection_counts in presence.items()
        if sum(collection_counts.values()) > 0
    }

    if residual_docs or residual_identities:
        print("\n[FAILED] Reset verification found remaining user data.")
        if residual_docs:
            print("Remaining collection counts:")
            for name, count in residual_docs.items():
                print(f"  - {name}: {count}")
        if residual_identities:
            print("Remaining .env-linked identities:")
            for key, collection_counts in residual_identities.items():
                print(f"  - {key}: {sum(collection_counts.values())} matches")
        return 1

    print("\n[OK] All reset collections are empty and .env test identities are gone.")
    return 0


async def main_async(args: argparse.Namespace) -> int:
    try:
        if args.verify:
            return await verify_reset()
        if args.execute:
            return await execute_reset(assume_yes=args.yes)
        await dry_run()
        return 0
    finally:
        try:
            mongo.close()
        except Exception:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset local test user data")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Delete all account and user-generated data listed by this script",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify that all reset collections are empty and .env test identities are absent",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the interactive confirmation prompt when used with --execute",
    )
    args = parser.parse_args()

    if args.execute and args.verify:
        parser.error("Choose either --execute or --verify, not both.")

    raise SystemExit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
