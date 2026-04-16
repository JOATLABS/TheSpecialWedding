from __future__ import annotations

from typing import Any, Mapping

PLANNER_BILLING_USER_FIELDS = (
    "plan_id",
    "subscription_status",
    "subscription_tier",
    "trial_end_date",
    "trial_warning_sent",
    "trial_expired_at",
    "trial_used",
    "previous_trial_used",
    "warning_sent_at",
    "stripe_customer_id",
    "stripe_subscription_id",
    "pending_expires_at",
)


def is_planner_billing_role(role: str | None) -> bool:
    """Return True when planner billing fields are valid for this role."""

    return role == "wedding_planner"


def strip_planner_billing_fields(
    user_data: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Drop planner-only billing fields from non-planner user payloads."""

    sanitized = dict(user_data or {})
    for field in PLANNER_BILLING_USER_FIELDS:
        sanitized.pop(field, None)
    return sanitized


def planner_billing_unset_fields() -> dict[str, str]:
    """Return a MongoDB $unset payload for planner-only billing fields."""

    return {field: "" for field in PLANNER_BILLING_USER_FIELDS}
