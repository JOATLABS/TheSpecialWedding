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
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from bson import ObjectId

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DEMO_SEED_SOURCE = "system:demo_video_seed"
DEFAULT_PRIMARY_WEDDING_ID = "wedding_demo_video_maya_jordan"
DEFAULT_PRIMARY_SLUG = "maya-jordan-demo"
DEFAULT_SECONDARY_WEDDING_ID = "wedding_demo_video_harper_sol"
DEFAULT_SECONDARY_SLUG = "harper-sol-demo"
NON_PRODUCTION_ENVIRONMENTS = {"development", "dev", "local", "test", "testing", "ci"}
DEMO_SUBSCRIPTION_ID = "demo_video_signature_subscription"
DEMO_PLAN_ID = "plan_signature"
DEMO_PUBLIC_FORM_ID = "form_demo_couple_intake"
DEMO_COUPLE_FORM_ID = "64f200000000000000000001"
DEMO_VENDOR_CONTRACT_ID = "64f100000000000000000001"
DEMO_VENDOR_CONTRACT_TOKEN = "demo-vendor-contract-token"
DEMO_CLIENT_CONTRACT_ID = "64f300000000000000000001"
DEMO_CLIENT_PORTAL_TOKEN = "demo-contract-payment-portal-token"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _date_from_now(days: int) -> str:
    return (_utc_now() + timedelta(days=days)).date().isoformat()


def _planner_email(args: argparse.Namespace) -> str:
    email = args.planner_email or os.getenv("SMOKE_PLANNER_EMAIL")
    if not email:
        raise RuntimeError(
            "Planner email is required. Pass --planner-email or set SMOKE_PLANNER_EMAIL."
        )
    return email.strip().lower()


def _assert_demo_seed_allowed(args: argparse.Namespace) -> None:
    environment = os.getenv("ENVIRONMENT", os.getenv("NODE_ENV", "development")).strip().lower()
    if environment in NON_PRODUCTION_ENVIRONMENTS:
        return
    if args.allow_nonlocal:
        return
    raise RuntimeError(
        "Refusing to seed demo-video data outside a local/test environment. "
        f"Current ENVIRONMENT/NODE_ENV is {environment!r}. "
        "Pass --allow-nonlocal only for an intentional disposable demo database."
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
    return planner


def _guest_doc(
    *,
    wedding_id: str,
    index: int,
    name: str,
    group_id: str,
    invited_days_ago: int,
    plus_ones: int = 0,
    table_id: str | None = None,
    email_domain: str = "example.test",
) -> dict[str, Any]:
    guest_id = ObjectId(hashlib.sha256(f"{wedding_id}:{index}".encode("utf-8")).hexdigest()[:24])
    invited_at = _utc_now() - timedelta(days=invited_days_ago)
    phone_suffix = f"{5500 + index:04d}"
    token_prefix = "".join(ch for ch in wedding_id if ch.isalnum())[-8:].upper()
    return {
        "_id": guest_id,
        "wedding_id": wedding_id,
        "name": name,
        "token": f"{token_prefix}{index:04d}",
        "email": f"{name.lower().replace(' ', '.')}@{email_domain}",
        "phone": f"+1312555{phone_suffix}",
        "group_id": group_id,
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
        "created_at": invited_at - timedelta(days=1),
        "updated_at": _utc_now(),
        "seed_source": DEMO_SEED_SOURCE,
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
    await mongo.db["user_subscriptions"].replace_one(
        {"_id": DEMO_SUBSCRIPTION_ID},
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
            "stripe_subscription_id": "sub_demo_video_signature",
            "stripe_customer_id": "cus_demo_video_signature",
            "created_at": now - timedelta(days=3),
            "updated_at": now,
            "seed_source": DEMO_SEED_SOURCE,
        },
        upsert=True,
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
        "_id": f"rsvp_demo_{guest_id}",
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
        "seed_source": DEMO_SEED_SOURCE,
    }
    plus_ones = []
    for index, name in enumerate(plus_one_names or [], start=1):
        plus_ones.append(
            {
                "_id": f"plus_one_demo_{guest_id}_{index}",
                "wedding_id": wedding_id,
                "guest_id": guest_id,
                "name": name,
                "attending": ["traditional"] if attending else [],
                "created_at": submitted_at,
                "updated_at": submitted_at,
                "seed_source": DEMO_SEED_SOURCE,
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
    actor_email: str = "system",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    timestamp = _utc_now() - timedelta(hours=hours_ago)
    return {
        "_id": f"activity_demo_{wedding_id}_{key}",
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
        "seed_source": DEMO_SEED_SOURCE,
    }


async def _replace_seeded_docs(collection: Any, wedding_ids: list[str], docs: list[dict[str, Any]]) -> None:
    await collection.delete_many(
        {"wedding_id": {"$in": wedding_ids}, "seed_source": DEMO_SEED_SOURCE}
    )
    if docs:
        await collection.insert_many(docs)


async def _upsert_wedding(
    *,
    wedding_id: str,
    slug: str,
    couple_names: str,
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
        "date": date,
        "slug": slug,
        "assigned_planner_id": planner_id,
        "assigned_planner_email": planner_email,
        "status": "active",
        "venue": "The Glasshouse at Riverbend" if ready else "",
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
            "contact_email": planner_email,
        },
        "theme": {
            "primaryColor": "#7f1d1d",
            "accentColor": "#d4a5a5",
            "fontFamily": "serif",
        },
        "registries": [
            {"name": "Honeymoon Fund", "url": "https://example.test/honeymoon"},
            {"name": "Home Essentials", "url": "https://example.test/registry"},
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
        "updated_by": DEMO_SEED_SOURCE,
        "seed_source": DEMO_SEED_SOURCE,
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
                    {"time": "4:00 PM", "title": "Ceremony"},
                    {"time": "5:00 PM", "title": "Cocktail hour"},
                    {"time": "6:30 PM", "title": "Reception"},
                ],
                "event_notes": ["Planner arrival at 11:00 AM", "Golden-hour portraits at 6:05 PM"],
            }
        ]
        if ready
        else []
    )
    insert = {
        "created_at": now - timedelta(days=38 if ready else 9),
        "created_by": DEMO_SEED_SOURCE,
    }
    await mongo.get_weddings_collection().update_one(
        {"_id": wedding_id},
        {"$set": {**common, "events": events}, "$setOnInsert": insert},
        upsert=True,
    )


async def _seed_people_and_activity(primary_id: str, secondary_id: str, planner_email: str) -> None:
    from app.core.database import mongo

    guest_names = [
        ("Amara Bennett", "family", 16, 1, "table_head"),
        ("Theo Bennett", "family", 16, 0, "table_head"),
        ("Priya Shah", "friends", 15, 1, "table_two"),
        ("Mateo Rivera", "friends", 15, 0, "table_two"),
        ("Camille Brooks", "wedding_party", 14, 0, "table_head"),
        ("Elliot Brooks", "wedding_party", 14, 0, "table_head"),
        ("Noor Patel", "family", 13, 1, "table_three"),
        ("Jonah Park", "friends", 13, 0, "table_two"),
        ("Sofia Grant", "vendor_guest", 12, 0, "table_vendor"),
        ("Miles Carter", "friends", 12, 1, "table_three"),
        ("Leah Kim", "family", 11, 0, "table_three"),
        ("Owen Reed", "family", 11, 0, "table_four"),
        ("Nia Thompson", "friends", 10, 1, "table_four"),
        ("Ari Cohen", "friends", 10, 0, "table_four"),
        ("Grace Ellis", "family", 9, 0, "table_five"),
        ("Henry Ellis", "family", 9, 0, "table_five"),
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
        for index, (name, group, days, plus_ones, table_id) in enumerate(guest_names, start=1)
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
        plus_names = [f"{guest['name'].split()[0]} Plus One"] if attending and guest["number_of_plus_ones_allowed"] else []
        rsvp, guest_plus_ones = _rsvp_doc(
            wedding_id=primary_id,
            guest=guest,
            attending=attending,
            submitted_days_ago=max(1, 9 - index // 2),
            plus_one_names=plus_names,
            dietary="Vegetarian" if guest["name"] in {"Priya Shah", "Noor Patel"} else None,
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
    await _replace_seeded_docs(mongo.get_guest_collection(), wedding_ids, primary_guests + secondary_guests)
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
            actor_email="amara.bennett@example.test",
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
            message="Harper & Sol still needs schedule and access setup",
            activity_type="wedding_updated",
            hours_ago=25,
        ),
    ]
    await _replace_seeded_docs(mongo.get_collection("activity_logs"), wedding_ids, activities)


async def _seed_ai_cache(primary_id: str, planner: dict[str, Any]) -> None:
    from app.services.ai_cache_service import ai_cache_service
    from app.services.ai_service import ai_service

    plan = await ai_service._resolve_subscription_plan(str(planner["_id"]))
    await ai_cache_service.cache_response(
        feature="dashboard_insights",
        tenant_id=primary_id,
        context={"demo_seed": "morning-view", "version": 1},
        response={
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
                    "action_url": f"/admin/weddings/{primary_id}/seating",
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
        ttl_hours=24 * 14,
        subscription_plan=plan,
    )


async def _seed_guest_media_fixture(primary_id: str) -> str:
    from app.core.database import mongo
    from app.services.guest_media_service import guest_media_service

    wedding = await mongo.get_weddings_collection().find_one({"_id": primary_id})
    if not wedding:
        raise RuntimeError(f"Cannot seed guest media fixture; wedding {primary_id} was not found.")
    ensured = await guest_media_service.ensure_guest_media_config(wedding)
    return str(ensured["upload_token"])


async def _seed_form_fixture(
    primary_id: str, planner_email: str, couple_email: str | None
) -> tuple[str, str]:
    from bson import ObjectId

    from app.core.database import mongo

    now = _utc_now()
    couple_form_object_id = ObjectId(DEMO_COUPLE_FORM_ID)
    await mongo.get_forms_collection().delete_many(
        {"seed_source": DEMO_SEED_SOURCE}
    )
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
                "placeholder": "Maya Bennett",
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
        "planner_state": {"seed_source": DEMO_SEED_SOURCE},
        "created_at": now - timedelta(days=3),
        "updated_at": now,
        "seed_source": DEMO_SEED_SOURCE,
    }
    await mongo.get_forms_collection().replace_one(
        {"_id": DEMO_PUBLIC_FORM_ID},
        {"_id": DEMO_PUBLIC_FORM_ID, **common_form, "shared_with_couple": False},
        upsert=True,
    )
    await mongo.get_forms_collection().replace_one(
        {"_id": couple_form_object_id},
        {"_id": couple_form_object_id, **common_form},
        upsert=True,
    )
    await mongo.get_collection("form_responses").delete_many(
        {"seed_source": DEMO_SEED_SOURCE}
    )
    await mongo.get_collection("form_responses").insert_one(
        {
            "_id": "form_response_demo_couple_intake_1",
            "form_id": DEMO_PUBLIC_FORM_ID,
            "wedding_id": primary_id,
            "respondent_email": "maya.demo@example.test",
            "respondent_name": "Maya Bennett",
            "responses": {
                "full_name": "Maya Bennett",
                "priorities": "Keep the ceremony calm, protect photo time, and make vendor handoffs invisible.",
                "vip_count": 14,
            },
            "submitted_at": now - timedelta(days=2),
            "created_at": now - timedelta(days=2),
            "seed_source": DEMO_SEED_SOURCE,
        }
    )
    await mongo.get_collection("form_submissions").delete_many(
        {"seed_source": DEMO_SEED_SOURCE}
    )
    if couple_email:
        await mongo.get_collection("form_submissions").insert_one(
            {
                "_id": "form_submission_demo_couple_intake_1",
                "form_id": DEMO_COUPLE_FORM_ID,
                "wedding_id": primary_id,
                "submitted_by": couple_email,
                "submitted_by_name": "Maya & Jordan",
                "submitted_by_type": "couple",
                "responses": {
                    "full_name": "Maya Bennett",
                    "priorities": "Keep the ceremony calm, protect photo time, and make vendor handoffs invisible.",
                    "vip_count": 14,
                },
                "submitted_at": now - timedelta(days=2),
                "updated_at": now - timedelta(days=2),
                "seed_source": DEMO_SEED_SOURCE,
            }
        )
    return DEMO_PUBLIC_FORM_ID, DEMO_COUPLE_FORM_ID


async def _seed_vendor_contract_fixture(primary_id: str, planner_email: str) -> str:
    from bson import ObjectId

    from app.core.database import mongo
    from app.models.vendor import ContractKind, ContractStatus
    from app.services.vendor_service import vendor_service

    now = _utc_now()
    contract_object_id = ObjectId(DEMO_VENDOR_CONTRACT_ID)
    access_token_hash = vendor_service._hash_contract_access_token(DEMO_VENDOR_CONTRACT_TOKEN)
    contract = {
        "_id": contract_object_id,
        "wedding_id": primary_id,
        "vendor_profile_id": "vendor_demo_luna_photo",
        "budget_category_id": "budget_demo_photo",
        "vendor_name": "Luna & Co. Photography",
        "vendor_email": "luna.vendor@example.test",
        "service_category": "photographer",
        "contract_title": "Photography Services Agreement",
        "contract_number": "CON-DEMO-VIDEO-001",
        "sections": [
            {
                "id": "scope",
                "title": "Scope of Services",
                "content": "Ten hours of wedding-day photography coverage, timeline review, and edited gallery delivery.",
                "order": 0,
            },
            {
                "id": "delivery",
                "title": "Deliverables",
                "content": "Preview gallery within 72 hours and final edited gallery within six weeks.",
                "order": 1,
            },
        ],
        "terms_and_conditions": "Demo terms for production video capture only.",
        "cancellation_policy": "Demo cancellation policy with no legal effect.",
        "custom_clauses": "Planner and vendor confirm all demo-video assets are non-private fixtures.",
        "total_amount": 6800,
        "currency": "USD",
        "deposit_amount": 1700,
        "status": ContractStatus.SENT.value,
        "access_token_hash": access_token_hash,
        "token_expires_at": now + timedelta(days=30),
        "token_revoked_at": None,
        "token_last_sent_at": now - timedelta(days=1),
        "token_last_viewed_at": None,
        "created_by": planner_email,
        "created_at": now - timedelta(days=5),
        "updated_at": now,
        "version_number": 1,
        "root_contract_id": str(contract_object_id),
        "parent_contract_id": None,
        "supersedes_contract_id": None,
        "superseded_by_contract_id": None,
        "is_current_version": True,
        "contract_kind": ContractKind.ORIGINAL.value,
        "amendment_reason": None,
        "superseded_at": None,
        "sent_at": now - timedelta(days=1),
        "viewed_at": None,
        "signed_at": None,
        "signed_by_name": None,
        "signed_by_email": None,
        "signature_ip": None,
        "internal_notes": "Demo-video fixture only.",
        "is_soft_deleted": False,
        "seed_source": DEMO_SEED_SOURCE,
    }
    await mongo.get_collection("vendor_contracts").replace_one(
        {"_id": contract_object_id},
        contract,
        upsert=True,
    )
    return str(contract_object_id)


async def _seed_client_contract_portal_fixture(primary_id: str, planner: dict[str, Any]) -> str:
    from bson import ObjectId

    from app.core.database import mongo

    now = _utc_now()
    wedding = await mongo.get_weddings_collection().find_one({"_id": primary_id}) or {}
    planner_email = str(planner.get("email") or "")
    couple_email = wedding.get("couple_portal_email") or os.getenv("SMOKE_COUPLE_EMAIL")
    contract_object_id = ObjectId(DEMO_CLIENT_CONTRACT_ID)
    wedding_date = wedding.get("date")
    if isinstance(wedding_date, str):
        wedding_date_value = datetime.fromisoformat(wedding_date).replace(tzinfo=timezone.utc)
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
            {"name": "Design lock", "amount": 4800, "trigger": "fixed_date", "fixed_date": (now + timedelta(days=45)).date().isoformat()},
            {"name": "Final production", "amount": 4800, "trigger": "days_before_wedding", "days_before": 21},
        ],
    }
    contract = {
        "_id": contract_object_id,
        "planner_id": planner_email,
        "wedding_id": primary_id,
        "vendor_profile_id": "vendor_demo_signature_planning",
        "vendor_name": "The Special Wedding Studio",
        "vendor_email": planner_email,
        "contract_title": "Maya & Jordan - Signature Planning + Production",
        "contract_number": "CLIENT-DEMO-VIDEO-001",
        "token": DEMO_CLIENT_PORTAL_TOKEN,
        "status": "active",
        "couple": {
            "email": couple_email,
            "partner1_name": "Maya",
            "partner2_name": "Jordan",
            "name": "Maya",
            "partner_name": "Jordan",
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
        "planner_phone": planner.get("phone") or "(555) 014-2026",
        "sent_at": now - timedelta(days=9),
        "viewed_at": now - timedelta(days=8),
        "signed_at": now - timedelta(days=7),
        "completed_at": None,
        "cancelled_at": None,
        "created_at": now - timedelta(days=11),
        "updated_at": now,
        "seed_source": DEMO_SEED_SOURCE,
    }
    await mongo.get_collection("contracts").replace_one(
        {"_id": contract_object_id},
        contract,
        upsert=True,
    )

    await mongo.get_collection("scheduled_payments").delete_many(
        {"contract_id": str(contract_object_id), "seed_source": DEMO_SEED_SOURCE}
    )
    await mongo.get_collection("scheduled_payments").insert_many(
        [
            {
                "_id": ObjectId("64f300000000000000000101"),
                "contract_id": str(contract_object_id),
                "planner_id": planner_email,
                "name": "Retainer",
                "amount": 3200,
                "currency": "usd",
                "due_date": now - timedelta(days=7),
                "status": "succeeded",
                "paid_at": now - timedelta(days=7),
                "receipt_url": "https://example.test/demo-retainer-receipt",
                "created_at": now - timedelta(days=11),
                "updated_at": now - timedelta(days=7),
                "seed_source": DEMO_SEED_SOURCE,
            },
            {
                "_id": ObjectId("64f300000000000000000102"),
                "contract_id": str(contract_object_id),
                "planner_id": planner_email,
                "name": "Design lock",
                "amount": 4800,
                "currency": "usd",
                "due_date": now + timedelta(days=45),
                "status": "scheduled",
                "paid_at": None,
                "receipt_url": None,
                "created_at": now - timedelta(days=11),
                "updated_at": now,
                "seed_source": DEMO_SEED_SOURCE,
            },
            {
                "_id": ObjectId("64f300000000000000000103"),
                "contract_id": str(contract_object_id),
                "planner_id": planner_email,
                "name": "Final production",
                "amount": 4800,
                "currency": "usd",
                "due_date": wedding_date_value - timedelta(days=21),
                "status": "scheduled",
                "paid_at": None,
                "receipt_url": None,
                "created_at": now - timedelta(days=11),
                "updated_at": now,
                "seed_source": DEMO_SEED_SOURCE,
            },
        ]
    )
    return DEMO_CLIENT_PORTAL_TOKEN


def _write_capture_fixtures(fixtures: dict[str, Any]) -> None:
    fixture_path = ROOT / "output" / "demo-videos" / "capture-fixtures.json"
    fixture_path.parent.mkdir(parents=True, exist_ok=True)
    fixture_path.write_text(f"{json.dumps(fixtures, indent=2, sort_keys=True)}\n")


async def seed_demo_workspace(args: argparse.Namespace) -> None:
    from app.core.database import mongo

    planner_email = _planner_email(args)
    planner = await _load_planner(planner_email)
    primary_id = args.primary_wedding_id
    secondary_id = args.secondary_wedding_id

    await mongo.get_users_collection().update_one(
        {"_id": planner["_id"]},
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
                "seed_source": planner.get("seed_source") or DEMO_SEED_SOURCE,
                "updated_at": _utc_now(),
            },
            "$unset": {
                "stripe_connect_id": "",
                "stripe_connect_charges_enabled": "",
                "stripe_connect_payouts_enabled": "",
                "stripe_connect_details_submitted": "",
                "stripe_connect_updated_at": "",
            },
        },
    )
    await _seed_demo_subscription(planner)

    await _upsert_wedding(
        wedding_id=primary_id,
        slug=args.primary_slug,
        couple_names="Maya & Jordan",
        planner=planner,
        date=args.primary_date,
        ready=True,
    )
    await _upsert_wedding(
        wedding_id=secondary_id,
        slug=args.secondary_slug,
        couple_names="Harper & Sol",
        planner=planner,
        date=args.secondary_date,
        ready=False,
    )
    await _seed_people_and_activity(primary_id, secondary_id, planner_email)
    await _seed_ai_cache(primary_id, planner)
    upload_token = await _seed_guest_media_fixture(primary_id)
    primary_wedding = await mongo.get_weddings_collection().find_one({"_id": primary_id}) or {}
    couple_email = primary_wedding.get("couple_portal_email") or os.getenv("SMOKE_COUPLE_EMAIL")
    public_form_id, couple_form_id = await _seed_form_fixture(
        primary_id, planner_email, couple_email
    )
    vendor_contract_id = await _seed_vendor_contract_fixture(primary_id, planner_email)
    client_portal_token = await _seed_client_contract_portal_fixture(primary_id, planner)

    _write_capture_fixtures(
        {
            "plannerEmail": planner_email,
            "primaryWeddingId": primary_id,
            "primarySlug": args.primary_slug,
            "secondaryWeddingId": secondary_id,
            "secondarySlug": args.secondary_slug,
            "guestMemoriesUploadToken": upload_token,
            "formId": public_form_id,
            "coupleFormId": couple_form_id,
            "vendorContractId": vendor_contract_id,
            "vendorContractToken": DEMO_VENDOR_CONTRACT_TOKEN,
            "clientContractPortalToken": client_portal_token,
            "vendorPortalToken": client_portal_token,
            "seededAt": _utc_now().isoformat(),
        }
    )

    print(
        "[OK] Demo video workspace seeded: "
        f"planner={planner_email} primary={primary_id} secondary={secondary_id}"
    )

    mongo.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed realistic local demo-video data")
    parser.add_argument("--planner-email")
    parser.add_argument("--primary-wedding-id", default=os.getenv("SMOKE_WEDDING_ID", DEFAULT_PRIMARY_WEDDING_ID))
    parser.add_argument("--primary-slug", default=os.getenv("SMOKE_PUBLIC_WEDDING_SLUG", DEFAULT_PRIMARY_SLUG))
    parser.add_argument("--primary-date", default=os.getenv("SMOKE_WEDDING_DATE", _date_from_now(132)))
    parser.add_argument("--secondary-wedding-id", default=DEFAULT_SECONDARY_WEDDING_ID)
    parser.add_argument("--secondary-slug", default=DEFAULT_SECONDARY_SLUG)
    parser.add_argument("--secondary-date", default=_date_from_now(294))
    parser.add_argument(
        "--allow-nonlocal",
        action="store_true",
        help="Allow writes when ENVIRONMENT/NODE_ENV is not development, local, test, or ci.",
    )
    args = parser.parse_args()
    _assert_demo_seed_allowed(args)
    asyncio.run(seed_demo_workspace(args))


if __name__ == "__main__":
    main()
