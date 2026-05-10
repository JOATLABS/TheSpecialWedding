"""Central billing-model constants and operator gates."""

from __future__ import annotations

import os
from typing import Any, Mapping

BILLING_MODEL_FLAT_RATE = "flat_rate"
BILLING_MODEL_METERED = "metered"

CANONICAL_PUBLIC_PLAN_IDS = frozenset(
    {"plan_boutique", "plan_signature", "plan_enterprise"}
)
CANONICAL_PUBLIC_PLAN_BILLING_MODEL = BILLING_MODEL_METERED
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
