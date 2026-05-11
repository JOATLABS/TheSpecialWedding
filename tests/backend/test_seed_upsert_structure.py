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
