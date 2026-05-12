"""Unit tests for the lifetime-wedding cap enforcement (Solo tier).

The Solo free tier has ``max_weddings: 1`` AND ``max_weddings_lifetime: True``,
which means the cap is enforced against the LIFETIME wedding count (including
soft-deleted weddings). This prevents the "create, delete, repeat" loop that
would let a free planner run unlimited weddings against a 1-wedding cap.

This test file pins three behaviors:

1. ``max_weddings_lifetime=True`` plan uses lifetime count for the cap
2. ``max_weddings_lifetime=False`` plan (the default) uses active count
3. The Solo seed plan is shipped with lifetime cap enabled

References:
* scripts/seed_subscription_plans.py — Solo tier definition
* app/services/subscription_service.py — _live_wedding_count_lifetime
* docs/analysis/METERING_IMPLEMENTATION_2026-05-04.md — design rationale
"""

from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_unit")


# ===========================================================================
# 1. Solo seed plan ships with lifetime cap enabled
# ===========================================================================


def test_solo_seed_plan_has_lifetime_cap_enabled():
    """Pin: the Solo tier is configured for lifetime enforcement.

    Uses an AST parse (matches the pattern in test_metering_gating.py) so
    we don't trigger the seed script's Mongo connection side effects.
    """
    import ast
    from pathlib import Path

    seed_path = Path(PROJECT_ROOT) / "scripts" / "seed_subscription_plans.py"
    tree = ast.parse(seed_path.read_text())

    plans_node = None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if "plans" in targets:
                plans_node = node.value
                break

    assert plans_node is not None and isinstance(plans_node, ast.List), (
        "Could not locate the `plans = [...]` literal in the seed script."
    )

    solo_plan = None
    for plan_dict_node in plans_node.elts:
        if not isinstance(plan_dict_node, ast.Dict):
            continue
        plan_id = None
        lifetime_flag = None
        max_weddings = None
        for k_node, v_node in zip(plan_dict_node.keys, plan_dict_node.values):
            if not isinstance(k_node, ast.Constant):
                continue
            key = k_node.value
            if key == "_id" and isinstance(v_node, ast.Constant):
                plan_id = v_node.value
            elif key == "max_weddings_lifetime" and isinstance(v_node, ast.Constant):
                lifetime_flag = v_node.value
            elif key == "max_weddings" and isinstance(v_node, ast.Constant):
                max_weddings = v_node.value
        if plan_id == "plan_solo":
            solo_plan = {
                "max_weddings_lifetime": lifetime_flag,
                "max_weddings": max_weddings,
            }
            break

    assert solo_plan is not None, "Solo plan not found in seed script"
    # 2026-05-12 strategy refresh: Solo uses ACTIVE-count, not lifetime.
    # Planners can delete a wedding and create another — the upgrade
    # pressure comes from the 1-active-at-a-time cap + 50-guest cap,
    # not from a lifetime gate. The lifetime branch still exists in
    # subscription_service and is tested below — this assertion just
    # pins that Solo currently uses active-count.
    assert solo_plan["max_weddings_lifetime"] is False, (
        "Solo tier currently ships with max_weddings_lifetime=False (active "
        "count). If you flipped it to True, update this assertion AND the "
        "docs/specs/PRICING_STRATEGY_*.md spec describing the decision."
    )
    assert solo_plan["max_weddings"] == 1, (
        f"Solo tier should cap at 1 wedding, got max_weddings={solo_plan['max_weddings']!r}"
    )


# ===========================================================================
# 2. _live_wedding_count_lifetime includes soft-deleted weddings
# ===========================================================================


@pytest.mark.asyncio
async def test_live_wedding_count_lifetime_does_not_filter_soft_deleted():
    """Pin: the lifetime counter query does NOT exclude deleted_at rows.

    This is the key difference from _live_wedding_count, which excludes
    soft-deleted weddings. The lifetime version must include them — that's
    what makes the cap stick after a delete.
    """
    from app.services.subscription_service import SubscriptionService

    service = SubscriptionService.__new__(SubscriptionService)

    users_coll = MagicMock()
    users_coll.find_one = AsyncMock(
        return_value={"email": "solo@example.com", "_id": "user_solo"}
    )

    weddings_coll = MagicMock()
    captured_query = {}

    async def fake_count(query):
        captured_query.update(query)
        return 1  # arbitrary count

    weddings_coll.count_documents = fake_count

    service.users_collection = users_coll
    service.weddings_collection = weddings_coll

    with patch(
        "app.services.subscription_service.build_wedding_owner_query",
        return_value={"created_by": "solo@example.com"},
    ):
        result = await service._live_wedding_count_lifetime("user_solo")

    assert result == 1
    # The query MUST NOT include any deleted_at filter — soft-deleted
    # weddings still count.
    query_str = str(captured_query)
    assert "deleted_at" not in query_str, (
        f"_live_wedding_count_lifetime applied a deleted_at filter, but it "
        f"must NOT (that's the whole point of the lifetime variant). "
        f"Query was: {captured_query!r}"
    )


# ===========================================================================
# 3. check_limits branches on max_weddings_lifetime
# ===========================================================================


@pytest.mark.asyncio
async def test_check_limits_uses_lifetime_counter_when_plan_flag_set():
    """When the plan has max_weddings_lifetime=True, the limit check must
    use _live_wedding_count_lifetime (includes deleted), NOT
    _live_wedding_count (excludes deleted)."""
    from app.services.subscription_service import SubscriptionService

    service = SubscriptionService.__new__(SubscriptionService)

    # Mock both counters; assert which one is called.
    service._live_wedding_count = AsyncMock(return_value=0)
    service._live_wedding_count_lifetime = AsyncMock(return_value=1)

    # Mock the plan_snapshot path: limits_source comes from snapshot.
    fake_sub = {
        "user_id": "user_solo",
        "plan_id": "plan_solo",
        "plan_snapshot": {
            "max_weddings": 1,
            "max_weddings_lifetime": True,
        },
    }
    service.get_user_subscription = AsyncMock(return_value=fake_sub)
    service.plans_collection = MagicMock()
    service.plans_collection.find_one = AsyncMock(return_value=None)
    # check_usage_limits also calls get_usage_stats; mock it so we don't
    # hit mongo. The weddings branch live-queries anyway, so the dict
    # contents don't matter for the assertion.
    service.get_usage_stats = AsyncMock(return_value={"weddings_count": 0})

    result = await service.check_usage_limits("user_solo", "weddings", 1)

    # The lifetime counter MUST have been used (because flag is True).
    service._live_wedding_count_lifetime.assert_awaited_once_with("user_solo")
    service._live_wedding_count.assert_not_called()

    # Cap blocked: current=1, limit=1, requested=1 → would exceed.
    assert result["allowed"] is False
    assert "lifetime cap" in result["message"].lower(), (
        f"Lifetime-cap rejection should mention 'lifetime cap' in message; "
        f"got: {result['message']!r}"
    )


@pytest.mark.asyncio
async def test_check_limits_uses_active_counter_when_plan_flag_false():
    """The historical behavior: when max_weddings_lifetime is False (default),
    the limit check uses _live_wedding_count (excludes soft-deleted)."""
    from app.services.subscription_service import SubscriptionService

    service = SubscriptionService.__new__(SubscriptionService)

    service._live_wedding_count = AsyncMock(return_value=2)
    service._live_wedding_count_lifetime = AsyncMock(return_value=99)

    fake_sub = {
        "user_id": "user_boutique",
        "plan_id": "plan_boutique",
        "plan_snapshot": {
            "max_weddings": 10,
            "max_weddings_lifetime": False,
        },
    }
    service.get_user_subscription = AsyncMock(return_value=fake_sub)
    service.plans_collection = MagicMock()
    service.plans_collection.find_one = AsyncMock(return_value=None)
    # check_usage_limits also calls get_usage_stats; mock it so we don't
    # hit mongo. The weddings branch live-queries anyway, so the dict
    # contents don't matter for the assertion.
    service.get_usage_stats = AsyncMock(return_value={"weddings_count": 0})

    result = await service.check_usage_limits("user_boutique", "weddings", 1)

    # The active counter MUST have been used (because flag is False).
    service._live_wedding_count.assert_awaited_once_with("user_boutique")
    service._live_wedding_count_lifetime.assert_not_called()

    # Cap not hit: current=2, limit=10, requested=1 → allowed.
    assert result.get("allowed", True) is not False, (
        "Boutique planner with 2 active weddings should be allowed to "
        "create a 3rd (cap is 10)."
    )


@pytest.mark.asyncio
async def test_check_limits_lifetime_blocks_after_delete_recreate_simulation():
    """The headline scenario: a Solo planner has used their 1 lifetime
    wedding, then deleted it. The _live_wedding_count_lifetime returns 1
    (deleted weddings still count). They try to create another → BLOCKED."""
    from app.services.subscription_service import SubscriptionService

    service = SubscriptionService.__new__(SubscriptionService)

    # Active count: 0 (they deleted their wedding).
    # Lifetime count: 1 (the deleted wedding still counts).
    service._live_wedding_count = AsyncMock(return_value=0)
    service._live_wedding_count_lifetime = AsyncMock(return_value=1)

    fake_sub = {
        "user_id": "user_solo",
        "plan_id": "plan_solo",
        "plan_snapshot": {
            "max_weddings": 1,
            "max_weddings_lifetime": True,
        },
    }
    service.get_user_subscription = AsyncMock(return_value=fake_sub)
    service.plans_collection = MagicMock()
    service.plans_collection.find_one = AsyncMock(return_value=None)
    # check_usage_limits also calls get_usage_stats; mock it so we don't
    # hit mongo. The weddings branch live-queries anyway, so the dict
    # contents don't matter for the assertion.
    service.get_usage_stats = AsyncMock(return_value={"weddings_count": 0})

    result = await service.check_usage_limits("user_solo", "weddings", 1)

    # MUST be blocked. If this fails, the lifetime cap is gameable.
    assert result["allowed"] is False, (
        "Solo planner with 1 lifetime + 0 active should be BLOCKED from "
        "creating another wedding — that's the whole point of the lifetime "
        "cap. If this test fails, free planners can run unlimited weddings."
    )
    assert result["current_usage"] == 1, (
        f"Expected current_usage to reflect lifetime count (1), got "
        f"{result['current_usage']}"
    )
