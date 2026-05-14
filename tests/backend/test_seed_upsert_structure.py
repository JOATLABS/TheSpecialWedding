"""Pin the field placement in ``scripts/seed_subscription_plans.py``'s upsert.

Background (2026-05-10 pricing-refresh forensics):
Strategy-controlled fields (``price_monthly``, ``name``, ``features_list``,
``max_weddings_lifetime``, etc.) had been sitting in ``$setOnInsert`` —
which means they only get written when the plan document is FIRST inserted.
Re-running the seed against an already-existing plan would leave those
fields at their original values forever. That's how production ended up
showing ``Boutique $29`` and ``Signature $59`` long after the strategy was
refreshed to ``$49`` / ``$149``.

This file guards the field placement at the source level — AST parse so we
don't have to import the seed script (which connects to Mongo at module
init). If a future change accidentally moves ``price_monthly`` back into
``$setOnInsert``, CI fails here before the change can ship.

Companion: ``test_lifetime_wedding_cap.py`` guards the seed plan DICT;
this file guards the WRITE PATH that copies those dict values into Mongo.
"""

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# Fields that MUST be in $set so a re-deploy carries new strategy values into
# Mongo. If any of these drift back into $setOnInsert, the symptom is the same
# one we just fixed: production keeps showing stale prices/features.
STRATEGY_SET_FIELDS = frozenset(
    {
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
        "billing_model",
        "is_metered",
        "updated_at",
    }
)

# Fields that MUST be in $setOnInsert so admin display toggles survive deploys.
# If an admin hides a plan (is_active=False) or rearranges sort order, the next
# seed run must NOT clobber that decision.
ADMIN_SETONINSERT_FIELDS = frozenset(
    {
        "created_at",
        "created_by",
        "is_active",
        "is_featured",
        "sort_order",
        "display_order",
    }
)


def _find_seed_update_one_modifier() -> ast.Dict:
    """Locate the ``collection.update_one(..., {modifier_dict}, ...)`` call in
    the seed script and return the modifier dict node.

    Returns the ``ast.Dict`` for the second positional argument (which holds
    ``$set`` / ``$setOnInsert``). Raises ``AssertionError`` with a clear
    message if the call shape changed in a way we can't recognize.
    """
    seed_path = Path(PROJECT_ROOT) / "scripts" / "seed_subscription_plans.py"
    tree = ast.parse(seed_path.read_text())

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "update_one":
            continue
        # Need two positional args: filter dict + modifier dict
        if len(node.args) < 2:
            continue
        modifier = node.args[1]
        if not isinstance(modifier, ast.Dict):
            continue
        # Make sure this is the upsert we care about, not some unrelated
        # update_one elsewhere in the script.
        keys = {k.value for k in modifier.keys if isinstance(k, ast.Constant)}
        if "$set" in keys or "$setOnInsert" in keys:
            return modifier

    raise AssertionError(
        "Could not locate the seed-script `collection.update_one(filter, "
        "{$set..., $setOnInsert...}, upsert=True)` call. If the upsert was "
        "restructured, update this test alongside it."
    )


def _modifier_subdict_keys(modifier: ast.Dict, mongo_op: str) -> set[str]:
    """Return the literal keys of ``modifier[mongo_op]`` as a set.

    ``mongo_op`` is e.g. ``"$set"`` or ``"$setOnInsert"``. Stops at the
    top-level keys only — nested ``**spread`` expressions (used for the
    optional Stripe ID keys in $set) are ignored, which is fine because
    every field this test cares about is a literal key.
    """
    for key_node, value_node in zip(modifier.keys, modifier.values):
        if not isinstance(key_node, ast.Constant) or key_node.value != mongo_op:
            continue
        assert isinstance(value_node, ast.Dict), (
            f"{mongo_op} value must be a dict literal; got {type(value_node).__name__}"
        )
        return {k.value for k in value_node.keys if isinstance(k, ast.Constant)}
    raise AssertionError(
        f"{mongo_op} clause not found in the seed upsert modifier dict. "
        f"Found keys: {[k.value for k in modifier.keys if isinstance(k, ast.Constant)]}"
    )


def test_strategy_fields_live_in_set_not_set_on_insert():
    """Pin: every strategy-controlled field is in ``$set``, not ``$setOnInsert``.

    If this fails, the next deploy of a strategy refresh (new price, new
    plan name, new feature list) will silently NOT propagate into already-
    seeded Mongo documents. Production users see the old values forever.
    """
    modifier = _find_seed_update_one_modifier()
    set_keys = _modifier_subdict_keys(modifier, "$set")
    set_on_insert_keys = _modifier_subdict_keys(modifier, "$setOnInsert")

    missing_from_set = STRATEGY_SET_FIELDS - set_keys
    assert missing_from_set == set(), (
        f"These strategy-controlled fields are NOT in the seed's $set clause "
        f"and therefore won't propagate on redeploy: {sorted(missing_from_set)}. "
        "Either move them into $set or update STRATEGY_SET_FIELDS in this test "
        "if the field genuinely no longer belongs to the strategy."
    )

    drifted_to_set_on_insert = STRATEGY_SET_FIELDS & set_on_insert_keys
    assert drifted_to_set_on_insert == set(), (
        f"These strategy fields drifted into $setOnInsert: "
        f"{sorted(drifted_to_set_on_insert)}. They will stop refreshing on "
        "redeploy and trigger the 'production shows old prices forever' bug "
        "that this test exists to prevent. Move them back into $set."
    )


def test_admin_toggles_live_in_set_on_insert_not_set():
    """Pin: admin display toggles stay in ``$setOnInsert`` so an admin who
    hides a plan or rearranges order doesn't get clobbered on next deploy.
    """
    modifier = _find_seed_update_one_modifier()
    set_keys = _modifier_subdict_keys(modifier, "$set")
    set_on_insert_keys = _modifier_subdict_keys(modifier, "$setOnInsert")

    missing_from_set_on_insert = ADMIN_SETONINSERT_FIELDS - set_on_insert_keys
    assert missing_from_set_on_insert == set(), (
        f"These admin-toggle fields are NOT in $setOnInsert: "
        f"{sorted(missing_from_set_on_insert)}. They should be insert-only so "
        "admin choices (hide a plan, reorder) survive deploys. If you moved "
        "one to $set on purpose, update ADMIN_SETONINSERT_FIELDS to match."
    )

    drifted_to_set = ADMIN_SETONINSERT_FIELDS & set_keys
    assert drifted_to_set == set(), (
        f"Admin-toggle fields drifted into $set: {sorted(drifted_to_set)}. "
        "The next deploy will revert any admin who hid a plan or changed "
        "sort order. Move them back into $setOnInsert."
    )


def test_seed_version_is_a_valid_iso_timestamp():
    """SEED_VERSION must be parseable as an ISO-8601 datetime.

    The seed's per-field admin-override gating compares the value against
    ``admin_overrides[field]`` timestamps. If SEED_VERSION isn't a valid
    timestamp, the seed will crash at runtime — catch it here in CI.
    """
    import ast as _ast
    from datetime import datetime as _dt

    seed_path = Path(PROJECT_ROOT) / "scripts" / "seed_subscription_plans.py"
    tree = _ast.parse(seed_path.read_text())

    seed_version_value = None
    for node in tree.body:
        if not isinstance(node, _ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, _ast.Name) and target.id == "SEED_VERSION":
                assert isinstance(node.value, _ast.Constant), (
                    "SEED_VERSION must be a literal string constant."
                )
                seed_version_value = node.value.value
                break

    assert seed_version_value is not None, (
        "SEED_VERSION constant not found in scripts/seed_subscription_plans.py. "
        "It's required for the admin-override gating mechanism."
    )
    try:
        parsed = _dt.fromisoformat(seed_version_value)
    except ValueError as exc:
        raise AssertionError(
            f"SEED_VERSION={seed_version_value!r} is not valid ISO-8601: {exc}"
        )
    assert parsed.tzinfo is not None, (
        f"SEED_VERSION={seed_version_value!r} must be timezone-aware "
        "(UTC offset suffix like '+00:00') so comparisons against Mongo "
        "datetimes are unambiguous."
    )


def test_paid_plans_declare_unlimited_weddings_and_guests():
    """2026-05-12 strategy: Boutique/Signature/Enterprise have no volume caps.

    If you intentionally re-add caps to a paid tier, update this test and
    the strategy spec together. Mid-tier upgrade pressure must come from
    capability fields (team seats, white-label, API), not from volume.
    """
    import ast as _ast

    seed_path = Path(PROJECT_ROOT) / "scripts" / "seed_subscription_plans.py"
    tree = _ast.parse(seed_path.read_text())

    plans_node = None
    for node in tree.body:
        if isinstance(node, _ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, _ast.Name)]
            if "plans" in targets:
                plans_node = node.value
                break

    assert plans_node is not None and isinstance(plans_node, _ast.List)

    paid_ids = {"plan_boutique", "plan_signature", "plan_enterprise"}
    seen = {}
    for plan_dict_node in plans_node.elts:
        if not isinstance(plan_dict_node, _ast.Dict):
            continue
        plan_id = None
        max_weddings = None
        max_guests = None
        for k_node, v_node in zip(plan_dict_node.keys, plan_dict_node.values):
            if not isinstance(k_node, _ast.Constant):
                continue
            if k_node.value == "_id" and isinstance(v_node, _ast.Constant):
                plan_id = v_node.value
            elif k_node.value == "max_weddings" and isinstance(v_node, _ast.Constant):
                max_weddings = v_node.value
            elif k_node.value == "max_weddings" and isinstance(v_node, _ast.UnaryOp):
                # Handles `-1` parsed as UnaryOp(USub, Constant(1))
                if isinstance(v_node.op, _ast.USub) and isinstance(
                    v_node.operand, _ast.Constant
                ):
                    max_weddings = -v_node.operand.value
            elif k_node.value == "max_guests_per_wedding" and isinstance(
                v_node, _ast.Constant
            ):
                max_guests = v_node.value
            elif k_node.value == "max_guests_per_wedding" and isinstance(
                v_node, _ast.UnaryOp
            ):
                if isinstance(v_node.op, _ast.USub) and isinstance(
                    v_node.operand, _ast.Constant
                ):
                    max_guests = -v_node.operand.value
        if plan_id in paid_ids:
            seen[plan_id] = {
                "max_weddings": max_weddings,
                "max_guests_per_wedding": max_guests,
            }

    assert set(seen.keys()) == paid_ids, (
        f"Missing paid plans in seed: expected {paid_ids}, got {set(seen.keys())}"
    )
    for plan_id, caps in seen.items():
        assert caps["max_weddings"] == -1, (
            f"{plan_id} declares max_weddings={caps['max_weddings']!r}; "
            "paid tiers must use -1 (unlimited) per 2026-05-12 strategy."
        )
        assert caps["max_guests_per_wedding"] == -1, (
            f"{plan_id} declares max_guests_per_wedding={caps['max_guests_per_wedding']!r}; "
            "paid tiers must use -1 (unlimited) per 2026-05-12 strategy."
        )


def test_paid_plans_have_uniform_30_day_trial():
    """All paid plans get the same 30-day trial. Split trial lengths (14/14/30)
    confused buyers and are no longer the design.
    """
    import ast as _ast

    seed_path = Path(PROJECT_ROOT) / "scripts" / "seed_subscription_plans.py"
    tree = _ast.parse(seed_path.read_text())

    plans_node = None
    for node in tree.body:
        if isinstance(node, _ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, _ast.Name)]
            if "plans" in targets:
                plans_node = node.value
                break

    paid_ids = {"plan_boutique", "plan_signature", "plan_enterprise"}
    trial_days_by_plan = {}
    for plan_dict_node in plans_node.elts:
        if not isinstance(plan_dict_node, _ast.Dict):
            continue
        plan_id = None
        trial_days = None
        for k_node, v_node in zip(plan_dict_node.keys, plan_dict_node.values):
            if not isinstance(k_node, _ast.Constant):
                continue
            if k_node.value == "_id" and isinstance(v_node, _ast.Constant):
                plan_id = v_node.value
            elif k_node.value == "trial_days" and isinstance(v_node, _ast.Constant):
                trial_days = v_node.value
        if plan_id in paid_ids:
            trial_days_by_plan[plan_id] = trial_days

    for plan_id, trial_days in trial_days_by_plan.items():
        assert trial_days == 30, (
            f"{plan_id} declares trial_days={trial_days!r}; paid plans must "
            "use the uniform 30-day trial per 2026-05-12 strategy."
        )


def test_update_plan_clears_deleted_at_on_reactivation():
    """Pin: ``subscription_service.update_plan`` must $unset ``deleted_at``
    when the admin re-activates a soft-deleted plan.

    Source-level AST guard. Without this, a plan that was soft-deleted via
    delete_plan (which writes ``is_active=False`` AND ``deleted_at: <ts>``)
    can be re-activated via the admin UI — but ``deleted_at`` stays set,
    leaving the doc in a half-state. Any downstream filter that treats
    ``deleted_at`` as authoritative would still consider the plan deleted.
    """
    import ast as _ast

    src_path = Path(PROJECT_ROOT) / "app" / "services" / "subscription_service.py"
    tree = _ast.parse(src_path.read_text())

    # Find the update_plan async function definition.
    update_plan_fn = None
    for node in _ast.walk(tree):
        if isinstance(node, _ast.AsyncFunctionDef) and node.name == "update_plan":
            update_plan_fn = node
            break

    assert update_plan_fn is not None, (
        "Could not locate `async def update_plan` in subscription_service.py. "
        "If the function was renamed or moved, update this test."
    )

    # The cleanup must use $unset on deleted_at, guarded by the
    # is_active=True + existing deleted_at conditions. We assert via
    # AST.unparse() text inspection — looking for the canonical pattern.
    fn_text = _ast.unparse(update_plan_fn)

    # ast.unparse re-serializes with single quotes; check for both quote
    # styles to be robust against the AST round-trip.
    assert "'deleted_at'" in fn_text or '"deleted_at"' in fn_text, (
        "update_plan no longer references 'deleted_at'. The re-activation "
        "cleanup is missing — admin can no longer clear soft-delete markers."
    )
    assert "'$unset'" in fn_text or '"$unset"' in fn_text, (
        "update_plan no longer uses $unset. Without it, deleted_at can't "
        "be cleared on re-activation (using $set: {deleted_at: None} is a "
        "different semantic that leaves the field present)."
    )
    assert "is_active" in fn_text and "True" in fn_text, (
        "Cleanup must be gated on is_active=True so it only fires when the "
        "admin is explicitly re-activating."
    )


def test_max_weddings_lifetime_is_written_to_mongo():
    """Pin the specific field that was silently missing entirely.

    Before the 2026-05-10 fix, ``max_weddings_lifetime`` was in the seed
    plan DICT but in neither ``$set`` nor ``$setOnInsert`` — so it never
    made it into Mongo at all. Free Solo planners could create → delete →
    create unlimited weddings, bypassing the lifetime cap. This is the
    canary test for that whole class of "field in dict but not in upsert"
    drops.
    """
    modifier = _find_seed_update_one_modifier()
    set_keys = _modifier_subdict_keys(modifier, "$set")
    assert "max_weddings_lifetime" in set_keys, (
        "max_weddings_lifetime MUST be in the seed's $set clause. Without "
        "it, the Solo lifetime cap silently doesn't write to Mongo, and "
        "subscription_service._live_wedding_count_lifetime never gets "
        "invoked because plan_snapshot lacks the flag. Free Solo planners "
        "can then create → delete → create indefinitely."
    )
