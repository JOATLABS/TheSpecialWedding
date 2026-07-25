"""
ROOT_ADMIN acquisition analytics — proxies Umami's REST API server-to-server.

This module exposes a single endpoint, `GET /admin/analytics/funnel`, that
aggregates public-marketing-site analytics for the root admin dashboard. It is
strictly gated to root admin (developer/operator) — planners and team members
never see this surface.

Why a backend proxy at all (versus calling Umami from the browser):
- Keeps the Umami API key on the server. Browsing into the Umami UI is fine,
  but baking a key into the client bundle is not.
- Lets us cache aggregated funnel responses for ~5 minutes so the dashboard
  doesn't hammer Umami on every page load.
- Centralises the funnel definition (which event names roll up into which
  funnel stage) on the backend, so the frontend stays presentation-only.

Umami v3 API surface used:
- POST /auth/login                — exchange username+password for a JWT
- GET /websites/{id}/stats        — pageviews, visitors, visits, bounce rate
- GET /websites/{id}/metrics      — top dimensions (referrer, url, event)

Auth model:
- Self-hosted v3 has no API-key UI; backend logs in with UMAMI_USERNAME +
  UMAMI_PASSWORD, caches the resulting JWT in Redis, sends as
  `Authorization: Bearer <token>` for subsequent calls.
- If UMAMI_API_KEY is set (Umami Cloud, or a future self-hosted build that
  exposes API keys), it takes precedence and is sent as `x-umami-api-key`,
  skipping the login round-trip.
- On 401 with a cached JWT, the cache is busted and one re-login retry runs.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.cache import cache
from app.core.config import Settings
from app.dependencies.auth_extended import ExtendedAuthUser, require_root_admin

logger = logging.getLogger(__name__)

settings = Settings()

router = APIRouter()

# Funnel event names — must stay in sync with the `umamiTrack(...)` callsites
# in `app/utils/umami.ts` consumers (PricingSignupSection, SignupModal,
# IntegratedHeroSection). Order matters: each entry should be a downstream
# step relative to the one above so the UI can render conversion ratios.
FUNNEL_EVENTS: tuple[str, ...] = (
    "hero_cta_clicked",
    "pricing_viewed",
    "pricing_cta_clicked",
    "signup_modal_opened",
    "signup_step_advanced",
    "signup_registered",
    "signup_checkout_redirect",
)

# Supported window labels and their durations in seconds. The frontend selector
# offers exactly these three; anything else is rejected at the query layer.
WINDOWS: dict[str, int] = {
    "24h": 24 * 60 * 60,
    "7d": 7 * 24 * 60 * 60,
    "30d": 30 * 24 * 60 * 60,
}

# Cache TTL for aggregated funnel responses. Five minutes balances dashboard
# freshness against the cost of a fan-out to Umami every page load.
CACHE_TTL_SECONDS = 5 * 60

# Per-request timeout for individual Umami HTTP calls. We fan out four reads
# in parallel; 8s per call keeps the worst-case admin-page wait under ~10s.
UMAMI_REQUEST_TIMEOUT_SECONDS = 8.0

# JWT cache TTL. Umami's login token default lifetime is ~24h; we cache for
# 12h so a token is always well within its validity window even if Umami's
# clock and ours drift. On 401, the cache is busted and we re-login once.
UMAMI_TOKEN_CACHE_TTL_SECONDS = 12 * 60 * 60
UMAMI_TOKEN_CACHE_KEY = "admin:analytics:umami_token"


def _require_umami_configured() -> None:
    """Fail fast with a 503 if the Umami connection isn't fully configured.

    Returning 503 (not 500) signals to the frontend that this is a deploy /
    configuration gap rather than a code bug, which lets the admin tile render
    a "not configured" state instead of a generic error.

    Auth is satisfied by either an API key (Umami Cloud) OR the
    username/password pair (self-hosted login flow). Both being unset is a
    misconfiguration.
    """

    missing: list[str] = []
    if not settings.UMAMI_API_BASE:
        missing.append("UMAMI_API_BASE")
    if not settings.UMAMI_WEBSITE_ID:
        missing.append("UMAMI_WEBSITE_ID")

    has_api_key = bool(settings.UMAMI_API_KEY)
    has_login = bool(settings.UMAMI_USERNAME and settings.UMAMI_PASSWORD)
    if not has_api_key and not has_login:
        missing.append("UMAMI_API_KEY or (UMAMI_USERNAME + UMAMI_PASSWORD)")

    if missing:
        raise HTTPException(
            status_code=503,
            detail=f"Umami analytics not configured. Missing: {', '.join(missing)}",
        )


async def _login_to_umami(client: httpx.AsyncClient) -> str:
    """Exchange the configured username/password for a Umami JWT.

    Caller is responsible for caching the returned token. We deliberately do
    *not* cache here so the caller controls the re-login policy (e.g., when a
    401 has just invalidated a stale token in the cache).
    """

    base = (settings.UMAMI_API_BASE or "").rstrip("/")
    try:
        response = await client.post(
            f"{base}/auth/login",
            json={
                "username": settings.UMAMI_USERNAME,
                "password": settings.UMAMI_PASSWORD,
            },
        )
    except httpx.RequestError as exc:
        logger.warning("Umami login request error: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=(
                f"Could not reach Umami at {base} for login. "
                "Check UMAMI_API_BASE and that the Umami service is reachable from the backend."
            ),
        ) from exc

    if response.status_code in (401, 403):
        raise HTTPException(
            status_code=503,
            detail=(
                "Umami rejected the username/password. Verify UMAMI_USERNAME and UMAMI_PASSWORD "
                "match a Umami account (Manage → Users in the Umami admin UI)."
            ),
        )
    if response.status_code >= 400:
        logger.warning(
            "Umami login returned %s: %s", response.status_code, response.text[:300]
        )
        raise HTTPException(
            status_code=503,
            detail=f"Umami login failed with HTTP {response.status_code}.",
        )

    try:
        body = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=503,
            detail="Umami login returned a non-JSON body.",
        ) from exc

    token = body.get("token") if isinstance(body, dict) else None
    if not isinstance(token, str) or not token:
        raise HTTPException(
            status_code=503,
            detail="Umami login response did not contain a token field.",
        )
    return token


async def _get_umami_token(
    client: httpx.AsyncClient, force_refresh: bool = False
) -> str:
    """Return a Umami JWT, served from cache when possible.

    Passing `force_refresh=True` skips the cache and logs in fresh. Used by
    `_umami_get` after a 401 so a stale token doesn't keep getting retried.
    """

    if not force_refresh:
        cached = await cache.get(UMAMI_TOKEN_CACHE_KEY)
        if isinstance(cached, str) and cached:
            return cached

    token = await _login_to_umami(client)
    await cache.set(UMAMI_TOKEN_CACHE_KEY, token, expire=UMAMI_TOKEN_CACHE_TTL_SECONDS)
    return token


def _window_bounds_ms(window: str) -> tuple[int, int]:
    """Translate a window label into Umami's `startAt`/`endAt` millisecond pair."""

    seconds = WINDOWS.get(window)
    if seconds is None:
        # Belt and braces — the Query() validator below should catch this.
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported window '{window}'. Use 24h, 7d, or 30d.",
        )
    now = datetime.now(UTC)
    end = int(now.timestamp() * 1000)
    start = int((now - timedelta(seconds=seconds)).timestamp() * 1000)
    return start, end


async def _umami_get(
    client: httpx.AsyncClient,
    path: str,
    params: dict[str, Any],
) -> Any:
    """GET a Umami endpoint, normalising auth + error handling.

    On 401 with the JWT auth path, the token cache is busted and we re-login
    exactly once before giving up — this absorbs the case where Umami invalidated
    a token (restart, password rotation) without making the caller restart.
    Returns the JSON body on 2xx. Raises HTTPException(503) on persistent
    failure with an instructive `detail`.
    """

    base = (settings.UMAMI_API_BASE or "").rstrip("/")
    url = f"{base}{path}"

    async def _attempt(force_token_refresh: bool) -> httpx.Response:
        headers = (
            {"x-umami-api-key": settings.UMAMI_API_KEY}
            if settings.UMAMI_API_KEY
            else {
                "Authorization": f"Bearer {await _get_umami_token(client, force_refresh=force_token_refresh)}"
            }
        )
        return await client.get(url, params=params, headers=headers)

    try:
        response = await _attempt(force_token_refresh=False)
        if response.status_code == 401 and not settings.UMAMI_API_KEY:
            # JWT was rejected — most likely cached past its server-side TTL.
            # Drop the cached token, force a fresh login, retry once.
            logger.info("Umami rejected cached JWT; refreshing token and retrying once")
            await cache.delete(UMAMI_TOKEN_CACHE_KEY)
            response = await _attempt(force_token_refresh=True)
    except httpx.RequestError as exc:
        logger.warning("Umami request error for %s: %s", url, exc)
        raise HTTPException(
            status_code=503,
            detail=(
                f"Could not reach Umami at {base}. "
                "Check UMAMI_API_BASE and that the Umami service is reachable from the backend."
            ),
        ) from exc

    if response.status_code == 401:
        # Either the API key is wrong, or login+retry both 401'd (credentials bad).
        detail = (
            "Umami rejected the API key. Verify UMAMI_API_KEY in the backend env."
            if settings.UMAMI_API_KEY
            else (
                "Umami rejected the username/password. Verify UMAMI_USERNAME and "
                "UMAMI_PASSWORD match a Umami account (Manage → Users)."
            )
        )
        raise HTTPException(status_code=503, detail=detail)
    if response.status_code >= 400:
        body_snippet = response.text[:300].strip()
        logger.warning(
            "Umami %s returned %s: %s", path, response.status_code, body_snippet
        )
        # Include Umami's own response body in the detail so the admin UI shows
        # the actual upstream error (param validation, schema mismatch, etc.),
        # not just an opaque status code. Truncated to keep banner readable.
        detail = (
            f"Umami returned HTTP {response.status_code} for {path}"
            f"{f' — {body_snippet}' if body_snippet else '.'}"
        )
        raise HTTPException(status_code=503, detail=detail)
    try:
        return response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Umami returned a non-JSON body for {path}.",
        ) from exc


def _top_entry(rows: Any) -> dict[str, Any] | None:
    """Pick the highest-`value` row out of a Umami `/metrics` response.

    The response is a list of `{x: ..., y: ...}` objects in v3. We tolerate the
    older `{name: ..., value: ...}` shape too in case the user is on a slightly
    older self-hosted build.
    """

    if not isinstance(rows, list) or not rows:
        return None

    def _name(row: Any) -> str | None:
        if not isinstance(row, dict):
            return None
        return row.get("x") if "x" in row else row.get("name")

    def _value(row: Any) -> int:
        if not isinstance(row, dict):
            return 0
        raw = row.get("y") if "y" in row else row.get("value")
        try:
            return int(raw or 0)
        except (TypeError, ValueError):
            return 0

    best = max(rows, key=_value)
    name = _name(best)
    if not name:
        return None
    return {"name": name, "value": _value(best)}


def _events_to_funnel(rows: Any) -> dict[str, int]:
    """Project Umami's event-metrics rows into our fixed funnel keys.

    Any funnel event Umami hasn't seen yet defaults to 0 — the frontend renders
    those as `—` so the operator can immediately tell signal-vs-no-signal.
    """

    counts: dict[str, int] = {event: 0 for event in FUNNEL_EVENTS}
    if not isinstance(rows, list):
        return counts
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = row.get("x") if "x" in row else row.get("name")
        if name not in counts:
            continue
        raw_value = row.get("y") if "y" in row else row.get("value")
        try:
            counts[name] = int(raw_value or 0)
        except (TypeError, ValueError):
            counts[name] = 0
    return counts


def _summary_from_stats(stats: Any) -> dict[str, Any]:
    """Reshape Umami's stats payload into the dashboard summary fields.

    Umami v3 returns each metric as `{value, prev}`; we only surface the
    current-window value here. Bounce rate is computed as bounces / visits to
    avoid pushing the raw counts the dashboard doesn't need.
    """

    def _v(field: str) -> int:
        if not isinstance(stats, dict):
            return 0
        block = stats.get(field)
        if isinstance(block, dict):
            try:
                return int(block.get("value") or 0)
            except (TypeError, ValueError):
                return 0
        try:
            return int(block or 0)
        except (TypeError, ValueError):
            return 0

    pageviews = _v("pageviews")
    visitors = _v("visitors")
    visits = _v("visits")
    bounces = _v("bounces")
    total_time = _v("totaltime")

    bounce_rate = (bounces / visits) if visits > 0 else 0.0
    avg_visit_seconds = (total_time / visits) if visits > 0 else 0.0

    return {
        "pageviews": pageviews,
        "visitors": visitors,
        "visits": visits,
        "bounces": bounces,
        "bounce_rate": round(bounce_rate, 4),
        "avg_visit_seconds": round(avg_visit_seconds, 1),
    }


async def _safe_umami_get(
    client: httpx.AsyncClient, path: str, params: dict[str, Any]
) -> Any:
    """Call _umami_get but swallow 503 — return None instead.

    Used for the /metrics fan-out so one failing dimension (e.g. a permission
    split where the backend user can read /stats but not /metrics) degrades
    that single tile to '—' instead of blanking the whole funnel card.
    """

    try:
        return await _umami_get(client, path, params)
    except HTTPException as exc:
        logger.info("Soft-failing optional Umami call %s: %s", path, exc.detail)
        return None


async def _fetch_funnel_payload(window: str) -> dict[str, Any]:
    """Top-level fetch + aggregation. Caller is responsible for caching."""

    start_ms, end_ms = _window_bounds_ms(window)
    website_id = settings.UMAMI_WEBSITE_ID or ""

    # Umami v3's /metrics endpoint is stricter than /stats — some builds
    # (3.0.x specifically) reject requests missing `timezone` and `unit` with
    # an opaque "Bad request" 400. Sending sane defaults matches what Umami's
    # own UI sends and avoids the schema validator complaining.
    common = {
        "startAt": start_ms,
        "endAt": end_ms,
        "timezone": "UTC",
        "unit": "day",
    }

    async with httpx.AsyncClient(timeout=UMAMI_REQUEST_TIMEOUT_SECONDS) as client:
        # /stats is required — without it the summary tiles have no data and
        # the card has no reason to exist. A hard failure here surfaces in
        # the UI banner so the operator knows analytics are dark.
        stats = await _umami_get(client, f"/websites/{website_id}/stats", common)

        # /metrics calls are soft — a 503 on any one of them blanks that
        # specific tile rather than the whole card. Lets partial signal land
        # when (e.g.) the Umami user has stats permission but not metrics.
        referrers = await _safe_umami_get(
            client,
            f"/websites/{website_id}/metrics",
            {**common, "type": "referrer", "limit": 10},
        )
        urls = await _safe_umami_get(
            client,
            f"/websites/{website_id}/metrics",
            {**common, "type": "url", "limit": 10},
        )
        events = await _safe_umami_get(
            client,
            f"/websites/{website_id}/metrics",
            {**common, "type": "event", "limit": 50},
        )

    return {
        "window": window,
        "generated_at": datetime.now(UTC).isoformat() + "Z",
        "summary": _summary_from_stats(stats),
        "top_referrer": _top_entry(referrers),
        "top_page": _top_entry(urls),
        "funnel": _events_to_funnel(events),
        "funnel_order": list(FUNNEL_EVENTS),
        "umami_dashboard_url": settings.UMAMI_DASHBOARD_URL,
    }


@router.get("/analytics/funnel", tags=["ROOT_ADMIN"])
async def get_acquisition_funnel(
    window: str = Query("7d", description="One of 24h, 7d, 30d."),
    refresh: bool = Query(
        False,
        description="Bypass the 5-minute cache (use sparingly — hits Umami every time).",
    ),
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Return the marketing-site acquisition funnel for the given window.

    The response is cached for 5 minutes keyed on the window so refreshing the
    admin dashboard doesn't fan out to Umami every time. Pass `?refresh=true`
    to force a re-fetch.
    """

    if window not in WINDOWS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported window '{window}'. Use 24h, 7d, or 30d.",
        )

    _require_umami_configured()

    cache_key = f"admin:analytics:funnel:{window}"

    if not refresh:
        cached = await cache.get(cache_key)
        if cached is not None:
            cached["cached"] = True
            return cached

    payload = await _fetch_funnel_payload(window)
    await cache.set(cache_key, payload, expire=CACHE_TTL_SECONDS)
    payload["cached"] = False
    return payload
