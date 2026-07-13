#!/usr/bin/env python3
"""Reset, seed, verify, and expose browser checks for Phase 1 captures."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import requests
from pymongo.database import Database

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from testbed.cleanup_marketing_capture_workspace_state import (  # noqa: E402
    SEED_SCOPE,
    SEED_SOURCE,
    _load_database,
    cleanup_marketing_capture_workspace_state,
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


def _run_python(
    script: Path, *, env: dict[str, str], args: list[str] | None = None
) -> None:
    command = [sys.executable, str(script), *(args or [])]
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def _require(condition: Any, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


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
        and str(wedding.get("public_site_url") or "").startswith(
            "https://www.thespecialwedding.io"
        ),
        "Public microsite fixture is not capture-ready",
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
    _require(
        database["gallery"].count_documents(
            {
                "wedding_id": PRIMARY_WEDDING_ID,
                "approved_for_marketing": True,
                "is_public": True,
            }
        )
        >= 3,
        "Approved gallery metadata is incomplete",
    )
    _require(
        database["kb_articles"].count_documents({}) == kb_count_before,
        "Marketing capture must not insert or delete global knowledge-base articles",
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
        f"/admin/weddings/{PRIMARY_WEDDING_ID}/seating",
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
    args = parser.parse_args()

    client, database = _load_database()
    try:
        kb_count_before = database["kb_articles"].count_documents({})
        print("[RESET] Removing the prior isolated capture workspace")
        cleanup_marketing_capture_workspace_state(database)

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

        backend_url = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
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

    frontend_url = os.getenv("FRONTEND_URL", "http://127.0.0.1:3100").rstrip("/")
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
