#!/usr/bin/env python3
"""Seed a richer local workspace for publishable demo-video captures.

This script intentionally complements, rather than replaces,
``scripts/setup_smoke_accounts.py``. The smoke seeder creates login identities
and a public wedding. This script adds realistic but disposable product data so
browser recordings show a living planner workspace instead of an empty shell.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from bson import ObjectId

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.constants.seed_sources import (  # noqa: E402
    LEGACY_SMOKE_SEED_SCOPE,
    MARKETING_CAPTURE_SEED_SCOPE,
    MARKETING_CAPTURE_SEED_SOURCE,
    SMOKE_ACCOUNT_SEED_SOURCE,
)
from app.constants.marketing_capture_media import (  # noqa: E402
    MARKETING_CAPTURE_GALLERY_ITEMS,
)
from testbed._marketing_capture_seed_ownership import (  # noqa: E402
    replace_scoped_document,
)

MARKETING_CAPTURE_TIMEZONE_NAME = "America/Chicago"
MARKETING_CAPTURE_TIMEZONE = ZoneInfo(MARKETING_CAPTURE_TIMEZONE_NAME)
MARKETING_CAPTURE_PLANNER_EMAIL = "amina@studio.thespecialwedding.io"
MARKETING_CAPTURE_PLANNER_USER_ID = "user_marketing_capture_amina_cole"
MARKETING_CAPTURE_TEAM_EMAIL = "maya@studio.thespecialwedding.io"
MARKETING_CAPTURE_TEAM_PASSWORD = "CaptureTeam2026!"
MARKETING_CAPTURE_COMPANY = "Marigold & Co. Weddings"
MARKETING_CAPTURE_PLANNER_FIRST_NAME = "Amina"
MARKETING_CAPTURE_PLANNER_LAST_NAME = "Cole"
MARKETING_CAPTURE_PUBLIC_ORIGIN = "https://www.thespecialwedding.io"
MARKETING_CAPTURE_VENDOR_ORIGIN = "https://vendors.thespecialwedding.io"
DEFAULT_CAPTURE_ANCHOR_LOCAL = "2026-07-12T10:00:00"
DEFAULT_PRIMARY_WEDDING_ID = "wedding_marketing_capture_sofia_daniel"
DEFAULT_PRIMARY_SLUG = "sofia-and-daniel"
DEFAULT_PRIMARY_DATE = "2027-01-25"
DEFAULT_PRIMARY_COUPLE_NAMES = "Sofia & Daniel"
DEFAULT_PRIMARY_PARTNER1_NAME = "Sofia"
DEFAULT_PRIMARY_PARTNER2_NAME = "Daniel"
DEMO_COUPLE_ID = "couple_marketing_capture_sofia_daniel"
DEMO_COUPLE_EMAIL = "sofia.daniel@couples.thespecialwedding.io"
DEMO_COUPLE_PASSWORD = "CaptureCouple2026!"
DEFAULT_SECONDARY_WEDDING_ID = "wedding_marketing_capture_avery_morgan"
DEFAULT_SECONDARY_SLUG = "avery-and-morgan"
DEFAULT_SECONDARY_DATE = "2027-07-06"
DEFAULT_SECONDARY_COUPLE_NAMES = "Avery & Morgan"
NON_PRODUCTION_ENVIRONMENTS = {"development", "dev", "local", "test", "testing", "ci"}
DEMO_SUBSCRIPTION_ID = "marketing_capture_signature_subscription"
DEMO_PLAN_ID = "plan_signature"
DEMO_PUBLIC_FORM_ID = "form_marketing_capture_couple_intake"
DEMO_COUPLE_FORM_ID = "67c200000000000000000001"
DEMO_KB_ARTICLE_ID = "67c900000000000000000001"
DEMO_KB_ARTICLE_SLUG = "planner-command-center-first-steps"
DEMO_VENDOR_CONTRACT_ID = "67c100000000000000000001"
DEMO_VENDOR_CONTRACT_TOKEN = "marketing-capture-vendor-contract-token"
DEMO_VENDOR_PROFILE_ID = "67c400000000000000000001"
DEMO_VENDOR_ASSIGNMENT_ID = "67c400000000000000000101"
DEMO_VENDOR_BUSINESS_NAME = "Luna Meridian Photography"
DEMO_VENDOR_PUBLIC_SEARCH_TERM = "Luna Meridian"
DEMO_VENDOR_EMAIL = "hello.luna-meridian@vendors.thespecialwedding.io"
DEMO_VENDOR_DIRECTORY_FIXTURES = [
    {
        "profile_id": DEMO_VENDOR_PROFILE_ID,
        "assignment_id": DEMO_VENDOR_ASSIGNMENT_ID,
        "contract_id": DEMO_VENDOR_CONTRACT_ID,
        "token": DEMO_VENDOR_CONTRACT_TOKEN,
        "business_name": DEMO_VENDOR_BUSINESS_NAME,
        "contact_name": "Elena Rivera",
        "email": DEMO_VENDOR_EMAIL,
        "phone": "(312) 555-0131",
        "website": f"{MARKETING_CAPTURE_VENDOR_ORIGIN}/luna-meridian-photography",
        "service_category": "photographer",
        "service_subcategories": [
            "Wedding photography",
            "Second shooter",
            "Engagement session",
        ],
        "service_description": "Editorial wedding photography with timeline review, family-shot planning, and a six-week gallery delivery window.",
        "typical_price_min": 5200,
        "typical_price_max": 7800,
        "budget_category_id": "budget_marketing_capture_photo",
        "status": "contracted",
        "quoted_amount": 6800.0,
        "contracted_amount": 6800.0,
        "paid_amount": 1700.0,
        "contract_title": "Photography Services Agreement",
        "contract_number": "MCW-2027-001",
        "contract_status": "sent",
        "deposit_amount": 1700,
        "city": "Chicago",
        "state": "IL",
    },
    {
        "profile_id": "67c400000000000000000002",
        "assignment_id": "67c400000000000000000102",
        "contract_id": "67c100000000000000000002",
        "token": "marketing-capture-vendor-contract-token-floral",
        "business_name": "Ever After Floral Studio",
        "contact_name": "Nadia Blake",
        "email": "ever.after@vendors.thespecialwedding.io",
        "phone": "(312) 555-0132",
        "website": f"{MARKETING_CAPTURE_VENDOR_ORIGIN}/ever-after-floral-studio",
        "service_category": "decorator",
        "service_subcategories": [
            "Floral design",
            "Reception installation",
            "Ceremony backdrop",
        ],
        "service_description": "Full floral and decor production with ceremony installation, reception flip, and strike crew.",
        "typical_price_min": 8500,
        "typical_price_max": 14000,
        "budget_category_id": "budget_marketing_capture_guest_experience",
        "status": "confirmed",
        "quoted_amount": 9200.0,
        "contracted_amount": 9200.0,
        "paid_amount": 3000.0,
        "contract_title": "Floral & Decor Production Agreement",
        "contract_number": "MCW-2027-002",
        "contract_status": "signed",
        "deposit_amount": 3000,
        "city": "Chicago",
        "state": "IL",
    },
    {
        "profile_id": "67c400000000000000000003",
        "assignment_id": "67c400000000000000000103",
        "contract_id": "67c100000000000000000003",
        "token": "marketing-capture-vendor-contract-token-mc",
        "business_name": "Elton Mensah MC Services",
        "contact_name": "Elton Mensah",
        "email": "elton.mensah@vendors.thespecialwedding.io",
        "phone": "(405) 555-0133",
        "website": f"{MARKETING_CAPTURE_VENDOR_ORIGIN}/elton-mensah-mc-services",
        "service_category": "mc",
        "service_subcategories": [
            "Reception hosting",
            "Program flow",
            "Family introductions",
        ],
        "service_description": "Master of ceremonies for reception entrances, cultural program flow, and guest engagement.",
        "typical_price_min": 1200,
        "typical_price_max": 2500,
        "budget_category_id": "budget_marketing_capture_planning",
        "status": "contracted",
        "quoted_amount": 1500.0,
        "contracted_amount": 1500.0,
        "paid_amount": 500.0,
        "contract_title": "Master of Ceremonies Agreement",
        "contract_number": "MCW-2027-003",
        "contract_status": "viewed",
        "deposit_amount": 500,
        "city": "Oklahoma City",
        "state": "OK",
    },
    {
        "profile_id": "67c400000000000000000004",
        "assignment_id": "67c400000000000000000104",
        "contract_id": "67c100000000000000000004",
        "token": "marketing-capture-vendor-contract-token-venue",
        "business_name": "The Glasshouse at Riverbend",
        "contact_name": "Marisol Chen",
        "email": "glasshouse@vendors.thespecialwedding.io",
        "phone": "(405) 555-0134",
        "website": f"{MARKETING_CAPTURE_VENDOR_ORIGIN}/glasshouse-riverbend",
        "service_category": "venue",
        "service_subcategories": ["Reception venue", "Ceremony garden", "In-house bar"],
        "service_description": "Modern garden venue with ceremony lawn, reception hall, and private wedding-suite access.",
        "typical_price_min": 30000,
        "typical_price_max": 48000,
        "budget_category_id": "budget_marketing_capture_venue",
        "status": "quoted",
        "quoted_amount": 42000.0,
        "contracted_amount": 42000.0,
        "paid_amount": 12000.0,
        "contract_title": "Venue Rental & Bar Service Agreement",
        "contract_number": "MCW-2027-004",
        "contract_status": "draft",
        "deposit_amount": 12000,
        "city": "Oklahoma City",
        "state": "OK",
    },
    {
        "profile_id": "67c400000000000000000005",
        "assignment_id": "67c400000000000000000105",
        "business_name": "Harvest Table Catering",
        "contact_name": "Priya Shah",
        "email": "harvest.table@vendors.thespecialwedding.io",
        "phone": "(918) 555-0135",
        "website": f"{MARKETING_CAPTURE_VENDOR_ORIGIN}/harvest-table-catering",
        "service_category": "caterer",
        "service_subcategories": [
            "Dinner service",
            "Cocktail hour",
            "Late-night bites",
        ],
        "service_description": "Seasonal plated dinner service with cocktail-hour bites and late-night snack station.",
        "typical_price_min": 15000,
        "typical_price_max": 28000,
        "budget_category_id": "budget_marketing_capture_venue",
        "status": "confirmed",
        "quoted_amount": 18000.0,
        "contracted_amount": 18000.0,
        "paid_amount": 6000.0,
        "city": "Tulsa",
        "state": "OK",
    },
    {
        "profile_id": "67c400000000000000000006",
        "assignment_id": "67c400000000000000000106",
        "business_name": "Atlas Coach",
        "contact_name": "Marcus Hill",
        "email": "atlas.coach@vendors.thespecialwedding.io",
        "phone": "(405) 555-0136",
        "website": f"{MARKETING_CAPTURE_VENDOR_ORIGIN}/atlas-coach",
        "service_category": "transportation",
        "service_subcategories": [
            "Guest shuttle",
            "Hotel pickup",
            "Late-night return route",
        ],
        "service_description": "Guest transportation provider for hotel-to-venue shuttles and late-night return routes.",
        "typical_price_min": 2800,
        "typical_price_max": 5200,
        "budget_category_id": "budget_marketing_capture_guest_experience",
        "status": "quoted",
        "quoted_amount": 4600.0,
        "contracted_amount": 4600.0,
        "paid_amount": 2000.0,
        "city": "Oklahoma City",
        "state": "OK",
    },
]
DEMO_CLIENT_CONTRACT_ID = "67c300000000000000000001"
DEMO_CLIENT_PORTAL_TOKEN = "marketing-capture-contract-payment-portal-token"
DEMO_SEATING_TABLE_IDS = {
    "head": "67c600000000000000000001",
    "friends": "67c600000000000000000002",
    "family": "67c600000000000000000003",
    "couple_friends": "67c600000000000000000004",
    "extended_family": "67c600000000000000000005",
    "vendor": "67c600000000000000000006",
}
DEMO_SEATING_LAYOUT_ID = "67c600000000000000000101"
MARKETING_CAPTURE_TEAM_MEMBER_ID = ObjectId("67c700000000000000000001")
MARKETING_CAPTURE_TEAM_USER_ID = ObjectId("67c700000000000000000002")
MARKETING_CAPTURE_GALLERY_ASSETS = [
    {
        **fixture,
        "_id": ObjectId(f"67c80000000000000000000{index}"),
        "approved_for_marketing": True,
    }
    for index, fixture in enumerate(MARKETING_CAPTURE_GALLERY_ITEMS, start=1)
]
_VENUE_PLAN_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1000" viewBox="0 0 1600 1000"><rect width="1600" height="1000" fill="#f7f4ef"/><rect x="80" y="80" width="1440" height="840" rx="24" fill="#fffdf9" stroke="#9a8f80" stroke-width="8"/><path d="M620 80h360v130H620z" fill="#e8dfd2"/><text x="800" y="155" text-anchor="middle" font-family="Arial" font-size="34" fill="#4a4038">Ceremony stage</text><path d="M660 430h280v190H660z" fill="#ead3cf"/><text x="800" y="530" text-anchor="middle" font-family="Arial" font-size="30" fill="#6f3f3a">Dance floor</text><path d="M80 760h120v160H80z" fill="#d9e6de"/><text x="140" y="845" text-anchor="middle" font-family="Arial" font-size="22" fill="#315a46">Entry</text></svg>"""
MARKETING_CAPTURE_VENUE_BACKGROUND = "data:image/svg+xml;base64," + base64.b64encode(
    _VENUE_PLAN_SVG.encode("utf-8")
).decode("ascii")

_CAPTURE_ANCHOR_UTC: datetime | None = None


def _configure_anchor(anchor_at: str) -> datetime:
    """Pin every fixture timestamp to one injectable Chicago wall-clock instant."""

    raw = str(anchor_at or "").strip()
    if not raw:
        raise RuntimeError("--anchor-at is required for deterministic capture data")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RuntimeError(
            "--anchor-at must be an ISO-8601 datetime, for example 2026-07-12T10:00:00"
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=MARKETING_CAPTURE_TIMEZONE)
    return parsed.astimezone(timezone.utc)


def _utc_now() -> datetime:
    return _CAPTURE_ANCHOR_UTC or datetime.now(timezone.utc)


def _date_from_now(days: int) -> str:
    return (_utc_now() + timedelta(days=days)).date().isoformat()


def _stock_demo_media_allowed(
    *,
    couple_names: str | None = None,
    partner1_name: str | None = None,
    partner2_name: str | None = None,
    slug: str | None = None,
) -> bool:
    del couple_names, partner1_name, partner2_name, slug
    return True


def _demo_featured_image(
    *,
    ready: bool,
    couple_names: str | None,
    partner1_name: str | None,
    partner2_name: str | None,
    slug: str | None,
) -> str | None:
    if not ready:
        return None
    del couple_names, partner1_name, partner2_name, slug
    return MARKETING_CAPTURE_GALLERY_ASSETS[0]["url"]


def _planner_email(args: argparse.Namespace) -> str:
    email = (
        (
            args.planner_email
            or os.getenv("MARKETING_CAPTURE_PLANNER_EMAIL")
            or os.getenv("SMOKE_PLANNER_EMAIL")
            or MARKETING_CAPTURE_PLANNER_EMAIL
        )
        .strip()
        .lower()
    )
    if email != MARKETING_CAPTURE_PLANNER_EMAIL:
        raise RuntimeError(
            "Refusing to rebrand an arbitrary planner or existing owner. "
            f"Marketing capture requires {MARKETING_CAPTURE_PLANNER_EMAIL}."
        )
    return email


def _demo_env(name: str, default: str) -> str:
    """Read demo-video-specific env without inheriting generic smoke wedding values."""

    return os.getenv(f"DEMO_VIDEO_{name}", default)


def _assert_demo_seed_allowed(args: argparse.Namespace) -> None:
    del args
    environment = (
        os.getenv("ENVIRONMENT", os.getenv("NODE_ENV", "development")).strip().lower()
    )
    if environment not in NON_PRODUCTION_ENVIRONMENTS:
        raise RuntimeError(
            "Refusing to seed marketing-capture data outside a local/test environment. "
            f"Current ENVIRONMENT/NODE_ENV is {environment!r}."
        )

    mongo_uri = (os.getenv("MONGO_URI") or os.getenv("MONGODB_URI") or "").strip()
    if not mongo_uri:
        raise RuntimeError(
            "MONGO_URI is required so local-only database safety can be verified"
        )
    parsed = urlparse(mongo_uri)
    allowed_hosts = {"localhost", "127.0.0.1", "::1", "mongo", "mongodb"}
    if parsed.scheme == "mongodb+srv" or parsed.hostname not in allowed_hosts:
        raise RuntimeError(
            "Refusing to seed marketing-capture data into a non-local Mongo database"
        )


async def _load_planner(planner_email: str) -> dict[str, Any]:
    from app.core.database import mongo

    planner = await mongo.get_users_collection().find_one({"email": planner_email})
    if not planner:
        raise RuntimeError(
            f"No planner found for {planner_email}. Run scripts/setup_smoke_accounts.py first."
        )
    if planner.get("role") != "wedding_planner":
        raise RuntimeError(f"{planner_email} is not a wedding_planner account.")
    if str(planner.get("_id") or "") != MARKETING_CAPTURE_PLANNER_USER_ID:
        raise RuntimeError(
            "The marketing-capture planner email is not attached to its fixed "
            "showcase identity."
        )
    ownership = (planner.get("seed_source"), planner.get("seed_scope"))
    if ownership not in {
        (SMOKE_ACCOUNT_SEED_SOURCE, LEGACY_SMOKE_SEED_SCOPE),
        (MARKETING_CAPTURE_SEED_SOURCE, MARKETING_CAPTURE_SEED_SCOPE),
    }:
        raise RuntimeError(
            "Refusing to take over an existing owner that was not created by the "
            "fixed smoke bootstrap or this exact marketing-capture scope."
        )
    return planner


async def _assert_capture_namespace_available(
    planner: dict[str, Any],
    *,
    primary_id: str,
    primary_slug: str,
    secondary_id: str,
    secondary_slug: str,
) -> None:
    """Fail closed before any write when deterministic capture IDs collide."""

    from app.core.database import mongo

    planner_id = str(planner["_id"])
    planner_email = str(planner["email"])
    for wedding_id, slug in (
        (primary_id, primary_slug),
        (secondary_id, secondary_slug),
    ):
        candidates = (
            await mongo.get_weddings_collection()
            .find({"$or": [{"_id": wedding_id}, {"slug": slug}]})
            .to_list(length=3)
        )
        for existing in candidates:
            owner_matches = (
                str(existing.get("assigned_planner_id") or "") == planner_id
                or str(existing.get("assigned_planner_email") or "").lower()
                == planner_email
            )
            ownership = (existing.get("seed_source"), existing.get("seed_scope"))
            canonical_owner = ownership == (
                MARKETING_CAPTURE_SEED_SOURCE,
                MARKETING_CAPTURE_SEED_SCOPE,
            )
            fixed_legacy_owner = (
                wedding_id == DEFAULT_PRIMARY_WEDDING_ID
                and slug == DEFAULT_PRIMARY_SLUG
                and str(existing.get("_id") or "") == DEFAULT_PRIMARY_WEDDING_ID
                and ownership == (SMOKE_ACCOUNT_SEED_SOURCE, LEGACY_SMOKE_SEED_SCOPE)
            )
            if not owner_matches or not (canonical_owner or fixed_legacy_owner):
                raise RuntimeError(
                    f"Wedding {wedding_id}/{slug} collides with an existing owner; "
                    "capture seeding stopped before mutation."
                )

    deterministic_ids: dict[str, list[Any]] = {
        "couple_users": [DEMO_COUPLE_ID],
        "team_members": [MARKETING_CAPTURE_TEAM_MEMBER_ID],
        "users": [MARKETING_CAPTURE_TEAM_USER_ID],
        "user_subscriptions": [DEMO_SUBSCRIPTION_ID],
        "seating_layouts": [ObjectId(DEMO_SEATING_LAYOUT_ID)],
        "contracts": [ObjectId(DEMO_CLIENT_CONTRACT_ID)],
        "kb_articles": [ObjectId(DEMO_KB_ARTICLE_ID)],
    }
    for collection_name, ids in deterministic_ids.items():
        async for existing in mongo.db[collection_name].find({"_id": {"$in": ids}}):
            ownership = (existing.get("seed_source"), existing.get("seed_scope"))
            canonical_owner = ownership == (
                MARKETING_CAPTURE_SEED_SOURCE,
                MARKETING_CAPTURE_SEED_SCOPE,
            )
            fixed_legacy_couple = (
                collection_name == "couple_users"
                and str(existing.get("_id") or "") == DEMO_COUPLE_ID
                and existing.get("email") == DEMO_COUPLE_EMAIL
                and ownership == (SMOKE_ACCOUNT_SEED_SOURCE, LEGACY_SMOKE_SEED_SCOPE)
            )
            if not (canonical_owner or fixed_legacy_couple):
                raise RuntimeError(
                    f"{collection_name} contains a deterministic capture ID owned by "
                    "an existing owner; capture seeding stopped before mutation."
                )

    kb_article_id = ObjectId(DEMO_KB_ARTICLE_ID)
    kb_candidates = (
        await mongo.db["kb_articles"]
        .find(
            {
                "$or": [
                    {"_id": kb_article_id},
                    {"slug": DEMO_KB_ARTICLE_SLUG},
                ]
            }
        )
        .to_list(length=3)
    )
    for existing in kb_candidates:
        if (
            existing.get("seed_source") != MARKETING_CAPTURE_SEED_SOURCE
            or existing.get("seed_scope") != MARKETING_CAPTURE_SEED_SCOPE
            or existing.get("_id") != kb_article_id
        ):
            raise RuntimeError(
                f"Knowledge Base article {DEMO_KB_ARTICLE_SLUG!r} collides with "
                "an existing owner or ID; capture seeding stopped before mutation."
            )


async def _migrate_legacy_smoke_workspace() -> None:
    """Retag only the three fixed smoke-bootstrap identities for this showcase."""

    from app.core.database import mongo

    canonical_ownership = {
        "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
        "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
    }
    await mongo.get_users_collection().update_one(
        {
            "_id": MARKETING_CAPTURE_PLANNER_USER_ID,
            "email": MARKETING_CAPTURE_PLANNER_EMAIL,
            "seed_source": SMOKE_ACCOUNT_SEED_SOURCE,
            "seed_scope": LEGACY_SMOKE_SEED_SCOPE,
        },
        {"$set": canonical_ownership},
    )
    await mongo.get_weddings_collection().update_one(
        {
            "_id": DEFAULT_PRIMARY_WEDDING_ID,
            "slug": DEFAULT_PRIMARY_SLUG,
            "seed_source": SMOKE_ACCOUNT_SEED_SOURCE,
            "seed_scope": LEGACY_SMOKE_SEED_SCOPE,
        },
        {"$set": canonical_ownership},
    )
    await mongo.get_couple_users_collection().update_one(
        {
            "_id": DEMO_COUPLE_ID,
            "email": DEMO_COUPLE_EMAIL,
            "wedding_id": DEFAULT_PRIMARY_WEDDING_ID,
            "seed_source": SMOKE_ACCOUNT_SEED_SOURCE,
            "seed_scope": LEGACY_SMOKE_SEED_SCOPE,
        },
        {"$set": canonical_ownership},
    )


async def _replace_seed_owned_document(
    collection: Any, document: dict[str, Any]
) -> None:
    """Replace only a deterministic row owned by the exact capture scope."""

    await _replace_marketing_capture_owned_document(collection, document)


async def _replace_marketing_capture_owned_document(
    collection: Any, document: dict[str, Any]
) -> None:
    """Replace only a row already owned by this exact capture scope."""

    await replace_scoped_document(
        collection,
        document,
        seed_source=MARKETING_CAPTURE_SEED_SOURCE,
        seed_scope=MARKETING_CAPTURE_SEED_SCOPE,
    )


def _guest_doc(
    *,
    wedding_id: str,
    index: int,
    name: str,
    group_id: str,
    invited_days_ago: int,
    plus_ones: int = 0,
    table_id: str | None = None,
    email_domain: str = "guests.thespecialwedding.io",
) -> dict[str, Any]:
    guest_id = ObjectId(
        hashlib.sha256(f"{wedding_id}:{index}".encode("utf-8")).hexdigest()[:24]
    )
    invited_at = _utc_now() - timedelta(days=invited_days_ago)
    phone_suffix = f"{100 + index:04d}"
    token_material = f"{MARKETING_CAPTURE_SEED_SCOPE}:{wedding_id}:token"
    token_prefix = (
        hashlib.sha256(token_material.encode("utf-8")).hexdigest()[:10].upper()
    )
    return {
        "_id": guest_id,
        "wedding_id": wedding_id,
        "name": name,
        "token": f"{token_prefix}{index:04d}",
        "email": f"{name.lower().replace(' ', '.')}@{email_domain}",
        "phone": f"+1312555{phone_suffix}",
        "group_id": group_id,
        "household_id": f"{wedding_id}:{group_id}:{(index - 1) // 2 + 1}",
        "role": "guest",
        "table_id": table_id,
        "plus_one_allowed": plus_ones > 0,
        "number_of_plus_ones_allowed": plus_ones,
        "plus_one_submitted": False,
        "sms_opt_in": True,
        "email_opt_in": True,
        "invite_sent": True,
        "invite_sent_date": invited_at,
        "phone_status": "valid",
        "age_group": "adult",
        "language_preference": "English",
        "accessibility_needs": (
            "Step-free route and an aisle seat near the terrace entrance"
            if index == 1
            else None
        ),
        "seating_preference": (
            "quiet_corner" if index in {15, 16} else "near_dance_floor"
        ),
        "created_at": invited_at - timedelta(days=1),
        "updated_at": _utc_now(),
        "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
        "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
    }


async def _seed_demo_subscription(planner: dict[str, Any]) -> None:
    from app.core.database import mongo

    now = _utc_now()
    planner_id = str(planner["_id"])
    planner_email = str(planner["email"])
    plan = await mongo.db["subscription_plans"].find_one({"_id": DEMO_PLAN_ID})
    if not plan:
        raise RuntimeError(f"Missing demo subscription plan {DEMO_PLAN_ID}")

    plan_snapshot = {
        "id": plan["_id"],
        "name": plan.get("name", "Signature"),
        "features": plan.get("features", {}),
        "staff_seats": plan.get("staff_seats", 5),
        "max_weddings": plan.get("max_weddings", -1),
    }
    await _replace_seed_owned_document(
        mongo.db["user_subscriptions"],
        {
            "_id": DEMO_SUBSCRIPTION_ID,
            "user_id": planner_id,
            "user_email": planner_email,
            "plan_id": DEMO_PLAN_ID,
            "plan_snapshot": plan_snapshot,
            "status": "active",
            "billing_interval": "monthly",
            "current_period_start": now - timedelta(days=3),
            "current_period_end": now + timedelta(days=27),
            "payment_status": "paid",
            "stripe_subscription_id": "sub_marketing_capture_signature",
            "stripe_customer_id": "cus_marketing_capture_signature",
            "created_at": now - timedelta(days=3),
            "updated_at": now,
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        },
    )


def _rsvp_doc(
    *,
    wedding_id: str,
    guest: dict[str, Any],
    attending: bool,
    submitted_days_ago: int,
    plus_one_names: list[str] | None = None,
    dietary: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    submitted_at = _utc_now() - timedelta(days=submitted_days_ago)
    guest_id = str(guest["_id"])
    rsvp = {
        "_id": f"rsvp_marketing_capture_{guest_id}",
        "wedding_id": wedding_id,
        "guest_id": guest_id,
        "guest_name": guest["name"],
        "attending": ["traditional"] if attending else [],
        "dietary": dietary,
        "phone": guest.get("phone"),
        "sms_opt_in": True,
        "email_opt_in": True,
        "created_at": submitted_at,
        "updated_at": submitted_at,
        "submitted_at": submitted_at,
        "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
        "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
    }
    plus_ones = []
    for index, name in enumerate(plus_one_names or [], start=1):
        plus_ones.append(
            {
                "_id": f"plus_one_marketing_capture_{guest_id}_{index}",
                "wedding_id": wedding_id,
                "guest_id": guest_id,
                "name": name,
                "attending": ["traditional"] if attending else [],
                "created_at": submitted_at,
                "updated_at": submitted_at,
                "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
                "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
            }
        )
    return rsvp, plus_ones


def _activity_doc(
    *,
    key: str,
    wedding_id: str,
    planner_email: str,
    message: str,
    activity_type: str,
    hours_ago: int,
    actor_email: str = "system@studio.thespecialwedding.io",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    timestamp = _utc_now() - timedelta(hours=hours_ago)
    return {
        "_id": f"activity_marketing_capture_{wedding_id}_{key}",
        "type": activity_type,
        "message": message,
        "timestamp": timestamp,
        "created_at": timestamp,
        "wedding_id": wedding_id,
        "planner_email": planner_email,
        "actor_email": actor_email,
        "actor_name": None,
        "actor_role": None,
        "metadata": metadata or {},
        "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
        "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
    }


async def _replace_seeded_docs(
    collection: Any, wedding_ids: list[str], docs: list[dict[str, Any]]
) -> None:
    await collection.delete_many(
        {
            "wedding_id": {"$in": wedding_ids},
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        }
    )
    if docs:
        await collection.insert_many(docs)


async def _upsert_wedding(
    *,
    wedding_id: str,
    slug: str,
    couple_names: str,
    partner1_name: str,
    partner2_name: str,
    planner: dict[str, Any],
    date: str,
    ready: bool,
) -> None:
    from app.core.database import mongo

    now = _utc_now()
    planner_id = str(planner["_id"])
    planner_email = str(planner["email"])
    common = {
        "couple_names": couple_names,
        "partner1_name": partner1_name,
        "partner2_name": partner2_name,
        "couple_portal_email": DEMO_COUPLE_EMAIL if ready else None,
        "date": date,
        "slug": slug,
        "assigned_planner_id": planner_id,
        "assigned_planner_email": planner_email,
        "status": "active",
        "venue": "The Glasshouse at Riverbend" if ready else "",
        "public_site_url": f"{MARKETING_CAPTURE_PUBLIC_ORIGIN}/{slug}",
        "featured_image": _demo_featured_image(
            ready=ready,
            couple_names=couple_names,
            partner1_name=partner1_name,
            partner2_name=partner2_name,
            slug=slug,
        ),
        "guest_count": 96 if ready else 54,
        "total_budget": 82500 if ready else 42000,
        "cultural_style": "modern multicultural",
        "privacy_settings": {
            "privacy_mode": "public" if ready else "password",
            "guest_auth_required": not ready,
            "allow_guest_sharing": ready,
            "require_phone_verification": False,
            "require_name_verification": not ready,
        },
        "rsvp_config": {
            "enabled": True,
            "deadline": _date_from_now(72 if ready else 110),
            "intro_text": "Please RSVP for the ceremony and reception.",
            "greeting": "Join us in celebrating our special day! Please let us know if you'll be attending.",
            "help_text": "Check your phone for your personal invitation link. If you need help, use the Get Help button and our planner will text you.",
            "help_button_label": "Get Help",
            "hide_phone_numbers": True,
            "phone_numbers": ["(312) 555-0142", "(312) 555-0168"] if ready else [],
            "contact_email": planner_email,
        },
        "theme": {
            "primaryColor": "#7f1d1d",
            "accentColor": "#d4a5a5",
            "fontFamily": "serif",
        },
        "theme_config": {
            "primary_color": "#6f3f3a",
            "secondary_color": "#d2ad79",
            "accent_color": "#8d6e63",
            "background_style": "image",
            "font_style": "elegant",
        },
        "our_story": (
            {
                "text": (
                    "Sofia and Daniel met through mutual friends in Chicago and "
                    "built their celebration around family, music, and a relaxed "
                    "garden dinner."
                ),
                "image_url": MARKETING_CAPTURE_GALLERY_ASSETS[0]["url"],
                "image_shape": "circle",
            }
            if ready
            else None
        ),
        "wedding_party": (
            [
                {
                    "id": "party-camille-brooks",
                    "name": "Camille Brooks",
                    "role": "maid_of_honor",
                    "side": "bride",
                    "display_order": 0,
                    "image_url": None,
                },
                {
                    "id": "party-elliot-brooks",
                    "name": "Elliot Brooks",
                    "role": "best_man",
                    "side": "groom",
                    "display_order": 0,
                    "image_url": None,
                },
            ]
            if ready
            else []
        ),
        "registries": [
            {
                "name": "Honeymoon Fund",
                "url": "https://registry.thespecialwedding.io/honeymoon",
            },
            {
                "name": "Home Essentials",
                "url": "https://registry.thespecialwedding.io/home",
            },
        ],
        "faqs": [
            {
                "question": "What should guests wear?",
                "answer": "Garden formal attire is encouraged.",
            },
            {
                "question": "Is transportation provided?",
                "answer": "Shuttles leave the hotel lobby at 3:15 PM.",
            },
        ]
        if ready
        else [],
        "updated_at": now,
        "updated_by": MARKETING_CAPTURE_SEED_SOURCE,
        "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
        "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
    }
    events = (
        [
            {
                "type": "traditional",
                "date": date,
                "details": {
                    "venue_name": "The Glasshouse at Riverbend",
                    "location": "Chicago, IL",
                    "time": "4:00 PM",
                    "attire": "Garden formal",
                },
                "order_of_events": [
                    {
                        "id": f"{wedding_id}_traditional_processional",
                        "time": "4:00 PM",
                        "title": "Family processional",
                        "description": "Parents, wedding party, and couple enter before the blessing.",
                        "duration_minutes": 12,
                        "order": 0,
                        "notes": [
                            {
                                "id": f"{wedding_id}_note_processional_music",
                                "author_role": "couple",
                                "author_name": partner1_name,
                                "text": "Please confirm the live drummer starts only after both moms are seated.",
                                "status": "pending",
                                "created_at": (
                                    now - timedelta(days=2, hours=4)
                                ).isoformat(),
                            }
                        ],
                    },
                    {
                        "id": f"{wedding_id}_traditional_cocktail_hour",
                        "time": "5:00 PM",
                        "title": "Cocktail hour opens",
                        "description": "Guests move to the terrace while portraits wrap.",
                        "duration_minutes": 60,
                        "order": 1,
                        "notes": [],
                    },
                    {
                        "id": f"{wedding_id}_traditional_reception",
                        "time": "6:30 PM",
                        "title": "Reception doors open",
                        "description": "MC welcomes guests and cues wedding party entrance.",
                        "duration_minutes": 15,
                        "order": 2,
                        "notes": [
                            {
                                "id": f"{wedding_id}_note_reception_mc_cue",
                                "author_role": "couple",
                                "author_name": partner2_name,
                                "text": "Can Elton announce us after the second chorus instead of right at the intro?",
                                "status": "seen",
                                "created_at": (
                                    now - timedelta(days=1, hours=3)
                                ).isoformat(),
                            },
                            {
                                "id": f"{wedding_id}_note_reception_mc_cue_reply",
                                "author_role": "planner",
                                "author_name": "Amina Cole",
                                "text": "Yes, I added that cue to the MC run sheet and will confirm during sound check.",
                                "status": "addressed",
                                "reply_to": f"{wedding_id}_note_reception_mc_cue",
                                "created_at": (
                                    now - timedelta(days=1, hours=2, minutes=35)
                                ).isoformat(),
                            },
                        ],
                    },
                ],
                "event_notes": [
                    {
                        "id": f"{wedding_id}_event_note_family_photos",
                        "author_role": "couple",
                        "author_name": partner1_name,
                        "text": "Please keep the immediate-family photo list separate from the extended-family list so portraits move faster.",
                        "status": "pending",
                        "created_at": (now - timedelta(days=2, hours=1)).isoformat(),
                    },
                    {
                        "id": f"{wedding_id}_event_note_portraits",
                        "author_role": "planner",
                        "author_name": "Amina Cole",
                        "text": "Golden-hour portraits are held for 6:05 PM; I will keep the couple hidden until the photographer is ready.",
                        "status": "seen",
                        "created_at": (now - timedelta(days=1, hours=22)).isoformat(),
                    },
                ],
            }
        ]
        if ready
        else []
    )
    insert = {
        "created_at": now - timedelta(days=38 if ready else 9),
        "created_by": MARKETING_CAPTURE_SEED_SOURCE,
    }
    await mongo.get_weddings_collection().update_one(
        {
            "_id": wedding_id,
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        },
        {"$set": {**common, "events": events}, "$setOnInsert": insert},
        upsert=True,
    )


async def _seed_accepted_team_fixture(planner: dict[str, Any], primary_id: str) -> None:
    """Create a fully accepted staff identity linked to the capture owner."""

    from app.core.database import mongo
    from app.models.team_member import resolve_team_permissions
    from app.utils.auth_utils import get_password_hash

    now = _utc_now()
    planner_id = str(planner["_id"])
    permissions = resolve_team_permissions("editor")
    password = os.getenv(
        "MARKETING_CAPTURE_TEAM_PASSWORD", MARKETING_CAPTURE_TEAM_PASSWORD
    )
    team_member_id = str(MARKETING_CAPTURE_TEAM_MEMBER_ID)
    team_user_id = str(MARKETING_CAPTURE_TEAM_USER_ID)

    await _replace_seed_owned_document(
        mongo.get_users_collection(),
        {
            "_id": MARKETING_CAPTURE_TEAM_USER_ID,
            "email": MARKETING_CAPTURE_TEAM_EMAIL,
            "password_hash": get_password_hash(password),
            "role": "team_member",
            "parent_planner_id": planner_id,
            "team_member_id": team_member_id,
            "first_name": "Maya",
            "last_name": "Thompson",
            "company_name": MARKETING_CAPTURE_COMPANY,
            "subscription_status": "active",
            "is_active": True,
            "email_verified": True,
            "onboarding_completed": True,
            "created_at": now - timedelta(days=30),
            "updated_at": now,
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        },
    )
    await _replace_seed_owned_document(
        mongo.db["team_members"],
        {
            "_id": MARKETING_CAPTURE_TEAM_MEMBER_ID,
            "owner_id": planner_id,
            "owner_email": str(planner["email"]),
            "user_id": team_user_id,
            "email": MARKETING_CAPTURE_TEAM_EMAIL,
            "first_name": "Maya",
            "last_name": "Thompson",
            "status": "active",
            "role": "editor",
            "custom_permissions": permissions,
            "wedding_access": "assigned",
            "assigned_wedding_ids": [primary_id],
            "invited_at": now - timedelta(days=32),
            "accepted_at": now - timedelta(days=30),
            "last_active_at": now - timedelta(hours=2),
            "created_at": now - timedelta(days=32),
            "updated_at": now,
            "deactivated_at": None,
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        },
    )


async def _seed_couple_portal_fixture(
    primary_id: str,
    planner: dict[str, Any],
    *,
    couple_names: str,
    partner1_name: str,
    partner2_name: str,
) -> str:
    from app.core.database import mongo
    from app.utils.auth_utils import get_password_hash
    from app.utils.messaging_roles import SENDER_ROLE_COUPLE, SENDER_ROLE_PLANNER

    now = _utc_now()
    planner_email = str(planner["email"])
    planner_id = str(planner["_id"])

    await _replace_seed_owned_document(
        mongo.get_couple_users_collection(),
        {
            "_id": DEMO_COUPLE_ID,
            "email": DEMO_COUPLE_EMAIL,
            "partner1_name": partner1_name,
            "partner2_name": partner2_name,
            "wedding_id": primary_id,
            "planner_id": planner_id,
            "planner_email": planner_email,
            "password_hash": get_password_hash(DEMO_COUPLE_PASSWORD),
            "setup_completed": True,
            "is_active": True,
            "access_state": "active",
            "wedding_archived": False,
            "archived_at": None,
            "invite_token": None,
            "invite_token_expires": None,
            "last_login": now - timedelta(days=1, hours=3),
            "owner_cancelled_at": None,
            "owner_cancelled_by_planner_id": None,
            "owner_cancelled_by_planner_email": None,
            "revoked_at": None,
            "revoked_by": None,
            "onboarding_completed": True,
            "onboarding_completed_at": now - timedelta(days=15),
            "onboarding_steps_completed": [
                "welcome",
                "overview",
                "guest_tracker",
                "messages",
                "forms",
            ],
            "created_at": now - timedelta(days=21),
            "updated_at": now,
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        },
    )

    await mongo.db["couple_messages"].delete_many(
        {
            "wedding_id": primary_id,
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        }
    )
    await mongo.db["couple_messages"].insert_many(
        [
            {
                "_id": ObjectId("67c900000000000000000001"),
                "wedding_id": primary_id,
                "sender_role": SENDER_ROLE_COUPLE,
                "sender_email": DEMO_COUPLE_EMAIL,
                "sender_name": couple_names,
                "content": "We uploaded the final family photo list and want Marigold & Co. Weddings to confirm the order before Saturday.",
                "read_by_couple": True,
                "read_by_planner": False,
                "created_at": now - timedelta(hours=6),
                "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
                "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
            },
            {
                "_id": ObjectId("67c900000000000000000002"),
                "wedding_id": primary_id,
                "sender_role": SENDER_ROLE_PLANNER,
                "sender_email": planner_email,
                "sender_name": "Amina Cole",
                "content": "Got it. I added it to the production timeline and will review the VIP groupings during our final walkthrough.",
                "read_by_couple": True,
                "read_by_planner": True,
                "created_at": now - timedelta(hours=4),
                "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
                "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
            },
            {
                "_id": ObjectId("67c900000000000000000003"),
                "wedding_id": primary_id,
                "sender_role": SENDER_ROLE_COUPLE,
                "sender_email": DEMO_COUPLE_EMAIL,
                "sender_name": couple_names,
                "content": "Perfect. Can you also remind guests about arriving 15 minutes early for the ceremony?",
                "read_by_couple": True,
                "read_by_planner": False,
                "created_at": now - timedelta(hours=2),
                "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
                "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
            },
        ]
    )
    return DEMO_COUPLE_EMAIL


async def _seed_communications_fixture(
    primary_id: str,
    planner_email: str,
    *,
    wedding_slug: str,
    couple_names: str,
) -> None:
    from app.core.database import mongo

    now = _utc_now()
    thread_id = f"wedding-{wedding_slug}"

    await mongo.db["reminders_sent"].delete_many(
        {
            "wedding_id": primary_id,
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        }
    )
    await mongo.db["email_logs"].delete_many(
        {
            "wedding_id": primary_id,
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        }
    )

    sms_logs = [
        {
            "_id": ObjectId("67ca00000000000000000001"),
            "wedding_id": primary_id,
            "wedding_slug": wedding_slug,
            "guest_id": "marketing_capture_guest_amara",
            "guest_name": "Amara Bennett",
            "phone": "+13125550101",
            "message": f"Hi Amara, this is a warm reminder from Marigold & Co. Weddings for {couple_names}'s wedding weekend. Please arrive 15 minutes early for ceremony seating.",
            "status": "success",
            "provider": "twilio",
            "type": "sms",
            "target_type": "guest",
            "event_type": "ceremony",
            "delivery_status": "delivered",
            "delivery_status_updated_at": now - timedelta(minutes=24),
            "sent_at": now - timedelta(minutes=42),
            "sent_by": planner_email,
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        },
        {
            "_id": ObjectId("67ca00000000000000000002"),
            "wedding_id": primary_id,
            "wedding_slug": wedding_slug,
            "guest_id": "marketing_capture_guest_mateo",
            "guest_name": "Mateo Rivera",
            "phone": "+13125550104",
            "message": f"Hi Mateo, Marigold & Co. Weddings is confirming RSVP details for {couple_names}. Please check the wedding site for schedule and FAQ updates.",
            "status": "success",
            "provider": "twilio",
            "type": "sms",
            "target_type": "guest",
            "event_type": "all",
            "delivery_status": "delivered",
            "delivery_status_updated_at": now - timedelta(minutes=18),
            "sent_at": now - timedelta(minutes=35),
            "sent_by": planner_email,
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        },
    ]
    await mongo.db["reminders_sent"].insert_many(sms_logs)

    await mongo.db["email_logs"].insert_many(
        [
            {
                "_id": ObjectId("67cb00000000000000000001"),
                "wedding_id": primary_id,
                "to": "family.hosts@guests.thespecialwedding.io",
                "subject": f"{couple_names} - Final Weekend Details",
                "message": "Final schedule, venue notes, and FAQ link shared with family hosts.",
                "html_content": "<p>Final schedule, venue notes, and FAQ link shared with family hosts.</p>",
                "from_email": planner_email,
                "from_name": "Amina Cole",
                "thread_id": thread_id,
                "status": "success",
                "provider": "resend",
                "email_type": "weekend_details",
                "sent_at": now - timedelta(minutes=28),
                "sent_by": planner_email,
                "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
                "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
            }
        ]
    )

    guest = await mongo.get_guest_collection().find_one(
        {"wedding_id": primary_id, "name": "Amara Bennett"}, {"_id": 1}
    )
    guest_id = str(guest["_id"]) if guest else None
    await mongo.db["inbound_emails"].delete_many(
        {
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        }
    )
    await mongo.db["inbound_emails"].insert_one(
        {
            "_id": ObjectId("67cc00000000000000000001"),
            "resend_email_id": "email_marketing_capture_guest_question",
            "from_address": "amara.bennett@guests.thespecialwedding.io",
            "from_name": "Amara Bennett",
            "to_address": (
                f"reply+{wedding_slug}--{guest_id}@messages.thespecialwedding.io"
                if guest_id
                else f"reply+{wedding_slug}@messages.thespecialwedding.io"
            ),
            "subject": "Shuttle pickup time for the wedding weekend",
            "attachments_metadata": [],
            "content": {
                "html_body": (
                    "<p>Hi Amina, could you confirm whether the first hotel "
                    "shuttle leaves at 3:15 PM?</p>"
                ),
                "text_body": (
                    "Hi Amina, could you confirm whether the first hotel "
                    "shuttle leaves at 3:15 PM?"
                ),
                "headers": {},
                "reply_to": [],
                "cc": [],
                "bcc": [],
                "attachments": [],
                "message_id": "capture-inbound-001",
                "raw_download_url": None,
            },
            "thread_context": {
                "wedding_id": primary_id,
                "wedding_slug": wedding_slug,
                "planner_id": planner_email,
                "thread_id": thread_id,
                "guest_id": guest_id,
                "guest_name": "Amara Bennett",
            },
            "status": "content_fetched",
            "content_fetch_attempts": 1,
            "content_fetch_last_error": None,
            "is_read": False,
            "read_at": None,
            "planner_response_sent": False,
            "created_at": now - timedelta(hours=3, minutes=20),
            "content_fetched_at": now - timedelta(hours=3, minutes=19),
            "updated_at": now - timedelta(hours=3, minutes=19),
            "svix_id": "svix_marketing_capture_guest_question",
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        }
    )

    await mongo.db["support_tickets"].delete_many(
        {
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        }
    )
    await mongo.db["support_tickets"].insert_many(
        [
            {
                "_id": ObjectId("67cd00000000000000000001"),
                "phone": "+13125550101",
                "message": (
                    "Could you confirm the accessibility entrance and shuttle "
                    "drop-off point?"
                ),
                "source": "sms",
                "provider": "twilio",
                "message_sid": "SM_MARKETING_CAPTURE_001",
                "guest_id": guest_id,
                "guest_name": "Amara Bennett",
                "relationship_to_couple": "College friend",
                "wedding_id": primary_id,
                "wedding_name": couple_names,
                "assigned_to": planner_email,
                "planner_name": "Amina Cole",
                "status": "new",
                "priority": "high",
                "category": "venue",
                "is_read": False,
                "responses": [],
                "origin": "public_help_form",
                "type": "help_request",
                "created_at": now - timedelta(hours=1, minutes=15),
                "updated_at": now - timedelta(hours=1, minutes=15),
                "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
                "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
            },
            {
                "_id": ObjectId("67cd00000000000000000002"),
                "ticket_number": "TKT-2026-1042",
                "subject": "Review custom RSVP wording",
                "description": (
                    "Please confirm the guest-facing arrival wording before the "
                    "final reminder is scheduled."
                ),
                "source": "web_form",
                "priority": "medium",
                "category": "general",
                "status": "open",
                "created_by": planner_email,
                "assigned_to": None,
                "wedding_id": primary_id,
                "attachments": [],
                "comments": [],
                "tags": ["rsvp", "copy-review"],
                "created_at": now - timedelta(days=1, hours=2),
                "updated_at": now - timedelta(days=1, hours=2),
                "resolved_at": None,
                "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
                "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
            },
        ]
    )


async def _seed_people_and_activity(
    primary_id: str,
    secondary_id: str,
    planner_email: str,
    *,
    secondary_couple_names: str,
) -> None:
    from app.core.database import mongo

    guest_names = [
        ("Amara Bennett", "family", 16, 1, DEMO_SEATING_TABLE_IDS["head"]),
        ("Theo Bennett", "family", 16, 0, DEMO_SEATING_TABLE_IDS["head"]),
        ("Priya Shah", "friends", 15, 1, DEMO_SEATING_TABLE_IDS["friends"]),
        ("Mateo Rivera", "friends", 15, 0, DEMO_SEATING_TABLE_IDS["friends"]),
        ("Camille Brooks", "wedding_party", 14, 0, DEMO_SEATING_TABLE_IDS["head"]),
        ("Elliot Brooks", "wedding_party", 14, 0, DEMO_SEATING_TABLE_IDS["head"]),
        ("Noor Patel", "family", 13, 1, DEMO_SEATING_TABLE_IDS["family"]),
        ("Jonah Park", "friends", 13, 0, DEMO_SEATING_TABLE_IDS["friends"]),
        ("Sofia Grant", "vendor_guest", 12, 0, DEMO_SEATING_TABLE_IDS["vendor"]),
        ("Miles Carter", "friends", 12, 1, DEMO_SEATING_TABLE_IDS["family"]),
        ("Leah Kim", "family", 11, 0, DEMO_SEATING_TABLE_IDS["family"]),
        ("Owen Reed", "family", 11, 0, DEMO_SEATING_TABLE_IDS["couple_friends"]),
        ("Nia Thompson", "friends", 10, 1, DEMO_SEATING_TABLE_IDS["couple_friends"]),
        ("Ari Cohen", "friends", 10, 0, DEMO_SEATING_TABLE_IDS["couple_friends"]),
        ("Grace Ellis", "family", 9, 0, DEMO_SEATING_TABLE_IDS["extended_family"]),
        ("Henry Ellis", "family", 9, 0, DEMO_SEATING_TABLE_IDS["extended_family"]),
        ("Lena Walsh", "friends", 8, 1, None),
        ("Marco Walsh", "friends", 8, 0, None),
        ("Riley Quinn", "family", 7, 0, None),
        ("Zara Ahmed", "friends", 7, 0, None),
        ("Drew Mason", "wedding_party", 6, 1, None),
        ("Kai Morgan", "friends", 6, 0, None),
        ("Mina Lopez", "family", 5, 0, None),
        ("Samir Khan", "friends", 5, 0, None),
    ]
    primary_guests = [
        _guest_doc(
            wedding_id=primary_id,
            index=index,
            name=name,
            group_id=group,
            invited_days_ago=days,
            plus_ones=plus_ones,
            table_id=table_id,
        )
        for index, (name, group, days, plus_ones, table_id) in enumerate(
            guest_names, start=1
        )
    ]

    secondary_guests = [
        _guest_doc(
            wedding_id=secondary_id,
            index=index,
            name=name,
            group_id=group,
            invited_days_ago=days,
            plus_ones=plus_ones,
            table_id=None,
        )
        for index, (name, group, days, plus_ones) in enumerate(
            [
                ("June Wallace", "family", 4, 1),
                ("Iris Chen", "friends", 4, 0),
                ("Logan Price", "friends", 4, 0),
                ("Anika Rao", "family", 3, 1),
                ("Ben Hart", "family", 3, 0),
                ("Mae Collins", "friends", 2, 0),
                ("Victor Lee", "friends", 2, 0),
                ("Sage Turner", "vendor_guest", 1, 0),
            ],
            start=1,
        )
    ]

    rsvps: list[dict[str, Any]] = []
    plus_ones: list[dict[str, Any]] = []
    for index, guest in enumerate(primary_guests[:18], start=1):
        attending = index not in {6, 12, 16}
        plus_names = (
            [f"{guest['name'].split()[0]} Plus One"]
            if attending and guest["number_of_plus_ones_allowed"]
            else []
        )
        rsvp, guest_plus_ones = _rsvp_doc(
            wedding_id=primary_id,
            guest=guest,
            attending=attending,
            submitted_days_ago=max(1, 9 - index // 2),
            plus_one_names=plus_names,
            dietary="Vegetarian"
            if guest["name"] in {"Priya Shah", "Noor Patel"}
            else "Gluten-free"
            if guest["name"] == "Grace Ellis"
            else None,
        )
        rsvps.append(rsvp)
        plus_ones.extend(guest_plus_ones)

    secondary_rsvp, secondary_plus_ones = _rsvp_doc(
        wedding_id=secondary_id,
        guest=secondary_guests[0],
        attending=True,
        submitted_days_ago=1,
        plus_one_names=["June Guest"],
    )
    rsvps.append(secondary_rsvp)
    plus_ones.extend(secondary_plus_ones)

    wedding_ids = [primary_id, secondary_id]
    await _replace_seeded_docs(
        mongo.get_guest_collection(), wedding_ids, primary_guests + secondary_guests
    )
    await _replace_seeded_docs(mongo.get_rsvps_collection(), wedding_ids, rsvps)
    await _replace_seeded_docs(mongo.get_plus_ones_collection(), wedding_ids, plus_ones)

    activities = [
        _activity_doc(
            key="rsvp_amara",
            wedding_id=primary_id,
            planner_email=planner_email,
            message="Amara Bennett accepted the invitation (+1 guest)",
            activity_type="rsvp_received",
            hours_ago=2,
            actor_email="amara.bennett@guests.thespecialwedding.io",
        ),
        _activity_doc(
            key="reminder_batch",
            wedding_id=primary_id,
            planner_email=planner_email,
            message="Sent RSVP reminder to 6 guests via email",
            activity_type="reminder_sent",
            hours_ago=6,
        ),
        _activity_doc(
            key="guest_import",
            wedding_id=primary_id,
            planner_email=planner_email,
            message="Imported 24 guests from final guest list",
            activity_type="guest_imported",
            hours_ago=22,
            metadata={"count": 24, "source": "csv"},
        ),
        _activity_doc(
            key="setup_secondary",
            wedding_id=secondary_id,
            planner_email=planner_email,
            message=f"{secondary_couple_names} still needs schedule and access setup",
            activity_type="wedding_updated",
            hours_ago=25,
        ),
    ]
    await _replace_seeded_docs(
        mongo.get_collection("activity_logs"), wedding_ids, activities
    )


async def _seed_seating_fixture(primary_id: str, secondary_id: str) -> None:
    from app.core.database import mongo

    now = _utc_now()
    table_specs = [
        ("head", "Family Honor Table", "rectangle", 8, 220, 260),
        ("friends", "College Friends", "round", 8, 540, 260),
        ("family", "Parents & Elders", "round", 8, 980, 260),
        ("couple_friends", "Close Friends", "round", 8, 220, 640),
        ("extended_family", "Extended Family", "round", 8, 560, 660),
        ("vendor", "Vendor Meals", "rectangle", 8, 980, 660),
    ]
    tables = [
        {
            "_id": ObjectId(DEMO_SEATING_TABLE_IDS[key]),
            "wedding_id": primary_id,
            "name": name,
            "shape": shape,
            "capacity": capacity,
            "x": x,
            "y": y,
            "created_at": now - timedelta(days=4),
            "updated_at": now,
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        }
        for key, name, shape, capacity, x, y in table_specs
    ]
    wedding_ids = [primary_id, secondary_id]
    capture_filter = {
        "wedding_id": {"$in": wedding_ids},
        "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
        "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
    }
    await mongo.db["tables"].delete_many(capture_filter)
    await mongo.db["tables"].insert_many(tables)

    await mongo.db["seating_layouts"].delete_many(capture_filter)
    await mongo.db["seating_layouts"].insert_one(
        {
            "_id": ObjectId(DEMO_SEATING_LAYOUT_ID),
            "wedding_id": primary_id,
            "canvas_width": 1600,
            "canvas_height": 1000,
            "outline": [
                {"x": 80, "y": 80},
                {"x": 1520, "y": 80},
                {"x": 1520, "y": 920},
                {"x": 80, "y": 920},
            ],
            "background_image_data_url": MARKETING_CAPTURE_VENUE_BACKGROUND,
            "background_image_name": "glasshouse-riverbend-approved-floorplan.svg",
            "background_locked": True,
            "scale_pixels": 300,
            "scale_distance": 40,
            "scale_unit": "ft",
            "fixtures": [
                {
                    "id": "fixture_demo_stage",
                    "type": "stage",
                    "label": "Ceremony Stage",
                    "x": 620,
                    "y": 115,
                    "width": 360,
                    "height": 80,
                    "rotation": 0,
                },
                {
                    "id": "fixture_demo_dance_floor",
                    "type": "dance_floor",
                    "label": "Dance Floor",
                    "x": 660,
                    "y": 455,
                    "width": 280,
                    "height": 150,
                    "rotation": 0,
                },
                {
                    "id": "fixture_demo_bar",
                    "type": "bar",
                    "label": "Cocktail Bar",
                    "x": 1240,
                    "y": 120,
                    "width": 180,
                    "height": 90,
                    "rotation": 0,
                },
                {
                    "id": "fixture_demo_entrance",
                    "type": "entrance",
                    "label": "Guest Entrance",
                    "x": 120,
                    "y": 820,
                    "width": 110,
                    "height": 70,
                    "rotation": 0,
                },
            ],
            "created_at": now - timedelta(days=4),
            "updated_at": now,
            "updated_by": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        }
    )


async def _seed_ai_cache(primary_id: str, planner: dict[str, Any]) -> None:
    from app.core.database import mongo
    from app.services.ai_cache_service import ai_cache_service
    from app.services.ai_service import ai_service

    plan = ai_cache_service._normalize_plan(
        await ai_service._resolve_subscription_plan(str(planner["_id"]))
    )
    fixtures = (
        (
            "dashboard_insights",
            {"demo_seed": "morning-view", "version": 1},
            {
                "insights": [
                    {
                        "title": "RSVP follow-up window is open",
                        "description": "6 invited guests are still pending. Send the reminder batch before the hotel count locks.",
                        "priority": "high",
                        "action_url": "/admin/communications/reminders",
                        "icon": "users",
                    },
                    {
                        "title": "Seating is ready for final pass",
                        "description": "18 RSVPs are in and 16 guests already have table context for the seating review.",
                        "priority": "medium",
                        "action_url": f"/admin/seating?weddingId={primary_id}",
                        "icon": "check-circle",
                    },
                    {
                        "title": "Public site essentials are complete",
                        "description": "Schedule, RSVP, access, and theme are configured, so the couple can preview the site confidently.",
                        "priority": "low",
                        "action_url": f"/admin/weddings/{primary_id}",
                        "icon": "calendar",
                    },
                ]
            },
        ),
        (
            "budget_insights",
            {"demo_seed": "budget-control", "version": 1},
            {
                "summary": "Attire & Beauty is $950 over plan while the remaining categories retain $45,800 of unspent budget.",
                "recommendations": [
                    "Confirm final alteration charges before approving the next invoice.",
                    "Protect the Guest Experience reserve until transportation headcount locks.",
                ],
                "risk_level": "attention",
            },
        ),
    )
    now = _utc_now()
    for feature, context, response in fixtures:
        cache_key = ai_cache_service._generate_cache_key(
            feature,
            primary_id,
            context,
            subscription_plan=plan,
        )
        context_json = json.dumps(context, sort_keys=True, default=str)
        await _replace_marketing_capture_owned_document(
            mongo.db["ai_cache"],
            {
                "_id": cache_key,
                "feature": feature,
                "tenant_id": primary_id,
                "subscription_plan": plan,
                "context_hash": hashlib.sha256(context_json.encode()).hexdigest(),
                "response": response,
                "created_at": now,
                "expires_at": now + timedelta(hours=24),
                "hit_count": 0,
                "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
                "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
            },
        )


async def _seed_knowledge_base_fixture(planner: dict[str, Any]) -> None:
    """Publish one isolated support article without touching global KB content."""

    from app.core.database import mongo

    now = _utc_now()
    author_email = str(planner["email"])
    await _replace_marketing_capture_owned_document(
        mongo.db["kb_articles"],
        {
            "_id": ObjectId(DEMO_KB_ARTICLE_ID),
            "title": "Planner Command Center: Your First 30 Minutes",
            "slug": DEMO_KB_ARTICLE_SLUG,
            "excerpt": "A practical first-session checklist for turning a new wedding into a connected planning workspace.",
            "content": """# Planner Command Center: Your First 30 Minutes

Start with the wedding workspace as your source of truth. Confirm the couple's public-site essentials, invite your collaborators, and add the next planning milestones to the shared calendar.

Then review the guest list, seating progress, vendor commitments, forms, and money from the planner command center. Each surface stays connected to the same wedding so the couple sees clear progress without needing access to your internal operating details.
""",
            "category": "getting-started",
            "tags": ["planner", "command-center", "onboarding", "workflow"],
            "status": "published",
            "is_official": True,
            "featured": True,
            "author_email": author_email,
            "author_name": "Amina Cole",
            "author_id": str(planner["_id"]),
            "created_by": author_email,
            "updated_by": author_email,
            "view_count": 0,
            "helpful_count": 0,
            "not_helpful_count": 0,
            "feedback": [],
            "order": 1,
            "estimated_read_minutes": 2,
            "card_image": None,
            "og_image": None,
            "created_at": now,
            "updated_at": now,
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        },
    )


async def _seed_gallery_fixture(
    primary_id: str, planner_email: str, wedding_slug: str
) -> None:
    """Store approved, production-shaped gallery metadata for the showcase site."""

    from app.core.database import mongo

    now = _utc_now()
    collection = mongo.get_gallery_collection()
    await collection.delete_many(
        {
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        }
    )
    docs = []
    for index, fixture in enumerate(MARKETING_CAPTURE_GALLERY_ASSETS):
        docs.append(
            {
                **fixture,
                "wedding_id": primary_id,
                "wedding_slug": wedding_slug,
                "storage_provider": "approved_showcase_cdn",
                "media_type": "image",
                "mime_type": fixture["content_type"],
                "display_order": index,
                "is_public": True,
                "uploaded_by": planner_email,
                "created_at": now - timedelta(days=20 - index),
                "updated_at": now,
                "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
                "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
            }
        )
    await collection.insert_many(docs)


async def _seed_guest_media_fixture(
    primary_id: str,
    *,
    couple_names: str,
    partner1_name: str,
    partner2_name: str,
) -> str:
    from app.core.database import mongo
    from app.services.guest_media_service import guest_media_service

    wedding = await mongo.get_weddings_collection().find_one({"_id": primary_id})
    if not wedding:
        raise RuntimeError(
            f"Cannot seed guest media fixture; wedding {primary_id} was not found."
        )

    # MongoDB stores datetimes at millisecond precision. The first ensure call may
    # create last_rotated_at with Python microseconds, so reload before returning
    # the route token that browser recordings will actually validate against.
    await guest_media_service.ensure_guest_media_config(wedding)
    wedding = await mongo.get_weddings_collection().find_one({"_id": primary_id})
    if not wedding:
        raise RuntimeError(
            f"Cannot reload guest media fixture; wedding {primary_id} was not found."
        )
    ensured = await guest_media_service.ensure_guest_media_config(wedding)
    now = _utc_now()
    wedding_slug = wedding.get("slug") or DEFAULT_PRIMARY_SLUG
    stock_media_allowed = _stock_demo_media_allowed(
        couple_names=couple_names,
        partner1_name=partner1_name,
        partner2_name=partner2_name,
        slug=wedding_slug,
    )
    asset_collection = mongo.db["guest_media_assets"]
    await asset_collection.delete_many(
        {
            "wedding_id": primary_id,
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        }
    )
    preview_urls = {
        "couple": MARKETING_CAPTURE_GALLERY_ASSETS[0]["url"],
        "ceremony": MARKETING_CAPTURE_GALLERY_ASSETS[1]["url"],
        "reception": MARKETING_CAPTURE_GALLERY_ASSETS[2]["url"],
        "dance": MARKETING_CAPTURE_GALLERY_ASSETS[0]["url"],
    }
    memory_fixtures = (
        [
            (
                "marketing_capture_memory_pending_001",
                couple_names,
                "couple-staircase-portrait.jpg",
                "pending",
                None,
                preview_urls["couple"],
                560_709,
            ),
            (
                "marketing_capture_memory_pending_002",
                f"{partner1_name}'s Family",
                "ceremony-aisle-moment.jpg",
                "pending",
                "ceremony",
                preview_urls["ceremony"],
                861_884,
            ),
            (
                "marketing_capture_memory_pending_003",
                f"{partner2_name}'s Family",
                "reception-table-florals.jpg",
                "pending",
                "reception",
                preview_urls["reception"],
                533_947,
            ),
            (
                "marketing_capture_memory_pending_004",
                "Wedding Party",
                "first-dance-cheers.jpg",
                "pending",
                "reception",
                preview_urls["dance"],
                237_061,
            ),
            (
                "marketing_capture_memory_kept_001",
                f"{couple_names}'s Friends",
                "candlelit-reception-table.jpg",
                "kept",
                "reception",
                preview_urls["reception"],
                533_947,
            ),
            (
                "marketing_capture_memory_kept_002",
                f"{partner2_name} Family",
                "garden-ceremony-aisle.jpg",
                "kept",
                "ceremony",
                preview_urls["ceremony"],
                861_884,
            ),
            (
                "marketing_capture_memory_rejected_001",
                "Guest Upload",
                "overexposed-dance-floor.jpg",
                "rejected",
                "reception",
                preview_urls["dance"],
                237_061,
            ),
        ]
        if stock_media_allowed
        else [
            (
                "marketing_capture_memory_pending_001",
                "Reception Design",
                "reception-table-florals.jpg",
                "pending",
                "reception",
                preview_urls["reception"],
                533_947,
            ),
            (
                "marketing_capture_memory_pending_002",
                "Ceremony Details",
                "ceremony-floral-detail.jpg",
                "pending",
                "ceremony",
                preview_urls["ceremony"],
                533_947,
            ),
            (
                "marketing_capture_memory_pending_003",
                "Cocktail Hour",
                "cocktail-table-detail.jpg",
                "pending",
                "reception",
                preview_urls["reception"],
                533_947,
            ),
            (
                "marketing_capture_memory_pending_004",
                "Reception Setup",
                "place-setting-detail.jpg",
                "pending",
                "reception",
                preview_urls["dance"],
                533_947,
            ),
            (
                "marketing_capture_memory_kept_001",
                "Table Design",
                "candlelit-reception-table.jpg",
                "kept",
                "reception",
                preview_urls["reception"],
                533_947,
            ),
            (
                "marketing_capture_memory_kept_002",
                "Floral Install",
                "garden-ceremony-florals.jpg",
                "kept",
                "ceremony",
                preview_urls["ceremony"],
                533_947,
            ),
            (
                "marketing_capture_memory_rejected_001",
                "Guest Upload",
                "overexposed-detail-shot.jpg",
                "rejected",
                "reception",
                preview_urls["dance"],
                533_947,
            ),
        ]
    )
    await asset_collection.insert_many(
        [
            {
                "_id": asset_id,
                "wedding_id": primary_id,
                "wedding_slug": wedding_slug,
                "upload_batch_id": f"marketing_capture_guest_batch_{index + 1:02d}",
                "uploader_name": uploader_name,
                "event_type": event_type,
                "media_type": "image",
                "mime_type": "image/jpeg",
                "size_bytes": size_bytes,
                "original_filename": filename,
                "original_bucket": "local-demo-guest-memories",
                "original_key": f"guest-media/{wedding_slug}/demo/{filename}",
                "demo_preview_url": preview_url,
                "stream_uid": None,
                "stream_status": None,
                "stream_playback_base_url": None,
                "review_status": review_status,
                "visibility": "couple_only",
                "upload_status": "uploaded",
                "uploaded_at": now - timedelta(minutes=45 + index * 7),
                "reviewed_at": (
                    now - timedelta(minutes=18 + index * 4)
                    if review_status in {"kept", "rejected"}
                    else None
                ),
                "created_at": now - timedelta(hours=2, minutes=index * 5),
                "updated_at": now - timedelta(minutes=10 + index),
                "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
                "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
            }
            for index, (
                asset_id,
                uploader_name,
                filename,
                review_status,
                event_type,
                preview_url,
                size_bytes,
            ) in enumerate(memory_fixtures)
        ],
        ordered=False,
    )
    return str(ensured["upload_token"])


async def _seed_form_fixture(
    primary_id: str,
    planner_email: str,
    couple_email: str | None,
    *,
    couple_names: str,
    partner1_name: str,
) -> tuple[str, str]:
    from bson import ObjectId

    from app.core.database import mongo

    now = _utc_now()
    couple_form_object_id = ObjectId(DEMO_COUPLE_FORM_ID)
    common_form = {
        "title": "Couple Intake Questionnaire",
        "description": "A short planning intake for timeline, priorities, and VIP details.",
        "name": "Couple Intake Questionnaire",
        "settings": {
            "title": "Couple Intake Questionnaire",
            "description": "A short planning intake for timeline, priorities, and VIP details.",
            "submit_button_text": "Send intake",
            "success_message": "Thanks. Your planner has the details.",
            "allow_multiple_submissions": True,
            "collect_email": True,
            "is_public": True,
            "requires_auth": False,
        },
        "fields": [
            {
                "id": "full_name",
                "label": "Your name",
                "type": "text",
                "required": True,
                "order": 1,
                "placeholder": partner1_name,
            },
            {
                "id": "priorities",
                "label": "Top planning priorities",
                "type": "textarea",
                "required": True,
                "order": 2,
                "placeholder": "Guest comfort, ceremony timing, and vendor handoffs.",
            },
            {
                "id": "vip_count",
                "label": "VIP family count",
                "type": "number",
                "required": False,
                "order": 3,
            },
        ],
        "created_by": planner_email,
        "owner_email": planner_email,
        "wedding_id": primary_id,
        "shared_with_couple": True,
        "target_audience": "couple",
        "couple_email": couple_email,
        "is_active": True,
        "template_type": "couple_intake",
        "submission_count": 1,
        "unread_responses": 1,
        "planner_state": {"seed_source": MARKETING_CAPTURE_SEED_SOURCE},
        "created_at": now - timedelta(days=3),
        "updated_at": now,
        "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
        "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
    }
    await _replace_seed_owned_document(
        mongo.get_forms_collection(),
        {"_id": DEMO_PUBLIC_FORM_ID, **common_form, "shared_with_couple": False},
    )
    couple_form = {
        **common_form,
        "title": "Final Detail Confirmation",
        "description": "A final confirmation form for VIP contacts, arrival windows, and day-of preferences.",
        "name": "Final Detail Confirmation",
        "settings": {
            **common_form["settings"],
            "title": "Final Detail Confirmation",
            "description": "A final confirmation form for VIP contacts, arrival windows, and day-of preferences.",
        },
        "submission_count": 0,
        "unread_responses": 0,
    }
    await _replace_seed_owned_document(
        mongo.get_forms_collection(),
        {"_id": couple_form_object_id, **couple_form},
    )
    await mongo.get_collection("form_responses").delete_many(
        {
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
            "wedding_id": primary_id,
            "form_id": DEMO_PUBLIC_FORM_ID,
        }
    )
    response_email = couple_email or DEMO_COUPLE_EMAIL
    await mongo.get_collection("form_responses").insert_one(
        {
            "_id": "form_response_marketing_capture_couple_intake_1",
            "form_id": DEMO_PUBLIC_FORM_ID,
            "wedding_id": primary_id,
            "respondent_email": response_email,
            "respondent_name": partner1_name,
            "submitted_by_email": response_email,
            "submitted_by_name": partner1_name,
            "responses": {
                "full_name": partner1_name,
                "priorities": "Keep the ceremony calm, protect photo time, and make vendor handoffs invisible.",
                "vip_count": 14,
            },
            "submitted_at": now - timedelta(days=2),
            "created_at": now - timedelta(days=2),
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        }
    )
    await mongo.get_collection("form_submissions").delete_many(
        {
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
            "wedding_id": primary_id,
            "form_id": DEMO_COUPLE_FORM_ID,
        }
    )
    if couple_email:
        await mongo.get_collection("form_submissions").insert_one(
            {
                "_id": "form_submission_marketing_capture_couple_intake_1",
                "form_id": DEMO_COUPLE_FORM_ID,
                "wedding_id": primary_id,
                "submitted_by": couple_email,
                "submitted_by_name": couple_names,
                "submitted_by_type": "couple",
                "responses": {
                    "full_name": partner1_name,
                    "priorities": "Keep the ceremony calm, protect photo time, and make vendor handoffs invisible.",
                    "vip_count": 14,
                },
                "submitted_at": now - timedelta(days=2),
                "updated_at": now - timedelta(days=2),
                "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
                "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
            }
        )
    await mongo.get_collection("form_distributions").delete_many(
        {
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
            "wedding_id": primary_id,
            "form_id": DEMO_PUBLIC_FORM_ID,
        }
    )
    await mongo.get_collection("form_distributions").insert_one(
        {
            "_id": "form_distribution_marketing_capture_1",
            "form_id": DEMO_PUBLIC_FORM_ID,
            "wedding_id": primary_id,
            "recipient_email": couple_email or DEMO_COUPLE_EMAIL,
            "recipient_name": couple_names,
            "status": "completed",
            "sent_at": now - timedelta(days=3),
            "opened_at": now - timedelta(days=2, hours=8),
            "submitted_at": now - timedelta(days=2),
            "created_at": now - timedelta(days=3),
            "updated_at": now - timedelta(days=2),
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        }
    )
    return DEMO_PUBLIC_FORM_ID, DEMO_COUPLE_FORM_ID


async def _seed_budget_fixture(primary_id: str) -> None:
    from app.core.database import mongo

    now = _utc_now()
    payment_records = [
        {
            "_id": ObjectId("67c700000000000000000001"),
            "id": ObjectId("67c700000000000000000001"),
            "category_id": "budget_marketing_capture_planning",
            "vendor_name": "Marigold & Co. Weddings",
            "amount": 3200.0,
            "payment_method": "transfer",
            "payment_date": now - timedelta(days=16),
            "description": "Planning retainer and production kickoff",
            "status": "completed",
            "notes": "Retainer logged from the signed planning agreement.",
            "created_at": now - timedelta(days=16),
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        },
        {
            "_id": ObjectId("67c700000000000000000002"),
            "id": ObjectId("67c700000000000000000002"),
            "category_id": "budget_marketing_capture_venue",
            "vendor_name": "The Glasshouse at Riverbend",
            "amount": 12000.0,
            "payment_method": "transfer",
            "payment_date": now - timedelta(days=14),
            "description": "Venue deposit for ceremony and reception spaces",
            "status": "completed",
            "notes": "Contracted date hold and venue production deposit.",
            "created_at": now - timedelta(days=14),
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        },
        {
            "_id": ObjectId("67c700000000000000000003"),
            "id": ObjectId("67c700000000000000000003"),
            "category_id": "budget_marketing_capture_venue",
            "vendor_name": "Harvest Table Catering",
            "amount": 6000.0,
            "payment_method": "card",
            "payment_date": now - timedelta(days=12),
            "description": "Catering deposit after tasting approval",
            "status": "completed",
            "notes": "Menu includes cocktail hour bites, dinner service, and late-night snacks.",
            "created_at": now - timedelta(days=12),
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        },
        {
            "_id": ObjectId("67c700000000000000000004"),
            "id": ObjectId("67c700000000000000000004"),
            "category_id": "budget_marketing_capture_photo",
            "vendor_name": DEMO_VENDOR_BUSINESS_NAME,
            "amount": 1700.0,
            "payment_method": "transfer",
            "payment_date": now - timedelta(days=10),
            "description": "Photo and video retainer",
            "status": "completed",
            "notes": "Matches the assigned photography and video vendor.",
            "created_at": now - timedelta(days=10),
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        },
        {
            "_id": ObjectId("67c700000000000000000005"),
            "id": ObjectId("67c700000000000000000005"),
            "category_id": "budget_marketing_capture_attire",
            "vendor_name": "Mira Bridal Atelier",
            "amount": 5400.0,
            "payment_method": "card",
            "payment_date": now - timedelta(days=9),
            "description": "Attire balance and alterations package",
            "status": "completed",
            "notes": "Includes final fittings and pressing.",
            "created_at": now - timedelta(days=9),
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        },
        {
            "_id": ObjectId("67c700000000000000000006"),
            "id": ObjectId("67c700000000000000000006"),
            "category_id": "budget_marketing_capture_attire",
            "vendor_name": "Glow Room Beauty",
            "amount": 2000.0,
            "payment_method": "card",
            "payment_date": now - timedelta(days=8),
            "description": "Hair and makeup trial plus booking deposit",
            "status": "completed",
            "notes": "Bride, moms, and wedding party beauty team deposit.",
            "created_at": now - timedelta(days=8),
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        },
        {
            "_id": ObjectId("67c700000000000000000007"),
            "id": ObjectId("67c700000000000000000007"),
            "category_id": "budget_marketing_capture_guest_experience",
            "vendor_name": "Paper Moon Stationery",
            "amount": 2600.0,
            "payment_method": "check",
            "payment_date": now - timedelta(days=6),
            "description": "Invitation suite, day-of signage, and escort cards",
            "status": "completed",
            "notes": "Proofs approved by the couple.",
            "created_at": now - timedelta(days=6),
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        },
        {
            "_id": ObjectId("67c700000000000000000008"),
            "id": ObjectId("67c700000000000000000008"),
            "category_id": "budget_marketing_capture_guest_experience",
            "vendor_name": "Atlas Coach",
            "amount": 2000.0,
            "payment_method": "transfer",
            "payment_date": now - timedelta(days=4),
            "description": "Transportation retainer for hotel-to-venue shuttles",
            "status": "pending",
            "notes": "Pending bank confirmation; final route list due next week.",
            "created_at": now - timedelta(days=4),
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        },
        {
            "_id": ObjectId("67c700000000000000000009"),
            "id": ObjectId("67c700000000000000000009"),
            "category_id": "budget_marketing_capture_attire",
            "vendor_name": "Mira Bridal Atelier",
            "amount": 2750.0,
            "payment_method": "card",
            "payment_date": now - timedelta(days=7),
            "description": "Final tailoring, pressing, and delivery balance",
            "status": "completed",
            "notes": "Final alteration invoice reconciled after the last fitting.",
            "created_at": now - timedelta(days=7),
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        },
    ]
    payments_by_category: dict[str, list[dict[str, Any]]] = {}
    for payment in payment_records:
        category_id = str(payment["category_id"])
        payments_by_category.setdefault(category_id, []).append(
            {
                "id": str(payment["id"]),
                "category_id": category_id,
                "vendor_name": payment["vendor_name"],
                "amount": payment["amount"],
                "payment_method": payment["payment_method"],
                "payment_date": payment["payment_date"],
                "description": payment["description"],
                "status": payment["status"],
                "notes": payment["notes"],
                "created_at": payment["created_at"],
            }
        )
    categories = [
        {
            "_id": "budget_marketing_capture_planning",
            "name": "Planning & Production",
            "description": "Full-service planning, production management, and event-day staffing.",
            "budgeted_amount": 12800.0,
            "actual_spent": 3200.0,
            "payment_status": "partial",
            "priority": 1,
            "percentage_of_total": 15.5,
        },
        {
            "_id": "budget_marketing_capture_venue",
            "name": "Venue & Catering",
            "description": "Reception venue, catering package, staffing, and service fees.",
            "budgeted_amount": 42000.0,
            "actual_spent": 18000.0,
            "payment_status": "partial",
            "priority": 1,
            "percentage_of_total": 50.9,
        },
        {
            "_id": "budget_marketing_capture_photo",
            "name": "Photography & Video",
            "description": "Photography coverage, second shooter, gallery delivery, and short-form video.",
            "budgeted_amount": 6800.0,
            "actual_spent": 1700.0,
            "payment_status": "partial",
            "priority": 2,
            "percentage_of_total": 8.2,
        },
        {
            "_id": "budget_marketing_capture_attire",
            "name": "Attire & Beauty",
            "description": "Wedding attire, alterations, hair, makeup, and getting-ready support.",
            "budgeted_amount": 9200.0,
            "actual_spent": 10150.0,
            "payment_status": "partial",
            "priority": 3,
            "percentage_of_total": 11.2,
        },
        {
            "_id": "budget_marketing_capture_guest_experience",
            "name": "Guest Experience",
            "description": "Transportation, welcome bags, signage, stationery, and late-night snacks.",
            "budgeted_amount": 11700.0,
            "actual_spent": 4600.0,
            "payment_status": "partial",
            "priority": 3,
            "percentage_of_total": 14.2,
        },
    ]
    vendor_quote_records = [
        {
            "_id": ObjectId("67c800000000000000000001"),
            "wedding_id": primary_id,
            "vendor_id": "67c400000000000000000001",
            "category_id": "budget_marketing_capture_photo",
            "vendor_name": "DFam Productions",
            "vendor_email": "dfam.productions@vendors.thespecialwedding.io",
            "vendor_phone": "(405) 555-0198",
            "service_category": "photography",
            "quote_amount": 7600.0,
            "quote_details": {
                "coverage_hours": 10,
                "photo_team": "2 photographers",
                "video_team": "2 videographers",
                "highlight_film": "5-7 minutes",
                "gallery_delivery": "6 weeks",
            },
            "includes": [
                "Engagement session",
                "Wedding-day photo and video coverage",
                "Drone coverage when venue rules allow",
                "Edited online gallery",
                "Short-form social preview reel",
            ],
            "excludes": [
                "Same-day edit",
                "Raw unedited footage",
            ],
            "terms_conditions": "30% retainer due on signing; remaining balance due 14 days before the wedding.",
            "status": "pending",
            "valid_until": now + timedelta(days=21),
            "notes": "Strong fit for combined photography and videography coverage.",
            "rating": 5,
            "created_at": now - timedelta(days=5),
            "updated_at": now - timedelta(days=2),
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        },
        {
            "_id": ObjectId("67c800000000000000000002"),
            "wedding_id": primary_id,
            "vendor_id": "67c400000000000000000002",
            "category_id": "budget_marketing_capture_photo",
            "vendor_name": DEMO_VENDOR_BUSINESS_NAME,
            "vendor_email": DEMO_VENDOR_EMAIL,
            "vendor_phone": "(312) 555-0131",
            "service_category": "photography",
            "quote_amount": 6800.0,
            "quote_details": {
                "coverage_hours": 10,
                "photo_team": "2 photographers",
                "video_team": "short-form add-on",
                "gallery_delivery": "6 weeks",
            },
            "includes": [
                "Timeline review",
                "Two photographers",
                "Preview gallery within 72 hours",
                "Final edited gallery",
            ],
            "excludes": [
                "Full ceremony film",
                "Drone coverage",
            ],
            "terms_conditions": "25% retainer due on signing; final payment due 10 days before event.",
            "status": "pending",
            "valid_until": now + timedelta(days=14),
            "notes": "Best still-photo package, but video scope is lighter than DFam.",
            "rating": 4,
            "created_at": now - timedelta(days=6),
            "updated_at": now - timedelta(days=3),
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        },
        {
            "_id": ObjectId("67c800000000000000000003"),
            "wedding_id": primary_id,
            "category_id": "budget_marketing_capture_photo",
            "vendor_name": "Golden Hour Collective",
            "vendor_email": "golden.hour@vendors.thespecialwedding.io",
            "vendor_phone": "(405) 555-0197",
            "service_category": "photography",
            "quote_amount": 5900.0,
            "quote_details": {
                "coverage_hours": 8,
                "photo_team": "lead photographer + second shooter",
                "video_team": "not included",
                "gallery_delivery": "8 weeks",
            },
            "includes": [
                "Eight hours of wedding-day coverage",
                "Second shooter",
                "Online proofing gallery",
                "Print release",
            ],
            "excludes": [
                "Videography",
                "Engagement session",
                "Travel outside Oklahoma City metro",
            ],
            "terms_conditions": "40% retainer due on signing; overtime billed hourly.",
            "status": "pending",
            "valid_until": now + timedelta(days=10),
            "notes": "Lowest price, but missing video and shorter coverage window.",
            "rating": 3,
            "created_at": now - timedelta(days=7),
            "updated_at": now - timedelta(days=4),
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        },
    ]
    await mongo.get_collection("budget_categories").delete_many(
        {
            "wedding_id": primary_id,
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        }
    )
    await mongo.get_collection("payment_records").delete_many(
        {
            "category_id": {"$in": [str(category["_id"]) for category in categories]},
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        }
    )
    await mongo.db["vendor_quotes"].delete_many(
        {
            "wedding_id": primary_id,
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        }
    )
    await mongo.get_collection("payment_records").insert_many(payment_records)
    await mongo.db["vendor_quotes"].insert_many(vendor_quote_records)
    await mongo.get_collection("budget_categories").insert_many(
        [
            {
                **category,
                "wedding_id": primary_id,
                "subcategories": [],
                "vendor_quotes": [
                    str(quote["_id"])
                    for quote in vendor_quote_records
                    if quote.get("category_id") == category["_id"]
                ],
                "payments": payments_by_category.get(str(category["_id"]), []),
                "created_at": now - timedelta(days=18),
                "updated_at": now,
                "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
                "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
            }
            for category in categories
        ]
    )


async def _seed_service_packages_fixture(planner: dict[str, Any]) -> None:
    from app.core.database import mongo

    now = _utc_now()
    planner_id = str(planner["_id"])
    packages = [
        {
            "_id": ObjectId("67c310000000000000000001"),
            "planner_id": planner_id,
            "name": "Signature Planning + Production",
            "description": "Full-service planning, production management, budget oversight, vendor orchestration, and wedding-week command center.",
            "services": [
                {
                    "name": "Planning command center setup",
                    "description": "Build the couple portal, microsite, RSVP flow, shared calendar, and planning dashboard.",
                    "included": True,
                },
                {
                    "name": "Vendor and contract management",
                    "description": "Coordinate vendor onboarding, contract status, payment milestones, and quote comparisons.",
                    "included": True,
                },
                {
                    "name": "Wedding-week production",
                    "description": "Run-of-show, seating checks, guest communications, and event-day team briefings.",
                    "included": True,
                },
            ],
            "total_amount": 12800.0,
            "currency": "usd",
            "payment_schedule": [
                {"name": "Retainer", "trigger": "on_signing", "amount": 3200.0},
                {
                    "name": "Design lock",
                    "trigger": "fixed_date",
                    "fixed_date": (now + timedelta(days=45)).date().isoformat(),
                    "amount": 4800.0,
                },
                {
                    "name": "Final production",
                    "trigger": "days_before_wedding",
                    "days_before": 21,
                    "amount": 4800.0,
                },
            ],
            "cancellation_policy": "Retainer is non-refundable once planning production begins. Date transfers are reviewed case by case.",
            "late_payment_policy": "Late balances may pause vendor outreach and final production deliverables until resolved.",
            "custom_terms": "Includes one lead planner, two event-day assistants, and all shared workspace setup.",
            "is_template": False,
            "status": "active",
            "contracts_count": 3,
            "created_at": now - timedelta(days=32),
            "updated_at": now - timedelta(days=1),
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        },
        {
            "_id": ObjectId("67c310000000000000000002"),
            "planner_id": planner_id,
            "name": "Month-of Coordination",
            "description": "A lighter package for couples who planned most details and need final logistics, vendor confirmation, and event-week execution.",
            "services": [
                {
                    "name": "Final detail intake",
                    "description": "Import the couple's vendor list, timeline, RSVP status, and outstanding decisions.",
                    "included": True,
                },
                {
                    "name": "Timeline and seating review",
                    "description": "Clean up run-of-show, seating constraints, and event-day communication plans.",
                    "included": True,
                },
                {
                    "name": "Event-day coordination",
                    "description": "Lead vendor arrivals, cue ceremony/reception moments, and resolve guest-service issues.",
                    "included": True,
                },
            ],
            "total_amount": 4800.0,
            "currency": "usd",
            "payment_schedule": [
                {
                    "name": "Booking payment",
                    "trigger": "on_signing",
                    "percentage": 50.0,
                },
                {
                    "name": "Wedding-week balance",
                    "trigger": "days_before_wedding",
                    "days_before": 14,
                    "percentage": 50.0,
                },
            ],
            "cancellation_policy": "Booking payment is non-refundable after kickoff.",
            "late_payment_policy": "Final balance is due before the wedding-week production call.",
            "custom_terms": "Best for couples with confirmed vendor contracts and a working guest list.",
            "is_template": False,
            "status": "active",
            "contracts_count": 1,
            "created_at": now - timedelta(days=24),
            "updated_at": now - timedelta(days=3),
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        },
        {
            "_id": ObjectId("67c310000000000000000003"),
            "planner_id": planner_id,
            "name": "Luxury Destination Weekend",
            "description": "Template for multi-day celebrations with travel logistics, concierge guest support, and expanded vendor production.",
            "services": [
                {
                    "name": "Weekend itinerary design",
                    "description": "Build a multi-event guest itinerary, travel FAQ, and vendor arrival plan.",
                    "included": True,
                },
                {
                    "name": "Guest concierge workflow",
                    "description": "Coordinate VIP arrivals, hotel blocks, shuttles, and event access messaging.",
                    "included": True,
                },
                {
                    "name": "Expanded production team",
                    "description": "Plan staffing coverage across welcome party, ceremony, reception, and farewell brunch.",
                    "included": True,
                },
            ],
            "total_amount": 24500.0,
            "currency": "usd",
            "payment_schedule": [
                {
                    "name": "Strategy retainer",
                    "trigger": "on_signing",
                    "percentage": 30.0,
                },
                {
                    "name": "Production lock",
                    "trigger": "days_after_signing",
                    "days_after": 60,
                    "percentage": 40.0,
                },
                {
                    "name": "Final logistics",
                    "trigger": "days_before_wedding",
                    "days_before": 30,
                    "percentage": 30.0,
                },
            ],
            "cancellation_policy": "Destination retainers are non-refundable once travel planning begins.",
            "late_payment_policy": "Late balances may pause travel concierge and vendor-production handoffs.",
            "custom_terms": "Template package used for destination inquiries; customize after discovery.",
            "is_template": True,
            "status": "draft",
            "contracts_count": 0,
            "created_at": now - timedelta(days=18),
            "updated_at": now - timedelta(days=4),
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        },
    ]
    await mongo.get_collection("packages").delete_many(
        {
            "planner_id": planner_id,
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        }
    )
    await mongo.get_collection("packages").insert_many(packages)


def _demo_schedule_start(hour_offset: int) -> datetime:
    now = datetime.now(MARKETING_CAPTURE_TIMEZONE)
    start = (now + timedelta(hours=hour_offset)).replace(
        minute=0,
        second=0,
        microsecond=0,
    )
    if start.month != now.month:
        start = now.replace(hour=20, minute=0, second=0, microsecond=0)
    return start.astimezone(timezone.utc)


def _calendar_fixture_doc(
    *,
    object_id: str,
    planner: dict[str, Any],
    primary_id: str,
    title: str,
    description: str,
    start_date: datetime,
    duration_minutes: int,
    category: str,
    priority: str,
    schedule_item_type: str,
    couple_names: str,
    status: str = "pending",
    couple_email: str | None = None,
    color: str | None = None,
) -> dict[str, Any]:
    planner_email = str(planner["email"])
    planner_id = str(planner["_id"])
    end_date = start_date + timedelta(minutes=duration_minutes)
    return {
        "_id": ObjectId(object_id),
        "planner_email": planner_email,
        "owner_planner_id": planner_id,
        "owner_planner_email": planner_email,
        "created_by_user_id": planner_id,
        "created_by_email": planner_email,
        "assigned_user_ids": [planner_id, str(MARKETING_CAPTURE_TEAM_USER_ID)],
        "assigned_user_emails": [planner_email, MARKETING_CAPTURE_TEAM_EMAIL],
        "wedding_id": primary_id,
        "title": title,
        "description": description,
        "category": category,
        "priority": priority,
        "status": status,
        "schedule_item_type": schedule_item_type,
        "visibility_mode": "details",
        "calendar_sync_policy": "owner_only",
        "sync_target_override_enabled": False,
        "sync_target_connection_ids": [],
        "external_sync_requested": False,
        "start_date": start_date,
        "end_date": end_date,
        "all_day": False,
        "due_date": end_date if schedule_item_type == "task" else None,
        "timezone": "America/Chicago",
        "couple_attendee_emails": [couple_email] if couple_email else [],
        "external_attendees": [],
        "conference_provider": None,
        "conference_url": None,
        "invite_delivery_mode": "portal_only"
        if schedule_item_type == "meeting"
        else "none",
        "meeting_status": "scheduled" if schedule_item_type == "meeting" else None,
        "reminder_minutes": 60,
        "is_recurring": False,
        "recurrence_rule": None,
        "color": color,
        "notes": f"Demo-video fixture for the {couple_names} planning timeline.",
        "attachments": [],
        "created_at": _utc_now() - timedelta(days=5),
        "updated_at": _utc_now(),
        "version": 1,
        "completed_at": None,
        "external_conflict_status": "none",
        "external_conflict_source": None,
        "external_conflict_detected_at": None,
        "external_last_modified_at": None,
        "external_start_date": None,
        "external_end_date": None,
        "external_title": None,
        "external_description": None,
        "external_location": None,
        "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
        "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
    }


async def _seed_calendar_fixture(
    primary_id: str,
    planner: dict[str, Any],
    couple_email: str | None,
    *,
    couple_names: str,
) -> None:
    from app.core.database import mongo

    base_start = _demo_schedule_start(10)
    docs = [
        _calendar_fixture_doc(
            object_id="67c500000000000000000001",
            planner=planner,
            primary_id=primary_id,
            title=f"{couple_names} final timeline review",
            description="Confirm ceremony handoff, cocktail hour flow, reception entrances, and vendor cue sheet.",
            start_date=base_start,
            duration_minutes=75,
            category="meeting",
            priority="high",
            schedule_item_type="meeting",
            couple_email=couple_email,
            color="#0f766e",
            couple_names=couple_names,
        ),
        _calendar_fixture_doc(
            object_id="67c500000000000000000002",
            planner=planner,
            primary_id=primary_id,
            title="Vendor load-in confirmation",
            description="Verify venue access windows for decor, catering, photography, and entertainment teams.",
            start_date=base_start + timedelta(hours=2),
            duration_minutes=45,
            category="reception",
            priority="urgent",
            schedule_item_type="task",
            status="in_progress",
            color="#d97706",
            couple_names=couple_names,
        ),
        _calendar_fixture_doc(
            object_id="67c500000000000000000003",
            planner=planner,
            primary_id=primary_id,
            title="Family photo list final pass",
            description="Review VIP groupings, couple portraits, and post-ceremony family photo order.",
            start_date=base_start + timedelta(hours=4),
            duration_minutes=60,
            category="photography",
            priority="medium",
            schedule_item_type="meeting",
            couple_email=couple_email,
            color="#7c3aed",
            couple_names=couple_names,
        ),
        _calendar_fixture_doc(
            object_id="67c500000000000000000004",
            planner=planner,
            primary_id=primary_id,
            title="RSVP and seating checkpoint",
            description="Lock the current guest count, table assignments, and meal-note exceptions before final print.",
            start_date=base_start + timedelta(hours=6),
            duration_minutes=30,
            category="guest_management",
            priority="high",
            schedule_item_type="task",
            color="#2563eb",
            couple_names=couple_names,
        ),
    ]

    await mongo.get_planner_tasks_collection().delete_many(
        {
            "wedding_id": primary_id,
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        }
    )
    await mongo.get_planner_tasks_collection().insert_many(docs)


async def _seed_vendor_directory_fixture(
    primary_id: str,
    planner_email: str,
    *,
    couple_names: str,
) -> str:
    from app.core.database import mongo

    now = _utc_now()
    for index, fixture in enumerate(DEMO_VENDOR_DIRECTORY_FIXTURES):
        vendor_object_id = ObjectId(fixture["profile_id"])
        assignment_object_id = ObjectId(fixture["assignment_id"])
        vendor = {
            "_id": vendor_object_id,
            "created_by": planner_email,
            "business_name": fixture["business_name"],
            "contact_name": fixture["contact_name"],
            "email": fixture["email"],
            "phone": fixture["phone"],
            "website": fixture["website"],
            "address": f"{1200 + index * 37} Meridian Ave",
            "city": fixture["city"],
            "state": fixture["state"],
            "country": "US",
            "postal_code": "73102",
            "service_category": fixture["service_category"],
            "custom_service_category": None,
            "service_subcategories": fixture["service_subcategories"],
            "service_description": fixture["service_description"],
            "typical_price_min": fixture["typical_price_min"],
            "typical_price_max": fixture["typical_price_max"],
            "currency": "USD",
            "is_preferred": index < 4,
            "source": "manual",
            "tags": ["preferred", "wedding day ready"]
            if index < 4
            else ["shortlisted"],
            "notes": "Preferred for polished communication, clear scope, and reliable event-week follow-through.",
            "internal_notes": "Confirmed scope, contact preferences, and event-week follow-through.",
            "internal_rating": 5 if index in {0, 1, 3} else 4,
            "portfolio_urls": [],
            "weddings_count": 3 if index < 4 else 1,
            "total_revenue": float(
                fixture.get("contracted_amount") or fixture["quoted_amount"]
            ),
            "is_active": True,
            "last_used_at": now - timedelta(days=3 + index),
            "created_at": now - timedelta(days=24 - index),
            "updated_at": now,
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        }
        await _replace_seed_owned_document(
            mongo.get_collection("vendor_profiles"),
            vendor,
        )

        assignment = {
            "_id": assignment_object_id,
            "wedding_id": primary_id,
            "vendor_profile_id": fixture["profile_id"],
            "budget_category_id": fixture.get("budget_category_id"),
            "status": fixture["status"],
            "vendor_name": vendor["business_name"],
            "vendor_email": vendor["email"],
            "service_category": vendor["service_category"],
            "custom_service_category": None,
            "quote_ids": [],
            "contract_id": fixture.get("contract_id"),
            "service_notes": f"{vendor['business_name']} is attached to the {couple_names} production plan.",
            "quoted_amount": fixture["quoted_amount"],
            "contracted_amount": fixture["contracted_amount"],
            "paid_amount": fixture["paid_amount"],
            "is_deleted": False,
            "created_by": planner_email,
            "created_at": now - timedelta(days=12 - index),
            "updated_at": now,
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        }
        await _replace_seed_owned_document(
            mongo.get_collection("vendor_assignments"),
            assignment,
        )
    return DEMO_VENDOR_PROFILE_ID


async def _seed_vendor_contract_fixture(
    primary_id: str,
    planner_email: str,
    *,
    couple_names: str,
) -> str:
    from app.core.database import mongo
    from app.models.vendor import ContractKind, ContractStatus
    from app.models.vendor_contracts import VendorContractActivityType
    from app.services.vendor_service import vendor_service

    now = _utc_now()
    wedding = await mongo.get_weddings_collection().find_one({"_id": primary_id}) or {}
    planner = (
        await mongo.get_users_collection().find_one({"email": planner_email}) or {}
    )
    planner_first_name = str(
        planner.get("first_name")
        or planner.get("user_data", {}).get("first_name")
        or ""
    ).strip()
    planner_last_name = str(
        planner.get("last_name") or planner.get("user_data", {}).get("last_name") or ""
    ).strip()
    planner_name = " ".join(
        part for part in [planner_first_name, planner_last_name] if part
    ).strip()
    planner_company = str(
        planner.get("company_name")
        or planner.get("user_data", {}).get("company_name")
        or "Marigold & Co. Weddings"
    ).strip()
    wedding_date = wedding.get("date")
    service_date = (
        datetime.fromisoformat(str(wedding_date)).replace(tzinfo=timezone.utc)
        if isinstance(wedding_date, str) and wedding_date
        else None
    )
    service_location = str(
        wedding.get("venue") or "The Glasshouse at Riverbend, Chicago, IL"
    ).strip()
    status_lookup = {
        "draft": ContractStatus.DRAFT.value,
        "sent": ContractStatus.SENT.value,
        "viewed": ContractStatus.VIEWED.value,
        "signed": ContractStatus.SIGNED.value,
    }
    await mongo.get_collection("vendor_payment_milestones").delete_many(
        {
            "wedding_id": primary_id,
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        }
    )
    await mongo.get_collection("vendor_contract_activities").delete_many(
        {
            "wedding_id": primary_id,
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        }
    )
    for index, fixture in enumerate(
        item for item in DEMO_VENDOR_DIRECTORY_FIXTURES if item.get("contract_id")
    ):
        contract_object_id = ObjectId(fixture["contract_id"])
        access_token_hash = vendor_service._hash_contract_access_token(fixture["token"])
        contract_status = status_lookup[str(fixture["contract_status"])]
        sent_at = (
            now - timedelta(days=4 - index)
            if contract_status != ContractStatus.DRAFT.value
            else None
        )
        viewed_at = (
            now - timedelta(days=3 - index)
            if contract_status
            in {ContractStatus.VIEWED.value, ContractStatus.SIGNED.value}
            else None
        )
        signed_at = (
            now - timedelta(days=2)
            if contract_status == ContractStatus.SIGNED.value
            else None
        )
        contract = {
            "_id": contract_object_id,
            "wedding_id": primary_id,
            "vendor_profile_id": fixture["profile_id"],
            "budget_category_id": fixture.get("budget_category_id"),
            "vendor_name": fixture["business_name"],
            "vendor_email": fixture["email"],
            "vendor_phone": fixture["phone"],
            "planner_name": planner_name or planner_company or "Wedding Planner",
            "planner_company": planner_company
            or planner_name
            or "Marigold & Co. Weddings",
            "couple_names": couple_names,
            "wedding_date": service_date,
            "service_date": service_date,
            "service_location": service_location,
            "service_category": fixture["service_category"],
            "custom_service_category": None,
            "contract_title": fixture["contract_title"],
            "contract_number": fixture["contract_number"],
            "sections": [
                {
                    "id": "scope",
                    "title": "Scope of Services",
                    "content": f"{fixture['business_name']} will provide {fixture['service_description']}",
                    "order": 0,
                },
                {
                    "id": "delivery",
                    "title": "Deliverables",
                    "content": "Planner receives a confirmed scope, event-week contact, and final production notes before the wedding weekend.",
                    "order": 1,
                },
            ],
            "terms_and_conditions": "Planner and vendor will coordinate final timing, access, and setup requirements through the shared wedding workspace.",
            "cancellation_policy": "Cancellation and rescheduling terms follow the signed proposal and require written confirmation from both parties.",
            "custom_clauses": "Vendor must confirm final arrival window and emergency contact before event week.",
            "total_amount": fixture["contracted_amount"],
            "currency": "USD",
            "deposit_amount": fixture["deposit_amount"],
            "status": contract_status,
            "access_token_hash": access_token_hash,
            "token_expires_at": now + timedelta(days=30),
            "token_revoked_at": None,
            "token_last_sent_at": sent_at,
            "token_last_viewed_at": viewed_at,
            "created_by": planner_email,
            "created_at": now - timedelta(days=8 - index),
            "updated_at": now - timedelta(days=index),
            "version_number": 1,
            "root_contract_id": str(contract_object_id),
            "parent_contract_id": None,
            "supersedes_contract_id": None,
            "superseded_by_contract_id": None,
            "is_current_version": True,
            "contract_kind": ContractKind.ORIGINAL.value,
            "amendment_reason": None,
            "superseded_at": None,
            "sent_at": sent_at,
            "viewed_at": viewed_at,
            "signed_at": signed_at,
            "signed_by_name": fixture["contact_name"] if signed_at else None,
            "signed_by_email": fixture["email"] if signed_at else None,
            "signature_ip": "127.0.0.1" if signed_at else None,
            "internal_notes": f"Scope reviewed for the {couple_names} production plan.",
            "is_soft_deleted": False,
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        }
        await _replace_seed_owned_document(
            mongo.get_collection("vendor_contracts"),
            contract,
        )
        if signed_at:
            activity_type = VendorContractActivityType.CONTRACT_SIGNED
            activity_title = "Contract signed"
            activity_description = f"{fixture['business_name']} signed the contract."
            actor_type = "vendor"
            actor_identifier = fixture["email"]
            actor_display_name = fixture["contact_name"]
            activity_created_at = signed_at
        elif viewed_at:
            activity_type = VendorContractActivityType.CONTRACT_VIEWED
            activity_title = "Contract viewed"
            activity_description = f"{fixture['business_name']} viewed the contract."
            actor_type = "vendor"
            actor_identifier = fixture["email"]
            actor_display_name = fixture["contact_name"]
            activity_created_at = viewed_at
        elif sent_at:
            activity_type = VendorContractActivityType.CONTRACT_SENT
            activity_title = "Contract sent"
            activity_description = f"Sent to {fixture['business_name']} for review."
            actor_type = "planner"
            actor_identifier = planner_email
            actor_display_name = planner_name or "Amina Cole"
            activity_created_at = sent_at
        else:
            activity_type = VendorContractActivityType.CONTRACT_CREATED
            activity_title = "Contract created"
            activity_description = f"Created for {fixture['business_name']}."
            actor_type = "planner"
            actor_identifier = planner_email
            actor_display_name = planner_name or "Amina Cole"
            activity_created_at = contract["created_at"]
        await _replace_seed_owned_document(
            mongo.get_collection("vendor_contract_activities"),
            {
                "_id": ObjectId(f"67ce00000000000000000{index + 1:03d}"),
                "contract_id": fixture["contract_id"],
                "root_contract_id": str(contract_object_id),
                "wedding_id": primary_id,
                "vendor_profile_id": fixture["profile_id"],
                "activity_type": activity_type.value,
                "title": activity_title,
                "description": activity_description,
                "actor": {
                    "type": actor_type,
                    "identifier": actor_identifier,
                    "display_name": actor_display_name,
                },
                "metadata": {"contract_number": fixture["contract_number"]},
                "created_at": activity_created_at,
                "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
                "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
            },
        )

        remaining_amount = max(
            float(fixture["contracted_amount"]) - float(fixture["paid_amount"]),
            0.0,
        )
        milestone_docs = [
            {
                "_id": ObjectId(f"67c800000000000000000{index * 2 + 1:03d}"),
                "contract_id": fixture["contract_id"],
                "wedding_id": primary_id,
                "vendor_profile_id": fixture["profile_id"],
                "budget_category_id": fixture.get("budget_category_id"),
                "description": f"{fixture['business_name']} retainer",
                "amount": fixture["paid_amount"],
                "currency": "USD",
                "percentage_of_total": round(
                    (
                        float(fixture["paid_amount"])
                        / float(fixture["contracted_amount"])
                    )
                    * 100,
                    1,
                )
                if fixture["contracted_amount"]
                else None,
                "due_date": now - timedelta(days=10 - index),
                "days_before_event": None,
                "status": "paid" if fixture["paid_amount"] > 0 else "pending",
                "paid_amount": fixture["paid_amount"],
                "paid_at": now - timedelta(days=9 - index)
                if fixture["paid_amount"] > 0
                else None,
                "payment_method": "bank_transfer"
                if fixture["paid_amount"] > 0
                else None,
                "vendor_name": fixture["business_name"],
                "vendor_email": fixture["email"],
                "created_by": planner_email,
                "created_at": now - timedelta(days=12 - index),
                "updated_at": now - timedelta(days=8 - index),
                "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
                "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
            }
        ]
        if remaining_amount > 0:
            milestone_docs.append(
                {
                    "_id": ObjectId(f"67c800000000000000000{index * 2 + 2:03d}"),
                    "contract_id": fixture["contract_id"],
                    "wedding_id": primary_id,
                    "vendor_profile_id": fixture["profile_id"],
                    "budget_category_id": fixture.get("budget_category_id"),
                    "description": f"{fixture['business_name']} final balance",
                    "amount": remaining_amount,
                    "currency": "USD",
                    "percentage_of_total": round(
                        (remaining_amount / float(fixture["contracted_amount"])) * 100,
                        1,
                    ),
                    "due_date": now + timedelta(days=14 + index * 3),
                    "days_before_event": 30,
                    "status": "pending",
                    "paid_amount": 0.0,
                    "paid_at": None,
                    "payment_method": None,
                    "vendor_name": fixture["business_name"],
                    "vendor_email": fixture["email"],
                    "created_by": planner_email,
                    "created_at": now - timedelta(days=8 - index),
                    "updated_at": now,
                    "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
                    "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
                }
            )
        await mongo.get_collection("vendor_payment_milestones").insert_many(
            milestone_docs
        )
    return DEMO_VENDOR_CONTRACT_ID


async def _seed_client_contract_portal_fixture(
    primary_id: str,
    planner: dict[str, Any],
    *,
    couple_names: str,
    partner1_name: str,
    partner2_name: str,
) -> str:
    from bson import ObjectId

    from app.core.database import mongo

    now = _utc_now()
    wedding = await mongo.get_weddings_collection().find_one({"_id": primary_id}) or {}
    planner_email = str(planner.get("email") or "")
    planner_id = str(planner.get("_id") or planner_email)
    couple_email = wedding.get("couple_portal_email") or os.getenv("SMOKE_COUPLE_EMAIL")
    contract_object_id = ObjectId(DEMO_CLIENT_CONTRACT_ID)
    wedding_date = wedding.get("date")
    if isinstance(wedding_date, str):
        wedding_date_value = datetime.fromisoformat(wedding_date).replace(
            tzinfo=timezone.utc
        )
    elif isinstance(wedding_date, datetime):
        wedding_date_value = wedding_date
    else:
        wedding_date_value = now + timedelta(days=132)

    package_snapshot = {
        "name": "Signature Planning + Production",
        "total_amount": 12800,
        "currency": "usd",
        "payment_schedule": [
            {"name": "Retainer", "amount": 3200, "trigger": "on_signing"},
            {
                "name": "Design lock",
                "amount": 4800,
                "trigger": "fixed_date",
                "fixed_date": (now + timedelta(days=45)).date().isoformat(),
            },
            {
                "name": "Final production",
                "amount": 4800,
                "trigger": "days_before_wedding",
                "days_before": 21,
            },
        ],
    }
    contract = {
        "_id": contract_object_id,
        "planner_id": planner_id,
        "wedding_id": primary_id,
        "vendor_profile_id": "vendor_marketing_capture_signature_planning",
        "vendor_name": "The Special Wedding Studio",
        "vendor_email": planner_email,
        "contract_title": f"{couple_names} - Signature Planning + Production",
        "contract_number": "CLIENT-DEMO-VIDEO-001",
        "token": DEMO_CLIENT_PORTAL_TOKEN,
        "status": "active",
        "couple": {
            "email": couple_email,
            "partner1_name": partner1_name,
            "partner2_name": partner2_name,
            "name": partner1_name,
            "partner_name": partner2_name,
        },
        "wedding_date": wedding_date_value,
        "venue": "The Glasshouse at Meridian",
        "package_snapshot": package_snapshot,
        "total_amount": 12800,
        "deposit_amount": 3200,
        "currency": "usd",
        "payment_method_last4": "4242",
        "payment_method_brand": "visa",
        "planner_name": planner.get("company_name") or "The Special Wedding Studio",
        "planner_email": planner_email,
        "planner_phone": "(312) 555-0100",
        "sent_at": now - timedelta(days=9),
        "viewed_at": now - timedelta(days=8),
        "signed_at": now - timedelta(days=7),
        "completed_at": None,
        "cancelled_at": None,
        "created_at": now - timedelta(days=11),
        "updated_at": now,
        "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
        "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
    }
    await _replace_seed_owned_document(
        mongo.get_collection("contracts"),
        contract,
    )

    await mongo.get_collection("scheduled_payments").delete_many(
        {
            "contract_id": str(contract_object_id),
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        }
    )
    await mongo.get_collection("scheduled_payments").insert_many(
        [
            {
                "_id": ObjectId("67c300000000000000000101"),
                "contract_id": str(contract_object_id),
                "planner_id": planner_id,
                "name": "Retainer",
                "amount": 3200,
                "currency": "usd",
                "due_date": now - timedelta(days=7),
                "status": "succeeded",
                "paid_at": now - timedelta(days=7),
                "receipt_url": "https://payments.thespecialwedding.io/receipts/planning-retainer",
                "created_at": now - timedelta(days=11),
                "updated_at": now - timedelta(days=7),
                "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
                "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
            },
            {
                "_id": ObjectId("67c300000000000000000102"),
                "contract_id": str(contract_object_id),
                "planner_id": planner_id,
                "name": "Design lock",
                "amount": 4800,
                "currency": "usd",
                "due_date": now + timedelta(days=45),
                "status": "scheduled",
                "paid_at": None,
                "receipt_url": None,
                "created_at": now - timedelta(days=11),
                "updated_at": now,
                "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
                "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
            },
            {
                "_id": ObjectId("67c300000000000000000103"),
                "contract_id": str(contract_object_id),
                "planner_id": planner_id,
                "name": "Final production",
                "amount": 4800,
                "currency": "usd",
                "due_date": wedding_date_value - timedelta(days=21),
                "status": "scheduled",
                "paid_at": None,
                "receipt_url": None,
                "created_at": now - timedelta(days=11),
                "updated_at": now,
                "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
                "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
            },
            {
                "_id": ObjectId("67c300000000000000000104"),
                "contract_id": str(contract_object_id),
                "planner_id": planner_id,
                "name": "Welcome dinner add-on",
                "amount": 650,
                "currency": "usd",
                "due_date": now - timedelta(days=1),
                "status": "failed",
                "paid_at": None,
                "receipt_url": None,
                "retry_count": 1,
                "last_error": "Payment method requires an update",
                "next_retry_at": now + timedelta(days=2),
                "created_at": now - timedelta(days=6),
                "updated_at": now - timedelta(hours=8),
                "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
                "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
            },
        ]
    )
    return DEMO_CLIENT_PORTAL_TOKEN


async def _seed_planner_notifications_fixture(
    primary_id: str,
    planner_email: str,
    *,
    couple_names: str,
) -> None:
    from app.core.database import mongo

    now = _utc_now()
    notifications = [
        {
            "_id": ObjectId("67c320000000000000000001"),
            "planner_id": planner_email,
            "wedding_id": primary_id,
            "type": "rsvp_update",
            "title": "12 RSVPs confirmed overnight",
            "message": f"{couple_names} crossed 140 confirmed guests after the weekend reminder.",
            "metadata": {"confirmed_count": 140, "source": "reminder_follow_up"},
            "priority": "medium",
            "action_url": f"/admin/guests?weddingId={primary_id}",
            "is_read": False,
            "created_at": now - timedelta(hours=2, minutes=10),
            "read_at": None,
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        },
        {
            "_id": ObjectId("67c320000000000000000002"),
            "planner_id": planner_email,
            "wedding_id": primary_id,
            "type": "form_submission",
            "title": "Couple intake updated",
            "message": "Sofia added family-photo priorities and VIP arrival notes to the final detail form.",
            "metadata": {
                "form": "Final Detail Confirmation",
                "respondent": "Sofia Carter",
            },
            "priority": "high",
            "action_url": "/admin/forms",
            "is_read": False,
            "created_at": now - timedelta(hours=5, minutes=35),
            "read_at": None,
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        },
        {
            "_id": ObjectId("67c320000000000000000003"),
            "planner_id": planner_email,
            "wedding_id": primary_id,
            "type": "payment_received",
            "title": "Client retainer payment received",
            "message": "$3,200 retainer posted for the Signature Planning + Production agreement.",
            "metadata": {"amount": 3200, "package": "Signature Planning + Production"},
            "priority": "medium",
            "action_url": "/admin/money",
            "is_read": True,
            "created_at": now - timedelta(days=1, hours=1),
            "read_at": now - timedelta(hours=22),
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        },
        {
            "_id": ObjectId("67c320000000000000000004"),
            "planner_id": planner_email,
            "wedding_id": primary_id,
            "type": "contract_signed",
            "title": "Photography contract signed",
            "message": f"{DEMO_VENDOR_BUSINESS_NAME} signed the updated services agreement.",
            "metadata": {
                "vendor": DEMO_VENDOR_BUSINESS_NAME,
                "contract_status": "signed",
            },
            "priority": "medium",
            "action_url": "/admin/vendors",
            "is_read": True,
            "created_at": now - timedelta(days=1, hours=4),
            "read_at": now - timedelta(days=1, hours=3),
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        },
        {
            "_id": ObjectId("67c320000000000000000005"),
            "planner_id": planner_email,
            "wedding_id": primary_id,
            "type": "vendor_response",
            "title": "Venue production note answered",
            "message": "The Glasshouse confirmed ceremony rain-plan timing and vendor load-in access.",
            "metadata": {"vendor": "The Glasshouse at Riverbend", "topic": "rain_plan"},
            "priority": "medium",
            "action_url": "/admin/planner/calendar",
            "is_read": False,
            "created_at": now - timedelta(days=2, hours=2),
            "read_at": None,
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        },
        {
            "_id": ObjectId("67c320000000000000000006"),
            "planner_id": planner_email,
            "wedding_id": primary_id,
            "type": "reminder",
            "title": "Final seating check due",
            "message": "Review meal constraints and family grouping before the final RSVP sync.",
            "metadata": {"workflow": "seating", "unseated": 8},
            "priority": "low",
            "action_url": f"/admin/seating?weddingId={primary_id}",
            "is_read": True,
            "created_at": now - timedelta(days=2, hours=8),
            "read_at": now - timedelta(days=2, hours=7),
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        },
    ]
    await mongo.get_collection("planner_notifications").delete_many(
        {
            "planner_id": planner_email,
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        }
    )
    await mongo.get_collection("planner_notifications").insert_many(notifications)


def _write_capture_fixtures(fixtures: dict[str, Any]) -> None:
    fixture_path = ROOT / "output" / "demo-videos" / "capture-fixtures.json"
    fixture_path.parent.mkdir(parents=True, exist_ok=True)
    fixture_path.write_text(f"{json.dumps(fixtures, indent=2, sort_keys=True)}\n")


async def seed_demo_workspace(args: argparse.Namespace) -> None:
    from app.core.database import mongo

    global _CAPTURE_ANCHOR_UTC
    _CAPTURE_ANCHOR_UTC = _configure_anchor(args.anchor_at)
    planner_email = _planner_email(args)
    planner = await _load_planner(planner_email)
    primary_id = args.primary_wedding_id
    secondary_id = args.secondary_wedding_id

    await _assert_capture_namespace_available(
        planner,
        primary_id=primary_id,
        primary_slug=args.primary_slug,
        secondary_id=secondary_id,
        secondary_slug=args.secondary_slug,
    )

    await _migrate_legacy_smoke_workspace()
    planner = await _load_planner(planner_email)

    await mongo.get_users_collection().update_one(
        {
            "_id": planner["_id"],
            "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
            "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
        },
        {
            "$set": {
                "onboarding_completed": True,
                "onboarding_completed_at": _utc_now(),
                "onboarding_steps_completed": [
                    "welcome",
                    "site-essentials",
                    "optional-content",
                    "dashboard",
                    "ready",
                ],
                "ai_credits_remaining": 999,
                "plan_id": DEMO_PLAN_ID,
                "subscription_status": "active",
                "first_name": MARKETING_CAPTURE_PLANNER_FIRST_NAME,
                "last_name": MARKETING_CAPTURE_PLANNER_LAST_NAME,
                "company_name": MARKETING_CAPTURE_COMPANY,
                "business_name": MARKETING_CAPTURE_COMPANY,
                "user_data.first_name": MARKETING_CAPTURE_PLANNER_FIRST_NAME,
                "user_data.last_name": MARKETING_CAPTURE_PLANNER_LAST_NAME,
                "user_data.company_name": MARKETING_CAPTURE_COMPANY,
                "user_data.business_name": MARKETING_CAPTURE_COMPANY,
                "seed_source": MARKETING_CAPTURE_SEED_SOURCE,
                "seed_scope": MARKETING_CAPTURE_SEED_SCOPE,
                "updated_at": _utc_now(),
            },
        },
    )
    planner = {
        **planner,
        "first_name": MARKETING_CAPTURE_PLANNER_FIRST_NAME,
        "last_name": MARKETING_CAPTURE_PLANNER_LAST_NAME,
        "company_name": MARKETING_CAPTURE_COMPANY,
        "business_name": MARKETING_CAPTURE_COMPANY,
        "user_data": {
            **(planner.get("user_data") or {}),
            "first_name": MARKETING_CAPTURE_PLANNER_FIRST_NAME,
            "last_name": MARKETING_CAPTURE_PLANNER_LAST_NAME,
            "company_name": MARKETING_CAPTURE_COMPANY,
            "business_name": MARKETING_CAPTURE_COMPANY,
        },
    }
    await _seed_demo_subscription(planner)

    await _upsert_wedding(
        wedding_id=primary_id,
        slug=args.primary_slug,
        couple_names=args.primary_couple_names,
        partner1_name=args.primary_partner1_name,
        partner2_name=args.primary_partner2_name,
        planner=planner,
        date=args.primary_date,
        ready=True,
    )
    await _upsert_wedding(
        wedding_id=secondary_id,
        slug=args.secondary_slug,
        couple_names=args.secondary_couple_names,
        partner1_name=args.secondary_couple_names.split(" & ", 1)[0],
        partner2_name=(
            args.secondary_couple_names.split(" & ", 1)[1]
            if " & " in args.secondary_couple_names
            else ""
        ),
        planner=planner,
        date=args.secondary_date,
        ready=False,
    )
    await _seed_accepted_team_fixture(planner, primary_id)
    couple_email = await _seed_couple_portal_fixture(
        primary_id,
        planner,
        couple_names=args.primary_couple_names,
        partner1_name=args.primary_partner1_name,
        partner2_name=args.primary_partner2_name,
    )
    await _seed_people_and_activity(
        primary_id,
        secondary_id,
        planner_email,
        secondary_couple_names=args.secondary_couple_names,
    )
    await _seed_seating_fixture(primary_id, secondary_id)
    await _seed_ai_cache(primary_id, planner)
    await _seed_knowledge_base_fixture(planner)
    await _seed_gallery_fixture(primary_id, planner_email, args.primary_slug)
    upload_token = await _seed_guest_media_fixture(
        primary_id,
        couple_names=args.primary_couple_names,
        partner1_name=args.primary_partner1_name,
        partner2_name=args.primary_partner2_name,
    )
    public_form_id, couple_form_id = await _seed_form_fixture(
        primary_id,
        planner_email,
        couple_email,
        couple_names=args.primary_couple_names,
        partner1_name=args.primary_partner1_name,
    )
    await _seed_budget_fixture(primary_id)
    await _seed_service_packages_fixture(planner)
    await _seed_calendar_fixture(
        primary_id,
        planner,
        couple_email,
        couple_names=args.primary_couple_names,
    )
    await _seed_communications_fixture(
        primary_id,
        planner_email,
        wedding_slug=args.primary_slug,
        couple_names=args.primary_couple_names,
    )
    vendor_profile_id = await _seed_vendor_directory_fixture(
        primary_id,
        planner_email,
        couple_names=args.primary_couple_names,
    )
    vendor_contract_id = await _seed_vendor_contract_fixture(
        primary_id,
        planner_email,
        couple_names=args.primary_couple_names,
    )
    client_portal_token = await _seed_client_contract_portal_fixture(
        primary_id,
        planner,
        couple_names=args.primary_couple_names,
        partner1_name=args.primary_partner1_name,
        partner2_name=args.primary_partner2_name,
    )
    await _seed_planner_notifications_fixture(
        primary_id,
        planner_email,
        couple_names=args.primary_couple_names,
    )

    _write_capture_fixtures(
        {
            "plannerEmail": planner_email,
            "teamMemberEmail": MARKETING_CAPTURE_TEAM_EMAIL,
            "coupleEmail": couple_email,
            "publicOrigin": MARKETING_CAPTURE_PUBLIC_ORIGIN,
            "anchorAt": _utc_now().isoformat(),
            "seedSource": MARKETING_CAPTURE_SEED_SOURCE,
            "seedScope": MARKETING_CAPTURE_SEED_SCOPE,
            "primaryWeddingId": primary_id,
            "primarySlug": args.primary_slug,
            "secondaryWeddingId": secondary_id,
            "secondarySlug": args.secondary_slug,
            "knowledgeBaseArticleSlug": DEMO_KB_ARTICLE_SLUG,
            "guestMemoriesUploadToken": upload_token,
            "formId": public_form_id,
            "coupleFormId": couple_form_id,
            "vendorProfileId": vendor_profile_id,
            "vendorContractId": vendor_contract_id,
            "vendorContractToken": DEMO_VENDOR_CONTRACT_TOKEN,
            "clientContractPortalToken": client_portal_token,
            "vendorPortalToken": DEMO_VENDOR_CONTRACT_TOKEN,
            "seededAt": _utc_now().isoformat(),
        }
    )

    print(
        "[OK] Marketing capture workspace seeded: "
        f"planner={planner_email} primary={primary_id} secondary={secondary_id}"
    )

    mongo.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed the isolated local marketing-capture workspace"
    )
    parser.add_argument("--planner-email")
    parser.add_argument(
        "--anchor-at",
        default=os.getenv("MARKETING_CAPTURE_ANCHOR_AT", DEFAULT_CAPTURE_ANCHOR_LOCAL),
        help=(
            "ISO-8601 capture anchor. Naive values are interpreted in "
            f"{MARKETING_CAPTURE_TIMEZONE_NAME}."
        ),
    )
    parser.add_argument(
        "--primary-wedding-id",
        default=_demo_env("PRIMARY_WEDDING_ID", DEFAULT_PRIMARY_WEDDING_ID),
    )
    parser.add_argument(
        "--primary-slug", default=_demo_env("PRIMARY_SLUG", DEFAULT_PRIMARY_SLUG)
    )
    parser.add_argument("--primary-date")
    parser.add_argument(
        "--primary-couple-names",
        default=_demo_env("PRIMARY_COUPLE_NAMES", DEFAULT_PRIMARY_COUPLE_NAMES),
    )
    parser.add_argument(
        "--primary-partner1-name",
        default=_demo_env("PRIMARY_PARTNER1_NAME", DEFAULT_PRIMARY_PARTNER1_NAME),
    )
    parser.add_argument(
        "--primary-partner2-name",
        default=_demo_env("PRIMARY_PARTNER2_NAME", DEFAULT_PRIMARY_PARTNER2_NAME),
    )
    parser.add_argument(
        "--secondary-wedding-id",
        default=_demo_env("SECONDARY_WEDDING_ID", DEFAULT_SECONDARY_WEDDING_ID),
    )
    parser.add_argument(
        "--secondary-slug", default=_demo_env("SECONDARY_SLUG", DEFAULT_SECONDARY_SLUG)
    )
    parser.add_argument("--secondary-date")
    parser.add_argument(
        "--secondary-couple-names",
        default=_demo_env("SECONDARY_COUPLE_NAMES", DEFAULT_SECONDARY_COUPLE_NAMES),
    )
    args = parser.parse_args()
    _assert_demo_seed_allowed(args)
    global _CAPTURE_ANCHOR_UTC
    _CAPTURE_ANCHOR_UTC = _configure_anchor(args.anchor_at)
    args.primary_date = args.primary_date or _demo_env(
        "PRIMARY_DATE", DEFAULT_PRIMARY_DATE
    )
    args.secondary_date = args.secondary_date or _demo_env(
        "SECONDARY_DATE", DEFAULT_SECONDARY_DATE
    )
    asyncio.run(seed_demo_workspace(args))


if __name__ == "__main__":
    main()
