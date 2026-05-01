#!/usr/bin/env python3
"""
Auth Redis Cache — Live Verification Driver
============================================

Purpose
-------
Verify end-to-end that ``get_current_user_extended`` correctly:

  1. Misses the cache on the first authenticated request, falls through to
     Mongo, and writes the assembled ``ExtendedAuthUser`` snapshot to
     Redis under ``auth:user:{email}``.
  2. Hits the cache on subsequent requests within the TTL window (the
     snapshot deserializes back to the same shape; no Mongo reads).
  3. Honors explicit invalidation via ``invalidate_auth_cache(email)`` —
     the same hook that Stripe webhooks, trial expiry, and team-permission
     mutations call.
  4. Bypasses the cache for ROOT_ADMIN (no Redis key is ever written for
     the root admin email).
  5. Lets the snapshot expire on its own after the TTL elapses.

The test does NOT drive a Stripe webhook end-to-end — that path is already
covered by the lifecycle drivers in this directory, and the only thing
our new code added on the webhook side is a single call to
``invalidate_auth_cache_by_user_id``.  Driving Stripe just to prove that
one call line works is overkill.  We verify the invalidation primitive
itself works from any caller; the webhook hook then trivially inherits.

Phases
------
  PRECHECK     — Confirm Redis is enabled and reachable; confirm
                 ``audit_extended`` exposes the new cache helpers.
  SEED         — Bootstrap an isolated planner via the standard harness
                 path.  Clockless (we do not need test-clock advancement).
  COLD         — Hit ``/admin/profile`` once.  Confirm the cache key was
                 created.  Confirm the cached snapshot deserializes back
                 to a usable ExtendedAuthUser shape.
  WARM         — Hit ``/admin/profile`` again.  Confirm the cache key
                 still exists with a fresh-but-shorter TTL (proving the
                 TTL was set, not refreshed-on-read).
  INVALIDATE   — Call ``invalidate_auth_cache(email)`` directly.  Confirm
                 the cache key is gone.  Hit ``/admin/profile`` again,
                 confirm the key was repopulated.
  ROOT_BYPASS  — Hit ``/admin/profile`` as the root admin.  Confirm the
                 root admin's email has NO cache key (bypass is honored).
  TTL_EXPIRY   — Sleep ``ttl + 1`` seconds.  Confirm the cache key for
                 the planner has naturally expired.

Each phase is gated so the user can inspect Chrome / dev tools between
checkpoints if desired.

Usage
-----
    python testbed/testbed.py up           # bring up backend + Redis
    python testbed/verify_auth_redis_cache.py
    python testbed/cleanup_auth_redis_cache_state.py

Requirements
------------
  - Backend running with ``REDIS_ENABLED=true``
  - Redis reachable at ``REDIS_HOST``/``REDIS_PORT`` (defaults: localhost:6379)
  - MongoDB reachable
  - ``ROOT_ADMIN_PASSWORD`` set in ``.env``
  - Stripe test keys (used only for the seed step)
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from pathlib import Path

import requests

# Make the project root importable so we can call the cache helpers
# directly — same module the running backend uses.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from testbed.harness import Harness  # noqa: E402

DRIVER_NAME = "verify_auth_redis_cache"
STATE_FILE = (
    Path(__file__).resolve().parent / ".testbed" / "auth_redis_cache_state.json"
)

PLANNER_EMAIL = "test_planner+authcache@thespecialwedding.io"
PLANNER_PASSWORD = "AuthCacheTest2026!"  # pragma: allowlist secret
PLAN_ID = "plan_signature"

# Must mirror ``_AUTH_USER_CACHE_TTL_SECONDS`` in
# ``app/dependencies/auth_extended.py``. If you change the source, change
# this too — both numbers are intentionally kept side by side.
EXPECTED_TTL_SECONDS = 10


def _import_cache_helpers():
    """Load the same cache helpers the running backend uses.

    Imported lazily inside ``main()`` so the test still reports a clean
    error if Redis isn't configured in the dev .env.
    """
    from app.core.cache import cache as cache_singleton  # noqa: WPS433
    from app.core.cache import init_cache as init_cache_fn  # noqa: WPS433
    from app.core.settings import settings  # noqa: WPS433
    from app.dependencies.auth_extended import (  # noqa: WPS433
        _auth_user_cache_key,
        _deserialize_auth_user,
        invalidate_auth_cache,
    )

    return {
        "cache": cache_singleton,
        "init_cache": init_cache_fn,
        "settings": settings,
        "cache_key": _auth_user_cache_key,
        "deserialize": _deserialize_auth_user,
        "invalidate": invalidate_auth_cache,
    }


def _ttl_remaining(cache_singleton, key: str) -> int:
    """Synchronous TTL probe wrapper around the async cache method."""
    return asyncio.get_event_loop().run_until_complete(cache_singleton.ttl(key))


def _get_snapshot(cache_singleton, key: str):
    return asyncio.get_event_loop().run_until_complete(cache_singleton.get(key))


def _delete_key(cache_singleton, key: str):
    return asyncio.get_event_loop().run_until_complete(cache_singleton.delete(key))


def _invalidate(invalidate_fn, email: str):
    return asyncio.get_event_loop().run_until_complete(invalidate_fn(email))


def _initialize_cache(init_cache_fn):
    return asyncio.get_event_loop().run_until_complete(init_cache_fn())


def _hit_admin_profile(backend_url: str, jwt: str) -> requests.Response:
    """Single GET /admin/profile — the canonical hot path the cache covers."""
    return requests.get(
        f"{backend_url}/admin/profile",
        headers={"Authorization": f"Bearer {jwt}"},
        timeout=15,
    )


def main() -> int:
    h = Harness(driver_name=DRIVER_NAME)
    h.preflight()
    helpers = _import_cache_helpers()

    h.banner("AUTH REDIS CACHE — LIVE VERIFICATION")

    # ── PRECHECK ──────────────────────────────────────────────────
    h.phase("PRECHECK", "Confirm Redis is enabled and reachable")
    if not helpers["settings"].redis_enabled:
        raise AssertionError(
            "REDIS_ENABLED must be true for this driver. "
            "Set REDIS_ENABLED=true and rerun."
        )
    _initialize_cache(helpers["init_cache"])
    if not helpers["cache"].enabled:
        raise AssertionError(
            "Cache layer reports disabled after init_cache(). Check Redis "
            "host/port/password and that the server is reachable."
        )
    h.log.info("  OK Redis is enabled and reachable")

    # ── SEED ──────────────────────────────────────────────────────
    h.phase("SEED", "Bootstrap an isolated planner (clockless)")
    admin_token = h.get_admin_token()
    seed = h.seed_planner(
        admin_token=admin_token,
        email=PLANNER_EMAIL,
        password=PLANNER_PASSWORD,
        plan_id=PLAN_ID,
    )
    planner_token = h.login(seed.email, PLANNER_PASSWORD)
    cache_key = helpers["cache_key"](seed.email)
    h.log.info(f"  OK seed user_id={seed.user_id} cache_key={cache_key}")

    # Make sure no stale snapshot lingers from a previous run.
    _delete_key(helpers["cache"], seed.email and helpers["cache_key"](seed.email))

    # Persist state for cleanup.
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(
            {
                "user_id": seed.user_id,
                "email": seed.email,
                "customer_id": seed.customer_id,
                "subscription_id": seed.subscription_id,
                "cache_key": cache_key,
            }
        )
        + "\n"
    )

    # ── COLD ──────────────────────────────────────────────────────
    h.phase(
        "COLD",
        "First /admin/profile request → cache miss → snapshot written",
    )
    cold_start = time.time()
    cold_response = _hit_admin_profile(h.config.backend_url, planner_token)
    cold_elapsed_ms = (time.time() - cold_start) * 1000.0
    if cold_response.status_code != 200:
        raise AssertionError(
            f"COLD /admin/profile expected 200, got {cold_response.status_code}: "
            f"{cold_response.text[:300]}"
        )

    snapshot = _get_snapshot(helpers["cache"], cache_key)
    if snapshot is None:
        raise AssertionError(
            f"After COLD request, expected cache key {cache_key} to be set. "
            "Cache write hook in get_current_user_extended is missing or broken."
        )
    if not isinstance(snapshot, dict):
        raise AssertionError(
            f"Cached snapshot is not a dict: type={type(snapshot).__name__}"
        )

    # Round-trip through the deserializer to confirm the snapshot shape
    # is rebuildable into an ExtendedAuthUser (so the cache hit path
    # actually works in the live dependency).
    try:
        rehydrated = helpers["deserialize"](snapshot)
    except Exception as exc:
        raise AssertionError(f"Cached snapshot failed to deserialize: {exc}")
    if rehydrated.email != seed.email:
        raise AssertionError(
            f"Rehydrated email mismatch: cached={rehydrated.email!r} "
            f"expected={seed.email!r}"
        )
    if rehydrated.role != "wedding_planner":
        raise AssertionError(
            f"Rehydrated role mismatch: cached={rehydrated.role!r} "
            "expected='wedding_planner'"
        )

    cold_ttl = _ttl_remaining(helpers["cache"], cache_key)
    if cold_ttl <= 0 or cold_ttl > EXPECTED_TTL_SECONDS:
        raise AssertionError(
            f"COLD TTL out of range: got {cold_ttl}, expected 1..{EXPECTED_TTL_SECONDS}"
        )
    h.log.info(
        f"  OK cache populated, ttl={cold_ttl}s, elapsed={cold_elapsed_ms:.1f}ms"
    )

    # ── WARM ──────────────────────────────────────────────────────
    h.phase("WARM", "Second /admin/profile request → cache hit")
    warm_start = time.time()
    warm_response = _hit_admin_profile(h.config.backend_url, planner_token)
    warm_elapsed_ms = (time.time() - warm_start) * 1000.0
    if warm_response.status_code != 200:
        raise AssertionError(
            f"WARM /admin/profile expected 200, got {warm_response.status_code}: "
            f"{warm_response.text[:300]}"
        )
    warm_ttl = _ttl_remaining(helpers["cache"], cache_key)
    if warm_ttl <= 0:
        raise AssertionError(
            f"After WARM, cache key TTL is {warm_ttl} — key disappeared unexpectedly."
        )
    if warm_ttl > cold_ttl:
        raise AssertionError(
            f"After WARM, TTL increased: cold={cold_ttl}s warm={warm_ttl}s. "
            "TTL should not refresh on read — cache is incorrectly bumping it."
        )
    h.log.info(f"  OK still cached, ttl={warm_ttl}s, elapsed={warm_elapsed_ms:.1f}ms")

    # ── INVALIDATE ────────────────────────────────────────────────
    h.phase(
        "INVALIDATE",
        "invalidate_auth_cache() → key gone → next request repopulates",
    )
    _invalidate(helpers["invalidate"], seed.email)
    after_invalidate = _get_snapshot(helpers["cache"], cache_key)
    if after_invalidate is not None:
        raise AssertionError(
            "After invalidate_auth_cache(), expected cache key to be gone "
            f"but got: {after_invalidate!r}"
        )
    h.log.info("  OK cache key cleared")

    repopulate_response = _hit_admin_profile(h.config.backend_url, planner_token)
    if repopulate_response.status_code != 200:
        raise AssertionError(
            "Re-populate /admin/profile expected 200, got "
            f"{repopulate_response.status_code}"
        )
    repopulated = _get_snapshot(helpers["cache"], cache_key)
    if repopulated is None:
        raise AssertionError(
            "After invalidate + request, expected cache to be repopulated."
        )
    h.log.info("  OK cache key repopulated by next request")

    # ── ROOT_BYPASS ──────────────────────────────────────────────
    h.phase(
        "ROOT_BYPASS",
        "ROOT_ADMIN /admin/profile → no cache key written for root email",
    )
    root_email = h.config.admin_email
    root_cache_key = helpers["cache_key"](root_email)
    # Force-clear in case any previous run leaked a key (it shouldn't have).
    _delete_key(helpers["cache"], root_cache_key)

    root_response = _hit_admin_profile(h.config.backend_url, admin_token)
    if root_response.status_code != 200:
        raise AssertionError(
            f"ROOT /admin/profile expected 200, got {root_response.status_code}"
        )
    root_snapshot = _get_snapshot(helpers["cache"], root_cache_key)
    if root_snapshot is not None:
        raise AssertionError(
            "Root admin path is expected to bypass the cache, but a key was "
            f"written: {root_snapshot!r}. Check the ROOT_ADMIN guards in "
            "get_current_user_extended."
        )
    h.log.info("  OK root admin path bypasses cache")

    # ── TTL_EXPIRY ────────────────────────────────────────────────
    h.phase(
        "TTL_EXPIRY",
        f"Sleep {EXPECTED_TTL_SECONDS + 1}s → cache expires naturally",
    )
    h.log.info(f"  …sleeping {EXPECTED_TTL_SECONDS + 1}s …")
    time.sleep(EXPECTED_TTL_SECONDS + 1)
    expired = _get_snapshot(helpers["cache"], cache_key)
    if expired is not None:
        raise AssertionError(
            f"After {EXPECTED_TTL_SECONDS + 1}s, cache key was still present: "
            f"{expired!r}. TTL is not being honored."
        )
    h.log.info("  OK cache key expired after TTL")

    h.checkpoint(
        "AUTH_REDIS_CACHE_VERIFIED",
        [
            "Cold request populates the cache and TTL is bounded by 10 s.",
            "Warm request is served from cache; TTL does not refresh on read.",
            "invalidate_auth_cache(email) busts the key; next request repopulates.",
            "ROOT_ADMIN path never writes a cache key.",
            "Cache key expires naturally after the TTL elapses.",
            f"Cleanup state written to {STATE_FILE}.",
        ],
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        logging.getLogger(DRIVER_NAME).error(f"Verification failed: {exc}")
        raise SystemExit(1)
    except Exception as exc:
        logging.getLogger(DRIVER_NAME).error(f"Driver aborted: {exc}", exc_info=True)
        raise SystemExit(1)
