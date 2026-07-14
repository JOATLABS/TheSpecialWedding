#!/usr/bin/env python3
"""Reset, seed, verify, and expose browser checks for Phase 1 captures."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from bson import ObjectId
from pymongo.database import Database
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from testbed.cleanup_marketing_capture_workspace_state import (  # noqa: E402
    SEED_SCOPE,
    SEED_SOURCE,
    _load_database,
    cleanup_marketing_capture_workspace_state,
)
from app.models.vendor_contracts import (  # noqa: E402
    VendorContractActivityItem,
    VendorContractActivityType,
)

SETUP_SMOKE_ACCOUNTS = ROOT / "scripts" / "setup_smoke_accounts.py"
RICH_WORKSPACE_SEEDER = (
    ROOT / "scripts" / "demo-videos" / "seed-demo-video-workspace.py"
)
DEFAULT_ANCHOR_AT = "2026-07-12T10:00:00"
PLANNER_EMAIL = "amina@studio.thespecialwedding.io"
PLANNER_PASSWORD = "CapturePlanner2026!"  # pragma: allowlist secret
PLANNER_USER_ID = "user_marketing_capture_amina_cole"
TEAM_EMAIL = "maya@studio.thespecialwedding.io"
TEAM_PASSWORD = "CaptureTeam2026!"  # pragma: allowlist secret
COUPLE_EMAIL = "sofia.daniel@couples.thespecialwedding.io"
COUPLE_PASSWORD = "CaptureCouple2026!"  # pragma: allowlist secret
COUPLE_ID = "couple_marketing_capture_sofia_daniel"
PRIMARY_WEDDING_ID = "wedding_marketing_capture_sofia_daniel"
PRIMARY_SLUG = "sofia-and-daniel"
SECONDARY_WEDDING_ID = "wedding_marketing_capture_avery_morgan"
SECONDARY_SLUG = "avery-and-morgan"
DEMO_KB_ARTICLE_ID = ObjectId("67c900000000000000000001")
DEMO_KB_ARTICLE_SLUG = "planner-command-center-first-steps"
CONTROLLED_IDENTITY_DOMAIN = "thespecialwedding.io"
RESERVED_IDENTITY_DOMAINS = frozenset({"example.com", "example.net", "example.org"})
RESERVED_IDENTITY_SUFFIXES = (".example", ".invalid", ".test")
RESERVED_FICTIONAL_PHONE_PATTERN = re.compile(r"^1?[2-9]\d{2}55501\d{2}$")


def assert_setup_namespace_available(database: Database) -> None:
    """Fail before the smoke-account bootstrap can retag a real local record."""

    collision_queries = {
        "users": {
            "$or": [
                {"_id": PLANNER_USER_ID},
                {"_id": ObjectId("67c700000000000000000002")},
                {"email": {"$in": [PLANNER_EMAIL, TEAM_EMAIL]}},
            ]
        },
        "couple_users": {"$or": [{"_id": COUPLE_ID}, {"email": COUPLE_EMAIL}]},
        "team_members": {
            "$or": [
                {"_id": ObjectId("67c700000000000000000001")},
                {"email": TEAM_EMAIL},
            ]
        },
        "user_subscriptions": {"_id": "marketing_capture_signature_subscription"},
        "weddings": {
            "$or": [
                {"_id": {"$in": [PRIMARY_WEDDING_ID, SECONDARY_WEDDING_ID]}},
                {"slug": {"$in": [PRIMARY_SLUG, SECONDARY_SLUG]}},
            ]
        },
        "kb_articles": {
            "$or": [
                {"_id": DEMO_KB_ARTICLE_ID},
                {"slug": DEMO_KB_ARTICLE_SLUG},
            ]
        },
    }
    for collection_name, query in collision_queries.items():
        existing = database[collection_name].find_one(query, {"_id": 1})
        if existing:
            raise RuntimeError(
                f"Dedicated marketing-capture namespace collides in {collection_name}; "
                "refusing to let setup_smoke_accounts overwrite local data."
            )


def _run_python(
    script: Path, *, env: dict[str, str], args: list[str] | None = None
) -> None:
    command = [sys.executable, str(script), *(args or [])]
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def _require(condition: Any, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _identity_hostname_is_safe(hostname: str) -> bool:
    normalized = hostname.strip().lower().rstrip(".")
    if not normalized:
        return False
    if normalized == CONTROLLED_IDENTITY_DOMAIN or normalized.endswith(
        f".{CONTROLLED_IDENTITY_DOMAIN}"
    ):
        return True
    if any(
        normalized == domain or normalized.endswith(f".{domain}")
        for domain in RESERVED_IDENTITY_DOMAINS
    ):
        return True
    return normalized.endswith(RESERVED_IDENTITY_SUFFIXES)


def _identity_field_kind(key: str) -> str | None:
    normalized = key.lower()
    if (
        normalized == "email"
        or normalized.endswith("_email")
        or normalized.endswith("_emails")
    ):
        return "email"
    if (
        normalized == "phone"
        or normalized.endswith("_phone")
        or normalized.endswith("_phone_number")
    ):
        return "phone"
    if normalized == "phone_numbers" or normalized.endswith("_phone_numbers"):
        return "phone"
    return None


def _validate_seeded_identity_document(document: Any, *, path: str) -> None:
    """Reject real-world contact identities anywhere in one scoped fixture."""

    def visit(value: Any, *, value_path: str, field_kind: str | None = None) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                visit(
                    child,
                    value_path=f"{value_path}.{key}",
                    field_kind=_identity_field_kind(str(key)),
                )
            return
        if isinstance(value, (list, tuple)):
            for index, child in enumerate(value):
                visit(
                    child,
                    value_path=f"{value_path}[{index}]",
                    field_kind=field_kind,
                )
            return
        if value is None or isinstance(value, (bool, int, float)):
            return
        if not isinstance(value, str):
            return

        normalized = value.strip()
        if not normalized:
            return
        if field_kind == "phone":
            digits = re.sub(r"\D", "", normalized)
            _require(
                RESERVED_FICTIONAL_PHONE_PATTERN.fullmatch(digits) is not None,
                f"{value_path} must use the NANP reserved fictional 555-0100 "
                f"through 555-0199 range; got {value!r}",
            )

        looks_like_email = field_kind == "email" or (
            normalized.count("@") == 1
            and " " not in normalized
            and not normalized.startswith(("http://", "https://"))
        )
        if looks_like_email:
            local_part, separator, domain = normalized.rpartition("@")
            _require(
                bool(local_part and separator and _identity_hostname_is_safe(domain)),
                f"{value_path} email must use a controlled or reserved fictional "
                f"domain; got {value!r}",
            )

        if normalized.startswith(("http://", "https://")):
            hostname = urlparse(normalized).hostname or ""
            _require(
                _identity_hostname_is_safe(hostname),
                f"{value_path} hostname must use a controlled or reserved fictional "
                f"domain; got {value!r}",
            )

    visit(document, value_path=path)


def _validate_vendor_contract_activity_api_shape(
    activity: dict[str, Any],
) -> VendorContractActivityItem:
    """Validate one stored activity through the endpoint response schema."""

    payload = {
        **activity,
        "id": str(activity.get("_id") or activity.get("id") or ""),
        "contract_id": str(activity.get("contract_id") or ""),
        "root_contract_id": str(activity.get("root_contract_id") or ""),
    }
    try:
        return VendorContractActivityItem.model_validate(payload)
    except ValidationError as exc:
        raise RuntimeError(
            f"Seeded contract activity is not API-compatible: {payload['id']}: {exc}"
        ) from exc


def _login(backend_url: str, endpoint: str, email: str, password: str) -> None:
    try:
        response = requests.post(
            f"{backend_url}{endpoint}",
            json={"email": email, "password": password},
            timeout=15,
        )
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Dedicated showcase login endpoint is unreachable: {endpoint}: {exc}"
        ) from exc
    if response.status_code != 200:
        raise RuntimeError(
            f"Dedicated showcase login failed for {email}: "
            f"HTTP {response.status_code} {response.text[:240]}"
        )


def verify_seeded_workspace(
    database: Database,
    *,
    kb_count_before: int,
    backend_url: str,
) -> dict[str, int]:
    """Prove domain completeness, isolation, visible identity, and auth."""

    minimum_counts = {
        "users": 2,
        "user_subscriptions": 1,
        "team_members": 1,
        "weddings": 2,
        "couple_users": 1,
        "couple_messages": 3,
        "guests": 24,
        "rsvps": 12,
        "plus_ones": 1,
        "tables": 6,
        "seating_layouts": 1,
        "planner_tasks": 4,
        "inbound_emails": 1,
        "email_logs": 1,
        "support_tickets": 2,
        "vendor_profiles": 6,
        "vendor_assignments": 6,
        "vendor_contracts": 4,
        "vendor_contract_activities": 4,
        "vendor_payment_milestones": 4,
        "vendor_quotes": 3,
        "budget_categories": 4,
        "payment_records": 1,
        "contracts": 1,
        "scheduled_payments": 3,
        "packages": 3,
        "forms": 2,
        "form_responses": 1,
        "form_distributions": 1,
        "form_submissions": 1,
        "guest_media_assets": 7,
        "gallery": 3,
        "ai_cache": 2,
        "kb_articles": 1,
    }
    counts: dict[str, int] = {}
    for collection_name, minimum in minimum_counts.items():
        count = database[collection_name].count_documents(
            {"seed_source": SEED_SOURCE, "seed_scope": SEED_SCOPE}
        )
        counts[collection_name] = count
        _require(
            count >= minimum,
            f"{collection_name} has {count} capture fixtures; expected at least {minimum}",
        )

    for collection_name in database.list_collection_names():
        unscoped = database[collection_name].count_documents(
            {"seed_source": SEED_SOURCE, "seed_scope": {"$ne": SEED_SCOPE}},
            limit=1,
        )
        _require(
            unscoped == 0,
            f"{collection_name} contains marketing-capture fixtures without seed_scope",
        )

    capture_owner = {"seed_source": SEED_SOURCE, "seed_scope": SEED_SCOPE}
    for collection_name in database.list_collection_names():
        for document in database[collection_name].find(capture_owner):
            _validate_seeded_identity_document(
                document,
                path=f"{collection_name}/{document.get('_id', '<missing-id>')}",
            )

    contract_ids = {
        str(contract["_id"])
        for contract in database["vendor_contracts"].find(
            {"seed_source": SEED_SOURCE, "seed_scope": SEED_SCOPE}, {"_id": 1}
        )
    }
    contract_activities = [
        _validate_vendor_contract_activity_api_shape(activity)
        for activity in database["vendor_contract_activities"].find(
            {"seed_source": SEED_SOURCE, "seed_scope": SEED_SCOPE}
        )
    ]
    _require(
        all(
            item.contract_id in contract_ids
            and item.root_contract_id == item.contract_id
            for item in contract_activities
        ),
        "Seeded contract activity ownership does not match an original seeded contract",
    )
    _require(
        {item.activity_type for item in contract_activities}
        == {
            VendorContractActivityType.CONTRACT_CREATED,
            VendorContractActivityType.CONTRACT_SENT,
            VendorContractActivityType.CONTRACT_VIEWED,
            VendorContractActivityType.CONTRACT_SIGNED,
        },
        "Seeded contract activities do not cover the production lifecycle states",
    )

    planner = database["users"].find_one({"email": PLANNER_EMAIL})
    _require(planner is not None, "Dedicated showcase planner is missing")
    _require(
        planner.get("first_name") == "Amina"
        and planner.get("last_name") == "Cole"
        and planner.get("company_name") == "Marigold & Co. Weddings",
        "Planner identity does not match the approved showcase world",
    )

    team = database["team_members"].find_one({"email": TEAM_EMAIL})
    _require(
        team is not None
        and team.get("status") == "active"
        and bool(team.get("user_id")),
        "Accepted team-member linkage is incomplete",
    )
    couple = database["couple_users"].find_one({"email": COUPLE_EMAIL})
    _require(
        couple is not None
        and couple.get("setup_completed") is True
        and couple.get("is_active") is True,
        "Sofia & Daniel couple login is incomplete",
    )

    wedding = database["weddings"].find_one({"_id": PRIMARY_WEDDING_ID})
    _require(wedding is not None, "Primary showcase wedding is missing")
    _require(
        wedding.get("couple_names") == "Sofia & Daniel"
        and wedding.get("our_story")
        and len(wedding.get("wedding_party") or []) >= 2
        and wedding.get("public_site_url")
        == "https://www.thespecialwedding.io/sofia-and-daniel",
        "Public microsite fixture is not capture-ready",
    )
    _require(
        (wedding.get("rsvp_config") or {}).get("phone_numbers")
        == ["(312) 555-0142", "(312) 555-0168"]
        and (wedding.get("rsvp_config") or {}).get("hide_phone_numbers") is True,
        "RSVP support contacts must use the approved fictional capture identity",
    )
    layout = database["seating_layouts"].find_one({"wedding_id": PRIMARY_WEDDING_ID})
    _require(
        layout is not None
        and str(layout.get("background_image_data_url") or "").startswith(
            "data:image/svg+xml;base64,"
        )
        and len(layout.get("fixtures") or []) >= 4,
        "Venue floorplan/background fixture is incomplete",
    )
    gallery_items = list(
        database["gallery"].find(
            {
                "wedding_id": PRIMARY_WEDDING_ID,
                "approved_for_marketing": True,
                "is_public": True,
            }
        )
    )
    _require(
        len(gallery_items) >= 3
        and all(
            str(item.get("key") or "").startswith("gallery/sofia-and-daniel/20270125-")
            and "marketing-capture" not in str(item.get("key") or "")
            for item in gallery_items
        ),
        "Approved gallery metadata is incomplete",
    )
    for asset_name in (
        "elegant-couple-stairs.svg",
        "elegant-ceremony-aisle.svg",
        "elegant-reception-table.svg",
    ):
        _require(
            (ROOT / "public" / "demo-gallery" / asset_name).is_file(),
            f"Approved repository gallery asset is missing: {asset_name}",
        )
    _require(
        database["guests"].count_documents(
            {
                "wedding_id": PRIMARY_WEDDING_ID,
                "household_id": {"$exists": True, "$ne": ""},
            }
        )
        >= 12,
        "Guest household examples are incomplete",
    )
    _require(
        database["guests"].count_documents(
            {
                "wedding_id": PRIMARY_WEDDING_ID,
                "accessibility_needs": {"$exists": True, "$ne": None},
            }
        )
        >= 1,
        "Guest accessibility examples are incomplete",
    )
    _require(
        database["rsvps"].count_documents(
            {
                "wedding_id": PRIMARY_WEDDING_ID,
                "dietary": {"$exists": True, "$ne": None},
            }
        )
        >= 3,
        "Guest meal examples are incomplete",
    )
    _require(
        database["scheduled_payments"].count_documents(
            {
                "seed_source": SEED_SOURCE,
                "seed_scope": SEED_SCOPE,
                "status": "failed",
                "retry_count": {"$gte": 1},
            }
        )
        >= 1,
        "Payment failure/retry fixture is incomplete",
    )
    _require(
        database["budget_categories"].count_documents(
            {
                "seed_source": SEED_SOURCE,
                "seed_scope": SEED_SCOPE,
                "$expr": {"$gt": ["$actual_spent", "$budgeted_amount"]},
            }
        )
        >= 1,
        "Budget overrun fixture is incomplete",
    )
    for category in database["budget_categories"].find(
        {"seed_source": SEED_SOURCE, "seed_scope": SEED_SCOPE},
        {"_id": 1, "actual_spent": 1},
    ):
        payment_total = sum(
            float(payment.get("amount") or 0)
            for payment in database["payment_records"].find(
                {
                    "seed_source": SEED_SOURCE,
                    "seed_scope": SEED_SCOPE,
                    "category_id": str(category["_id"]),
                },
                {"amount": 1},
            )
        )
        _require(
            abs(payment_total - float(category.get("actual_spent") or 0)) < 0.01,
            f"Budget category {category['_id']} does not reconcile to payment records",
        )
    budget_insight = database["ai_cache"].find_one(
        {
            "seed_source": SEED_SOURCE,
            "seed_scope": SEED_SCOPE,
            "feature": "budget_insights",
        }
    )
    _require(
        budget_insight is not None
        and "$45,800"
        in str((budget_insight.get("response") or {}).get("summary") or ""),
        "Budget insight does not agree with the reconciled fixture totals",
    )
    kb_article = database["kb_articles"].find_one(
        {
            "_id": DEMO_KB_ARTICLE_ID,
            "slug": DEMO_KB_ARTICLE_SLUG,
            "status": "published",
            "seed_source": SEED_SOURCE,
            "seed_scope": SEED_SCOPE,
        }
    )
    _require(
        kb_article is not None
        and kb_article.get("title") == "Planner Command Center: Your First 30 Minutes"
        and len(str(kb_article.get("content") or "")) >= 50,
        "Published showcase Knowledge Base article is incomplete",
    )
    _require(
        database["kb_articles"].count_documents({}) == kb_count_before + 1,
        "Marketing capture must add only its isolated Knowledge Base article",
    )

    _login(backend_url, "/admin/token", PLANNER_EMAIL, PLANNER_PASSWORD)
    _login(backend_url, "/admin/token", TEAM_EMAIL, TEAM_PASSWORD)
    _login(backend_url, "/couple/login", COUPLE_EMAIL, COUPLE_PASSWORD)
    try:
        public_response = requests.get(
            f"{backend_url}/weddings/slug/{PRIMARY_SLUG}", timeout=15
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Public showcase route is unreachable: {exc}") from exc
    _require(
        public_response.status_code == 200,
        f"Public showcase wedding returned HTTP {public_response.status_code}",
    )
    try:
        kb_response = requests.get(
            f"{backend_url}/public/kb/articles/slug/{DEMO_KB_ARTICLE_SLUG}",
            timeout=15,
        )
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Published showcase Knowledge Base route is unreachable: {exc}"
        ) from exc
    _require(
        kb_response.status_code == 200
        and kb_response.json().get("slug") == DEMO_KB_ARTICLE_SLUG,
        "Published showcase Knowledge Base article is not publicly readable",
    )
    return counts


MARKETING_CAPTURE_E2E_CHECKPOINTS = (
    (
        "Planner command center",
        "/admin/planner",
        "Amina Cole sees Marigold & Co. Weddings with two realistic weddings and populated metrics.",
    ),
    (
        "Unified inbox",
        "/admin/communications/inbox",
        "Email, Sofia & Daniel messages, SMS help, and support threads are visibly distinct.",
    ),
    (
        "Wedding workspace",
        f"/admin/weddings/{PRIMARY_WEDDING_ID}",
        "Story, wedding party, events, approved imagery, and planner notes are complete.",
    ),
    (
        "Venue and seating",
        f"/admin/seating?weddingId={PRIMARY_WEDDING_ID}",
        "Approved venue floorplan, fixtures, tables, and assigned guests render without local-only labels.",
    ),
    (
        "Couple portal",
        "/couple/dashboard",
        "Sofia & Daniel see forms, messages, meetings, payments, and guest memories.",
    ),
    (
        "Public microsite",
        f"/{PRIMARY_SLUG}",
        "The public showcase uses approved fictional media on www.thespecialwedding.io.",
    ),
)


def verify_frontend_checkpoint_routes(frontend_url: str) -> None:
    origin = frontend_url.rstrip("/")
    for title, route, _expectation in MARKETING_CAPTURE_E2E_CHECKPOINTS:
        url = f"{origin}{route}"
        try:
            response = requests.get(url, timeout=15, allow_redirects=True)
        except requests.RequestException as exc:
            raise RuntimeError(
                f"Frontend checkpoint is unreachable ({title}): {exc}"
            ) from exc
        _require(
            200 <= response.status_code < 400,
            f"Frontend checkpoint returned HTTP {response.status_code}: {url}",
        )


def _non_interactive() -> bool:
    return os.getenv("TESTBED_NON_INTERACTIVE", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _seed_environment(anchor_at: str) -> dict[str, str]:
    primary_date = "2027-01-25"

    env = dict(os.environ)
    env.update(
        {
            "ENVIRONMENT": "development",
            "MARKETING_CAPTURE_ANCHOR_AT": anchor_at,
            "MARKETING_CAPTURE_PLANNER_EMAIL": PLANNER_EMAIL,
            "MARKETING_CAPTURE_TEAM_PASSWORD": TEAM_PASSWORD,
            "SMOKE_PLANNER_EMAIL": PLANNER_EMAIL,
            "SMOKE_PLANNER_PASSWORD": PLANNER_PASSWORD,
            "SMOKE_PLANNER_COMPANY_NAME": "Marigold & Co. Weddings",
            "SMOKE_PLANNER_FIRST_NAME": "Amina",
            "SMOKE_PLANNER_LAST_NAME": "Cole",
            "SMOKE_PLANNER_USER_ID": PLANNER_USER_ID,
            "SMOKE_PLANNER_PLAN_ID": "plan_signature",
            "SMOKE_WEDDING_ID": PRIMARY_WEDDING_ID,
            "SMOKE_PUBLIC_WEDDING_SLUG": PRIMARY_SLUG,
            "SMOKE_WEDDING_COUPLE_NAMES": "Sofia & Daniel",
            "SMOKE_WEDDING_DATE": primary_date,
            "DEMO_VIDEO_PRIMARY_DATE": primary_date,
            "DEMO_VIDEO_SECONDARY_DATE": "2027-07-06",
            "SMOKE_COUPLE_EMAIL": COUPLE_EMAIL,
            "SMOKE_COUPLE_PASSWORD": COUPLE_PASSWORD,
            "SMOKE_COUPLE_PARTNER1_NAME": "Sofia",
            "SMOKE_COUPLE_PARTNER2_NAME": "Daniel",
            "SMOKE_COUPLE_ID": COUPLE_ID,
        }
    )
    return env


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the isolated Phase 1 marketing-capture workspace"
    )
    parser.add_argument(
        "--anchor-at",
        default=os.getenv("MARKETING_CAPTURE_ANCHOR_AT", DEFAULT_ANCHOR_AT),
        help="ISO-8601 capture anchor; naive values use America/Chicago.",
    )
    parser.add_argument(
        "--backend-url",
        default=os.getenv(
            "MARKETING_CAPTURE_BACKEND_URL",
            os.getenv("BACKEND_URL", "http://127.0.0.1:8000"),
        ),
        help="Backend origin used for dedicated planner, team, couple, and public-route checks.",
    )
    parser.add_argument(
        "--frontend-url",
        default=os.getenv("MARKETING_CAPTURE_FRONTEND_URL", "http://127.0.0.1:3100"),
        help="Production-like frontend origin used for the manual browser checkpoints.",
    )
    args = parser.parse_args()

    client, database = _load_database()
    try:
        print("[RESET] Removing the prior isolated capture workspace")
        cleanup_marketing_capture_workspace_state(database)
        kb_count_before = database["kb_articles"].count_documents({})
        assert_setup_namespace_available(database)

        env = _seed_environment(args.anchor_at)
        print("[SEED] Creating the dedicated planner and couple identities")
        _run_python(SETUP_SMOKE_ACCOUNTS, env=env)
        print("[SEED] Enriching the production-shaped fictional workspace")
        _run_python(
            RICH_WORKSPACE_SEEDER,
            env=env,
            args=[
                "--planner-email",
                PLANNER_EMAIL,
                "--anchor-at",
                args.anchor_at,
            ],
        )

        backend_url = args.backend_url.rstrip("/")
        counts = verify_seeded_workspace(
            database,
            kb_count_before=kb_count_before,
            backend_url=backend_url,
        )
        print(
            "[OK] Marketing capture workspace verified: "
            + ", ".join(f"{name}={count}" for name, count in sorted(counts.items()))
        )
    finally:
        client.close()

    frontend_url = args.frontend_url.rstrip("/")
    verify_frontend_checkpoint_routes(frontend_url)
    for title, route, expectation in MARKETING_CAPTURE_E2E_CHECKPOINTS:
        print(
            f"\nCHECKPOINT — {title}\n  URL: {frontend_url}{route}\n  Expect: {expectation}"
        )
        if not _non_interactive():
            input("Press ENTER after verifying this checkpoint in the browser… ")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"\n[FAIL] Marketing capture verification aborted: {exc}\n")
        raise SystemExit(1)
