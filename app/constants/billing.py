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

# Couple-side one-time offer (lifetime-of-wedding access), locked 2026-07-27.
# There is no couple checkout flow yet — the catalog encodes the price and the
# env key that will carry the real Stripe Price id once the operator creates
# it (mode=payment, $199 USD). An unset env var means "not purchasable yet";
# code must never fabricate a placeholder price id.
COUPLE_LIFETIME_OFFER = {
    "id": "offer_couple_lifetime",
    "name": "Couple Lifetime Access",
    "amount_usd": 199,
    "billing": "one_time",
    "stripe_price_env": "STRIPE_COUPLE_LIFETIME_PRICE_ID",
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
