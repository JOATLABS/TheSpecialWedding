"""Unit coverage for ``@enforce_subscription_limit`` decorator paths.

Pairs with Scenarios B/C/D in
``testbed/verify_planner_active_lifecycle.py`` and the cap gates exercised
in ``tests/backend/test_subscription_limits.py``. This file focuses on the
**decorator envelope** rather than the cap math itself:

- 401 when ``current_user`` is missing or isn't an ``ExtendedAuthUser``
- 403 when the authenticated user has no ``_id`` on user_data
- Root-admin bypass returns the wrapped handler's result without hitting
  ``check_usage_limits`` at all
- 402 when ``check_usage_limits`` returns ``allowed=False``, with the
  upstream ``message`` surfaced verbatim to the HTTPException ``detail``
- 500 wrapper when ``check_usage_limits`` raises an unexpected error
- ``increment_usage`` fires only when the wrapped function's name contains
  "create" (the "create" heuristic at
  ``app/utils/subscription_decorators.py:55``) — this is a load-bearing
  naming convention; the test pins it down so a rename during refactor
  surfaces here, not in production.

Together with test_subscription_limits.py these cover plan §5.1-§5.2.
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any
from unittest.mock import AsyncMock

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
os.environ.setdefault("ROOT_ADMIN_EMAIL", "root@test.invalid")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def decorator_module(monkeypatch):
    """Import the decorator and swap the module-level subscription_service
    singleton for a mock. That singleton is created at import time by
    ``subscription_service = SubscriptionService()`` which attempts to
    hold Mongo collection handles — the import is unavoidable but the
    object is easy to replace post-import."""
    import app.utils.subscription_decorators as module

    fake = AsyncMock()
    monkeypatch.setattr(module, "subscription_service", fake)
    return module, fake


def _build_user(
    *,
    role: str = "wedding_planner",
    email: str = "planner@test.invalid",
    user_id: str | None = "user_test",
    is_root_admin_email: bool = False,
):
    """Build an ExtendedAuthUser without touching Mongo.

    ``is_root_admin`` is derived inside ``ExtendedAuthUser.__init__`` from
    ``role == "ROOT_ADMIN" and email == ROOT_ADMIN_EMAIL``. We set the env
    at module load; flipping roles here toggles the property directly.
    """
    from app.dependencies.auth_extended import ExtendedAuthUser

    user_data: dict[str, Any] = {}
    if user_id is not None:
        user_data["_id"] = user_id

    if is_root_admin_email:
        email = os.environ["ROOT_ADMIN_EMAIL"]
        role = "ROOT_ADMIN"

    return ExtendedAuthUser(email=email, role=role, user_data=user_data)


# ---------------------------------------------------------------------------
# Authentication gates
# ---------------------------------------------------------------------------


def test_missing_current_user_raises_401(decorator_module):
    module, _ = decorator_module

    @module.enforce_subscription_limit("weddings")
    async def handler(current_user=None):
        return "ok"

    with pytest.raises(HTTPException) as exc:
        _run(handler(current_user=None))

    assert exc.value.status_code == 401
    assert "Authentication" in exc.value.detail


def test_non_extended_auth_user_raises_401(decorator_module):
    """A dict or other object in ``current_user`` must not be accepted as
    a valid authenticated user — belt-and-suspenders against a future
    dependency that forgets to wrap the user."""
    module, _ = decorator_module

    @module.enforce_subscription_limit("weddings")
    async def handler(current_user=None):
        return "ok"

    with pytest.raises(HTTPException) as exc:
        _run(handler(current_user={"email": "spoof@test.invalid"}))

    assert exc.value.status_code == 401


def test_user_data_missing_id_raises_403(decorator_module):
    """A user that somehow authenticated but carries no ``_id`` on
    user_data cannot be rate-limited — surface 403 rather than trust the
    call through unchecked."""
    module, _ = decorator_module

    @module.enforce_subscription_limit("weddings")
    async def handler(current_user=None):
        return "ok"

    user = _build_user(user_id=None)

    with pytest.raises(HTTPException) as exc:
        _run(handler(current_user=user))

    assert exc.value.status_code == 403
    assert "User ID" in exc.value.detail


# ---------------------------------------------------------------------------
# Root-admin bypass
# ---------------------------------------------------------------------------


def test_root_admin_bypasses_limits_entirely(decorator_module):
    """Root admin returns the handler's result without ``check_usage_limits``
    or ``increment_usage`` being called. If a future change starts gating
    root admin, this test fails loudly — and that's almost certainly a bug
    since root admin is the internal operator account."""
    module, fake = decorator_module

    @module.enforce_subscription_limit("weddings")
    async def handler(current_user=None):
        return "root-ok"

    user = _build_user(is_root_admin_email=True)
    assert user.is_root_admin is True, (
        "env setup fell out of sync — check ROOT_ADMIN_EMAIL"
    )

    result = _run(handler(current_user=user))

    assert result == "root-ok"
    fake.check_usage_limits.assert_not_called()
    fake.increment_usage.assert_not_called()


# ---------------------------------------------------------------------------
# 402 payment-required path
# ---------------------------------------------------------------------------


def test_allowed_false_raises_402_with_message_passthrough(decorator_module):
    """The frontend matches exact message prefixes on 402 responses
    (``Wedding limit exceeded``, ``AI credits limit exceeded``, etc.) — see
    ``subscription_service.py:687`` + ``:699``. Verify the decorator
    propagates the upstream ``message`` verbatim as ``detail``."""
    module, fake = decorator_module
    fake.check_usage_limits.return_value = {
        "allowed": False,
        "message": "Wedding limit exceeded (3/3). Upgrade to add more.",
        "current_usage": 3,
        "limit": 3,
    }

    @module.enforce_subscription_limit("weddings")
    async def handler(current_user=None):
        return "should-not-reach"

    user = _build_user()

    with pytest.raises(HTTPException) as exc:
        _run(handler(current_user=user))

    assert exc.value.status_code == 402, (
        "Cap-exceeded responses must be 402 Payment Required. 403 would "
        "route the frontend to 'access denied' instead of the upgrade CTA."
    )
    assert exc.value.detail == "Wedding limit exceeded (3/3). Upgrade to add more."
    fake.increment_usage.assert_not_called()


def test_allowed_false_without_message_falls_back_to_resource_name(decorator_module):
    """Missing ``message`` on the check result shouldn't leak a KeyError —
    decorator falls back to ``Subscription limit exceeded for {resource_type}``."""
    module, fake = decorator_module
    fake.check_usage_limits.return_value = {"allowed": False}

    @module.enforce_subscription_limit("ai_credits")
    async def handler(current_user=None):
        return "should-not-reach"

    user = _build_user()

    with pytest.raises(HTTPException) as exc:
        _run(handler(current_user=user))

    assert exc.value.status_code == 402
    assert "ai_credits" in exc.value.detail


# ---------------------------------------------------------------------------
# Happy path + increment-on-create heuristic
# ---------------------------------------------------------------------------


def test_allowed_true_create_handler_fires_increment_usage(decorator_module):
    """``create`` in the wrapped function name opts the handler into
    post-hoc ``increment_usage`` — see subscription_decorators.py:55.
    This is a load-bearing naming convention; a refactor that renames
    a create endpoint to e.g. ``new_wedding`` would silently stop
    incrementing usage."""
    module, fake = decorator_module
    fake.check_usage_limits.return_value = {"allowed": True, "remaining": 2}

    @module.enforce_subscription_limit("weddings", amount=1)
    async def create_wedding(current_user=None):
        return {"wedding_id": "wed_123"}

    user = _build_user()
    result = _run(create_wedding(current_user=user))

    assert result == {"wedding_id": "wed_123"}
    fake.check_usage_limits.assert_awaited_once_with("user_test", "weddings", 1)
    fake.increment_usage.assert_awaited_once_with("user_test", "weddings", 1)


def test_allowed_true_non_create_handler_does_not_increment(decorator_module):
    """Reading endpoints (``get_*``, ``list_*``, etc.) still enforce limits
    but must NOT increment usage — otherwise every GET would burn a seat."""
    module, fake = decorator_module
    fake.check_usage_limits.return_value = {"allowed": True, "remaining": 50}

    @module.enforce_subscription_limit("ai_credits")
    async def list_ai_usage(current_user=None):
        return {"used": 50, "total": 100}

    user = _build_user()
    result = _run(list_ai_usage(current_user=user))

    assert result["used"] == 50
    fake.check_usage_limits.assert_awaited_once()
    fake.increment_usage.assert_not_called()


def test_custom_amount_flows_to_check_and_increment(decorator_module):
    """A bulk operation (e.g. ``amount=25`` AI credits for a batch job)
    must forward that amount to both the check and the increment call —
    mismatches here cause under- or over-counting."""
    module, fake = decorator_module
    fake.check_usage_limits.return_value = {"allowed": True, "remaining": 75}

    @module.enforce_subscription_limit("ai_credits", amount=25)
    async def create_ai_batch(current_user=None):
        return {"batch_id": "batch_1"}

    user = _build_user()
    _run(create_ai_batch(current_user=user))

    fake.check_usage_limits.assert_awaited_once_with("user_test", "ai_credits", 25)
    fake.increment_usage.assert_awaited_once_with("user_test", "ai_credits", 25)


# ---------------------------------------------------------------------------
# Unexpected-error wrapper
# ---------------------------------------------------------------------------


def test_unexpected_exception_becomes_500(decorator_module):
    """Any non-HTTPException from ``check_usage_limits`` is wrapped as a
    500 so callers don't see raw tracebacks. The wrapper lives at
    subscription_decorators.py:64-68 — if it's ever loosened, this test
    should fail and the change can be evaluated explicitly."""
    module, fake = decorator_module
    fake.check_usage_limits.side_effect = RuntimeError("mongo went away")

    @module.enforce_subscription_limit("weddings")
    async def handler(current_user=None):
        return "should-not-reach"

    user = _build_user()

    with pytest.raises(HTTPException) as exc:
        _run(handler(current_user=user))

    assert exc.value.status_code == 500
    assert "mongo went away" in exc.value.detail


def test_http_exception_from_downstream_passes_through_unchanged(decorator_module):
    """HTTPExceptions raised by the wrapped handler (not by
    check_usage_limits) must bubble up with their original status and
    detail — the decorator must not re-wrap them as 500s."""
    module, fake = decorator_module
    fake.check_usage_limits.return_value = {"allowed": True, "remaining": 10}

    @module.enforce_subscription_limit("weddings")
    async def create_wedding(current_user=None):
        raise HTTPException(status_code=409, detail="duplicate wedding name")

    user = _build_user()

    with pytest.raises(HTTPException) as exc:
        _run(create_wedding(current_user=user))

    assert exc.value.status_code == 409
    assert exc.value.detail == "duplicate wedding name"
    # increment_usage must NOT run if the handler itself raised — cap
    # accounting has to reflect actual resource creation, not attempts.
    fake.increment_usage.assert_not_called()
