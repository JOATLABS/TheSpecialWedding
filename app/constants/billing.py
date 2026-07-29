"""Central billing-model constants and operator gates."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

BILLING_MODEL_FLAT_RATE = "flat_rate"
BILLING_MODEL_METERED = "metered"

# 2026-07-28 locked pricing scheme (final operator ruling): the free tier is
# retired entirely and the catalog becomes two paid planner tiers. Yearly =
# monthly x 10 exactly (two months free). Mongo _ids stay stable so existing
# Stripe products, prices, and subscriptions stay attached.
#   plan_boutique      -> "Solo Founding"  $49/mo · $490/yr (was Boutique $49)
#   plan_solo_standard -> "Solo Standard"  $99/mo · $990/yr (new)
# plan_solo ($0), plan_signature (Signature $149 — NOT renamed to a "White
# Glove" tier; White-Glove is a one-time setup add-on, see
# WHITE_GLOVE_SETUP_ADDON), and plan_enterprise ($399) are retired — see
# RETIRED_PUBLIC_PLAN_IDS below.
CANONICAL_PUBLIC_PLAN_IDS_BY_NAME = {
    "Solo Founding": "plan_boutique",
    "Solo Standard": "plan_solo_standard",
}
CANONICAL_PUBLIC_PLAN_IDS = frozenset(CANONICAL_PUBLIC_PLAN_IDS_BY_NAME.values())

# Plans removed from sale by the 2026-07 pricing strategy. Their Mongo
# documents are retained (historical subscriptions must keep resolving —
# plan_signature carries an in-flight trial that converts onto Solo Founding
# at $49/mo) but they are forced inactive on every seed run and
# their Stripe products are archived so no new checkout can be created
# against them.
RETIRED_PUBLIC_PLAN_IDS = frozenset({"plan_solo", "plan_signature", "plan_enterprise"})

# Couple-side one-time offer (one wedding workspace, active through 90 days
# after the wedding — the workspace is then removed automatically like any
# other ended wedding; NOT lifetime access), locked 2026-07-27/28.
# There is no couple checkout flow yet — the catalog encodes the price and the
# env key that will carry the real Stripe Price id once the operator creates
# it (mode=payment, $199 USD). An unset env var means "not purchasable yet";
# code must never fabricate a placeholder price id.
COUPLE_LIFETIME_OFFER = {
    "id": "offer_couple_lifetime",
    "name": "Couple Plan — One Wedding",
    "amount_usd": 199,
    "billing": "one_time",
    "stripe_price_env": "STRIPE_COUPLE_LIFETIME_PRICE_ID",
}

# Internal entitlement plan backing the couple offer (locked 2026-07-28).
# The couple-plan purchaser uses the PLANNER dashboard for their own single
# wedding — they are NOT a couple-portal user. Their plan differs from the
# planner tiers in exactly four ways (operator ruling 2026-07-28; nothing
# else is gated):
#   1. no couple-portal surfaces (they ARE the couple — no couple invites),
#   2. no service packages (planner-to-client feature),
#   3. no team member seats (staff_seats=0 fails the team gate closed),
#   4. exactly ONE wedding — max_weddings=1 with the lifetime-style cap so
#      delete-and-recreate cannot mint a second workspace on a one-time
#      purchase. (Internal cap semantics only — user-facing copy must say
#      "the couple plan covers one wedding", never "lifetime".)
#
# ``is_active`` stays False FOREVER: /public/subscription-plans returns every
# active plan, so an active plan_couple would leak onto the planner pricing
# page. Entitlement resolution for the account that owns it does not require
# an active plan — subscriptions resolve through plan_snapshot and
# SubscriptionService.get_user_billing_plan explicitly supports inactive plan
# documents reached through the user's own subscription.
COUPLE_PLAN_ID = "plan_couple"
COUPLE_PLAN_NAME = "Couple Plan — One Wedding"
COUPLE_PLAN_SEED = {
    "_id": COUPLE_PLAN_ID,
    "name": COUPLE_PLAN_NAME,
    "description": (
        "One wedding workspace for a couple planning their own wedding. "
        "Active through 90 days after the wedding date."
    ),
    "price_monthly": 0,
    "price_yearly": None,
    "trial_days": 0,
    "billing_model": BILLING_MODEL_FLAT_RATE,
    "is_metered": False,
    "max_weddings": 1,
    "max_weddings_lifetime": True,
    "max_guests_per_wedding": -1,
    "ai_credits_monthly": 300,
    "storage_gb": 25,
    "staff_seats": 0,
    "features": {
        "guest_management": True,
        "email_invitations": True,
        "rsvp_system": True,
        "wedding_website": True,
        "timeline_builder": True,
        "basic_analytics": True,
        "vendor_management": True,
        "seating_orchestration": True,
        "ai_features": True,
        "qr_checkin": True,
        "automated_reminders": True,
        "calendar_sync": True,
        "payment_processing": True,
        # The four couple-plan exclusions. ``packages`` and ``couple_portal``
        # are include-by-default features (see
        # app/dependencies/feature_gates.py::require_plan_included_feature):
        # planner plans that never declare these keys keep access; an
        # explicit False here is what blocks the couple plan server-side.
        "packages": False,
        "couple_portal": False,
        "vendor_collaboration": False,
        "advanced_analytics": False,
        "planner_storefront": False,
        "custom_domain": False,
        "priority_support": False,
        "white_label": False,
        "api_access": False,
        "dedicated_support": False,
    },
    "features_list": [
        "One wedding workspace",
        "Unlimited guests",
        "Vendor management",
        "Seating orchestration",
        "Automated reminders",
        "Calendar sync (Google, Outlook)",
        "300 AI credits/month",
        "25GB guest memories storage",
        "Email support",
    ],
    "is_featured": False,
    "is_active": False,
    "display_order": 99,
    "sort_order": 99,
}

# White-Glove Setup add-on, locked 2026-07-28. This is NOT a subscription
# tier — it is a one-time $149 guided-activation session (operator helps the
# planner configure the workspace, import weddings, and go live). Like the
# couple offer there is no checkout flow for it yet; the catalog encodes the
# locked price and the env key that will carry the real Stripe Price id once
# created (mode=payment, $149 USD). An unset env var means "not purchasable
# yet"; code must never fabricate a placeholder price id.
WHITE_GLOVE_SETUP_ADDON = {
    "id": "addon_white_glove_setup",
    "name": "White-Glove Setup",
    "amount_usd": 149,
    "billing": "one_time",
    "stripe_price_env": "STRIPE_WHITE_GLOVE_SETUP_PRICE_ID",
}
# 2026-05-09 pricing strategy refresh: shipped plans are flat. The metering
# hardening infrastructure (stripe_meter_helpers, ensure_stripe_meter,
# assert_meter_config) stays available — a plan can be flipped to metered
# per-plan by setting is_metered=True + meter_event_name. The canonical
# default just reflects what we actually ship today.
CANONICAL_PUBLIC_PLAN_BILLING_MODEL = BILLING_MODEL_FLAT_RATE
CANONICAL_PUBLIC_PLAN_METER_EVENT_NAME = "wedding_active"

METERED_PLAN_MANAGEMENT_FLAG = "TSW_ENABLE_METERED_PLAN_MANAGEMENT"
PLAN_BILLING_MODEL_MIGRATION_FLAG = "TSW_ALLOW_PLAN_BILLING_MODEL_MIGRATION"

TRUTHY_ENV_VALUES = frozenset({"1", "true", "yes", "on"})


def env_flag_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in TRUTHY_ENV_VALUES


def metered_plan_management_enabled() -> bool:
    return env_flag_enabled(METERED_PLAN_MANAGEMENT_FLAG)


def plan_billing_model_migration_enabled() -> bool:
    return env_flag_enabled(PLAN_BILLING_MODEL_MIGRATION_FLAG)


def plan_billing_model(plan: Mapping[str, Any] | None) -> str:
    if plan and plan.get("is_metered"):
        return BILLING_MODEL_METERED
    return BILLING_MODEL_FLAT_RATE
