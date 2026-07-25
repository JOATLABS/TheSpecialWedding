"""Central billing-model constants and operator gates."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

BILLING_MODEL_FLAT_RATE = "flat_rate"
BILLING_MODEL_METERED = "metered"

CANONICAL_PUBLIC_PLAN_IDS_BY_NAME = {
    "Solo": "plan_solo",
    "Boutique": "plan_boutique",
    "Signature": "plan_signature",
    "Enterprise": "plan_enterprise",
}
CANONICAL_PUBLIC_PLAN_IDS = frozenset(CANONICAL_PUBLIC_PLAN_IDS_BY_NAME.values())
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
