#!/usr/bin/env python3
"""Idempotent cleanup for the isolated marketing-capture workspace.

The reset is deliberately independent of root-admin HTTP authentication. It
uses the dedicated seed namespace and exact fictional identities, so a stale or
misconfigured root account cannot broaden what this cleanup is allowed to
delete.
"""

from __future__ import annotations

import ipaddress
import json
import os
import sys
from pathlib import Path

from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import ConfigurationError, InvalidURI
from pymongo.uri_parser import parse_uri

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.constants.seed_sources import (  # noqa: E402
    LEGACY_SMOKE_SEED_SCOPE,
    MARKETING_CAPTURE_SEED_SCOPE,
    MARKETING_CAPTURE_SEED_SOURCE,
    SMOKE_ACCOUNT_SEED_SOURCE,
)

SEED_SOURCE = MARKETING_CAPTURE_SEED_SOURCE
SEED_SCOPE = MARKETING_CAPTURE_SEED_SCOPE
PLANNER_EMAIL = "amina@studio.thespecialwedding.io"
PLANNER_USER_ID = "user_marketing_capture_amina_cole"
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
ALLOWED_IDENTITY_OWNER_PAIRS = frozenset(
    {
        (SEED_SOURCE, SEED_SCOPE),
        (SMOKE_ACCOUNT_SEED_SOURCE, LEGACY_SMOKE_SEED_SCOPE),
    }
)

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
    "kb_articles",
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
    shell_environment = dict(os.environ)
    load_dotenv(ROOT / ".env", override=False)
    testbed_env = ROOT / "testbed" / ".env"
    if testbed_env.exists():
        load_dotenv(testbed_env, override=True)
    os.environ.update(shell_environment)

    environment = _shell_authoritative_setting(
        shell_environment,
        "ENVIRONMENT",
        "NODE_ENV",
        default="development",
    )
    if environment.strip().lower() not in {
        "development",
        "dev",
        "local",
        "test",
        "testing",
        "ci",
    }:
        raise RuntimeError("Marketing-capture cleanup is local/test only")

    uri = _shell_authoritative_setting(
        shell_environment,
        "MONGO_URI",
        "MONGODB_URI",
        default="",
    ).strip()
    if not uri:
        raise RuntimeError("MONGO_URI is required")
    if not uri.startswith("mongodb://"):
        raise RuntimeError("Marketing-capture cleanup refuses non-local Mongo")
    try:
        nodes = parse_uri(uri)["nodelist"]
    except (ConfigurationError, InvalidURI, ValueError) as exc:
        raise RuntimeError("Marketing-capture cleanup refuses non-local Mongo") from exc
    if not nodes or any(
        host.lower() != "localhost" and not _is_loopback_ip(host)
        for host, _port in nodes
    ):
        raise RuntimeError("Marketing-capture cleanup refuses non-local Mongo")

    database_name = _shell_authoritative_setting(
        shell_environment,
        "MONGO_DB",
        "MONGO_NAME",
        default="wedding",
    ).strip()
    if not database_name:
        raise RuntimeError("MONGO_DB is required")
    client = MongoClient(uri)
    database = client[database_name]
    client.admin.command("ping")
    return client, database


def _is_loopback_ip(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _shell_authoritative_setting(
    shell_environment: dict[str, str],
    primary_name: str,
    alias_name: str,
    *,
    default: str,
) -> str:
    if primary_name in shell_environment:
        return shell_environment[primary_name]
    if alias_name in shell_environment:
        return shell_environment[alias_name]
    return os.getenv(primary_name) or os.getenv(alias_name) or default


def _seed_filter() -> dict[str, str]:
    return {"seed_source": SEED_SOURCE, "seed_scope": SEED_SCOPE}


def _owned_identity_filter(identity_filter: dict[str, object]) -> dict[str, object]:
    """Pair an exact identity with one approved source/scope ownership tuple."""

    ownership_filter = {
        "$or": [
            {"seed_source": source, "seed_scope": scope}
            for source, scope in sorted(ALLOWED_IDENTITY_OWNER_PAIRS)
        ]
    }
    return {"$and": [identity_filter, ownership_filter]}


def _capture_namespace_is_owned(database: Database) -> bool:
    """Authorize runtime-row cleanup only from seed-owned identity evidence."""

    identity_queries = {
        "users": {
            "$or": [
                {"email": {"$in": [PLANNER_EMAIL, TEAM_EMAIL, *LEGACY_EMAILS]}},
                {"_id": {"$in": [PLANNER_USER_ID, TEAM_USER_ID]}},
            ]
        },
        "weddings": {
            "$or": [
                {"_id": {"$in": [PRIMARY_WEDDING_ID, SECONDARY_WEDDING_ID]}},
                {"assigned_planner_email": PLANNER_EMAIL},
            ]
        },
        "couple_users": {
            "$or": [
                {"_id": COUPLE_ID},
                {"email": {"$in": [COUPLE_EMAIL, *LEGACY_EMAILS]}},
            ]
        },
        "team_members": {
            "$or": [
                {"_id": TEAM_MEMBER_ID},
                {"email": {"$in": [TEAM_EMAIL, *LEGACY_EMAILS]}},
            ]
        },
        "user_subscriptions": {"_id": SUBSCRIPTION_ID},
    }

    found_identity = False
    for collection_name, query in identity_queries.items():
        records = database[collection_name].find(
            query,
            {"seed_source": 1, "seed_scope": 1},
        )
        for record in records:
            found_identity = True
            owner = (record.get("seed_source"), record.get("seed_scope"))
            if owner not in ALLOWED_IDENTITY_OWNER_PAIRS:
                return False
    return found_identity


def assert_no_seeded_survivors(database: Database) -> None:
    survivors: dict[str, int] = {}
    for collection_name in SEEDED_COLLECTIONS:
        count = database[collection_name].count_documents(_seed_filter(), limit=1)
        if count:
            survivors[collection_name] = count

    identity_checks = {
        "users": _owned_identity_filter(
            {
                "$or": [
                    {"email": {"$in": [PLANNER_EMAIL, TEAM_EMAIL, *LEGACY_EMAILS]}},
                    {"_id": TEAM_USER_ID},
                ],
            }
        ),
        "weddings": _owned_identity_filter(
            {
                "_id": {"$in": [PRIMARY_WEDDING_ID, SECONDARY_WEDDING_ID]},
                "assigned_planner_email": PLANNER_EMAIL,
            }
        ),
        "couple_users": _owned_identity_filter(
            {
                "$or": [
                    {"_id": COUPLE_ID},
                    {"email": {"$in": [COUPLE_EMAIL, *LEGACY_EMAILS]}},
                ],
            }
        ),
        "team_members": _owned_identity_filter(
            {
                "$or": [
                    {"_id": TEAM_MEMBER_ID},
                    {"email": {"$in": [TEAM_EMAIL, *LEGACY_EMAILS]}},
                ],
            }
        ),
        "user_subscriptions": _owned_identity_filter(
            {
                "_id": SUBSCRIPTION_ID,
            }
        ),
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
        runtime_artifacts_are_owned = _capture_namespace_is_owned(database)

        for collection_name in SEEDED_COLLECTIONS:
            result = database[collection_name].delete_many(_seed_filter())
            deleted[collection_name] = result.deleted_count

        # Authentication and visible browser reads create audit/usage rows that
        # are not authored by the seeder and therefore do not carry seed_scope.
        # Remove only rows bound to the exact dedicated showcase identities.
        deleted["audit_logs:runtime"] = 0
        deleted["usage_tracking:runtime"] = 0
        if runtime_artifacts_are_owned:
            deleted["audit_logs:runtime"] = (
                database["audit_logs"]
                .delete_many(
                    {
                        "$or": [
                            {"user_id": PLANNER_EMAIL},
                            {"user_id": PLANNER_USER_ID},
                            {"user_email": PLANNER_EMAIL},
                            {"user_email": TEAM_EMAIL},
                            {"user_email": COUPLE_EMAIL},
                        ]
                    }
                )
                .deleted_count
            )
            deleted["usage_tracking:runtime"] = (
                database["usage_tracking"]
                .delete_many(
                    {
                        "$or": [
                            {"user_id": PLANNER_USER_ID},
                            {"subscription_id": SUBSCRIPTION_ID},
                        ]
                    }
                )
                .deleted_count
            )

        # If a run stopped after setup_smoke_accounts.py but before the rich
        # seeder converted the namespace, remove only the exact dedicated
        # identities and only when their source is one of the two seed sources.
        deleted["couple_users:identity"] = (
            database["couple_users"]
            .delete_many(
                _owned_identity_filter(
                    {
                        "$or": [
                            {"_id": COUPLE_ID},
                            {"email": {"$in": [COUPLE_EMAIL, *LEGACY_EMAILS]}},
                        ],
                    }
                )
            )
            .deleted_count
        )
        deleted["weddings:identity"] = (
            database["weddings"]
            .delete_many(
                _owned_identity_filter(
                    {
                        "_id": {"$in": [PRIMARY_WEDDING_ID, SECONDARY_WEDDING_ID]},
                        "assigned_planner_email": PLANNER_EMAIL,
                    }
                )
            )
            .deleted_count
        )
        deleted["team_members:identity"] = (
            database["team_members"]
            .delete_many(
                _owned_identity_filter(
                    {
                        "$or": [
                            {"_id": TEAM_MEMBER_ID},
                            {"email": {"$in": [TEAM_EMAIL, *LEGACY_EMAILS]}},
                        ],
                    }
                )
            )
            .deleted_count
        )
        deleted["user_subscriptions:identity"] = (
            database["user_subscriptions"]
            .delete_many(
                _owned_identity_filter(
                    {
                        "_id": SUBSCRIPTION_ID,
                    }
                )
            )
            .deleted_count
        )
        deleted["users:identity"] = (
            database["users"]
            .delete_many(
                _owned_identity_filter(
                    {
                        "$or": [
                            {
                                "email": {
                                    "$in": [PLANNER_EMAIL, TEAM_EMAIL, *LEGACY_EMAILS]
                                }
                            },
                            {"_id": TEAM_USER_ID},
                        ],
                    }
                )
            )
            .deleted_count
        )

        assert_no_seeded_survivors(database)

        fixture_path = ROOT / "output" / "demo-videos" / "capture-fixtures.json"
        fixture_is_owned = False
        if fixture_path.exists():
            try:
                fixture_payload = json.loads(fixture_path.read_text())
            except (OSError, json.JSONDecodeError):
                fixture_payload = {}
            fixture_is_owned = (
                fixture_payload.get("seedSource") == SEED_SOURCE
                and fixture_payload.get("seedScope") == SEED_SCOPE
            )

        if fixture_is_owned:
            for artifact_path in (
                fixture_path,
                ROOT / "output" / "demo-videos" / "state" / "demo-planner.json",
                ROOT / "output" / "demo-videos" / "state" / "demo-couple.json",
                ROOT / "output" / "demo-videos" / "state" / "demo-public.json",
                ROOT / "output" / "demo-videos" / "route-audit-receipt.json",
            ):
                if artifact_path.exists():
                    artifact_path.unlink()
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
