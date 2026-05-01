#!/usr/bin/env python3
"""Clean up state from verify_auth_redis_cache.py.

Removes the seeded planner's Mongo chain (users, user_subscriptions,
stripe_customers), deletes the corresponding Stripe customer, and clears
the Redis auth-cache key for the plus-variant email.  Idempotent — safe
to run repeatedly even if the state file is missing.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

import stripe

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from testbed.harness import Harness  # noqa: E402

STATE_FILE = (
    Path(__file__).resolve().parent / ".testbed" / "auth_redis_cache_state.json"
)


def _delete_redis_key(cache_singleton, key: str) -> None:
    """Best-effort Redis key delete; ignores any error."""
    try:
        asyncio.get_event_loop().run_until_complete(cache_singleton.delete(key))
    except Exception as exc:
        logging.getLogger("cleanup_auth_redis_cache_state").debug(
            f"Redis delete failed (non-fatal) for {key}: {exc}"
        )


def main() -> int:
    h = Harness(driver_name="cleanup_auth_redis_cache_state")
    h.banner("CLEANUP — Auth Redis cache verifier")

    if not STATE_FILE.exists():
        h.log.info(f"No state file at {STATE_FILE}; nothing to clean.")
        return 0

    state = json.loads(STATE_FILE.read_text())
    user_id = state.get("user_id")
    email = state.get("email")
    customer_id = state.get("customer_id")
    cache_key = state.get("cache_key")

    # 1. Mongo chain.  Reuse the harness helper so cancelled subs etc.
    #    are torn down consistently with the other drivers.
    if email:
        try:
            removed = h.delete_user_chain(email)
            h.log.info(f"  Removed Mongo chain for {email}: {removed}")
        except AttributeError:
            # Older harness versions may not expose delete_user_chain;
            # fall back to manual removal of the three core collections.
            h.mongo["users"].delete_many({"email": email})
            h.mongo["user_subscriptions"].delete_many({"user_email": email})
            h.mongo["stripe_customers"].delete_many({"email": email})
            h.log.info(f"  Removed Mongo rows for {email} via fallback path")

    # 2. Stripe customer (clockless, so we own the lifecycle).
    if customer_id:
        try:
            stripe.api_key = h.config.stripe_secret_key
            stripe.Customer.delete(customer_id)
            h.log.info(f"  Deleted Stripe customer {customer_id}")
        except stripe.error.InvalidRequestError as exc:
            # Already deleted on a prior run.
            h.log.info(f"  Stripe customer already gone: {exc}")
        except Exception as exc:
            h.log.warning(f"  Stripe customer delete raised (non-fatal): {exc}")

    # 3. Redis key for the auth cache.  Should already be gone after the
    #    TTL expired, but a failed run can leave a stale key around.
    if cache_key:
        try:
            from app.core.cache import cache as cache_singleton  # noqa: WPS433
            from app.core.cache import init_cache  # noqa: WPS433

            asyncio.get_event_loop().run_until_complete(init_cache())
            _delete_redis_key(cache_singleton, cache_key)
            h.log.info(f"  Cleared Redis key {cache_key}")
        except Exception as exc:
            h.log.debug(f"  Redis cleanup skipped: {exc}")

    STATE_FILE.unlink(missing_ok=True)
    if user_id:
        h.log.info(f"  Removed state file for user_id={user_id}")
    h.log.info("Cleanup complete.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        logging.getLogger("cleanup_auth_redis_cache_state").error(
            f"Cleanup aborted: {exc}", exc_info=True
        )
        raise SystemExit(1)
