#!/usr/bin/env python3
"""
Seed runtime smoke planner, wedding, and couple accounts when configured.

This complements scripts/setup_admin_user.py. Root-admin seeding remains
separate. This script is intentionally idempotent and skip-friendly so it can
run on every container start without blocking application boot.

Supported runtime env vars:
  Generic:
    SMOKE_PLANNER_EMAIL / SMOKE_PLANNER_PASSWORD
    SMOKE_ADMIN_EMAIL / SMOKE_ADMIN_PASSWORD   (legacy alias)
    SMOKE_COUPLE_EMAIL / SMOKE_COUPLE_PASSWORD
    SMOKE_PUBLIC_WEDDING_SLUG

  Environment-scoped fallback (based on ENVIRONMENT):
    STAGING_SMOKE_...
    PRODUCTION_SMOKE_...
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Mapping, Optional
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


SEED_SOURCE = "system:smoke_account_seed"


@dataclass(frozen=True)
class SmokePlannerConfig:
    email: str
    password: str
    company_name: str
    first_name: str
    last_name: str
    user_id: str
    plan_id: Optional[str]


@dataclass(frozen=True)
class SmokeWeddingConfig:
    wedding_id: str
    slug: str
    couple_names: str
    date: str


@dataclass(frozen=True)
class SmokeCoupleConfig:
    email: str
    password: str
    partner1_name: str
    partner2_name: Optional[str]
    couple_id: str


@dataclass(frozen=True)
class SmokeSeedConfig:
    scope: str
    planner: SmokePlannerConfig
    wedding: SmokeWeddingConfig
    couple: Optional[SmokeCoupleConfig]


class SmokeSeedConflict(RuntimeError):
    """Raised when smoke seeding would overwrite a non-smoke identity."""


def _non_empty(value: object) -> Optional[str]:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _current_scope(environ: Mapping[str, str]) -> str:
    return (_non_empty(environ.get("ENVIRONMENT")) or "development").lower()


def _read_scoped_env(environ: Mapping[str, str], *names: str) -> Optional[str]:
    """Read a generic env var first, then the ENVIRONMENT-scoped variant."""
    scope = _current_scope(environ).upper()
    for name in names:
        value = _non_empty(environ.get(name))
        if value:
            return value
    for name in names:
        value = _non_empty(environ.get(f"{scope}_{name}"))
        if value:
            return value
    return None


def normalize_public_slug(value: object) -> Optional[str]:
    raw = _non_empty(value)
    if not raw:
        return None

    parsed = urlparse(raw)
    if parsed.scheme and parsed.netloc:
        raw = parsed.path

    normalized = raw.strip().lstrip("/")
    return normalized or None


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9\s-]", "", value.lower())
    slug = re.sub(r"[\s_]+", "-", slug).strip("-")
    return slug or "demo-wedding"


def _display_name_from_scope(scope: str, suffix: str) -> str:
    label = scope.replace("_", " ").strip().title() or "Demo"
    return f"{label} {suffix}"


def build_smoke_seed_config(
    environ: Mapping[str, str], now: Optional[datetime] = None
) -> Optional[SmokeSeedConfig]:
    scope = _current_scope(environ)

    planner_email = _read_scoped_env(
        environ, "SMOKE_PLANNER_EMAIL", "SMOKE_ADMIN_EMAIL"
    )
    planner_password = _read_scoped_env(
        environ, "SMOKE_PLANNER_PASSWORD", "SMOKE_ADMIN_PASSWORD"
    )

    if not planner_email or not planner_password:
        return None

    planner_email = planner_email.strip().lower()
    company_name = _read_scoped_env(
        environ, "SMOKE_PLANNER_COMPANY_NAME"
    ) or _display_name_from_scope(scope, "Event Studio")
    planner_first_name = (
        _read_scoped_env(environ, "SMOKE_PLANNER_FIRST_NAME")
        or "Alex"
    )
    planner_last_name = (
        _read_scoped_env(environ, "SMOKE_PLANNER_LAST_NAME") or "Planner"
    )
    planner_plan_id = _read_scoped_env(environ, "SMOKE_PLANNER_PLAN_ID")
    planner_user_id = (
        _read_scoped_env(environ, "SMOKE_PLANNER_USER_ID")
        or f"user_smoke_{_slugify(scope)}_planner"
    )

    couple_email = _read_scoped_env(environ, "SMOKE_COUPLE_EMAIL")
    couple_password = _read_scoped_env(environ, "SMOKE_COUPLE_PASSWORD")
    partner1_name = _read_scoped_env(environ, "SMOKE_COUPLE_PARTNER1_NAME") or "Taylor"
    partner2_name = _read_scoped_env(environ, "SMOKE_COUPLE_PARTNER2_NAME") or "Jordan"

    couple_config: Optional[SmokeCoupleConfig] = None
    if couple_email and couple_password:
        couple_config = SmokeCoupleConfig(
            email=couple_email.strip().lower(),
            password=couple_password,
            partner1_name=partner1_name,
            partner2_name=partner2_name,
            couple_id=(
                _read_scoped_env(environ, "SMOKE_COUPLE_ID")
                or f"couple_smoke_{_slugify(scope)}"
            ),
        )

    wedding_couple_names = _read_scoped_env(environ, "SMOKE_WEDDING_COUPLE_NAMES")
    if not wedding_couple_names and couple_config:
        if couple_config.partner2_name:
            wedding_couple_names = (
                f"{couple_config.partner1_name} & {couple_config.partner2_name}"
            )
        else:
            wedding_couple_names = couple_config.partner1_name
    if not wedding_couple_names:
        wedding_couple_names = "Taylor & Jordan"

    wedding_slug = normalize_public_slug(
        _read_scoped_env(environ, "SMOKE_PUBLIC_WEDDING_SLUG", "SMOKE_WEDDING_SLUG")
    ) or _slugify(wedding_couple_names)

    effective_now = now or datetime.now(timezone.utc)
    wedding_date = (
        _read_scoped_env(environ, "SMOKE_WEDDING_DATE")
        or (effective_now + timedelta(days=180)).date().isoformat()
    )
    wedding_id = (
        _read_scoped_env(environ, "SMOKE_WEDDING_ID")
        or f"wedding_smoke_{_slugify(scope)}"
    )

    return SmokeSeedConfig(
        scope=scope,
        planner=SmokePlannerConfig(
            email=planner_email,
            password=planner_password,
            company_name=company_name,
            first_name=planner_first_name,
            last_name=planner_last_name,
            user_id=planner_user_id,
            plan_id=planner_plan_id,
        ),
        wedding=SmokeWeddingConfig(
            wedding_id=wedding_id,
            slug=wedding_slug,
            couple_names=wedding_couple_names,
            date=wedding_date,
        ),
        couple=couple_config,
    )


def _stable_str_id(value: object) -> Optional[str]:
    normalized = _non_empty(value)
    return normalized


async def _ensure_planner_account(config: SmokeSeedConfig) -> str:
    from app.core.database import mongo
    from app.utils.auth_utils import get_password_hash

    users = mongo.get_users_collection()
    now = datetime.now(timezone.utc)
    existing = await users.find_one({"email": config.planner.email})

    if existing and existing.get("role") == "ROOT_ADMIN":
        raise SmokeSeedConflict(
            f"Smoke planner email {config.planner.email} belongs to ROOT_ADMIN"
        )

    planner_id = (
        _stable_str_id(existing.get("_id")) if existing else config.planner.user_id
    )
    if not planner_id:
        planner_id = config.planner.user_id

    update_fields = {
        "email": config.planner.email,
        "password_hash": get_password_hash(config.planner.password),
        "role": "wedding_planner",
        "first_name": config.planner.first_name,
        "last_name": config.planner.last_name,
        "company_name": config.planner.company_name,
        "subscription_status": "active",
        "is_active": True,
        "email_verified": True,
        "registration_source": "smoke_seed",
        "max_weddings": 5,
        "ai_credits_remaining": 999,
        "timezone": "America/Chicago",
        "updated_at": now,
        "seed_source": SEED_SOURCE,
        "seed_scope": config.scope,
    }
    if config.planner.plan_id:
        update_fields["plan_id"] = config.planner.plan_id

    if existing:
        await users.update_one({"_id": existing["_id"]}, {"$set": update_fields})
        print(f"[OK] Smoke planner synced: {config.planner.email}")
        return planner_id

    doc = {
        "_id": planner_id,
        **update_fields,
        "created_at": now,
    }
    await users.insert_one(doc)
    print(f"[CREATED] Smoke planner: {config.planner.email}")
    return planner_id


def _default_smoke_events(wedding_date: str) -> list[dict]:
    return [
        {
            "type": "traditional",
            "date": wedding_date,
            "details": {
                "venue_name": "Riverside Hall",
                "location": "Oklahoma City, OK",
                "time": "4:00 PM",
            },
            "order_of_events": [],
            "event_notes": [],
        }
    ]


async def _ensure_smoke_wedding(config: SmokeSeedConfig, planner_id: str) -> str:
    from app.core.database import mongo
    from app.utils.planner_ownership import wedding_belongs_to_owner

    weddings = mongo.get_weddings_collection()
    now = datetime.now(timezone.utc)
    by_id = await weddings.find_one({"_id": config.wedding.wedding_id})
    by_slug = await weddings.find_one({"slug": config.wedding.slug})

    if (
        by_id
        and by_slug
        and _stable_str_id(by_id.get("_id")) != _stable_str_id(by_slug.get("_id"))
    ):
        raise SmokeSeedConflict(
            f"Smoke wedding id {config.wedding.wedding_id} and slug {config.wedding.slug} point to different documents"
        )

    existing = by_id or by_slug
    if existing and not (
        existing.get("seed_source") == SEED_SOURCE
        or wedding_belongs_to_owner(existing, planner_id, config.planner.email)
    ):
        raise SmokeSeedConflict(
            f"Wedding slug {config.wedding.slug} already belongs to another owner"
        )

    wedding_id = (
        _stable_str_id(existing.get("_id")) if existing else config.wedding.wedding_id
    )
    if not wedding_id:
        wedding_id = config.wedding.wedding_id

    update_fields = {
        "couple_names": config.wedding.couple_names,
        "date": config.wedding.date,
        "slug": config.wedding.slug,
        "assigned_planner_id": planner_id,
        "assigned_planner_email": config.planner.email,
        "privacy_settings": {
            "privacy_mode": "public",
            "guest_auth_required": False,
            "allow_guest_sharing": True,
            "require_phone_verification": False,
            "require_name_verification": False,
        },
        "couple_portal_enabled": bool(config.couple),
        "couple_portal_email": config.couple.email if config.couple else None,
        "status": "active",
        "updated_at": now,
        "updated_by": SEED_SOURCE,
        "seed_source": SEED_SOURCE,
        "seed_scope": config.scope,
    }

    insert_fields = {
        "_id": wedding_id,
        "events": _default_smoke_events(config.wedding.date),
        "registries": [],
        "faqs": [],
        "created_at": now,
        "created_by": SEED_SOURCE,
    }

    if existing:
        await weddings.update_one(
            {"_id": existing["_id"]},
            {"$set": update_fields, "$setOnInsert": insert_fields},
        )
        print(f"[OK] Smoke wedding synced: {config.wedding.slug}")
        return wedding_id

    doc = {**insert_fields, **update_fields}
    await weddings.insert_one(doc)
    print(f"[CREATED] Smoke wedding: {config.wedding.slug}")
    return wedding_id


async def _ensure_smoke_couple(
    config: SmokeSeedConfig, wedding_id: str, planner_id: str
) -> None:
    from app.core.database import mongo
    from app.utils.auth_utils import get_password_hash

    couple = config.couple
    if not couple:
        print(
            "[SKIP] SMOKE_COUPLE_EMAIL/SMOKE_COUPLE_PASSWORD not set. Couple seed skipped."
        )
        return

    now = datetime.now(timezone.utc)
    couples = mongo.get_couple_users_collection()
    existing = await couples.find_one({"email": couple.email})

    if existing and existing.get("wedding_id") not in (None, wedding_id):
        if existing.get("seed_source") != SEED_SOURCE:
            raise SmokeSeedConflict(
                f"Smoke couple email {couple.email} is already linked to wedding {existing.get('wedding_id')}"
            )

    couple_id = _stable_str_id(existing.get("_id")) if existing else couple.couple_id
    if not couple_id:
        couple_id = couple.couple_id

    update_fields = {
        "email": couple.email,
        "partner1_name": couple.partner1_name,
        "partner2_name": couple.partner2_name,
        "wedding_id": wedding_id,
        "planner_id": planner_id,
        "planner_email": config.planner.email,
        "password_hash": get_password_hash(couple.password),
        "setup_completed": True,
        "is_active": True,
        "access_state": "active",
        "wedding_archived": False,
        "archived_at": None,
        "invite_token": None,
        "invite_token_expires": None,
        "last_login": None,
        "owner_cancelled_at": None,
        "owner_cancelled_by_planner_id": None,
        "owner_cancelled_by_planner_email": None,
        "revoked_at": None,
        "revoked_by": None,
        "onboarding_completed": True,
        "onboarding_completed_at": now,
        "onboarding_steps_completed": [
            "welcome",
            "overview",
            "guest_tracker",
            "messages",
        ],
        "updated_at": now,
        "seed_source": SEED_SOURCE,
        "seed_scope": config.scope,
    }

    if existing:
        await couples.update_one({"_id": existing["_id"]}, {"$set": update_fields})
        print(f"[OK] Smoke couple synced: {couple.email}")
        return

    doc = {
        "_id": couple_id,
        **update_fields,
        "created_at": now,
    }
    await couples.insert_one(doc)
    print(f"[CREATED] Smoke couple: {couple.email}")


async def setup_smoke_accounts(auto_create: bool = False) -> bool:
    del auto_create  # Reserved for parity with setup_admin_user.py.

    config = build_smoke_seed_config(os.environ)
    if not config:
        print(
            "[SKIP] No smoke planner credentials found. Set SMOKE_PLANNER_* or ENV-scoped STAGING_/PRODUCTION_ variants."
        )
        return True

    print(
        f"[INFO] Seeding smoke accounts for scope={config.scope} planner={config.planner.email}"
    )

    try:
        planner_id = await _ensure_planner_account(config)
        wedding_id = await _ensure_smoke_wedding(config, planner_id)
        await _ensure_smoke_couple(config, wedding_id, planner_id)
        print("[OK] Smoke account seed finished")
        return True
    except SmokeSeedConflict as exc:
        print(f"[ERROR] Smoke account seed skipped: {exc}")
        return True
    except Exception as exc:
        print(f"[ERROR] Smoke account seed failed: {exc}")
        return True
    finally:
        try:
            from app.core.database import mongo

            mongo.close()
        except Exception:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed smoke planner/couple accounts")
    parser.add_argument(
        "--auto-create",
        action="store_true",
        help="Retained for CLI parity with setup_admin_user.py",
    )
    args = parser.parse_args()
    result = asyncio.run(setup_smoke_accounts(auto_create=args.auto_create))
    raise SystemExit(0 if result else 1)


if __name__ == "__main__":
    main()
