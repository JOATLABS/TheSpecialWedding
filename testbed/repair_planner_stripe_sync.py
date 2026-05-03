#!/usr/bin/env python3
"""
Planner Stripe → Mongo Sync Repair — Live Driver
=================================================

Repairs the case where a planner has paid in Stripe but the local
Mongo state never converged to ``active``.  Fires the same code path
as the ``customer.subscription.created`` webhook would — directly via
``StripeService._sync_subscription_state`` — and polls until the user
record flips, mirroring ``_wait_for_subscription_active`` from
``verify_planner_email_change.py``.

When this is needed
-------------------

* A webhook delivery failed at some point (e.g. early backend 500),
  Stripe stopped retrying after the event aged out, and the local DB
  is stuck in ``pending_payment``.
* A test_clock + checkout flow created a customer whose
  ``metadata.user_id`` doesn't match the platform user, so
  ``_sync_subscription_state`` returned without writing to
  ``user_subscriptions``.
* Local dev forgot to start ``stripe listen`` before the first
  checkout completed.

What the driver does
--------------------

  RESOLVE   — Find the planner row by email; pull stripe_customer_id
              from the users doc (or stripe_customers as fallback).

  STRIPE    — List active subscriptions for that customer and pick the
              most recent one.  Bail with a clear message if Stripe
              shows no subscription at all (genuine "user never paid").

  REPAIR    — Call ``stripe_service._sync_subscription_state`` with the
              resolved user_id + subscription object.  This is the
              same code path the webhook would have run.  Idempotent —
              safe to re-run.

  CONVERGE  — Poll users.subscription_status until ``active`` (or
              ``trialing``).  On timeout, dumps the same diagnostic
              bundle as ``_wait_for_subscription_active`` so the cause
              is observable from the run log.

  CACHE     — Bust the auth-extended Redis key for this email so the
              next request rebuilds from the freshly-synced values.

Usage
-----

    PLANNER_EMAIL=test_planner+formapply_a@thespecialwedding.io \\
      python testbed/repair_planner_stripe_sync.py

If ``PLANNER_EMAIL`` is unset it defaults to the FormApply test
planner that surfaced this issue.  The driver is read-from-Stripe,
write-to-Mongo — it does not call Stripe write APIs and it does not
delete anything.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from pathlib import Path

import stripe
from bson import ObjectId

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from testbed.harness import Harness  # noqa: E402

DRIVER_NAME = "repair_planner_stripe_sync"

DEFAULT_EMAIL = "test_planner+formapply_a@thespecialwedding.io"
PLANNER_EMAIL = os.getenv("PLANNER_EMAIL", DEFAULT_EMAIL)


async def _sync_via_stripe_service(user_id: str, subscription: stripe.Subscription):
    """Fire the same code path the webhook would have run.

    ``_sync_subscription_state`` expects ``subscription`` to be a plain
    ``dict`` (every internal access goes through ``.get(...)`` and
    ``["..."]``).  ``handle_webhook_event`` does this conversion at the
    boundary (see ``stripe_service.py:1557-1561``) — when called from
    the webhook path the data comes in as JSON and is already dict-shaped.

    When called directly from this driver, ``stripe.Subscription.list``
    returns ``StripeObject`` instances.  Recent Stripe Python SDK versions
    do NOT subclass dict on StripeObject, so ``subscription.get(...)``
    falls through ``__getattr__`` → ``__getitem__`` looking for the key
    ``"get"`` and raises ``KeyError("get")`` (re-raised as
    ``AttributeError: get``).  Convert to a plain dict here so the same
    code path the webhook uses works unchanged.
    """
    from app.services.stripe_service import stripe_service

    if hasattr(subscription, "to_dict"):
        subscription_dict = subscription.to_dict()
    else:
        subscription_dict = dict(subscription)

    customer_id = subscription_dict.get("customer")

    return await stripe_service._sync_subscription_state(
        user_id=user_id,
        subscription=subscription_dict,
        customer_id=customer_id,
    )


async def _bust_auth_cache(email: str) -> None:
    """Bust the auth-extended Redis key so the next request rebuilds."""
    try:
        from app.core.cache import cache, init_cache
        from app.dependencies.auth_extended import invalidate_auth_cache

        await init_cache()
        if not cache.enabled:
            print("  (Redis disabled — auth cache bust skipped, no-op)")
            return
        await invalidate_auth_cache(email)
        print(f"  ✅ Auth cache key cleared for {email}")
    except Exception as exc:
        print(f"  ⚠️ Auth cache bust failed (non-fatal): {exc}")


def _resolve_customer_id(h: Harness, email: str) -> tuple[str, str]:
    """Return (user_id, stripe_customer_id) for the planner."""
    user = h.mongo["users"].find_one({"email": email})
    if not user:
        raise SystemExit(f"No users row for {email}; nothing to repair.")
    user_id = str(user["_id"])

    customer_id = user.get("stripe_customer_id")
    if not customer_id:
        link = h.mongo["stripe_customers"].find_one({"user_id": user_id})
        if link:
            customer_id = link.get("stripe_customer_id")
    if not customer_id:
        link = h.mongo["stripe_customers"].find_one({"email": email})
        if link:
            customer_id = link.get("stripe_customer_id")

    if not customer_id:
        raise SystemExit(
            f"No stripe_customer_id resolvable for {email}. "
            "Either the user never started checkout, or the link rows "
            "were never written. Check users.stripe_customer_id and the "
            "stripe_customers collection."
        )

    print(
        f"  ✅ Resolved {email}: user_id={user_id} customer_id={customer_id} "
        f"users.subscription_status={user.get('subscription_status')!r}"
    )
    return user_id, customer_id


def _pick_subscription(customer_id: str) -> stripe.Subscription:
    """Pick the most recent active/trialing/past_due sub for this customer.

    Falls back to the most recent subscription of any status if none
    are currently active — that handles the case where the planner has
    a paid sub that's somehow shown as canceled in our local DB but is
    fine in Stripe.
    """
    # Prefer live (non-canceled) subs.
    live = stripe.Subscription.list(
        customer=customer_id,
        status="all",
        limit=20,
    )
    if not live.data:
        raise SystemExit(
            f"Stripe shows zero subscriptions for customer {customer_id}. "
            "If the user paid, they paid one-off (no subscription was "
            "created). This driver only repairs subscription state."
        )

    preferred = [s for s in live.data if s.status in {"active", "trialing", "past_due"}]
    chosen = preferred[0] if preferred else live.data[0]
    print(
        f"  ✅ Using subscription {chosen.id} "
        f"(status={chosen.status}, created={chosen.created})"
    )
    return chosen


def _wait_for_active(
    h: Harness, user_id: str, max_attempts: int = 24, poll_sec: float = 1.5
):
    """Poll until users.subscription_status is active/trialing.

    Borrows the diagnostic dump pattern from
    ``_wait_for_subscription_active`` in ``verify_planner_email_change``.
    """
    print(f"  ⏳ Polling users.subscription_status (max {max_attempts} × {poll_sec}s)…")
    last_status = "<unset>"
    for attempt in range(1, max_attempts + 1):
        user = h.mongo["users"].find_one(
            {"_id": ObjectId(user_id)},
            {"subscription_status": 1, "is_active": 1},
        )
        last_status = (user or {}).get("subscription_status")
        if last_status in {"active", "trialing"}:
            print(
                f"  ✅ users.subscription_status = {last_status!r} "
                f"after {attempt} poll(s)"
            )
            return
        print(
            f"     poll {attempt}/{max_attempts}: subscription_status={last_status!r}"
        )
        time.sleep(poll_sec)

    # Diagnostic dump on timeout.
    print("─" * 72)
    print("Subscription state did not converge to active. Dumping state:")
    print("─" * 72)
    user = h.mongo["users"].find_one({"_id": ObjectId(user_id)}) or {}
    print(
        f"  users[{user_id}]:\n"
        f"    subscription_status    = {user.get('subscription_status')!r}\n"
        f"    is_active              = {user.get('is_active')!r}\n"
        f"    stripe_customer_id     = {user.get('stripe_customer_id')!r}\n"
        f"    stripe_subscription_id = {user.get('stripe_subscription_id')!r}"
    )
    sub_doc = h.mongo["user_subscriptions"].find_one({"user_id": user_id}) or {}
    if sub_doc:
        print(
            f"  user_subscriptions[{user_id}]:\n"
            f"    status                 = {sub_doc.get('status')!r}\n"
            f"    plan_id                = {sub_doc.get('plan_id')!r}\n"
            f"    stripe_subscription_id = {sub_doc.get('stripe_subscription_id')!r}"
        )
    else:
        print(
            f"  user_subscriptions[{user_id}]: <none> ← _sync_subscription_state "
            "returned but did not write a row. Check that user_id matched."
        )
    raise SystemExit(
        f"users.subscription_status stuck at {last_status!r} after sync. "
        "Dump above shows the actual state."
    )


def main() -> int:
    h = Harness(driver_name=DRIVER_NAME)
    h.preflight()
    h.banner(f"REPAIR — {DRIVER_NAME} for {PLANNER_EMAIL}")

    # Bind Stripe key (harness already does, but explicit here for clarity).
    stripe.api_key = h.config.stripe_secret_key

    # ── RESOLVE ─────────────────────────────────────────────────
    print("\nPhase 1/4 — RESOLVE")
    user_id, customer_id = _resolve_customer_id(h, PLANNER_EMAIL)

    # ── STRIPE ──────────────────────────────────────────────────
    print("\nPhase 2/4 — STRIPE")
    subscription = _pick_subscription(customer_id)

    # ── REPAIR ──────────────────────────────────────────────────
    print("\nPhase 3/4 — REPAIR (calling _sync_subscription_state)")
    result = asyncio.run(_sync_via_stripe_service(user_id, subscription))
    print(
        f"  ✅ _sync_subscription_state returned:\n"
        f"     status                 = {result.get('status')!r}\n"
        f"     stripe_status          = {result.get('stripe_status')!r}\n"
        f"     stripe_subscription_id = {result.get('stripe_subscription_id')!r}"
    )

    # ── CONVERGE ────────────────────────────────────────────────
    print("\nPhase 4/4 — CONVERGE + CACHE BUST")
    _wait_for_active(h, user_id)
    asyncio.run(_bust_auth_cache(PLANNER_EMAIL))

    h.banner("REPAIR COMPLETE")
    print(f"  Planner {PLANNER_EMAIL} should now pass the subscription gate.")
    print("  Reload /admin/planner in your browser to see the dashboard.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        logging.getLogger(DRIVER_NAME).error(
            f"Repair driver aborted: {exc}", exc_info=True
        )
        raise SystemExit(1)
