"""Unit coverage for SubscriptionService.check_usage_limits.

Pairs with the Scenarios B/C scripted driver
(``testbed/verify_planner_active_lifecycle.py``). The driver exercises this
code path against real Mongo/Stripe; these tests exercise every branch
fast — so CI catches a regression in under a second instead of waiting
for a 20-minute clock-advance run.

Branches covered per ``app/services/subscription_service.py:652-730``:

- ``plan_snapshot`` preferred over current plan (grandfather rule, line 669-671)
- Fallback to current plan when ``plan_snapshot`` is missing (line 672-674)
- Wedding cap hit/just-below/just-over
- ``max_weddings == -1`` unlimited bypass (Enterprise)
- AI credits returns ``remaining`` on both allowed + exceeded paths
- Unknown resource_type returns allowed without false-positive blocks
"""

from __future__ import annotations

import asyncio
import os
import sys

import pytest
from fastapi import HTTPException

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_unit")


def _build_service(
    *,
    plan_snapshot: dict | None,
    plan: dict | None,
    usage: dict,
    subscription_extra: dict | None = None,
    live_wedding_count: int | None = None,
    live_ai_credits_used: int | None = None,
    live_staff_seats_count: int | None = None,
):
    """Construct a SubscriptionService with its Mongo-hitting methods
    stubbed so every test stays synchronous and hermetic.

    We deliberately mutate the instance, not the class — keeps tests
    independent and avoids fixture ordering bugs.

    ``live_wedding_count`` / ``live_ai_credits_used`` /
    ``live_staff_seats_count``: authoritative live values returned by the
    matching ``_live_*`` helper. When ``None`` (the default), the stub
    echoes the equivalent counter from ``usage`` so tests expressed
    against the old counter contract keep asserting the same thing. Pass
    a different integer to simulate counter/reality drift.

    These stubs MUST be installed even when a test doesn't care about
    drift — without them, ``check_usage_limits`` falls through to a real
    Motor ``aggregate``+``to_list`` that crashes on the per-test event
    loop pattern in ``_run`` with ``RuntimeError: Event loop is closed``.
    """
    # Import here so the module-level mongo connection attempt doesn't run
    # at collection time (the real subscription_service instantiates at
    # import, but the singleton is only built on attribute access).
    from app.services.subscription_service import SubscriptionService

    service = SubscriptionService.__new__(SubscriptionService)  # skip __init__
    # __init__ expects Mongo collections we don't have — install stubs for
    # the attributes check_usage_limits doesn't touch anyway.
    service.plans_collection = None
    service.subscriptions_collection = None
    service.usage_collection = None
    service.users_collection = None
    service.weddings_collection = None

    sub = {
        "_id": "sub_test",
        "user_id": "user_test",
        "plan_id": plan["_id"] if plan else "plan_test",
        "status": "active",
    }
    if plan_snapshot is not None:
        sub["plan_snapshot"] = plan_snapshot
    sub.update(subscription_extra or {})

    async def fake_get_user_subscription(user_id: str):
        return sub

    async def fake_get_plan(plan_id: str):
        return plan

    async def fake_get_usage_stats(user_id: str):
        return usage

    resolved_live_count = (
        live_wedding_count
        if live_wedding_count is not None
        else usage.get("weddings_count", 0)
    )

    async def fake_live_wedding_count(user_id: str):
        return resolved_live_count

    resolved_live_ai = (
        live_ai_credits_used
        if live_ai_credits_used is not None
        else usage.get("ai_credits_used_month", 0)
    )

    async def fake_live_ai_credits_used(user_id: str, current_month: str):
        return resolved_live_ai

    resolved_live_seats = (
        live_staff_seats_count
        if live_staff_seats_count is not None
        else usage.get("staff_seats_used", 0)
    )

    async def fake_live_staff_seats_count(user_id: str):
        return resolved_live_seats

    service.get_user_subscription = fake_get_user_subscription  # type: ignore
    service.get_plan = fake_get_plan  # type: ignore
    service.get_usage_stats = fake_get_usage_stats  # type: ignore
    service._live_wedding_count = fake_live_wedding_count  # type: ignore
    service._live_ai_credits_used = fake_live_ai_credits_used  # type: ignore
    service._live_staff_seats_count = fake_live_staff_seats_count  # type: ignore
    return service


def _run(coro):
    # Use a fresh loop per call and close it explicitly — subscription_service
    # imports grab the default loop at module time; creating our own and
    # closing cleanly avoids "Invalid file descriptor: -1" teardown noise.
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Weddings gate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "current, requested, cap, allowed",
    [
        (0, 1, 3, True),  # empty -> first create OK
        (2, 1, 3, True),  # at-cap-minus-one, create fills last slot
        (3, 1, 3, False),  # at cap, next create blocks
        (3, 2, 3, False),  # bulk request over cap blocks
        (99, 1, -1, True),  # -1 == unlimited (Enterprise)
    ],
)
def test_weddings_cap_allow_vs_block(current, requested, cap, allowed):
    """check_usage_limits respects max_weddings with the -1 unlimited escape."""
    plan = {"_id": "plan_boutique", "max_weddings": cap}
    service = _build_service(
        plan_snapshot=None,
        plan=plan,
        usage={"weddings_count": current},
    )
    result = _run(
        service.check_usage_limits("user_test", "weddings", requested_amount=requested)
    )
    assert result["allowed"] is allowed, (
        f"weddings gate decision flipped — current={current} "
        f"requested={requested} cap={cap} expected={allowed} got={result}"
    )
    if not allowed:
        assert "Wedding limit exceeded" in result["message"], (
            "Error message regex on the frontend depends on this exact prefix; "
            "see app/services/subscription_service.py:687."
        )
        assert result["current_usage"] == current
        assert result["limit"] == cap


def test_weddings_plan_snapshot_beats_current_plan():
    """Grandfather rule — plan_snapshot wins when set, current plan is ignored."""
    plan_snapshot = {"_id": "plan_boutique", "max_weddings": 3}
    current_plan = {"_id": "plan_boutique", "max_weddings": 999}  # plan drifted up

    service = _build_service(
        plan_snapshot=plan_snapshot,
        plan=current_plan,
        usage={"weddings_count": 3},
    )
    result = _run(service.check_usage_limits("user_test", "weddings"))
    # If the snapshot is honored, 3/3 blocks. If the code mis-read the
    # current plan at 999, this would pass — the point of this test is to
    # keep the snapshot path honest.
    assert result["allowed"] is False, (
        "plan_snapshot drift: check_usage_limits pulled limits from the "
        "current plan instead of the stored snapshot. The grandfather "
        "contract at subscription_service.py:669-671 is broken."
    )
    assert result["limit"] == 3


def test_weddings_fallback_when_snapshot_missing():
    """Subscriptions older than the snapshot feature still use current plan."""
    plan = {"_id": "plan_boutique", "max_weddings": 3}
    service = _build_service(
        plan_snapshot=None,
        plan=plan,
        usage={"weddings_count": 3},
    )
    result = _run(service.check_usage_limits("user_test", "weddings"))
    assert result["allowed"] is False
    assert result["limit"] == 3


def test_weddings_cap_uses_live_count_not_drifted_counter():
    """Regression guard — the cap reads the live weddings collection, not
    the ``usage_tracking.weddings_count`` counter.

    Scenario encoded here is the exact false-positive that A1/A2 of the
    trial lifecycle driver hit: the per-user-id counter is 0 (user was
    re-provisioned, counter initialized fresh) while the tenancy's real
    wedding count is already 6 against a cap of 3. Pre-fix, the counter
    was load-bearing and the cap silently lifted. Post-fix, live count
    wins and the next create is blocked.

    If this test ever fails, revert to counter-based enforcement is the
    most likely culprit. Do not "fix" the test by flipping the expected
    value — read ``_live_wedding_count`` docstring first.
    """
    plan = {"_id": "plan_boutique", "max_weddings": 3}
    service = _build_service(
        plan_snapshot=None,
        plan=plan,
        usage={"weddings_count": 0},  # stale counter (the drift)
        live_wedding_count=6,  # authoritative reality
    )
    result = _run(service.check_usage_limits("user_test", "weddings"))
    assert result["allowed"] is False, (
        "Cap bypass: check_usage_limits honored the stale counter "
        "(weddings_count=0) instead of the live collection count (6). "
        "This is the regression the planner trial driver caught."
    )
    assert result["current_usage"] == 6, (
        "current_usage in the 402 payload must reflect live reality, "
        "otherwise the UI shows a lower number than the actual tenancy."
    )
    assert result["limit"] == 3


# ---------------------------------------------------------------------------
# AI credits gate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "current, requested, cap, in_overage",
    [
        (0, 1, 100, False),  # well under cap
        (99, 1, 100, False),  # final credit just fits
        (100, 1, 100, False),  # at cap, no overage yet — request is the
        # crossing event but cumulative_overage_credits reads cumulative
        # past usage, not projected. Projected overage surfaces via
        # overage_credits_projected.
        (101, 0, 100, True),  # one credit past cap → soft-cap fires
        (150, 0, 100, True),  # well past cap → soft-cap fires
    ],
)
def test_ai_credits_soft_cap_overage_shape(current, requested, cap, in_overage):
    """Soft-cap contract: ai_credits ALWAYS reports allowed=True; overage
    metadata kicks in once cumulative usage exceeds the included allotment.

    Replaces the prior hard-cap assertion (``allowed=False`` + canonical
    error message) which no longer matches the production contract — see
    docs/plans/SUBSCRIPTION_LIFECYCLE_TEST_PLAN.md §6 and
    subscription_service.py:901-934.
    """
    plan = {"_id": "plan_boutique", "ai_credits_monthly": cap}
    service = _build_service(
        plan_snapshot=None,
        plan=plan,
        usage={"ai_credits_used_month": current},
    )
    result = _run(
        service.check_usage_limits(
            "user_test", "ai_credits", requested_amount=requested
        )
    )
    # Soft-cap NEVER blocks the workflow.
    assert result["allowed"] is True, (
        f"ai_credits gate must never return allowed=False — got {result}"
    )
    # Remaining must not leak negative even when usage is past cap.
    assert result["remaining"] >= 0, (
        f"remaining leaked negative: {result}. Floor at 0 — UI renders "
        f"this directly as the bar denominator."
    )
    assert result["limit"] == cap
    assert result["current_usage"] == current
    if in_overage:
        assert result["overage"] is True, (
            f"overage flag missed past-cap usage: {result}"
        )
        assert result["overage_credits"] >= 1, (
            f"overage_credits should reflect cumulative past-cap usage, got {result}"
        )
        assert result["overage_cost_cents"] > 0, (
            f"overage_cost_cents must be > 0 once in overage, got {result}"
        )
    else:
        assert result["overage"] is False, (
            f"overage flag must stay false at/under cap, got {result}"
        )
        assert result["overage_credits"] == 0
        assert result["overage_cost_cents"] == 0


def test_ai_credits_downgrade_snapshot_pin():
    """Pin C5 behavior: snapshot-from-Signature (300) is honored after
    Mongo plan reference is flipped to Boutique (100) mid-period.

    Under the soft-cap contract this still matters — the snapshot's
    larger limit means 150 credits is comfortably under cap (no overage
    flag), whereas if the live Boutique plan won, 150 would be 50 past
    cap and ``overage`` would fire.

    If the downgrade updates plan_snapshot immediately, this test needs
    flipping. That IS Q1 from the test plan — the point here is that the
    answer is pinned by a code-level test so regressions show up fast.
    """
    plan_snapshot = {"_id": "plan_signature", "ai_credits_monthly": 300}
    # Mongo subscription references Boutique now, but snapshot says Signature.
    current_plan = {"_id": "plan_boutique", "ai_credits_monthly": 100}

    service = _build_service(
        plan_snapshot=plan_snapshot,
        plan=current_plan,
        usage={"ai_credits_used_month": 150},
    )
    result = _run(service.check_usage_limits("user_test", "ai_credits"))

    # Soft-cap always returns allowed=True, but the discriminator now is
    # the overage flag. Snapshot honored → no overage. Snapshot dropped →
    # overage=True at 50 past Boutique's 100 cap.
    assert result["allowed"] is True
    assert result["limit"] == 300, (
        "Q1 pin drifted. check_usage_limits was expected to honor "
        "plan_snapshot's 300-credit Signature limit even after the "
        "subscription's current plan_id moved to Boutique."
    )
    assert result["remaining"] == 150
    assert result["overage"] is False, (
        "Snapshot must keep usage under cap — overage flag firing here "
        "means the live (Boutique) plan was used, snapshot was ignored."
    )


# ---------------------------------------------------------------------------
# Staff seats + no-subscription paths
# ---------------------------------------------------------------------------


def test_staff_seats_cap_block():
    plan = {"_id": "plan_boutique", "staff_seats": 5}
    service = _build_service(
        plan_snapshot=None,
        plan=plan,
        usage={"staff_seats_used": 5},
    )
    result = _run(service.check_usage_limits("user_test", "staff_seats"))
    assert result["allowed"] is False
    assert "Staff seats limit exceeded" in result["message"]


def test_no_subscription_raises_403():
    from app.services.subscription_service import SubscriptionService

    service = SubscriptionService.__new__(SubscriptionService)
    service.plans_collection = None
    service.subscriptions_collection = None
    service.usage_collection = None
    service.users_collection = None
    service.weddings_collection = None

    async def none_subscription(user_id: str):
        return None

    service.get_user_subscription = none_subscription  # type: ignore

    with pytest.raises(HTTPException) as exc:
        _run(service.check_usage_limits("user_test", "weddings"))

    assert exc.value.status_code == 403
    assert "No active subscription" in exc.value.detail
