#!/usr/bin/env python3
"""Idempotent cleanup for the isolated marketing-capture workspace.

The reset is deliberately independent of root-admin HTTP authentication. It
uses the dedicated seed namespace and exact fictional identities, so a stale or
misconfigured root account cannot broaden what this cleanup is allowed to
delete.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.database import Database

ROOT = Path(__file__).resolve().parent.parent
SEED_SOURCE = "system:marketing_capture_seed"
SEED_SCOPE = "phase1_showcase_workspace_v1"
PLANNER_EMAIL = "amina@studio.thespecialwedding.io"
TEAM_EMAIL = "maya@studio.thespecialwedding.io"
COUPLE_EMAIL = "sofia.daniel@couples.thespecialwedding.io"
LEGACY_EMAILS = (
    "amina+marketing-capture@showcase.thespecialwedding.io",
    "maya+marketing-capture@showcase.thespecialwedding.io",
    "sofia.daniel+marketing-capture@showcase.thespecialwedding.io",
)
PRIMARY_WEDDING_ID = "wedding_marketing_capture_sofia_daniel"
SECONDARY_WEDDING_ID = "wedding_marketing_capture_avery_morgan"
COUPLE_ID = "couple_marketing_capture_sofia_daniel"
TEAM_MEMBER_ID = ObjectId("67c700000000000000000001")
TEAM_USER_ID = ObjectId("67c700000000000000000002")
SUBSCRIPTION_ID = "marketing_capture_signature_subscription"
ALLOWED_IDENTITY_SOURCES = {SEED_SOURCE, "system:smoke_account_seed"}

# This is the complete graph written by the capture seeder. Keep the manifest
# explicit so additions are reviewable and assert_no_seeded_survivors can prove
# reset completeness instead of relying on the application's older cascade list.
SEEDED_COLLECTIONS = (
    "couple_messages",
    "rsvps",
    "plus_ones",
    "tables",
    "seating_layouts",
    "planner_tasks",
    "inbound_emails",
    "email_logs",
    "support_tickets",
    "vendor_profiles",
    "vendor_assignments",
    "vendor_contracts",
    "vendor_contract_activities",
    "vendor_payment_milestones",
    "vendor_quotes",
    "budget_categories",
    "payment_records",
    "contracts",
    "scheduled_payments",
    "packages",
    "forms",
    "form_responses",
    "form_distributions",
    "form_submissions",
    "guest_media_assets",
    "guest_media_exports",
    "ai_cache",
    "gallery",
    "activity_logs",
    "reminders_sent",
    "planner_notifications",
    "guests",
    "couple_users",
    "team_members",
    "user_subscriptions",
    "weddings",
    "users",
)


def _load_database() -> tuple[MongoClient, Database]:
    load_dotenv(ROOT / ".env")
    testbed_env = ROOT / "testbed" / ".env"
    if testbed_env.exists():
        load_dotenv(testbed_env, override=True)

    environment = os.getenv("ENVIRONMENT", os.getenv("NODE_ENV", "development"))
    if environment.strip().lower() not in {
        "development",
        "dev",
        "local",
        "test",
        "testing",
        "ci",
    }:
        raise RuntimeError("Marketing-capture cleanup is local/test only")

    uri = (os.getenv("MONGO_URI") or os.getenv("MONGODB_URI") or "").strip()
    if not uri:
        raise RuntimeError("MONGO_URI is required")
    parsed = urlparse(uri)
    if parsed.scheme == "mongodb+srv" or parsed.hostname not in {
        "localhost",
        "127.0.0.1",
        "::1",
        "mongo",
        "mongodb",
    }:
        raise RuntimeError("Marketing-capture cleanup refuses non-local Mongo")

    client = MongoClient(uri)
    database = client[os.getenv("MONGO_DB") or os.getenv("MONGO_NAME", "wedding")]
    client.admin.command("ping")
    return client, database


def _seed_filter() -> dict[str, str]:
    return {"seed_source": SEED_SOURCE, "seed_scope": SEED_SCOPE}


def assert_no_seeded_survivors(database: Database) -> None:
    survivors: dict[str, int] = {}
    for collection_name in SEEDED_COLLECTIONS:
        count = database[collection_name].count_documents(_seed_filter(), limit=1)
        if count:
            survivors[collection_name] = count

    identity_checks = {
        "users": {
            "$or": [
                {"email": {"$in": [PLANNER_EMAIL, TEAM_EMAIL, *LEGACY_EMAILS]}},
                {"_id": TEAM_USER_ID},
            ],
            "seed_source": {"$in": sorted(ALLOWED_IDENTITY_SOURCES)},
        },
        "weddings": {
            "_id": {"$in": [PRIMARY_WEDDING_ID, SECONDARY_WEDDING_ID]},
            "assigned_planner_email": PLANNER_EMAIL,
            "seed_source": {"$in": sorted(ALLOWED_IDENTITY_SOURCES)},
        },
        "couple_users": {
            "$or": [
                {"_id": COUPLE_ID},
                {"email": {"$in": [COUPLE_EMAIL, *LEGACY_EMAILS]}},
            ],
            "seed_source": {"$in": sorted(ALLOWED_IDENTITY_SOURCES)},
        },
        "team_members": {
            "$or": [
                {"_id": TEAM_MEMBER_ID},
                {"email": {"$in": [TEAM_EMAIL, *LEGACY_EMAILS]}},
            ],
            "seed_source": {"$in": sorted(ALLOWED_IDENTITY_SOURCES)},
        },
        "user_subscriptions": {"_id": SUBSCRIPTION_ID},
    }
    for collection_name, query in identity_checks.items():
        count = database[collection_name].count_documents(query, limit=1)
        if count:
            survivors[f"{collection_name}:identity"] = count

    if survivors:
        raise RuntimeError(
            "Marketing-capture cleanup left seeded survivors: "
            + json.dumps(survivors, sort_keys=True)
        )


def cleanup_marketing_capture_workspace_state(
    database: Database | None = None,
) -> dict[str, int]:
    """Delete the full capture graph and prove that no scoped fixture remains."""

    owned_client: MongoClient | None = None
    if database is None:
        owned_client, database = _load_database()

    assert database is not None
    deleted: dict[str, int] = {}
    try:
        for collection_name in SEEDED_COLLECTIONS:
            result = database[collection_name].delete_many(_seed_filter())
            deleted[collection_name] = result.deleted_count

        # If a run stopped after setup_smoke_accounts.py but before the rich
        # seeder converted the namespace, remove only the exact dedicated
        # identities and only when their source is one of the two seed sources.
        deleted["couple_users:identity"] = (
            database["couple_users"]
            .delete_many(
                {
                    "$or": [
                        {"_id": COUPLE_ID},
                        {"email": {"$in": [COUPLE_EMAIL, *LEGACY_EMAILS]}},
                    ],
                    "seed_source": {"$in": sorted(ALLOWED_IDENTITY_SOURCES)},
                }
            )
            .deleted_count
        )
        deleted["weddings:identity"] = (
            database["weddings"]
            .delete_many(
                {
                    "_id": {"$in": [PRIMARY_WEDDING_ID, SECONDARY_WEDDING_ID]},
                    "assigned_planner_email": PLANNER_EMAIL,
                    "seed_source": {"$in": sorted(ALLOWED_IDENTITY_SOURCES)},
                }
            )
            .deleted_count
        )
        deleted["team_members:identity"] = (
            database["team_members"]
            .delete_many(
                {
                    "$or": [
                        {"_id": TEAM_MEMBER_ID},
                        {"email": {"$in": [TEAM_EMAIL, *LEGACY_EMAILS]}},
                    ],
                    "seed_source": {"$in": sorted(ALLOWED_IDENTITY_SOURCES)},
                }
            )
            .deleted_count
        )
        deleted["user_subscriptions:identity"] = (
            database["user_subscriptions"]
            .delete_many({"_id": SUBSCRIPTION_ID})
            .deleted_count
        )
        deleted["users:identity"] = (
            database["users"]
            .delete_many(
                {
                    "$or": [
                        {"email": {"$in": [PLANNER_EMAIL, TEAM_EMAIL, *LEGACY_EMAILS]}},
                        {"_id": TEAM_USER_ID},
                    ],
                    "seed_source": {"$in": sorted(ALLOWED_IDENTITY_SOURCES)},
                }
            )
            .deleted_count
        )

        assert_no_seeded_survivors(database)

        fixture_path = ROOT / "output" / "demo-videos" / "capture-fixtures.json"
        if fixture_path.exists():
            try:
                payload: dict[str, Any] = json.loads(fixture_path.read_text())
            except (OSError, json.JSONDecodeError):
                payload = {}
            if (
                payload.get("seedSource") == SEED_SOURCE
                and payload.get("seedScope") == SEED_SCOPE
            ):
                fixture_path.unlink()
        return deleted
    finally:
        if owned_client is not None:
            owned_client.close()


def main() -> int:
    deleted = cleanup_marketing_capture_workspace_state()
    changed = {name: count for name, count in deleted.items() if count}
    print(
        "[OK] Marketing capture cleanup complete; removed "
        f"{sum(deleted.values())} documents across {len(changed)} targets."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"\n[FAIL] Marketing capture cleanup aborted: {exc}\n")
        raise SystemExit(1)
