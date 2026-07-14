"""Field-scoped policy for canonical subscription-plan seed refreshes.

The public plan catalog mixes product strategy with operator-owned display
state. A copy refresh must be able to repair retired descriptions and feature
highlights without silently resetting a later price experiment, plan limit, or
hidden-plan decision. Keeping the revision cutoff per field makes that
boundary explicit and gives the boot seed and the root-admin fallback one
shared decision function.
"""

from collections.abc import Callable, Mapping
from typing import Any

from app.constants.billing import CANONICAL_PUBLIC_PLAN_IDS_BY_NAME
from app.utils.mongo_dates import to_utc_datetime


PLAN_SEED_VERSION = "2026-07-14T00:00:00+00:00"
PUBLIC_PLAN_COPY_SEED_VERSION = "2026-07-14T15:30:33+00:00"

# Only the fields changed by the follow-up copy refresh receive the later
# cutoff. Commercial settings continue to use PLAN_SEED_VERSION, so a price,
# cap, or entitlement edit made after that strategy release is preserved.
PLAN_FIELD_SEED_VERSIONS: Mapping[str, str] = {
    "description": PUBLIC_PLAN_COPY_SEED_VERSION,
    "features_list": PUBLIC_PLAN_COPY_SEED_VERSION,
}

ADMIN_MUTABLE_PLAN_FIELDS = (
    "name",
    "description",
    "price_monthly",
    "price_yearly",
    "trial_days",
    "max_weddings",
    "max_weddings_lifetime",
    "max_guests_per_wedding",
    "ai_credits_monthly",
    "storage_gb",
    "staff_seats",
    "features",
    "features_list",
)

# These values are display/operator decisions, not seed strategy. Existing
# values always win, including when their historical admin_overrides metadata
# is absent or older than a strategy release.
ADMIN_PRESERVED_PLAN_FIELDS = (
    "is_active",
    "is_featured",
    "sort_order",
    "display_order",
)


def _field_seed_cutoff(field: str):
    raw_cutoff = PLAN_FIELD_SEED_VERSIONS.get(field, PLAN_SEED_VERSION)
    cutoff = to_utc_datetime(raw_cutoff)
    if cutoff is None:
        raise RuntimeError(
            f"Seed version for {field!r} ({raw_cutoff!r}) must be a valid "
            "ISO-8601 timestamp."
        )
    return cutoff


def build_effective_seed_plan(
    seed_plan: Mapping[str, Any],
    existing_plan: Mapping[str, Any] | None,
    *,
    log: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Merge a canonical seed with newer admin intent and display state."""

    effective = dict(seed_plan)
    if not existing_plan:
        return effective

    admin_overrides = existing_plan.get("admin_overrides") or {}
    for field in ADMIN_MUTABLE_PLAN_FIELDS:
        if field not in seed_plan or field not in existing_plan:
            continue

        admin_edit_at = admin_overrides.get(field)
        admin_edit_at_dt = to_utc_datetime(admin_edit_at)
        field_cutoff = _field_seed_cutoff(field)
        if admin_edit_at_dt and admin_edit_at_dt > field_cutoff:
            effective[field] = existing_plan[field]
            if log is not None:
                log(
                    f"  [PRESERVE] {field} = {existing_plan[field]!r} "
                    f"(admin edit at {admin_edit_at_dt.isoformat()} > field seed "
                    f"version {field_cutoff.isoformat()})"
                )

    for field in ADMIN_PRESERVED_PLAN_FIELDS:
        if field in seed_plan and field in existing_plan:
            effective[field] = existing_plan[field]

    return effective


def seeded_field_updates(
    seed_values: Mapping[str, Any],
    existing_plan: Mapping[str, Any],
) -> dict[str, Any]:
    """Return only seed-owned fields that are both eligible and stale."""

    effective = build_effective_seed_plan(seed_values, existing_plan)
    return {
        field: effective[field]
        for field in seed_values
        if field in effective and existing_plan.get(field) != effective[field]
    }


def legacy_canonical_plan_aliases(
    plans: list[Mapping[str, Any]],
    *,
    require_canonical_present: bool = True,
) -> list[tuple[Any, str]]:
    """Identify same-name noncanonical IDs that must leave public selection.

    By default an alias is returned only after its canonical replacement is
    present in the same snapshot. That makes cleanup fail closed if a seed
    aborts before creating the canonical document. The root-admin seed opts
    out while planning its work, but still archives each alias only after the
    corresponding canonical create/update succeeds.
    """

    canonical_by_name = {
        name.strip().casefold(): plan_id
        for name, plan_id in CANONICAL_PUBLIC_PLAN_IDS_BY_NAME.items()
    }
    present_plan_ids = {plan.get("_id") for plan in plans}
    aliases: list[tuple[Any, str]] = []
    for plan in plans:
        plan_id = plan.get("_id")
        normalized_name = str(plan.get("name") or "").strip().casefold()
        canonical_plan_id = canonical_by_name.get(normalized_name)
        admin_overrides = plan.get("admin_overrides") or {}
        already_archived = (
            plan.get("is_active") is False
            and plan.get("canonical_plan_id") == canonical_plan_id
            and admin_overrides.get("is_active") is not None
        )
        canonical_is_ready = (
            not require_canonical_present or canonical_plan_id in present_plan_ids
        )
        if (
            canonical_plan_id
            and canonical_is_ready
            and plan_id != canonical_plan_id
            and not already_archived
        ):
            aliases.append((plan_id, canonical_plan_id))
    return aliases
